# AGENTS.md

Home Assistant-integrasjon for nettleie, strømstøtte og Norgespris-sammenligning i Norge.

## Hovedfiler

- `custom_components/stromkalkulator/`: integrasjonskode
- `dso.py`: nettselskap-data
- `const.py`: avgifter, satser, helligdager
- `coordinator.py`: beregningslogikk
- `sensor.py`: sensor-definisjoner

## Før commit

```bash
pipx run pytest tests/ -v
ruff check custom_components/stromkalkulator/ tests/
```

Kjøres også via pre-commit hooks.

## Viktige regler

- **Lagring**: bruk `entry.entry_id` som lagringsnøkkel, aldri DSO-id eller brukervalgt konfigurasjon. Se [incident 001](docs/incidents/001-delt-data-mellom-instanser.md).
- **Satser**: endringer i `const.py` (avgifter, terskel) eller `dso.py` (energiledd, kapasitetstrinn) krever offisiell kilde og bestått testsuite.
- **Månedsskifte**: ikke nullstill `_daily_max_power`, `_monthly_consumption` eller `_previous_month_*` manuelt. Skjer automatisk.

## Dokumentasjon

- [docs/domain-rules.md](docs/domain-rules.md): domene-regler, avgifter, sjekklister, kilder
- [docs/beregninger.md](docs/beregninger.md): formler og sensorer
- [docs/SENSORS.md](docs/SENSORS.md): sensorer og attributter
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): arkitektur
- [docs/TESTING.md](docs/TESTING.md): test-guide
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md): oppdatere priser, rapportere feil
