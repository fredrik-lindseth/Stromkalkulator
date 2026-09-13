# Kjente begrensninger

Integrasjonen treffer fakturaen på øret. Sensorer i HA vises i kr og kWh som matcher det nettselskapet fakturerer. Begrensningene under er ikke-validerte scenarier eller spesielle tilfeller du bør vite om.

## 1. Spisset mot ett oppsett

All faktura-verifisering er gjort mot eget oppsett:

| Komponent               | Verdi                                   |
| ----------------------- | --------------------------------------- |
| Nettselskap             | BKK (NO5), verifisert mot 10 fakturaer  |
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

Vil du validere noen av disse, send faktura + Elhub-data, så kan vi utvide verifiserings-suiten.

## 3. Norgespris-kompensasjon (prisårgang i den løpende sensoren)

Løst for verifisering 2026-07-06. Med Nord Pools publiserte Final-priser reproduseres Norgespris-linjen eksakt (juni 2026: 0,00 kr avvik). Formelen, symmetrien og kursgrunnlaget er riktig. Se [research/norgespris-eksakt-match.md](research/norgespris-eksakt-match.md).

Det som gjenstår er den løpende sensoren i HA. Den akkumulerer med prisen slik den ser ut i leveringstimen, og på dager der valutamarkedet var stengt på auksjonsdagen (søndager, enkelte helligdager) er det en foreløpig kurs som Nord Pool senere korrigerer til Final. En akkumulert sum kan ikke rettes bakover. Målt effekt: 0,15 kr (juni) og 0,55 kr (mai), altså 0,04-0,05 % av kompensasjonen. Fakturaverifiseringen i etterkant er ikke berørt, den bruker publiserte Final-priser fra prisarkivet (`just snapshot-kurs`).

Avregningen på intervaller (L3a og L3b) flyttet ikke på dette. Den fjernet polltiden fra regnestykket, altså hvilket øyeblikk vi spurte sensoren, men prisen som ligger i intervallet er fortsatt den som var publisert da timen ble levert. Er den foreløpig, blir den stående. Sensorene leser de samme kronene fra L3c og arver derfor det samme.

## 4. Strømstøtte-formel (~30 kr/mnd vs BKKs visning)

Vår "spot etter strømstøtte" avviker ~30 kr/mnd fra BKKs egen "Uten Norgespris"-visning (april 2026: vi beregner 1408,52 kr, BKK viser 1377 kr). Vi bruker 2026-terskel fra forskrift 2025-09-08-1791 §5: 90 % refusjon når spotpris overstiger 77 øre/kWh eks. mva (0,9625 kr/kWh inkl. mva), time-for-time.

Avviket ser ut til å skyldes at BKKs visning fortsatt bruker 2025-terskelen (75 øre eks. mva / 0,9375 inkl. mva). Med lavere terskel blir refusjonen større, så BKK trekker fra mer enn vi gjør. Vi gir altså mer strømstøtte i vår beregning enn det BKK viser. Dette er anekdotisk basert på én faktura (april 2026); det kan også være avrundingsregler eller andre detaljer i forskriften som spiller inn.

Kun relevant for Norgespris-kunder som vil sammenligne mot BKKs "Uten Norgespris"-tall i kundeportalen. Tallet er en hypotetisk visning, ikke en faktisk fakturalinje. Norgespris-kunder mottar ikke strømstøtte uansett.

## 5. Momentan-effekt sample-frekvens (2,5 sek)

AMS-måleren broadcaster momentan effekt (`p`) hvert ~2,5 sek på list1. Kortere spikes enn dette fanges ikke (motor-spikes, kapasitiv inrush ved oppstart). Ingen praktisk relevans for fakturakontroll, fordi nettselskapet heller ikke ser sub-time-spikes. Kapasitetstrinn er basert på timesnitt.

Relevant kun hvis du vil oppdage korte effekt-topper i hjemmet ditt.

## 6. For utviklere: verifisering mot ekte faktura

Vi har en dev-pipeline (`scripts/research/verify_invoice_hourly.py`) som leser tpi-broadcast direkte fra AMS-måleren for å sammenligne mot Elhub og fakturaen. Den har et 13-sek sample-skift (10 sek inne i måleren + 3 sek transmisjon på Kaifa + Pow-U-oppsett) som påvirker bare denne pipelinen.

Selve HA-integrasjonen leser `p`-strømmen kontinuerlig og er ikke påvirket. Det betyr at sensorene du ser i Energy Dashboard og månedstotaler ikke har de 9 Wh-avvikene som dev-pipelinen viser.

Se [research/klokke-og-tidsstempling.md](research/klokke-og-tidsstempling.md) og [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for full kontekst.

Attesten er sist revalidert mot `7ea60cb`, med før/etter per komponent i
[research/revalidering-l3b-september-2026.md](research/revalidering-l3b-september-2026.md).
Den runden er gyldig bare for den commiten: neste serie som rører
`coordinator.py`, `kostnad.py` eller BKK-satsene må kjøre alle ti månedene på
nytt.

## 7. Gap-bucket ved lang nedetid (energy_sensor): pensjonert

Sto her til september 2026, og beskrev at hele backlog-deltaet etter en lang
nedetid ble kreditert klokketimen og dag/natt-tariffen som gjaldt da HA kom
tilbake, ikke timene forbruket faktisk skjedde i.

Avregningen på intervaller (L3a) fjernet den. Energi bokføres nå etter
avlesningens observasjonstid, ikke pollens, og et delta som spenner flere
intervaller fordeles over dem (`fordel_delta` og `Bok._fordel` i
`avregning.py`). Et gjenopptatt delta lander derfor i timene det hører hjemme i,
med riktig dag/natt-splitt, og døgnmaks blir ikke blåst opp av en enkelt poll.

Grensen som står igjen er `MAX_ENERGY_DELTA_KWH` (100 kWh per avlesning), og
uten `energy_sensor` gjelder fortsatt Riemann-stien: et vindu lengre enn
`MAX_ELAPSED_HOURS` bokføres ikke i det hele tatt
([avregning.md B1](kontrakter/avregning.md#b1-energiavlesning)). Det er prisen
for ikke å ha en teller, og den er uendret.

## 8. Øyeblikks-prising av gap-forbruk (energy_sensor): pensjonert

Sto her til september 2026, og beskrev at hele gap-deltaet ble priset til én
øyeblikksverdi av spotpris og energiledd fra oppstartstidspunktet.

Kostnadskjernen (L3b) fjernet den. Kroner regnes per avregnet intervall med
intervallets egen pris, aldri med den som sto på sensoren da vi spurte.
Kilowattimer som ikke har noen pris får heller ingen: de bokføres synlig som
`kwh_uten_pris` i stedet for å bli priset med en sats fra et annet intervall.
Det er strengere enn det som sto her, og det betyr at et gap gir et lavere,
ikke et skjevt, kronetall, med et felt som sier hvor mye som mangler.

Kostnadskjernen tok samtidig `monthly_cost_kr`, `monthly_net_cost_kr` og
`daily_cost_kr` ut av polltidens pris: de er nå én akkumulator sammen med
`monthly_accumulated_cost_kr`, og fastleddet legges inn som periodebeløp i
stedet for som en kroner-per-time-sats ganget med kilowattimer. Målt mot
fakturaen falt `monthly_cost_kr` 64 til 145 kroner ned på riktig verdi for mai,
juni og juli 2026, se
[research/revalidering-l3b-september-2026.md](research/revalidering-l3b-september-2026.md).

Sensorene leser de samme kronene fra september 2026 (L3c). Ett unntak står
igjen: «Forrige måned nettleie» regner satser ganget med arkiverte
kilowattimer, fordi arkivet ikke lagrer forrige måneds bokførte kroner. Den
bommer når energileddsatsen endret seg midt i måneden, altså ved nyttår og for
sesong-nettselskap 1. april og 1. november. Attributtet `kilde` på sensoren sier
det, og fikses i stromkalkulator-1fnzdn8.

Det som ellers står igjen er en visningskuriositet: attributtet
`kapasitetsledd_per_kwh` er kroner per time presentert som kroner per
kilowattime, og de to er bare like ved nøyaktig 1 kWh/h. Tallet ganges ikke inn
i noe beløp lenger, så det rammer bare den viste prisen per kWh.

## 9. Fem nettselskap har en annen kapasitetsledd-modell

Kapasitetsleddet beregnes som snittet av de tre høyeste døgnmaksene i måneden. Det er den vanligste innretningen, og 69 av de 74 valgbare oppføringene i `dso.py` bruker den. RME anbefaler den ikke, de skriver at nettselskapene «har en viss frihet til å bestemme hvordan de vil differensiere» fastleddet, og nevner både døgnmaks, snitt av flere døgnmakser og sikringsstørrelse som lovlige innretninger ([RME: Nettleie for forbruk](https://www.nve.no/reguleringsmyndigheten/regulering/nettvirksomhet/nettleie/nettleie-for-forbruk/)). De fem under bryter altså ingen regel. Alle fem er implementert etter sin egen modell, men de har hver sin restbegrensning:

| Nettselskap       | Metode          | Hva som gjelder nå                                                             |
| ----------------- | --------------- | ------------------------------------------------------------------------------ |
| Sør Aurdal Energi | `MND_MAX`       | Månedsmaksen bestemmer trinnet. Ingen restbegrensning.                         |
| Alut, Netera      | `OV_TREFASE`    | Fastledd etter hovedsikring. Du må velge sikringsstørrelsen selv.              |
| Fjellnett         | `FEM_VEKTET_ÅR` | Lineær sats fra fem sesongvektede ukestopper. Trenger tolv måneders historikk. |
| Tinfos            | `UKJENT`        | Nettselskapet publiserer ikke metoden. Beløpet er merket uverifisert.          |

Alut og Netera fakturerer etter størrelsen på hovedsikringen, som ingen sensor kan lese. Du velger raden fra prislisten i oppsettet, eller under Configure hvis du hadde integrasjonen fra før. Til den er valgt, står kapasitetstrinn-sensoren som Ukjent, og fastleddet mangler i månedskostnad og fakturaestimat. Det er et bevisst valg: et gjettet trinn ville sett riktig ut og vært feil, og hos Netera skiller trinnene seg med en faktor to.

Fjellnett har ingen trinn. Fastleddet er grunnbeløp pluss en sats per kW, der kW er snittet av de fem høyeste ukestoppene over løpende tolv måneder, sesongvektet. Vi bygger opp den historikken fra dagen du installerer integrasjonen, så det første året viser sensoren for lite (i starten bare grunnbeløpet) og konvergerer mot riktig beløp over tolv måneder. Vi kan ikke hente historikk bakover, den ligger hos Fjellnett og i Elhub. Beløpet rundes til hele kroner per måned, som resten av satsene, altså opptil 50 øre/mnd unna Fjellnetts øre-eksakte beløp.

Tinfos publiserer ikke tariffen sin, og fri-nettleie har sendt dem en forespørsel uten å få svar. Trinnprisene stemmer, men ingen av kildene vet hvilken kW-verdi de slås opp med. Vi regner med NVE-modellen og setter attributtet `metode_uverifisert` på sensoren. Har du en Tinfos-faktura, se [bidra med faktura](fakturaer/bidra-med-faktura.md).

Metodenavnene er fri-nettleies. Detaljer i [beregninger.md](beregninger.md#nettselskap-med-en-annen-metode), historikken i [incident 006](incidents/006-kapasitetstrinn-uten-kilde.md).

Én ting til om Fjellnett: energiledd og fastledd følger nettselskapets egen prisliste fra 01.07.2026, mens fri-nettleie fortsatt har 01.01.2026-tariffen. Avviket er ført opp i `KJENTE_AVVIK` i drift-vakten og fjernes når fri-nettleie er oppdatert.

## 10. To nettselskap vi ikke får verifisert godt nok

Drift-vakten sammenligner mot fri-nettleie hver uke, men den fanger bare det begge kildene ser. Disse to har et hull ingen av dem dekker.

Area Nett har tre prisområder med ulik pris, og hvilket som gjelder avgjøres av adressen. Du velger området selv i oppsettet: område 1 (Nordkapp, Måsøy), område 2 (Karasjok, Porsanger) eller område 3 (Gamvik, Lebesby). Har du integrasjonen fra før, står du på den utfasede oppføringen som regner med område 2, og et repair-varsel ber deg velge. Laveste trinn spriker fra 358 til 525 kr/mnd mellom områdene, så valget betyr noe. Kilde er Areas eget prisblad for 2026. For område 1 avviker fri-nettleie i de tre øverste trinnene, ført opp i `KJENTE_AVVIK`.

Tinfos er dekket i punkt 9. Ingen kilde finnes for metoden.

Felles for begge: se [bidra med faktura](fakturaer/bidra-med-faktura.md).

Arva sto her fram til 13. september 2026. Prissiden rendres med JavaScript, men artikkelen bak den ligger åpent som JSON på `arva.no/Api/v2/template/rendered-article?pageId=484888468&Article=305`, og der står hele prislisten. Satsene stemmer tall for tall, og Arva skriver selv at nettleien er holdt uendret fra 1. januar 2026, så fri-nettleies fil fra 2024 er ikke ustelt, bare uendret. Sesongprisingen hos Arva gjelder kun kunder over 100 000 kWh i året, en gruppe vi ikke dekker.

## 11. Egendefinert nettselskap har ikke noe fastledd før du oppgir det

Velger du Egendefinert, finnes det ingen prisliste vi kan lese. Til og med 1.16.0 lå det likevel ti kapasitetstrinn i koden for den oppføringen. De var en mal, ikke priser, og siden kapasitetsleddet er et fast månedsbeløp gikk feilen rett inn i månedskostnaden. De er fjernet, av samme grunn som i [incident 006](incidents/006-kapasitetstrinn-uten-kilde.md).

I stedet kan du skrive inn dine egne trinn i oppsettet, ett trinn per rad i prislisten, som kW-grense og kr/mnd inkl. mva skilt av kolon og trinnene skilt av komma: `kW-grense:kr/mnd,kW-grense:kr/mnd`, med stigende kW-grenser. Det øverste trinnet gjelder alt over grensen under, så du trenger ikke skrive noe for «og oppover». Beløpene henter du fra nettleiefakturaen eller prislisten din. Vi setter ikke et eksempel med tall her, for vi har ingen prisliste for Egendefinert, og tallene måtte i så fall vært hentet fra et annet nettselskap.

Lar du feltet stå tomt, er fastleddet ukjent. Da står kapasitetstrinn, trinn-nummer, margin til neste trinn, månedlig nettleie, månedlig total, estimert månedskostnad og akkumulert kostnad som Ukjent, og prisene per kWh regnes uten fastledd med attributtet `fastledd_ukjent`. Energiledd, forbruk, spotpris, strømstøtte, Norgespris og avgifter er uberørt. Et repair-varsel ber om tabellen ved hver oppstart til den er fylt inn, og en lagret tabell som ikke lar seg lese (håndredigert `.storage`) gir sitt eget varsel om at den må skrives om.

Ukjent er med vilje. Et beløp vi ikke har kilde på ser ut som en pris uten å være det, og en nettleie som er 200 kr/mnd feil melder seg ikke selv før fakturaen kommer.

## Sammendrag

Reelle avvik som påvirker brukeren:

| Type                   | Worst case | Typisk         | Konsekvens                                      |
| ---------------------- | ---------- | -------------- | ----------------------------------------------- |
| Norgespris prisårgang  | ~1 kr/mnd  | 0,1-0,6 kr/mnd | Kun løpende sensor, verifisering treffer eksakt |
| Strømstøtte-beregning  | 30 kr/mnd  | 30 kr/mnd      | Kun for teoretisk visning                       |
| Kapasitetstrinn-grense | 165 kr/mnd | 0              | Kun hvis permanent på grense                    |

Total typisk ukjent feil er under 5 kr/mnd for en vanlig bruker, altså under 0,1 % av fakturasummen. Integrasjonen kan trygt brukes for fakturakontroll og fanger reelle feil i størrelsesorden 50 kr+.
