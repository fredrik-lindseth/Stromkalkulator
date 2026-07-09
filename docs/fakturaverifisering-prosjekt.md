# Fakturaverifisering på time-nivå

Prosjektdokument for arbeidet med å validere `stromkalkulator` ende-til-ende mot ekte HAN-meter-data og Nord Pool-priser. Beskriver hvor vi står, hva som er testet, og hva som gjenstår.

## Hvorfor dette prosjektet finnes

Vi har allerede `tests/test_faktura_bkk.py` som sjekker at formlene og satsene i integrasjonen reproduserer kjente BKK-fakturaer. Den testen tar akkumulerte verdier som input, og verifiserer at de gir riktig fakturasum. Den sier ingenting om hvorvidt de akkumulerte verdiene fra integrasjonen faktisk matcher det måleren har sendt ut.

Vi lukker hullet ved å validere mot to ekte datakilder:

- Time-for-time-forbruk fra AMS-måleren (Kaifa MA304H3E + Pow-U + AMSleser.no)
- Time-for-time-spotpriser fra Nord Pool-integrasjonen i HA

Utforskingen 2026-05-22 viste at dette fungerer veldig bra. Avvikene mot april 2026-fakturaen er små nok til å forklares av sample-presisjon, ikke logiske feil.

## Det vi har bekreftet

Eksporterte april 2026-hourly-data fra HAs `home-assistant_v2.db` på `ha-local`. Brukte `tpi`-delta (Total Power In, OBIS 1-0:1.8.0, kumulativ kWh-teller i måleren) som forbrukskilde.

| Måling          | HAN-data                 | BKK-faktura              | Avvik            | Forklaring                                      |
| --------------- | ------------------------ | ------------------------ | ---------------- | ----------------------------------------------- |
| Total kWh       | 1381,818                 | 1381,827                 | +9 Wh            | tpi-broadcast HH:00:13 (13s × 1,92 kW = 6,9 Wh) |
| Dag kWh         | 620,858                  | 620,829                  | -29 Wh           | Samme sample-skifte                             |
| Natt kWh        | 760,960                  | 760,998                  | +38 Wh           | Samme                                           |
| Topp 3 maks     | [5,947, 4,776, 4,266] kW | [5,939, 4,779, 4,262] kW | 3-8 W            | Hourly aggregat-grense                          |
| Topp 3 snitt    | 4,9963 kW                | 4,993 kW                 | 3 mW             | Innenfor støy                                   |
| Norgespris-komp | -1430,81 kr              | -1427,89 kr              | +2,92 kr (0,2 %) | Trolig EUR/NOK-kurs                             |

Totalavviket forklares av sample-presisjon i HAN-broadcast, ikke av logiske feil i integrasjonen. Nord Pool-integrasjonen i HA returnerer priser eks. mva, så de må multipliseres med 1,25 for å matche fakturaens Norgespris-beregning.

Med Elhub-data og NOK-omregningsanalyse (oppdatert 2026-05-22 kveld) er flere spørsmål besvart:

| Spørsmål                                         | Svar                                                                  | Kilde                                                                      |
| ------------------------------------------------ | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Sender Elhub presis HH:00:00 til BKK?            | Ja, 0 avvik mellom Elhub og faktura                                   | [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) |
| Bruker BKK timesnitt-effekt for kapasitetstrinn? | Ja, kWh-diff per time                                                 | Topp 3 i Elhub = faktura eksakt                                            |
| Hvor stort er kurs-avviket på Norgespris?        | Løst 2026-07-06: eksakt match med publiserte Final-priser. Recorder-avviket (0,04-0,05 %) er prisårgang | [research/norgespris-eksakt-match.md](research/norgespris-eksakt-match.md) |
| Hvor er 13-sek-laget?                            | Ikke mellom Elhub og BKK. 10 sek i selve måleren (Kaifa/Aidon-spec) + 3 sek Pow-U-transmisjon. | Elhub-totaler matcher faktura presis                                       |

## Det vi mangler

Se [måler-hardware.md](måler-hardware.md). Gjenstående:

1. ~~Hvilken EUR/NOK-kurs bruker BKK eksakt?~~ Besvart 2026-07-06: Nord Pools publiserte Final-pris. Med Elhub-kWh x Final-priser treffer både mai og juni fakturaen innenfor 0,005 kr. Mai-restavviket på 0,35 kr var en recorder-aggregatglipp 2. pinsedag, ikke pris. Ingenting gjenstår på Norgespris-sporet.

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
- [x] Norgespris-avvik lukket: eksakt match (0,00 kr) mot publiserte Final-priser for juni 2026, recorder-avviket var prisårgang, se [research/norgespris-eksakt-match.md](research/norgespris-eksakt-match.md)
- [x] Måler-spec lest (Kaifa KFM_001 og Aidon RJ45 HAN v1.6): 10 sek dokumentert som design, se [måler-hardware.md](måler-hardware.md#han-broadcast-timing)
- [ ] Test med Tibber Pulse parallelt (krever fysisk bytte av HAN-leser, se `stromkalkulator-450dw5`)
- [ ] Oppdater [måler-hardware.md](måler-hardware.md) ved nye funn (løpende, ikke en engangsoppgave)

### Fase 3: Bygg verktøyene

- [x] `scripts/research/export_invoice_hourly.py` (kjøres på HA-host, eksporterer JSON for én måned)
- [x] `scripts/research/verify_invoice_hourly.py` (kjøres lokalt, sammenligner JSON mot fixture)
- [x] Snapshot-fixture `tests/fixtures/bkk_april_2026_hourly.json` (allerede eksportert, nå én fixture per måned des 2025-juni 2026)
- [x] ~~`tests/test_faktura_hourly_snapshot.py`~~ Slettet 2026-05-23 (`98cd37a`): reimplementerte dag/natt-split og Norgespris-komp parallelt med coordinator uten å kjøre den. Erstattet av `tests/test_coordinator_replay.py`, som mater fixturene gjennom ekte `_async_update_data()` og kjører i CI via vanlig `pytest tests/`.
- [x] Vurdert snapshot-automation i HA på HH:00:00: virker ikke, 10 av 13 sek ligger inne i selve måleren mellom Elhub-snapshot og HAN-frame-bygging, se [måler-hardware.md](måler-hardware.md#hva-vi-kan-gjøre-bedre)

### Fase 4: Validere neste måned

- [x] Mai og juni 2026-faktura eksportert og analysert
- [x] Verifiserings-script kjørt (`verify_norgespris_eksakt.py`, `verify_invoice_hourly.py`)
- [x] Sammenlignet avvik mot april: juni konsistent (prisårgang), mai avvek initialt
- [x] Konsistente avvik (juni, april) dokumentert som prisårgang, se [norgespris-eksakt-match.md](research/norgespris-eksakt-match.md)
- [x] Inkonsistent avvik (mai, -0,35 kr) undersøkt: recorder-aggregatglipp 2. pinsedag, løst med Elhub-CSV som kWh-fasit

### Fase 5: Generaliser for andre brukere

- [x] Brukerveiledning skrevet: [verifiser-din-faktura.md](fakturaer/verifiser-din-faktura.md)
- [ ] Parametriser scripts for andre AMS-lesere (Tibber Pulse, Tibber Bridge, andre Pow-U-varianter)
- [ ] Parametriser for andre DSO-er enn BKK (se `stromkalkulator-2b94op`)

### Fase 6: Beslutning om release

- [ ] Hvis verktøyene fungerer bredt: vurder HA add-on eller integrert sensor
- [ ] Hvis kun lokalt: behold som dev-scripts, dokumenter for andre

## Beslutninger som er tatt

- **Bruk tpi-delta, ikke houruse**: tpi gir 9 Wh-presisjon, houruse gir 0,5 % avvik fordi den er beregnet av Pow-U separat.
- **Multipliser Nord Pool-pris med 1,25**: bekreftet eks. mva.
- **Bruk forbruksvektet snitt for spot**: `sum(kwh * spot) / sum(kwh)`, ikke tidsvektet.
- **Topp 3 fra max(kwh per time per dato)**: ikke `peaks0/1/2`-sensoren, fordi den resettes ved månedsskifte.

## Beslutninger som gjenstår

- ~~Skal vi bygge en HA add-on for snapshot-automation, eller bare dokumentere config-endringer?~~ Bortfalt: snapshot-automation virker ikke uansett trigger-tidspunkt (10 av 13 sek ligger inne i måleren selv).
- ~~Skal verifisering kjøre i CI med hardkodet fixture, eller kun manuelt som dev-tool?~~ Besvart: `tests/test_coordinator_replay.py` kjører automatisk i `.github/workflows/ci.yml` via `pytest tests/`, ikke som separat dev-tool.
- Skal vi gjøre samme verifisering for andre DSO-er proaktivt, eller vente på brukernes egen verifisering?
