# AGENTS.md — Strømkalkulator

Home Assistant-integrasjon for beregning av nettleie, strømstøtte og Norgespris-sammenligning.

## Hovedfiler

- `custom_components/stromkalkulator/` - Integrasjonskode
- `tso.py` - Nettselskap-data
- `const.py` - Avgifter, satser, helligdager
- `coordinator.py` - Beregningslogikk
- `sensor.py` - Sensor-definisjoner

## Kvalitetskontroll

```bash
pipx run pytest tests/ -v
ruff check custom_components/stromkalkulator/ tests/
```

## Dokumentasjon

- [docs/domain-rules.md](docs/domain-rules.md) — Domene-regler, avgifter, sjekklister og kilder
- [docs/beregninger.md](docs/beregninger.md) — Alle formler og sensorer
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — Utvikling og arkitektur
- [docs/TESTING.md](docs/TESTING.md) — Test-guide
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — Oppdatere priser / rapportere feil
