# AGENTS.md

Home Assistant-integrasjon for nettleie, strømstøtte og Norgespris-sammenligning i Norge.

## Hovedfiler

- `custom_components/stromkalkulator/`: integrasjonskode
- `dso.py`: nettselskap-data
- `const.py`: avgifter, satser, helligdager
- `coordinator.py`: beregningslogikk
- `sensor.py`: sensor-definisjoner
- `config_flow.py`: oppsett og options-flow, sensor-validering

## Før commit

```bash
pipx run pytest tests/ -v
ruff check custom_components/stromkalkulator/ tests/
```

Kjøres også via pre-commit hooks.

## Viktige regler

- **Lagring**: bruk `entry.entry_id` som lagringsnøkkel, aldri DSO-id eller brukervalgt konfigurasjon. Se [incident 001](docs/incidents/001-delt-data-mellom-instanser.md).
- **Satser**: endringer i `const.py` (avgifter, terskel) eller `dso.py` (energiledd, kapasitetstrinn) krever offisiell kilde og bestått testsuite.
- **DSO-helligdager**: `helligdager_ekstra` i `dso.py` (f.eks. `["12-24", "12-31"]` for BKK) skal kun legges til når en ekte faktura fra DSO-en bekrefter at hele dagen behandles som natt-tariff. Default er kun offisielle norske helligdager.
- **Månedsskifte**: ikke nullstill `_daily_max_power`, `_monthly_consumption` eller `_previous_month_*` manuelt. Skjer automatisk.

## Dokumentasjon

- [docs/domain-rules.md](docs/domain-rules.md): domene-regler, avgifter, sjekklister, kilder
- [docs/beregninger.md](docs/beregninger.md): formler og sensorer
- [docs/sensorer.md](docs/sensorer.md): sensorer og attributter
- [docs/input-sensorer.md](docs/input-sensorer.md): hva integrasjonen trenger som input (effekt, energi, spotpris)
- [docs/development.md](docs/development.md): arkitektur
- [docs/testing.md](docs/testing.md): test-guide
- [docs/contributing.md](docs/contributing.md): oppdatere priser, rapportere feil
