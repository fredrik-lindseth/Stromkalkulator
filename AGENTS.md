# AGENTS.md — Strømkalkulator

Home Assistant-integrasjon for beregning av nettleie, strømstøtte og Norgespris-sammenligning.

## Hovedfiler

- `custom_components/stromkalkulator/` - Integrasjonskode
- `dso.py` - Nettselskap-data (DSO)
- `const.py` - Avgifter, satser, helligdager
- `coordinator.py` - Beregningslogikk
- `sensor.py` - Sensor-definisjoner

## Kvalitetskontroll

Kjør før commit (også automatisert via pre-commit hooks):

```bash
pipx run pytest tests/ -v
ruff check custom_components/stromkalkulator/ tests/
```

## Viktige regler

- **Lagring**: Bruk alltid `entry.entry_id` som lagringsnøkkel, aldri DSO-id eller brukervalgt konfigurasjon. Se [incident 001](docs/incidents/001-delt-data-mellom-instanser.md).
- **Satser**: Endringer i `const.py` (avgifter, terskel) eller `dso.py` (energiledd, kapasitetstrinn) krever offisiell kilde og bestått testsuite.
- **Månedsskifte**: Ikke nullstill `_daily_max_power`, `_monthly_consumption` eller `_previous_month_*` manuelt — dette skjer automatisk ved månedsskifte.

## Dokumentasjon

- [docs/domain-rules.md](docs/domain-rules.md) — Domene-regler, avgifter, sjekklister og kilder
- [docs/beregninger.md](docs/beregninger.md) — Alle formler og sensorer
- [docs/SENSORS.md](docs/SENSORS.md) — Alle sensorer og attributter
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — Utvikling og arkitektur
- [docs/TESTING.md](docs/TESTING.md) — Test-guide
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — Oppdatere priser / rapportere feil
