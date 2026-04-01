# Incident 001: Delt data mellom instanser med samme nettselskap

**Dato:** mars 2026
**Rapportert i:** [GitHub issue #1](https://github.com/fredrik-lindseth/Stromkalkulator/issues/1)
**Status:** Løst

## Symptomer

Bruker med to strømmålere hos samme nettselskap (Elvia) opplevde:

1. Peak consumption #1, #2 og #3 var identiske mellom begge instansene
2. Kapasitetstrinn var identisk, selv om faktisk forbruk var forskjellig
3. Etter fix: kapasitetstrinn stemte fortsatt ikke med Elvias egne data

## Rotårsak

### Bug 1: Delt lagring

Lagringsnøkkelen var basert på nettselskap-ID (`stromkalkulator_{dso_id}`), ikke config entry-ID. Når to instanser hadde samme nettselskap, delte de samme lagringsfil:

```
# Før fix — begge instanser brukte samme fil:
Store(hass, 1, f"{DOMAIN}_{dso_id}")

# Etter fix — unik fil per instans:
Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
```

Effekttoppene fra begge målerne ble blandet i én `_daily_max_power`-dict, og begge leste tilbake identiske verdier.

### Bug 2: Kontaminert data etter migrering

Migreringskoden flyttet data fra gammel DSO-basert fil til ny entry-basert fil. Men:

- **Instans 1** fikk all den gamle (blandede) dataen — toppverdiene tilhørte kanskje ikke denne måleren
- **Instans 2** startet med tom data — hadde bare noen få dager, ikke et komplett bilde

Begge viste dermed feil kapasitetstrinn sammenlignet med Elvias beregning.

## Fiks

### Bug 1 — commit 68d7947, 6d5573d, e2807f4

1. Byttet lagringsnøkkel fra `dso_id` til `entry.entry_id`
2. La til migrering fra gammel til ny nøkkel
3. La til `await old_store.async_remove()` etter migrering — forhindrer at instans 2 laster samme data

### Bug 2 — selvløsende

Ingen kodeendring nødvendig. Ved månedsskifte nullstilles `_daily_max_power`, og begge instansene begynner å samle rene, isolerte data. Løser seg automatisk ved neste måned.

## Lærdom

### 1. Lagringsnøkler må være globalt unike per instans

Aldri bruk domenedata (nettselskap-ID, API-nøkkel, etc.) som lagringsnøkkel. Bruk alltid `entry.entry_id` — det er det eneste som er garantert unikt per config entry i Home Assistant.

**Tommelregel:** Alt som er per-instans (lagring, sensorer, koordinatorer) skal nøkles på `entry_id`, aldri på brukervalgt konfigurasjon.

### 2. Migreringer kan forurense data

Når du fikser en delt-tilstand-bug, er den eksisterende dataen allerede kontaminert. En ren migrering (kopier data → slett gammel) gir én instans forurenset data og den andre ingenting.

**Mulige strategier:**
- Aksepter at data er forurenset og la den nullstilles naturlig (det vi gjorde)
- Slett all data for begge instansene og start fra scratch (mer drastisk, men umiddelbart korrekt)
- Varsle brukeren om at data kan være unøyaktig inntil neste reset

### 3. Multi-instans må testes fra starten

Integrasjoner som støtter flere config entries må ha tester som verifiserer full isolasjon: lagring, sensorer, koordinatorer, og alle mellomlagrede verdier. Legg til multi-instans-tester tidlig — det er mye vanskeligere å oppdage delt tilstand i etterkant.

### 4. Brukere oppdager subtile datafeil

Brukeren i issue #1 fanget at kapasitetstrinn var feil selv etter at den åpenbare feilen (identiske verdier) var fikset. Brukere som sammenligner med eksterne systemer (Elvias egne tall) er verdifulle for å avdekke datakvalitetsproblemer.
