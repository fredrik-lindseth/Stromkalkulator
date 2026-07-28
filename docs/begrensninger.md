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

Vil du validere noen av disse, send faktura + Elhub-data, så kan vi utvide verifiserings-suiten.

## 3. Norgespris-kompensasjon (prisårgang i den løpende sensoren)

**Løst for verifisering 2026-07-06:** Med Nord Pools publiserte Final-priser reproduseres Norgespris-linjen eksakt (juni 2026: 0,00 kr avvik). Formelen, symmetrien og kursgrunnlaget er riktig. Se [research/norgespris-eksakt-match.md](research/norgespris-eksakt-match.md).

Det som gjenstår er den løpende sensoren i HA. Den akkumulerer med prisen slik den ser ut i leveringstimen, og på dager der valutamarkedet var stengt på auksjonsdagen (søndager, enkelte helligdager) er det en foreløpig kurs som Nord Pool senere korrigerer til Final. En akkumulert sum kan ikke rettes bakover. Målt effekt: 0,15 kr (juni) og 0,55 kr (mai), altså 0,04-0,05 % av kompensasjonen. Fakturaverifiseringen i etterkant er ikke berørt, den bruker publiserte Final-priser fra prisarkivet (`just snapshot-kurs`).

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

## 7. Gap-bucket ved lang nedetid (energy_sensor)

Med `energy_sensor` konfigurert (kumulativ kWh-teller) leser coordinator forbruket som differansen mot forrige avlesning, uavhengig av hvor lenge det er siden forrige poll. Er HA nede lenger enn noen få minutter, krediteres hele backlog-deltaet til klokketimen og dag/natt-tariffen som gjelder når HA er tilbake og poller igjen, ikke til timene det egentlig ble brukt i. Deltaet er bundet oppad av `MAX_ENERGY_DELTA_KWH` (100 kWh), og verdien det måles mot (`_last_tpi_kwh`) bundet av `TPI_STALE_HOURS` (24 timer, eldre verdi forkastes ved omstart).

Dette kan forbigående blåse opp vist døgnmaks og kapasitetstrinn, og skjeve dag/natt-split-attributtet for den dagen (og måneden fram til neste månedsskifte). DSO-fakturaen er upåvirket, nettselskapet måler timesforbruk uavhengig av hvordan HA bokfører det.

Bevisst valg. En fiks krever et nytt persistert tidsstempel og en time-for-time-loop som fordeler backlogget på riktige klokketimer. Det er samme filosofi som den aksepterte forenklingen i `coordinator.py:714` (Norgespris-taket som nås midt i en time, teller hele timen i feil bucket). Mekanisme: `_compute_energy_delta` (`coordinator.py:340-380`) beregner deltaet, bucket-logikken (`coordinator.py:547-580`) avgjør hvilken dag og klokketime det krediteres til.

Gjelder kun oppsett med `energy_sensor` satt. Uten den faller coordinator tilbake på Riemann-sum (`p * elapsed_hours`), der `elapsed_hours` er begrenset til `MAX_ELAPSED_HOURS` (6 min), så et langt gap bare mister de manglende minuttene i stedet for å dumpe et stort delta i én bucket.

## 8. Øyeblikks-prising av gap-forbruk ved HA-nedetid (energy_sensor)

Beslektet med punkt 7, men om prisingen. Med `energy_sensor` konfigurert: er HA nede mellom 6 minutter og 24 timer, fanges alt forbruk i nedetiden i første poll etter oppstart (delta på kWh-telleren, kappet til 100 kWh). Hele deltaet prises til én øyeblikksverdi av spotpris og energiledd fra oppstartstidspunktet, ikke time-for-time faktiske satser. Rammer `monthly_cost_kr`, `monthly_accumulated_cost_strom_kr` og `monthly_accumulated_cost_energiledd_kr`. Kapasitetsleddet rammes ikke (akkumuleres tidsbasert og hopper bare over gap-sekundene).

Konsekvens: for spot-kunder gir et enkelt flertimers-avbrudd typisk et avvik på 15-25 kr, som nullstilles ved månedsskifte. For Norgespris-kunder er strømdelen fast pris og dermed korrekt uansett; kun energiledd dag/natt bommer marginalt. Forbruket i kWh fanges korrekt uansett.

Bevisst valg. En tidsriktig spot-korreksjon krever historiske timespriser for gap-vinduet, som coordinatoren ikke har tilgang til. Riemann-stien (uten `energy_sensor`) rammes ikke: der forkastes gap-forbruk over 6 minutter helt.

## 9. Fem nettselskap har en annen kapasitetsledd-modell

Kapasitetsleddet beregnes som snittet av de tre høyeste døgnmaksene i måneden. Det er modellen NVE anbefaler, og 68 av 73 nettselskap bruker den. Fem gjør noe annet. Alle fem er nå implementert etter sin egen modell, men de har hver sin restbegrensning:

| Nettselskap       | Metode          | Hva som gjelder nå                                                             |
| ----------------- | --------------- | ------------------------------------------------------------------------------ |
| Sør Aurdal Energi | `MND_MAX`       | Månedsmaksen bestemmer trinnet. Ingen restbegrensning.                         |
| Alut, Netera      | `OV_TREFASE`    | Fastledd etter hovedsikring. Du må velge sikringsstørrelsen selv.              |
| Fjellnett         | `FEM_VEKTET_ÅR` | Lineær sats fra fem sesongvektede ukestopper. Trenger tolv måneders historikk. |
| Tinfos            | `UKJENT`        | Nettselskapet publiserer ikke metoden. Beløpet er merket uverifisert.          |

**Alut og Netera** fakturerer etter størrelsen på hovedsikringen, som ingen sensor kan lese. Du velger raden fra prislisten i oppsettet, eller under Configure hvis du hadde integrasjonen fra før. Til den er valgt, står kapasitetstrinn-sensoren som Ukjent, og fastleddet mangler i månedskostnad og fakturaestimat. Det er et bevisst valg: et gjettet trinn ville sett riktig ut og vært feil, og hos Netera skiller trinnene seg med en faktor to.

**Fjellnett** har ingen trinn. Fastleddet er grunnbeløp pluss en sats per kW, der kW er snittet av de fem høyeste ukestoppene over løpende tolv måneder, sesongvektet. Vi bygger opp den historikken fra dagen du installerer integrasjonen, så det første året viser sensoren for lite (i starten bare grunnbeløpet) og konvergerer mot riktig beløp over tolv måneder. Vi kan ikke hente historikk bakover, den ligger hos Fjellnett og i Elhub. Beløpet rundes til hele kroner per måned, som resten av satsene, altså opptil 50 øre/mnd unna Fjellnetts øre-eksakte beløp.

**Tinfos** publiserer ikke tariffen sin, og fri-nettleie har sendt dem en forespørsel uten å få svar. Trinnprisene stemmer, men ingen av kildene vet hvilken kW-verdi de slås opp med. Vi regner med NVE-modellen og setter attributtet `metode_uverifisert` på sensoren. Har du en Tinfos-faktura, se [bidra med faktura](fakturaer/bidra-med-faktura.md).

Metodenavnene er fri-nettleies. Detaljer i [beregninger.md](beregninger.md#nettselskap-med-en-annen-metode), historikken i [incident 006](incidents/006-kapasitetstrinn-uten-kilde.md).

Én ting til om Fjellnett: energiledd og fastledd følger nettselskapets egen prisliste fra 01.07.2026, mens fri-nettleie fortsatt har 01.01.2026-tariffen. Avviket er ført opp i `KJENTE_AVVIK` i drift-vakten og fjernes når fri-nettleie er oppdatert.

## 10. Tre nettselskap vi ikke får verifisert godt nok

Drift-vakten sammenligner mot fri-nettleie hver uke, men den fanger bare det begge kildene ser. Disse tre har et hull ingen av dem dekker.

**Area Nett** har tre prisområder med ulik pris, og hvilket som gjelder avgjøres av adressen. Du velger området selv i oppsettet: område 1 (Nordkapp, Måsøy), område 2 (Karasjok, Porsanger) eller område 3 (Gamvik, Lebesby). Har du integrasjonen fra før, står du på den utfasede oppføringen som regner med område 2, og et repair-varsel ber deg velge. Laveste trinn spriker fra 358 til 525 kr/mnd mellom områdene, så valget betyr noe. Kilde er Areas eget prisblad for 2026. For område 1 avviker fri-nettleie i de tre øverste trinnene, ført opp i `KJENTE_AVVIK`.

**Arva** publiserer prisene med JavaScript, så siden er ikke lesbar uten nettleser, og fri-nettleies `arva.yml` er sist oppdatert 22. oktober 2024. Satsene våre matcher fri-nettleie eksakt, men begge kan ha stått stille siden 2024. En tidligere kommentar i `dso.py` påsto at Arva har sesongpriser, uten kilde på sommersatsen og uten at det var implementert, altså brukte vi vintersatsen hele året på en ubekreftet påstand. Påstanden er fjernet. Har du en Arva-faktura, er den spesielt nyttig.

**Tinfos** er dekket i punkt 9. Ingen kilde finnes for metoden.

Felles for alle tre: se [bidra med faktura](fakturaer/bidra-med-faktura.md).


## Sammendrag

Reelle avvik som påvirker brukeren:

| Type                   | Worst case | Typisk         | Konsekvens                                      |
| ---------------------- | ---------- | -------------- | ----------------------------------------------- |
| Norgespris prisårgang  | ~1 kr/mnd  | 0,1-0,6 kr/mnd | Kun løpende sensor, verifisering treffer eksakt |
| Strømstøtte-beregning  | 30 kr/mnd  | 30 kr/mnd      | Kun for teoretisk visning                       |
| Kapasitetstrinn-grense | 165 kr/mnd | 0              | Kun hvis permanent på grense                    |

Total typisk ukjent feil er under 5 kr/mnd for en vanlig bruker, altså under 0,1 % av fakturasummen. Integrasjonen kan trygt brukes for fakturakontroll og fanger reelle feil i størrelsesorden 50 kr+.
