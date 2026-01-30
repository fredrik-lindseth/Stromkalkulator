# Changelog

Alle viktige endringer i dette prosjektet dokumenteres i denne filen.

Formatet er basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
og prosjektet følger [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.31.0] - 2026-01-30

### Lagt til
- Sensorer for forrige måned (forrige måned totalpris, strømstøtte, nettleie, etc.)
- Full type annotations for bedre kodekvalitet
- HACS/brands forberedelser for offisiell HACS-publisering

### Endret
- Forbedret dokumentasjon med norske skjermbilder
- Bedre sensornavn for diagnostikk-sensorer
- Bedre sensornavn for strømstøtte-status

### Fikset
- Ny Norgespris aktiv-sensor for bedre statusrapportering

## [0.23.0] - 2025-12-15

### Lagt til
- `totalpris_inkl_avgifter` sensor for total pris inkludert avgifter
- Månedlig forbrukssporing for bedre analyse av strømforbruk

### Endret
- Forbedret dokumentasjon med anonymiserte fakturaer
- Lagt til brand images og logo i README
- HACS publiserings-guide

### Dokumentasjon
- Lagt til anonymiserte fakturaer for testing
- Lagt til fakturabehandlings-skript

## [0.22.0] - 2025-11-20

### Lagt til
- Pytest-migrering for bedre test-dekning
- Type hints for alle funksjoner

### Endret
- Forbedret kodekvalitet med type annotations

## [0.21.0] - 2025-10-15

### Lagt til
- CI badges for status-visning
- HACS validering
- Code coverage rapportering
- Faktura-tester for validering av beregninger
- Mypy type-checking

### Endret
- Økt kodekvalitet generelt

## [0.20.0] - 2025-09-10

### Fikset
- ÆØÅ-tegn håndtering i dokumentasjon

### Endret
- Oppdatert dokumentasjon med nye skjermbilder

### Dokumentasjon
- Faktura-verifisering prosess
- Beads-arbeidsflyt guide

## [0.19.0] - 2025-08-20

### Lagt til
- Strømstøtte 2026 beregninger
- Norgespris-støtte for sammenligning av strømpriser

### Endret
- Oppdatert strømstøtte-terskel til 2025-sats (93,75 øre)

## [0.17.0] - 2025-07-01

### Lagt til
- TariffSensor for dag/natt-tariff-støtte
- Utility_meter integrasjon

## [0.16.0] - 2025-06-15

### Lagt til
- Avgiftssoner (Standard, Nord-Norge, Tiltakssonen)
- 2026-satser for forbruksavgift

## [0.15.0] - 2025-05-20

### Lagt til
- 4 nye nettselskaper: Lede, Lnett, Norgesnett og Arva

## [0.14.0] - 2025-04-10

### Lagt til
- Barents Nett og Nordvest Nett

### Endret
- GitHub Actions release workflow

## [0.13.0] - 2025-03-15

### Lagt til
- Test-pakke med unit-tester
- Pre-commit hooks for kodekvalitet

### Endret
- Ruff linting integrering
- Flytt til pre-commit framework

[Unreleased]: https://github.com/elden1337/hacs-stromkalkulator/compare/v0.31.0...HEAD
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
