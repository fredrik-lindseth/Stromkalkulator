# Incident 001: Delt data mellom instanser med samme nettselskap

**Dato:** mars 2026
**Status:** løst
**Rapportert i:** [GitHub issue #1](https://github.com/fredrik-lindseth/Stromkalkulator/issues/1)

## Symptomer

Bruker med to strømmålere hos samme nettselskap (Elvia):

1. Toppforbruk #1, #2 og #3 var identiske mellom instansene
2. Kapasitetstrinn var identisk, selv om faktisk forbruk var forskjellig
3. Etter fix: kapasitetstrinn stemte fortsatt ikke med Elvias egne data

## Rotårsak

### Bug 1: delt lagring

Lagringsnøkkelen var basert på nettselskap-ID (`stromkalkulator_{dso_id}`), ikke config entry-ID. Begge instanser delte samme fil:

```
# Før: begge instanser brukte samme fil
Store(hass, 1, f"{DOMAIN}_{dso_id}")

# Etter: unik fil per instans
Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
```

Effekttoppene fra begge målerne ble blandet i én `_daily_max_power`-dict.

### Bug 2: kontaminert data etter migrering

Migreringen flyttet data fra gammel DSO-basert fil til ny entry-basert fil. Resultat:

- Instans 1 fikk all den gamle (blandede) dataen, toppverdiene tilhørte kanskje ikke denne måleren
- Instans 2 startet tomt, hadde bare noen få dager

Begge viste feil kapasitetstrinn sammenlignet med Elvias beregning.

## Fiks

Bug 1 (commit 68d7947, 6d5573d, e2807f4):

1. Byttet lagringsnøkkel fra `dso_id` til `entry.entry_id`
2. La til migrering fra gammel til ny nøkkel
3. La til `await old_store.async_remove()` etter migrering, forhindrer at instans 2 laster samme data

Bug 2 var selvløsende. Ved månedsskifte nullstilles `_daily_max_power`, og data blir rene igjen.

## Lærdom

1. **Lagringsnøkler må være globalt unike per instans.** Aldri bruk domenedata (nettselskap-ID, API-nøkkel) som lagringsnøkkel. Bruk `entry.entry_id`.
2. **Migreringer kan forurense data.** Når du fikser en delt-tilstand-bug er eksisterende data allerede kontaminert. Akseptert her at data nullstilles naturlig ved månedsskifte.
3. **Multi-instans må testes fra starten.** Vanskelig å oppdage delt tilstand i etterkant.
