# Changelog

Format basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.13.0]

### Lagt til

- Nytt valgfritt config-flow-felt `energy_sensor` (kWh, TOTAL_INCREASING). Hvis konfigurert: integrasjonen bruker delta-akkumulering fra meter-registeret i stedet for Riemann-summering av effektmåleren. Treffer fakturaen ned til 0 Wh, uavhengig av HA-restart-mønster. Se [docs/input-sensorer.md](docs/input-sensorer.md).

### Fikset

- `_last_update` persisteres nå til storage. Tidligere ble feltet nullstilt ved HA-restart slik at akkumulator mistet tid i restart-vinduet. Eget oppsett april 2026: 36 % manglende forbruk i Norgespris-kompensasjon-sensor.
- `_load_stored_data`: `_last_tpi_kwh` restaureres kun hvis `last_update` finnes og er innenfor 24 timer. Forhindrer at en gammel verdi blir baseline ved første poll etter restart.
- `nb.json` og `en.json` manglet label for `spotpris_inkl_mva`. HA viste rå nøkkel-navn i config-flow-UIet.

### Verifisert

- 2001 tester passerer (47 nye for fix A og fix B).
- Snapshot-fixtures lagret lokalt for des 2025 til april 2026 (Nord Pool EUR + NB EUR/NOK). Kan reverifiseres offline.
- Hourly-replay-test mater fixturer time-for-time gjennom `_async_update_data()` og asserter mot fakturatall. Fanger akkumulasjons-bugs som unit-tester ikke ser.

### Dokumentert

- `docs/input-sensorer.md`: opplæring om hver input-sensor, OBIS-koder, Riemann-summering vs delta-akkumulering, anbefalt oppsett per situasjon.
- `docs/begrensninger.md` restrukturert til bruker-fokus.
- `docs/måler-hardware.md` med Kaifa MA304H3E som verifisert rigg, Aidon som referanse for andre brukere.
- `docs/research/`: 5 nye filer med audit-trail for klokke-stempling, NOK-omregning, Elhub-data, AMS-måler-spec.

### Rensket

- Slettet 433 linjer false-positive-tester (`test_faktura_hourly_snapshot.py`, `test_faktura_validering_nye_felter.py`). Erstattet med ekte ende-til-ende-tester som kjører coordinator-koden.
- Refaktorert `test_property.py`: Hypothesis tester nå ekte coordinator-metoder, ikke test-fil-helpers.

### Migrering

- Brukere uten energi-sensor: ingen endring. Integrasjonen fungerer bakoverkompatibelt.
- Anbefalt: legg til `energy_sensor` i config via Settings > Devices > Strømkalkulator > Configure. For Pow-U: `sensor.pow_u_ams_tpi`. For Tibber Pulse: `sensor.<navn>_last_meter_consumption`. Se [docs/input-sensorer.md](docs/input-sensorer.md).
- Hvis HA viser 4 reparasjonsmeldinger om `sensor.stromkostnad_per_time_*` etter oppgradering: dette gjelder dine egne template-sensorer (ikke integrasjonen). Klikk gjennom og godkjenn rydding av historiske statistikker.

## [1.12.1]

### Lagt til

- Knapp på "Forrige måned"-enheten som genererer en ferdig fakturaverifiserings-rapport som persistent_notification. Brukeren kopierer rapporten rett inn i et issue, ingen tabeller å fylle ut manuelt. Issue-mal forenklet tilsvarende.

### Fikset

- Migrering av `spotpris_inkl_mva` snudd: setter nå `False` (riktig for HA-core nordpool) for alle eksisterende konfig. Tidligere migrering satt `True` og krevde at brukeren leste repair-issue og slo AV. Det betydde at brukere som ikke leste repair-issue beholdt incident 004-buggen aktiv.
- Repair-issue trigges kun for Sør-Norge der mva-håndteringen utgjør en forskjell, og er nå informativ heller enn påkrevd handling.
- Fjernet URL fra `strings.json` (Hassfest-validering).
- Korrigerte feilaktige `sensor.stromkalkulator_X`-referanser i issue-mal og dokumentasjon. Sensorene heter `sensor.energiledd_dag` osv.
- Absolutte URL-er i issue-maler (relative virket ikke fra issue-konteksten).

## [1.12.0]

### Fikset

- **Spotpris-mva-håndtering** (incident 004): koden antok at spotpris-sensoren leverte priser inkl. mva, men HA-core nordpool-integrasjonen leverer eks. mva. Resultatet var 25 % feil i strømstøtte-trigger, totalpris og Norgespris-besparelse for Sør-Norge-brukere på spotprisavtaler. Nettleie-beregninger var ikke påvirket.
- **Eksportinntekt for plusskunder**: brukte spotpris inkl. mva. Plusskunder får betalt eks. mva av strømleverandøren, så Sør-Norge-eksport ble overrapportert med 25 %. Bruker nå spot_price_eks_mva.
- **Falsk Norgespris-besparelse ved manglende spot-data**: når spotpris-sensor var nede over 2 timer, akkumulerte koden 50 øre/kWh i fiktiv besparelse. Akkumuleringen hopper nå over når spot er ugyldig.
- **Avrundingsavvik mot ekte fakturaer**: DSO-energiledd lagres nå som rene eks-mva-priser. Inkl-mva-verdien beregnes i kode, slik at vi unngår presisjonstap fra display-avrundede summeringer. BKK-faktura: avvik fra 0,004 til 0,001 øre/kWh.

### Lagt til

- Konfigurasjons-felt `spotpris_inkl_mva` (default `False`) som lar brukere med spesielle spotpris-sensorer (egendefinerte template-sensorer, eldre custom_components/nordpool med VAT=true) overstyre normaliseringen.
- Faktura-verifisering som tillit-mekanisme (`docs/fakturaer/VERIFISER_DIN_FAKTURA.md`): brukere kan bekrefte at integrasjonen regner riktig for sitt nettselskap. Issue-mal for innsending. README har "Verifisert mot ekte fakturaer"-tabell.
- BKK april 2026-rapport.

### Endret

- DSO-struktur: `energiledd_dag` og `energiledd_natt` er erstattet med `energiledd_dag_eks_mva` og `energiledd_natt_eks_mva`. Verdiene er rene nettleiepriser, eks. forbruksavgift, Enova og MVA.
- Config-versjon bumpet til 3 med automatisk migrering:
  - `v1 → v2`: konverterer lagrede inkl-mva-overrides til eks-mva
  - `v2 → v3`: setter `spotpris_inkl_mva = True` for eksisterende konfig (preserves behavior). Repair-issue oppmuntrer til å sjekke og slå AV om man bruker HA-core nordpool.

### Vedlikehold

- Destillert dokumentasjon: AGENTS, README, CONTRIBUTING, DEVELOPMENT, TESTING, SENSORS, incidents.
- Konsolidert faktura-tester til parametrisert `test_faktura_bkk.py`, valideringer samlet ett sted, test-helpers flyttet til `tests/conftest.py`.
- Mindre kode-rydding: ubrukt `month`-parameter fjernet fra `get_forbruksavgift` og `compute_energiledd_inkl_mva`.
- Ryddet misvisende kommentarer i `dso.py`: kommentarene oppga tidligere sluttprisen (etter avgifter og mva) i stedet for ren energiledd, noe som forvirret reviewere og bidro til incidents 002, 003 og 004.
- Slettet utdaterte planer og fakta-filer.

## [0.55.0]

### Lagt til

- Støtte for flere strømmålere (flere instanser med samme nettselskap, f.eks. to Tibber-pulser i samme nettområde)
- Automatisk migrering ved fusjon av nettselskaper (Skiakernett til Vevig, Norgesnett til Glitre Nett)
- Repair issue varsler bruker etter automatisk migrering, forbruksdata bevares

### Fikset

- Lagring bruker unik nøkkel per instans (`entry_id`) i stedet for nettselskap-ID, slik at data ikke deles mellom instanser
- Eksisterende data migreres automatisk fra gammelt lagringsformat ved oppgradering

### Fjernet

- Norgesnett (fusjonert inn i Glitre Nett)

## [0.31.0] - 2026-01-30

- Sensorer for forrige måned (totalpris, strømstøtte, nettleie)
- Full type annotations
- HACS/brands forberedelser for offisiell HACS-publisering
- Norgespris aktiv-sensor for bedre statusrapportering
- Norske skjermbilder

## [0.23.0] - 2025-12-15

- `totalpris_inkl_avgifter` for total pris inkl. avgifter
- Månedlig forbrukssporing
- Anonymiserte fakturaer for testing
- Brand images og logo

## [0.22.0] - 2025-11-20

- Pytest-migrering for bedre test-dekning
- Type hints

## [0.21.0] - 2025-10-15

- CI badges, HACS-validering, code coverage
- Faktura-tester
- Mypy

## [0.20.0] - 2025-09-10

- ÆØÅ-håndtering i dokumentasjon
- Faktura-verifisering prosess

## [0.19.0] - 2025-08-20

- Strømstøtte 2026 beregninger
- Norgespris-støtte

## [0.17.0] - 2025-07-01

- TariffSensor for dag/natt-tariff
- utility_meter-integrasjon

## [0.16.0] - 2025-06-15

- Avgiftssoner (Standard, Nord-Norge, Tiltakssonen)
- 2026-satser for forbruksavgift

## [0.15.0] - 2025-05-20

- Fire nye nettselskaper: Lede, Lnett, Norgesnett, Arva

## [0.14.0] - 2025-04-10

- Barents Nett og Nordvest Nett
- GitHub Actions release workflow

## [0.13.0] - 2025-03-15

- Test-pakke med unit-tester
- Pre-commit hooks
- Ruff linting

[0.31.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.23.0...v0.31.0
[0.23.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.17.0...v0.19.0
[0.17.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/elden1337/hacs-stromkalkulator/releases/tag/v0.13.0
