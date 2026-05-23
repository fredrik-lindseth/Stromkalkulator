# Kjente begrensninger

Integrasjonen treffer fakturaen på øret. Sensorer i HA vises i kr og kWh som matcher det nettselskapet fakturerer. Begrensningene under er ikke-validerte scenarier eller spesielle tilfeller du bør vite om.

## 1. Spisset mot ett oppsett

All faktura-verifisering er gjort mot eget oppsett:

| Komponent               | Verdi                                   |
| ----------------------- | --------------------------------------- |
| Nettselskap             | BKK (NO5), verifisert mot 6 fakturaer   |
| Måler                   | Kaifa MA304H3E                          |
| HAN-leser               | Pow-U (AMSleser.no, AmsToMqtt-firmware) |
| Strømleverandør         | Tibber Norge AS                         |
| HA-integrasjon for spot | offisiell `nordpool` (eks. mva)         |

Resultatene gjelder strengt for denne kombinasjonen. Andre kombinasjoner kan ha andre presisjons-karakteristikker, spesielt på kurs-/MVA-håndtering i andre nordpool-integrasjoner og kapasitetstrinn-formler hos andre nettselskaper. Andre brukere bør verifisere mot egne fakturaer. Se [VERIFISER_DIN_FAKTURA.md](fakturaer/VERIFISER_DIN_FAKTURA.md).

## 2. Ikke-validerte scenarier

Følgende har ikke blitt verifisert mot ekte faktura:

- DST-overgang (mars og oktober, ±1 time per år)
- Negative spotpriser (kan oppstå ved overskudd av sol/vind)
- Norgespris kWh-tak (5000 kWh/mnd for bolig)
- Avgiftssone Nord-Norge / Tiltakssone (mva-fritak)
- Næringskunde (ikke husholdning)
- Andre nettselskaper enn BKK

Vil du validere noen av disse: send faktura + Elhub-data, så kan vi utvide verifiserings-suiten.

## 3. Norgespris-kompensasjon (EUR/NOK 0,2 % i HA-integrasjonen)

Beregningen av Norgespris-kompensasjon basert på `sensor.nord_pool_no5_current_price` avviker 0,14 % fra BKK på spot-snittet, som gir 0,2 % på kompensasjons-beløpet. April 2026: 2,92 kr på 1427,89 kr Norgespris-kompensasjon.

**Status 2026-05-23:** vi har testet 10 omregnings-varianter mot fakturaen ved å hente rå EUR/MWh fra Nord Pool og kombinere med ulike EUR/NOK-kurser:

| Variant                                          | Avvik     | Notat                            |
| ------------------------------------------------ | --------- | -------------------------------- |
| Rå EUR + NB same-day forward-fill                | +0,79 kr  | Beste enkeltkilde (0,055 %)      |
| Rå EUR + Nord Pool EXR (daglig)                  | -3,25 kr  | NPs egen interne kurs            |
| HA `nordpool`-integrasjonens NOK-pris            | +2,92 kr  | Det vi faktisk bruker i dag      |

Implisitt single-rate som ville gitt 0-treff: 11,0706 NOK/EUR. Den ligger mellom NB (11,06) og Nord Pool EXR (11,08). Ingen offentlig publisert kurs treffer presist — sannsynligvis 12:00 CET interbankkurs som ikke er gratis tilgjengelig.

| Tiltak                                          | Effekt                            | Kompleksitet       |
| ----------------------------------------------- | --------------------------------- | ------------------ |
| Akseptere (dagens valg)                         | 0,2 % avvik dokumentert           | Ingen              |
| Bytte til rå EUR + NB-kurs i integrasjonen      | Reduserer avvik til 0,055 %       | Middels            |
| Hente 12:00 CET interbankdata                   | Krever Bloomberg/Refinitiv        | Høy (ikke gratis)  |
| Spørre BKK direkte hvilken kurs de bruker       | Definitivt svar                   | Lav (kundeservice) |

Se [research/nok-omregning.md](research/nok-omregning.md) for full variant-matrise og kjørbart script.

## 4. Strømstøtte-formel (~30 kr/mnd vs BKKs visning)

Vår "spot etter strømstøtte" avviker ~30 kr/mnd fra BKKs egen "Uten Norgespris"-visning (april 2026: vi beregner 1408,52 kr, BKK viser 1377 kr). Vi bruker 2026-terskel fra forskrift 2025-09-08-1791 §5: 90 % refusjon når spotpris overstiger 77 øre/kWh eks. mva (0,9625 kr/kWh inkl. mva), time-for-time.

Avviket ser ut til å skyldes at BKKs visning fortsatt bruker 2025-terskelen (75 øre eks. mva / 0,9375 inkl. mva). Med lavere terskel blir refusjonen større, så BKK trekker fra mer enn vi gjør — vi gir altså MER strømstøtte i vår beregning enn det BKK viser. Dette er anekdotisk basert på én faktura (april 2026); det kan også være avrundingsregler eller andre forskrifts-detaljer i spill.

Kun relevant for Norgespris-kunder som vil sammenligne mot BKKs "Uten Norgespris"-tall i kundeportalen. Tallet er en hypotetisk visning, ikke en faktisk fakturalinje — Norgespris-kunder mottar ikke strømstøtte uansett.

## 5. Momentan-effekt sample-frekvens (2,5 sek)

AMS-måleren broadcaster momentan effekt (`p`) hvert ~2,5 sek på list1. Kortere spikes enn dette fanges ikke (motor-spikes, kapasitiv inrush ved oppstart). Ingen praktisk relevans for fakturakontroll, fordi nettselskapet heller ikke ser sub-time-spikes. Kapasitetstrinn er basert på timesnitt.

Relevant kun hvis du vil oppdage korte effekt-topper i hjemmet ditt.

## 6. For utviklere: verifisering mot ekte faktura

Vi har en dev-pipeline (`scripts/research/verify_invoice_hourly.py`) som leser tpi-broadcast direkte fra AMS-måleren for å sammenligne mot Elhub og fakturaen. Den har et 13-sek sample-skift (10 sek inne i måleren + 3 sek transmisjon på Kaifa + Pow-U-oppsett) som påvirker BARE denne pipelinen.

Selve HA-integrasjonen leser `p`-strømmen kontinuerlig og er ikke påvirket. Det betyr at sensorene du ser i Energy Dashboard og månedstotaler ikke har de 9 Wh-avvikene som dev-pipelinen viser.

Se [research/klokke-og-tidsstempling.md](research/klokke-og-tidsstempling.md) og [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for full kontekst.

## Sammendrag

Reelle avvik som påvirker brukeren:

| Type                   | Worst case | Typisk     | Konsekvens                   |
| ---------------------- | ---------- | ---------- | ---------------------------- |
| Norgespris-komp kurs   | 18 kr/mnd  | 2-3 kr/mnd | Marginalt, EUR/NOK-kurs (kan reduseres til <1 kr ved bytte til rå EUR + NB-kurs) |
| Strømstøtte-beregning  | 30 kr/mnd  | 30 kr/mnd  | Kun for teoretisk visning    |
| Kapasitetstrinn-grense | 165 kr/mnd | 0          | Kun hvis permanent på grense |

Total typisk ukjent feil: under 5 kr/mnd for vanlig bruker. Under 0,1 % av total fakturasum. Integrasjonen kan trygt brukes for fakturakontroll og fanger reelle feil i størrelsesorden 50 kr+ uten problem.
