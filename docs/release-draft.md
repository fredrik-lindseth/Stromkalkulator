## Norgespris-sammenligning fungerer nå

Strømstøtte beregnes nå alltid fra spotpris, også for Norgespris-kunder. Tidligere ble strømstøtte satt til 0 med Norgespris, noe som gjorde at sammenligning mellom Norgespris og spot+støtte ikke fungerte. Nå viser alle sammenligning-sensorer riktige verdier:

- **Strømstøtte** — viser hva støtten er basert på spotpris (for sammenligning)
- **Spotpris etter støtte** — viser spot minus støtte (ikke bare rå spotpris)
- **Prisforskjell** — viser faktisk differanse mellom din Norgespris og spot+støtte
- **Månedlig besparelse** — akkumulerer riktig over tid

Din totalpris bruker fortsatt fast Norgespris — strømstøtte vises kun for sammenligning.

## Bugfixes

- Barents Nett krasjet ved lasting (dict-format kapasitetstrinn)
- NaN/Infinity fra sensorer fanges i beregninger (elapsed_hours clampes til 0–6 min)
- Ugyldig energiledd/terskel i config krasjer ikke ved oppstart (faller tilbake til DSO-standardverdi)
- Manglende kildesensor varsler HA med UpdateFailed (tidligere bare ved begge)
- HA-restart over månedsskifte mister ikke lenger forrige måneds data
- Kapasitetsvarsel viste permanent "on" i høyeste trinn
- Spotpris falt til 0 ved sensorutfall, caches nå
- Norgespris-besparelse arkiveres ved månedsskifte
- Tidssone-konsistens: bruker HA-tidssone overalt, ikke systemklokke
- Korrupt storage krasjer ikke permanent (validering ved innlesing)
- Disk-feil tar ikke ned alle sensorer (logger warning, fortsetter)
- Negative verdier i storage avvises
- Urimelige effektavlesninger (>500 kW) ignoreres
- Dict-kopier i lagring forhindrer race condition
- Filmigrering blokkerer ikke event loop
- Attributt-nøkler bruker ASCII (NFC/NFD-konsistens)
- Options flow reloader integrasjonen ved endring
- Options flow bevarer energiledd-presisjon (0.4613 ble til 0)
- Effektsensor-unikhet valideres i options flow
- Monetary-sensorer ga HA-warnings (fjernet ugyldig state_class=MEASUREMENT). Du vil se 17 "state_class_removed" repairs i HA — klikk "ignore" på alle. Prissensorer (kr/kWh) er øyeblikkssatser som ikke hører hjemme i langtidsstatistikk. De nye sensorene (dagens kostnad, estimert månedskostnad) gir mer nyttige aggregeringer

## Nye sensorer

- **Dagens kostnad** — akkumulert strømkostnad i dag (nullstilles ved midnatt)
- **Estimert månedskostnad** — projiserer totalkostnad basert på forbruk hittil

## Nye attributter

- `dag_pct`/`natt_pct` på månedlig forbruk total — dag/natt-fordeling i prosent
- `vektet_snittpris_kr_per_kwh` på månedlig total — faktisk snittpris denne måneden

## Forbedringer

- ~17 sensorer aktive som standard, ~25 deaktivert — diagnostikk, nedbrytninger og Norgespris slås på ved behov under Enheter > Entities
- Rename TSO → DSO overalt (TSO er Statnett, nettselskaper er DSO)
- Manglende kildesensor gir nå spesifikk feilmelding per sensor

## Vedlikehold

- 1668 automatiserte tester
- To runder adversarial fuzzing med 40 agenter
- Coverage-review: 34 nye tester for 10 dekningshull
- Test-kvalitetsreview: 31 nye tester fra 10 parallelle reviewers

## Verifisering

**SHA256:** `(genereres av release-workflow)` — [hvordan verifisere](SECURITY.md)

<details>
<summary>Alle commits</summary>

- fix: normaliser Barents Nett dict-format kapasitetstrinn ved lasting
- fix: beskytt sensoravlesning mot ugyldig input
- fix: korrekt månedsskifte ved HA-restart og årsbevisst månedsformat
- fix: arkiver Norgespris-differanse ved månedsskifte
- fix: valider storage-data og beskytt mot disk-feil
- fix: cache spotpris ved sensorutfall
- fix: reload ved options-endring og korrekt energiledd-presisjon
- fix: kjør filmigrering i executor og migrer før config-oppdatering
- fix: bruk ASCII-nøkler i sensor-attributter
- fix: bruk dt_util.now() for konsistent tidssone
- fix: kapasitet_varsel alltid på i høyeste trinn
- fix: fang ValueError/TypeError i float()-konvertering i init
- fix: kopier dict-referanser i \_save_stored_data
- fix: avvis negative verdier og urimelige effektavlesninger
- fix: valider unikhet for effektsensor i options flow
- fix: raise UpdateFailed når begge sensorer mangler
- fix: fjern state_class=MEASUREMENT fra monetary-sensorer
- fix: beregn strømstøtte alltid fra spotpris (Norgespris-sammenligning)
- refactor: rename TSO→DSO overalt
- feat: sensor for dagens kostnad
- feat: sensor for estimert månedskostnad
- feat: attributt dag/natt-fordeling (%) på månedlig forbruk
- feat: attributt vektet snittpris (kr/kWh) på månedlig total
- feat: akkumuler daglig kostnad i coordinator
- feat: deaktivert som standard for diagnostikk- og nisje-sensorer

</details>
