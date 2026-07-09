# Kjente begrensninger

Integrasjonen treffer fakturaen på øret. Sensorer i HA vises i kr og kWh som matcher det nettselskapet fakturerer. Begrensningene under er ikke-validerte scenarier eller spesielle tilfeller du bør vite om.

## 1. Spisset mot ett oppsett

All faktura-verifisering er gjort mot eget oppsett:

| Komponent               | Verdi                                   |
| ----------------------- | --------------------------------------- |
| Nettselskap             | BKK (NO5), verifisert mot 8 fakturaer   |
| Måler                   | Kaifa MA304H3E                          |
| HAN-leser               | Pow-U (AMSleser.no, AmsToMqtt-firmware) |
| Strømleverandør         | Tibber Norge AS                         |
| HA-integrasjon for spot | offisiell `nordpool` (eks. mva)         |

Resultatene gjelder strengt for denne kombinasjonen. Andre kombinasjoner kan ha andre presisjons-karakteristikker, spesielt på kurs-/MVA-håndtering i andre nordpool-integrasjoner og kapasitetstrinn-formler hos andre nettselskaper. Andre brukere bør verifisere mot egne fakturaer. Se [verifiser-din-faktura.md](fakturaer/verifiser-din-faktura.md).

## 2. Ikke-validerte scenarier

Følgende har ikke blitt verifisert mot ekte faktura:

- DST-overgang høst (oktober, +1 time, doblet klokke-time, kjent bug: [research/ikke-validerte-scenarier.md](research/ikke-validerte-scenarier.md#1-dst-overgang)). Har ikke inntruffet ennå i verifiseringsperioden. Vår-DST (mars, -1 time) er derimot dekket: mars 2026-fakturaen omfatter hele 23-timersdøgnet 29.03, og dag/natt-totalene matcher innenfor vanlig avrundingsfeil (se `tests/fixtures/README.md`).
- Negative spotpriser (kan oppstå ved overskudd av sol/vind)
- Norgespris kWh-tak (5000 kWh/mnd for bolig)
- Avgiftssone Nord-Norge / Tiltakssone (mva-fritak)
- Næringskunde (ikke husholdning)
- Andre nettselskaper enn BKK

Vil du validere noen av disse: send faktura + Elhub-data, så kan vi utvide verifiserings-suiten.

## 3. Norgespris-kompensasjon (prisårgang i den løpende sensoren)

**Løst for verifisering 2026-07-06:** Med Nord Pools publiserte Final-priser reproduseres Norgespris-linjen eksakt (juni 2026: 0,00 kr avvik). Formelen, symmetrien og kursgrunnlaget er riktig. Se [research/norgespris-eksakt-match.md](research/norgespris-eksakt-match.md).

Det som gjenstår er den løpende sensoren i HA. Den akkumulerer med prisen slik den ser ut i leveringstimen, og på dager der valutamarkedet var stengt på auksjonsdagen (søndager, enkelte helligdager) er det en foreløpig kurs som Nord Pool senere korrigerer til Final. En akkumulert sum kan ikke rettes bakover. Målt effekt: 0,15 kr (juni) og 0,55 kr (mai), altså 0,04-0,05 % av kompensasjonen. Fakturaverifiseringen i etterkant er ikke berørt, den bruker publiserte Final-priser fra prisarkivet (`just snapshot-kurs`).

## 4. Strømstøtte-formel (~30 kr/mnd vs BKKs visning)

Vår "spot etter strømstøtte" avviker ~30 kr/mnd fra BKKs egen "Uten Norgespris"-visning (april 2026: vi beregner 1408,52 kr, BKK viser 1377 kr). Vi bruker 2026-terskel fra forskrift 2025-09-08-1791 §5: 90 % refusjon når spotpris overstiger 77 øre/kWh eks. mva (0,9625 kr/kWh inkl. mva), time-for-time.

Avviket ser ut til å skyldes at BKKs visning fortsatt bruker 2025-terskelen (75 øre eks. mva / 0,9375 inkl. mva). Med lavere terskel blir refusjonen større, så BKK trekker fra mer enn vi gjør, vi gir altså mer strømstøtte i vår beregning enn det BKK viser. Dette er anekdotisk basert på én faktura (april 2026); det kan også være avrundingsregler eller andre detaljer i forskriften som spiller inn.

Kun relevant for Norgespris-kunder som vil sammenligne mot BKKs "Uten Norgespris"-tall i kundeportalen. Tallet er en hypotetisk visning, ikke en faktisk fakturalinje, Norgespris-kunder mottar ikke strømstøtte uansett.

## 5. Momentan-effekt sample-frekvens (2,5 sek)

AMS-måleren broadcaster momentan effekt (`p`) hvert ~2,5 sek på list1. Kortere spikes enn dette fanges ikke (motor-spikes, kapasitiv inrush ved oppstart). Ingen praktisk relevans for fakturakontroll, fordi nettselskapet heller ikke ser sub-time-spikes. Kapasitetstrinn er basert på timesnitt.

Relevant kun hvis du vil oppdage korte effekt-topper i hjemmet ditt.

## 6. For utviklere: verifisering mot ekte faktura

Vi har en dev-pipeline (`scripts/research/verify_invoice_hourly.py`) som leser tpi-broadcast direkte fra AMS-måleren for å sammenligne mot Elhub og fakturaen. Den har et 13-sek sample-skift (10 sek inne i måleren + 3 sek transmisjon på Kaifa + Pow-U-oppsett) som påvirker bare denne pipelinen.

Selve HA-integrasjonen leser `p`-strømmen kontinuerlig og er ikke påvirket. Det betyr at sensorene du ser i Energy Dashboard og månedstotaler ikke har de 9 Wh-avvikene som dev-pipelinen viser.

Se [research/klokke-og-tidsstempling.md](research/klokke-og-tidsstempling.md) og [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for full kontekst.

## Sammendrag

Reelle avvik som påvirker brukeren:

| Type                   | Worst case | Typisk       | Konsekvens                   |
| ---------------------- | ---------- | ------------ | ---------------------------- |
| Norgespris prisårgang  | ~1 kr/mnd  | 0,1-0,6 kr/mnd | Kun løpende sensor, verifisering treffer eksakt |
| Strømstøtte-beregning  | 30 kr/mnd  | 30 kr/mnd    | Kun for teoretisk visning    |
| Kapasitetstrinn-grense | 165 kr/mnd | 0            | Kun hvis permanent på grense |

Total typisk ukjent feil: under 5 kr/mnd for vanlig bruker. Under 0,1 % av total fakturasum. Integrasjonen kan trygt brukes for fakturakontroll og fanger reelle feil i størrelsesorden 50 kr+.
