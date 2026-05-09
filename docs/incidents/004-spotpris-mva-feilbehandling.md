# Incident 004: Spotpris fra Nord Pool behandlet som inkl. mva

**Dato:** 9. mai 2026
**Status:** løst i v1.12.0
**Berørte versjoner:** v1.11.0 og tidligere (kraftpris-stien); nettleie var ikke berørt

## Symptomer

Bruker oppdaget at integrasjonens "spart med Norgespris hittil i mai" (168 kr) avvek kraftig fra BKK sitt tilsvarende tall (319 kr) på samme periode.

Sammenligning på BKK-instansens egne data 1.–9. mai 2026:

| Måling                              | Verdi              |
| ----------------------------------- | ------------------ |
| Forbruk (vår sensor)                | 352,75 kWh         |
| Forbruk (Tibber/Elhub)              | 316,55 kWh         |
| `monthly_norgespris_diff` (vår)     | +168,22 kr         |
| `monthly_norgespris_compensation`   | -244,82 kr         |
| BKK "spart med Norgespris hittil"   | +319,29 kr         |

Vektet snitt-spot utledet fra `monthly_norgespris_compensation`: 119,4 øre/kWh. Vektet snitt-spot utledet fra BKK: 150,9 øre/kWh.

Forholdstallet er nøyaktig 1,25.

## Rotårsak

Den offisielle Nord Pool-integrasjonen i Home Assistant (`domain: nordpool`) leverer kraftpriser **eks. mva**. Strømkalkulator antar i hele beregningskjeden at spotpris-sensoren leverer priser **inkl. mva**.

`const.py` linje 82:

```python
# Verdiene under er inkl. mva (spotpris fra Nord Pool er inkl. mva)
STROMSTOTTE_LEVEL: Final[float] = 0.9625  # 77 øre * 1.25 = 96,25 øre inkl. mva (2026)
```

Kommentaren er feil. Den ble skrevet da custom_components/nordpool var dominerende og ofte konfigurert med `VAT: true`. Den nye HA-core nordpool-integrasjonen har ingen mva-konfig og leverer alltid eks. mva.

## Konsekvenser

Alle Sør-Norge-brukere med spotprisavtale får feil i fire sensorer:

1. **Strømstøtte trigges 25 % for sent.** Vi sammenligner spotpris eks. mva mot terskel 96,25 øre inkl. mva (= 77 øre eks. mva). Strømstøtten settes inn ved 96,25 øre eks. mva = 120 øre inkl. mva i stedet for korrekt 96,25 øre inkl. mva.
2. **Totalpris-sensoren undervurderer kraftpris** med 25 % for kraftdelen.
3. **Akkumulert kostnad i Energy Dashboard** undervurderer faktiske kraftkostnader.
4. **Norgespris-sammenligning** viser for lav besparelse (vist 47 % lavere enn faktisk i caset over).

Bug-en ble ikke fanget av faktura-verifiseringen fordi fakturaene viser nettleie, ikke kraftpris. Nettleie-beregningene er korrekte.

Nord-Norge-brukere er ikke påvirket: avgiftssonen har 0 % mva, så `spot * (1 + 0)` = `spot`.

Tiltakssone-brukere er ikke påvirket av samme grunn.

## Berørte beregninger

I `coordinator.py`:

- Linje 519-526: `total_price` (alle if/else-grener bruker `spot_price` direkte)
- Linje 559-562: `kroner_spart_per_kwh`
- Linje 567-571: `monthly_norgespris_diff`, `monthly_norgespris_compensation`
- Linje 582-585: `_monthly_accumulated_cost_strom`

Alle disse må behandle `spot_price` som eks. mva og legge på korrekt mva-rate basert på avgiftssone før sammenligning eller summering.

## Foreslått løsning

### 1. Konfigurasjons-felt `spotpris_inkl_mva`

Legg til en boolean i config-flow med `default = False` (riktig for nordpool-domain). Brukere som har en sensor som allerede inkluderer mva (egendefinert template, eldre custom_components/nordpool med `VAT: true`) krysser av.

### 2. Beregning i `coordinator.py`

```python
mva_sats = get_mva_sats(self.avgiftssone)
if self.spotpris_inkl_mva:
    spot_price_inkl_mva = spot_price
else:
    spot_price_inkl_mva = spot_price * (1 + mva_sats)
```

Bruk `spot_price_inkl_mva` overalt der `spot_price` brukes i sammenligninger eller kostnader.

### 3. Migrering for eksisterende brukere

Ved migrering settes `spotpris_inkl_mva = False` for alle eksisterende konfig-entries. Det er riktig for HA-core nordpool (som er det ~alle brukere har). Repair-issue trigges kun for Sør-Norge (der mva-håndteringen utgjør en forskjell) og informerer:

> Strømkalkulator behandler nå spotpris-sensoren som eks. mva (riktig for HA-core nordpool). De fleste trenger ikke gjøre noe. Du trenger kun å handle hvis sensoren din allerede leverer inkl. mva (custom template eller eldre custom_components/nordpool med VAT=true). Da må du slå PÅ feltet i innstillingene.

Vurdert alternativ: sette `True` (preserves behavior) og be brukere slå AV. Forkastet fordi det betyr at brukere som ikke leser repair-issue beholder bug-en.

### 4. Tester

- Test at `spot_price_inkl_mva` beregnes riktig for begge bool-verdier i alle tre avgiftssoner
- Faktura-test for en spotpris-måned (september 2025 eller tidligere) for å verifisere mot ekte tall
- Migrering-test som verifiserer at eksisterende konfig får `spotpris_inkl_mva = True`

### 5. Dokumentasjon

- Oppdater `const.py:82`-kommentar
- Oppdater README med hva som er riktig for ulike integrasjoner
- Slett feilaktig påstand i `domain-rules.md` hvis den finnes der

## Lærdom

1. **Eksterne sensor-konvensjoner er ikke statiske.** Da koden ble skrevet var custom_components/nordpool med `VAT: true` vanlig. Den offisielle integrasjonen i HA-core endret default uten at vi merket. Antagelser om eksterne sensorer må verifiseres med jevne mellomrom.
2. **Faktura-verifisering dekker bare nettleie.** Vår tillit til at "alt regner riktig" var basert på BKK-faktura-match. Fakturaene viser ikke kraftpris (det går via strømleverandøren), så kraftpris-feil var usynlig i denne testen.
3. **Avvik på 25 % er signaleffekt, ikke avrundingsstøy.** Når et tall avviker med eksakt mva-rate, er sannsynligheten høy for en mva-håndtering-feil et sted i kjeden.

## Etterspill

Etter at hovedfixen ble implementert, kjørte vi en accountant-review for å fange relaterte mva-feil. Tre nye saker ble fikset i samme runde:

1. **Eksportinntekt brukte spotpris inkl. mva.** Når `spot_price` ble normalisert til inkl. mva, gjorde det at `_monthly_export_revenue += spot_price * export_kwh` ble overrapportert med 25 % i Sør-Norge. Plusskunder får betalt eks. mva av strømleverandøren (privat har ikke utgående mva). Fix: ny variabel `spot_price_eks_mva` brukes for eksportinntekt. Tre nye tester dekker eks-mva-sensor, inkl-mva-sensor og Nord-Norge.

2. **Falsk Norgespris-besparelse ved manglende spot-data.** Når spotpris-sensor var nede over 2 timer, falt `spot_price_raw` til 0.0 og koden akkumulerte `(norgespris - 0.0) × kwh = 50 øre/kWh` i fiktiv besparelse hver minutt sensoren var nede. Fix: ny `spot_price_valid`-flagg hopper over alle spot-avhengige akkumuleringer. Energiledd og Norgespris-under-tak akkumuleres uavhengig (de trenger ikke spot).

3. **Misvisende kommentarer i `dso.py`.** Verdiene `energiledd_dag_eks_mva` og `energiledd_natt_eks_mva` er ren energiledd, men kommentarene oppga sluttprisen etter at coordinator har lagt på avgifter og mva. Eksempel: `0.2099 # 36,40 øre/kWh inkl. avgifter` der 0.2099 i øre er 20.99, ikke 36.40. Dette har bidratt til å forvirre menneskelige reviewere og er antatt en medvirkende årsak til incidents 002 og 003. Kommentarene er ryddet til å beskrive ren energiledd.

## Kilder

- [Home Assistant Nord Pool integration docs](https://www.home-assistant.io/integrations/nordpool/) bekrefter at integrasjonen leverer priser eks. mva
- BKK fakturaoversikt og "spart med Norgespris" sammenlikningstall, mai 2026
- `coordinator.py:_async_update_data`, hvor `spot_price` brukes uten mva-konvertering
