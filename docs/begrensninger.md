# Kjente begrensninger

Liste over presisjons-begrensninger som er identifisert gjennom faktisk verifisering. Disse er ikke feil i integrasjonen, men karakteristika ved datakildene og målerne. Dokumentert her for transparens.

## 1. Verifiserings-script: sample-skift mellom HAN-broadcast og time-grense

> **TL;DR:** Dette gjelder KUN dev-scriptet `scripts/research/verify_invoice_hourly.py`, IKKE integrasjonen i HA. Brukernes Energy Dashboard og månedstotaler i `custom_components/stromkalkulator/` er upåvirket fordi integrasjonen leser `p`-strømmen kontinuerlig og IKKE tpi-broadcasten.

**Hva det er:** AMS-måleren broadcaster kumulativ tpi-verdi over HAN-port noen sekunder etter HH:00:00, ikke presis på time-grensen. Verifiserings-scriptet som sammenligner HAN-data mot Elhub/BKK får derfor time-aggregater forskjøvet med så mange sekunder som broadcasten ligger etter HH:00:00.

**13 sekunder er IKKE universelt.** Det er måltallet for Fredriks Kaifa MA304H3E + Pow-U-oppsett. Andre måler- og HAN-leser-kombinasjoner gir andre tall:

| Måler-merke + HAN-leser     | Total forsinkelse (forventet) | Komponenter                        |
| --------------------------- | ----------------------------- | ---------------------------------- |
| Kaifa MA304 + Pow-U         | 10-13 sek                     | 10 sek måler + 3 sek transmisjon   |
| Aidon 65xx + Pow-U          | 10-15 sek                     | 10 sek måler + 3-5 sek transmisjon |
| Kamstrup Omnipower + Pow-U  | 5-10 sek                      | 5 sek måler + 3-5 sek transmisjon  |
| Kaifa/Aidon + Tibber Pulse  | Ukjent                        | Annet nettverkslag (Tibber Cloud)  |
| Kaifa/Aidon + Tibber Bridge | Ukjent                        | RJ45 direkte HAN, lokal kobling    |
| Kaifa/Aidon + ESPHome AMS   | 3-10 sek                      | Avhengig av firmware               |

Tallene over kombinerer merke-spesifikk list3-broadcast (se [måler-hardware.md](måler-hardware.md#han-broadcast-timing)) med transmisjons-tid hos kjente HAN-lesere. For måler-leser-kombinasjoner som ikke er målt opp må du selv verifisere mot egen recorder.

**Hvor forsinkelsen ligger (Fredriks oppsett, Kaifa + Pow-U):** Verifisert via Home Assistants recorder ved å sammenligne `sensor.pow_u_ams_rtc` (målerens egen RTC i HAN-framen) mot `last_updated_ts` (HA-mottakstid) over 24 timer. Splittingen er konsistent på sekundet:

| Sekunder | Hvor                 | Hva skjer                                                      |
| -------- | -------------------- | -------------------------------------------------------------- |
| 10       | Inne i selve måleren | Mellom internt Elhub-snapshot HH:00:00 og bygging av HAN-frame |
| 3        | Transmisjonskjeden   | HAN-overføring, Pow-U-parsing, MQTT-publish til HA             |

Firmware-koden i [amsreader-firmware](https://github.com/UtilitechAS/amsreader-firmware) er gjennomgått. Det er ingen kunstig forsinkelse mellom parsing av HAN-frame og MQTT-publish, sub-millisekund i praksis. De 3 sekundene er fysisk transmisjon og parsing, ikke programvarevalg.

**Hvor stort (Fredriks oppsett):** 9 Wh på månedssummen (april 2026). Per enkelt time opptil ±21 Wh. Per topp-3-måling 3-8 W avvik. Andre kombinasjoner får andre tall, skalér lineært med forsinkelsen.

**Default i scriptet:** `verify_invoice_hourly.py` har `--shift-seconds 13` som default. Det matcher Fredriks Kaifa + Pow-U. Andre brukere må justere flagget basert på sitt eget oppsett, eller måle det opp empirisk via recorder.

**Hva kan gjøres:**

| Tiltak                                     | Effekt                                                                                                     | Kompleksitet                        |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| Akseptere som kjent (dagens valg)          | 9 Wh aksepteres som dokumentert sample-grense                                                              | Ingen                               |
| Interpolere tpi til HH:00 via `p`-strømmen | Forventet 0 Wh-presisjon                                                                                   | Middels, krever utvikling           |
| Snapshot-automation i HA på HH:00:00       | Virker IKKE. HAN-framen er allerede 10 sek forsinket inne i måleren, så HA mottar aldri en HH:00:00-verdi. | Irrelevant                          |
| Bruke `meterTimestamp` fra MQTT            | Gir kjent tidspunkt for framen, men flytter ikke selve snapshot-tidspunktet                                | Lav                                 |
| Bytte HAN-leser (Tibber Pulse)             | Kan fjerne 3 sek i transmisjon, men 10 sek i måleren består                                                | Lav (hardware-bytte)                |
| Bruke Elhub-API direkte                    | 0 Wh-presisjon, men dagsforsinkelse                                                                        | Høy (autentisering, ny integrasjon) |

Sample-presisjonen påvirker bare time-fordelingen i scriptet, ikke månedssummen meningsfullt. For faktura-kontroll-formål er 9 Wh ubetydelig.

Se [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for full analyse.

## 2. Momentan-effekt sample-frekvens (2,5 sekunder)

**Hva det er:** AMS-måleren broadcaster momentan effekt (`p`) hvert ~2,5 sek på list1. Vi kan ikke fange spikes som varer kortere enn dette.

**Hvor stort:** Korte motor-spikes, kapasitiv inrush ved oppstart kan være usynlig.

**Praktisk relevans:** Ingen for fakturakontroll, fordi BKK heller ikke ser sub-time-spikes. Kapasitetstrinn er basert på timesnitt.

## 3. EUR/NOK-omregning på Norgespris-kompensasjon

**Hva det er:** Vår beregning av Norgespris-kompensasjon avviker 0,14 % fra BKKs på spot-snitt (0,2 % på selve kompensasjons-beløpet). Sannsynlig årsak: forskjellig EUR/NOK-snittberegning eller forskjellig kurskilde.

**Hvor stort:** April 2026: 2,92 kr på 1427,89 kr Norgespris-kompensasjon.

**Hva kan gjøres:**

| Tiltak                                          | Effekt                                      | Kompleksitet       |
| ----------------------------------------------- | ------------------------------------------- | ------------------ |
| Akseptere (dagens valg)                         | 0,2 % avvik dokumentert                     | Ingen              |
| Hente rå EUR-priser fra Nord Pool + Norges Bank | Forventet 0 % match hvis BKK også bruker NB | Middels            |
| Spørre BKK direkte hvilken kurs de bruker       | Definitivt svar                             | Lav (kundeservice) |

Se [research/nok-omregning.md](research/nok-omregning.md) for full analyse.

## 4. Strømstøtte-formel (2 %)

**Hva det er:** Vår beregning av "spot etter strømstøtte" avviker 2 % fra BKKs egen visning (1347 kr vs 1377 kr for april 2026). Vi bruker standard formel: 90 % refusjon over 0,9125 kr/kWh inkl. mva, time-for-time.

**Mulige årsaker:**

- BKK bruker en litt annen avrundingsregel
- Tibbers prismodell-påslag inkluderes muligens
- Andre forskrifts-detaljer i strømstøtten som ikke er åpenbare

**Praktisk relevans:** Kun for sammenligning mot BKKs "Uten Norgespris"-tall. For brukere som faktisk har Norgespris er dette teoretisk tall, ikke faktisk fakturalinje.

## 5. Spisset mot ett oppsett

**Hva det er:** All faktura-verifisering er gjort mot Fredriks oppsett:

| Komponent               | Verdi                                   |
| ----------------------- | --------------------------------------- |
| Nettselskap             | BKK (NO5)                               |
| Måler                   | Kaifa MA304H3E                          |
| HAN-leser               | Pow-U (AMSleser.no, AmsToMqtt-firmware) |
| Strømleverandør         | Tibber Norge AS                         |
| HA-integrasjon for spot | offisiell `nordpool` (eks. mva)         |

**Konsekvens:** Resultatene gjelder strengt for dette oppsettet. Andre kombinasjoner kan ha:

- Andre HAN-broadcast-tidspunkt (Kaifa, Kamstrup)
- Andre HAN-leser-presisjoner (Tibber Pulse, Tibber Bridge, andre Pow-U-varianter)
- Andre kurs-/MVA-håndteringer i andre nordpool-integrasjoner
- Andre kapasitetstrinn-formler hos andre DSO-er

Andre brukere bør verifisere mot sine egne fakturaer. Se [VERIFISER_DIN_FAKTURA.md](fakturaer/VERIFISER_DIN_FAKTURA.md).

## 6. Ikke validert

Følgende scenarier har ikke blitt verifisert mot ekte faktura:

- DST-overgang (mars og oktober, ±1 time per år)
- Negative spotpriser (kan oppstå ved overskudd av sol/vind)
- Norgespris kWh-tak (5000 kWh/mnd for bolig)
- Avgiftssone Nord-Norge / Tiltakssone (mva-fritak)
- Næringskunde (ikke husholdning)
- Andre nettselskaper enn BKK

Brukere som ønsker å validere disse: send faktura + Elhub-data, så kan vi utvide verifiserings-suiten.

## Sammendrag

Total kjent presisjons-feil:

| Type                   | Worst case (kr/mnd) | Typisk (kr/mnd) | Konsekvens                                  |
| ---------------------- | ------------------- | --------------- | ------------------------------------------- |
| HAN sample-skift       | 0,05                | < 0,01          | Sample-vindu forskyvning                    |
| Kapasitetstrinn-grense | 165                 | 0               | Kun hvis permanent på grense                |
| Norgespris-komp kurs   | 18                  | 2-3             | Marginalt                                   |
| Strømstøtte-beregning  | 30                  | 30              | Kun for teoretisk "uten Norgespris"-visning |

For en gjennomsnittlig bruker er det total ukjent presisjons-feil under 5 kr/mnd, eller under 0,1 % av total fakturasum. Integrasjonen kan trygt brukes for fakturakontroll. Den fanger reelle feil i størrelsesorden 50 kr+ uten problem.
