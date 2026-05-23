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

## 3. Norgespris-kompensasjon (EUR/NOK 0,2 %)

Beregningen av Norgespris-kompensasjon avviker 0,14 % fra BKKs på spot-snitt, som gir 0,2 % på selve kompensasjons-beløpet. Sannsynlig årsak er forskjellig EUR/NOK-snittberegning eller forskjellig kurskilde.

April 2026: 2,92 kr på 1427,89 kr Norgespris-kompensasjon.

| Tiltak                                          | Effekt                                      | Kompleksitet       |
| ----------------------------------------------- | ------------------------------------------- | ------------------ |
| Akseptere (dagens valg)                         | 0,2 % avvik dokumentert                     | Ingen              |
| Hente rå EUR-priser fra Nord Pool + Norges Bank | Forventet 0 % match hvis BKK også bruker NB | Middels            |
| Spørre BKK direkte hvilken kurs de bruker       | Definitivt svar                             | Lav (kundeservice) |

Se [research/nok-omregning.md](research/nok-omregning.md) for full analyse.

## 4. Strømstøtte-formel (2 %)

Beregningen av "spot etter strømstøtte" avviker 2 % fra BKKs egen visning (1347 kr vs 1377 kr for april 2026). Vi bruker standard formel: 90 % refusjon over 0,9125 kr/kWh inkl. mva, time-for-time.

Mulige årsaker:

- BKK bruker en litt annen avrundingsregel
- Tibbers prismodell-påslag inkluderes muligens
- Andre forskrifts-detaljer i strømstøtten som ikke er åpenbare

Kun relevant for sammenligning mot BKKs "Uten Norgespris"-tall. Har du faktisk Norgespris er dette et teoretisk tall, ikke en faktisk fakturalinje.

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
| Norgespris-komp kurs   | 18 kr/mnd  | 2-3 kr/mnd | Marginalt, EUR/NOK-kurs      |
| Strømstøtte-beregning  | 30 kr/mnd  | 30 kr/mnd  | Kun for teoretisk visning    |
| Kapasitetstrinn-grense | 165 kr/mnd | 0          | Kun hvis permanent på grense |

Total typisk ukjent feil: under 5 kr/mnd for vanlig bruker. Under 0,1 % av total fakturasum. Integrasjonen kan trygt brukes for fakturakontroll og fanger reelle feil i størrelsesorden 50 kr+ uten problem.
