# Fakturaverifisering på time-nivå

Prosjektdokument for arbeidet med å validere `stromkalkulator` ende-til-ende mot ekte HAN-meter-data og Nord Pool-priser. Beskriver hvor vi står, hva som er testet, og hva som gjenstår.

## Hvorfor dette prosjektet finnes

Vi har allerede `tests/test_faktura_bkk.py` som sjekker at formlene og satsene i integrasjonen reproduserer kjente BKK-fakturaer. Den testen tar akkumulerte verdier som input, og verifiserer at de gir riktig fakturasum. Den sier ingenting om hvorvidt de akkumulerte verdiene fra integrasjonen faktisk matcher det måleren har sendt ut.

Fredrik foreslo å lukke det hullet ved å validere mot to ekte datakilder:

- Time-for-time-forbruk fra AMS-måleren (Aidon + Pow-U + AMSleser.no)
- Time-for-time-spotpriser fra Nord Pool-integrasjonen i HA

Utforskingen 2026-05-22 viste at dette fungerer veldig bra. Avvikene mot april 2026-fakturaen er små nok til å forklares av sample-presisjon, ikke logiske feil.

## Det vi har bekreftet

Eksporterte april 2026-hourly-data fra HA's `home-assistant_v2.db` på `ha-local`. Brukte `tpi`-delta (Total Power In, OBIS 1-0:1.8.0, kumulativ kWh-teller i måleren) som forbrukskilde.

| Måling          | HAN-data                 | BKK-faktura              | Avvik            | Forklaring                                      |
| --------------- | ------------------------ | ------------------------ | ---------------- | ----------------------------------------------- |
| Total kWh       | 1381,818                 | 1381,827                 | +9 Wh            | tpi-broadcast HH:00:13 (13s × 1,92 kW = 6,9 Wh) |
| Dag kWh         | 620,858                  | 620,829                  | -29 Wh           | Samme sample-skifte                             |
| Natt kWh        | 760,960                  | 760,998                  | +38 Wh           | Samme                                           |
| Topp 3 maks     | [5,947, 4,776, 4,266] kW | [5,939, 4,779, 4,262] kW | 3-8 W            | Hourly aggregat-grense                          |
| Topp 3 snitt    | 4,9963 kW                | 4,993 kW                 | 3 mW             | Innenfor støy                                   |
| Norgespris-komp | -1430,81 kr              | -1427,89 kr              | +2,92 kr (0,2 %) | Trolig EUR/NOK-kurs                             |

Totalavviket forklares av sample-presisjon i HAN-broadcast, ikke av logiske feil i integrasjonen. Nord Pool-integrasjonen i HA returnerer priser eks. mva, så de må multipliseres med 1,25 for å matche fakturaens Norgespris-beregning.

## Det vi har bekreftet (oppdatert 2026-05-22 kveld)

Med Elhub-data og NOK-omregningsanalyse er flere spørsmål nå besvart:

| Spørsmål                                         | Svar                                               | Kilde                                                                      |
| ------------------------------------------------ | -------------------------------------------------- | -------------------------------------------------------------------------- |
| Sender Elhub presis HH:00:00 til BKK?            | Ja, 0 avvik mellom Elhub og faktura                | [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) |
| Bruker BKK timesnitt-effekt for kapasitetstrinn? | Ja, kWh-diff per time                              | Topp 3 i Elhub = faktura eksakt                                            |
| Hvor stort er kurs-avviket på Norgespris?        | 0,14 % på spot, gir 0,2 % på kompensasjon          | [research/nok-omregning.md](research/nok-omregning.md)                     |
| Hvor er 13-sek-laget?                            | Ikke mellom Elhub og BKK. Enten Aidon eller Pow-U. | Elhub-totaler matcher faktura presis                                       |

## Det vi mangler

Se [måler-hardware.md](måler-hardware.md). Gjenstående:

1. Er 13-sek-laget i Aidon-måleren eller Pow-U firmware? Krever Tibber Pulse-test
2. Hvilken EUR/NOK-kurs bruker BKK eksakt? Krever spørsmål til BKK eller test mot flere kursvarianter

## Plan

### Fase 1: Utforsk og bekreft (ferdig)

- [x] SSH til ha-local, finn entity-IDs
- [x] Eksporter april 2026-hourly fra `statistics`-tabellen
- [x] Sammenlign mot faktura, identifiser avviksforklaring
- [x] Bekreft tpi-broadcast-timing (HH:00:13 konsistent)
- [x] Bekreft Nord Pool eks. mva

### Fase 2: Verifiser hardware-antagelser

- [x] Elhub-snapshot-presisjon: bekreftet HH:00:00 lokal tid, 0 avvik mot faktura
- [x] BKK bruker timesnitt-effekt for kapasitetstrinn (bekreftet via topp 3-sammenligning)
- [x] Norgespris-avvik forklart med EUR/NOK-snittberegning (innenfor 0,2 %)
- [ ] Hent Aidon-manual, sjekk om 13-sek-lag er målerens eller Pow-U's
- [ ] Test med Tibber Pulse parallelt (krever fysisk bytte av HAN-leser)
- [ ] Oppdater [måler-hardware.md](måler-hardware.md) når Aidon-svaret kommer

### Fase 3: Bygg verktøyene

- [ ] `scripts/export_invoice_hourly.py` (kjøres på HA-host, eksporterer JSON for én måned)
- [ ] `scripts/verify_invoice_hourly.py` (kjøres lokalt, sammenligner JSON mot fixture)
- [ ] Snapshot-fixture `tests/fixtures/bkk_april_2026_hourly.json` (allerede eksportert)
- [ ] `tests/test_faktura_hourly_snapshot.py` (kjører verifiserings-logikk i CI)
- [ ] Vurder snapshot-automation i HA som tar tpi-snapshot presis HH:00:00 (avhengig av Fase 2-svar)

### Fase 4: Validere neste måned

- [ ] Når mai 2026-faktura kommer (rundt 2026-06-04), eksporter samme data
- [ ] Kjør verifiserings-script
- [ ] Sammenlign avvik mot april. Er det konsistent?
- [ ] Hvis konsistent: dokumenter som kjent presisjons-grense
- [ ] Hvis inkonsistent: undersøk hvorfor

### Fase 5: Generaliser for andre brukere

- [ ] Skriv brukerveiledning i [VERIFISER_DIN_FAKTURA.md](fakturaer/VERIFISER_DIN_FAKTURA.md) eller egen fil
- [ ] Parametriser scripts for andre AMS-lesere (Tibber Pulse, Tibber Bridge, andre Pow-U-varianter)
- [ ] Parametriser for andre DSO-er enn BKK

### Fase 6: Beslutning om release

- [ ] Hvis verktøyene fungerer bredt: vurder HA add-on eller integrert sensor
- [ ] Hvis kun lokalt: behold som dev-scripts, dokumenter for andre

## Beslutninger som er tatt

- **Bruk tpi-delta, ikke houruse**: tpi gir 9 Wh-presisjon, houruse gir 0,5 % avvik fordi den er beregnet av Pow-U separat.
- **Multipliser Nord Pool-pris med 1,25**: bekreftet eks. mva.
- **Bruk forbruksvektet snitt for spot**: `sum(kwh * spot) / sum(kwh)`, ikke tidsvektet.
- **Topp 3 fra max(kwh per time per dato)**: ikke `peaks0/1/2`-sensoren, fordi den resettes ved månedsskifte.

## Beslutninger som gjenstår

- Skal vi bygge en HA add-on for snapshot-automation, eller bare dokumentere config-endringer?
- Skal verifisering kjøre i CI med hardkodet fixture, eller kun manuelt som dev-tool?
- Skal vi gjøre samme verifisering for andre DSO-er proaktivt, eller vente på brukernes egen verifisering?
