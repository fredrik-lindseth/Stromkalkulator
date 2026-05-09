# Changelog

Format basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
