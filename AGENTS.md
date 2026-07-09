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
pipx run --with hypothesis pytest tests/ --ignore=tests/test_smoke_ha.py -v
ruff check custom_components/stromkalkulator/ tests/
```

`--with hypothesis` trengs fordi `tests/test_property.py` bruker den; uten
flagget feiler `pipx run pytest` allerede på collection. `--ignore` trengs fordi
`test_smoke_ha.py` krever `pytest-homeassistant-custom-component` og kjører i en
egen CI-jobb med `--noconftest`. Kjøres også via pre-commit hooks.

## Viktige regler

- **Lagring**: bruk `entry.entry_id` som lagringsnøkkel, aldri DSO-id eller brukervalgt konfigurasjon. Se [incident 001](docs/incidents/001-delt-data-mellom-instanser.md).
- **Sensor-enheter**: `MONETARY` krever ISO 4217 (`NOK`), satser skal ikke ha `device_class` og beholder `NOK/kWh` eller `kr/mnd`. Å bytte enhet på en sensor med `state_class` gir én repair hos hver bruker, så gjør det bare når gevinsten er reell. Se [domain-rules.md](docs/domain-rules.md#sensor-enheter-og-device_class).
- **Satser**: endringer i `const.py` (avgifter, terskel) eller `dso.py` (energiledd, kapasitetstrinn) krever offisiell kilde og bestått testsuite. Kjør `uv run --with pyyaml python scripts/sjekk_mot_fri_nettleie.py --bare-avvik` for å fange pris-drift mot fri-nettleie før du endrer eller committer satser.
- **DSO-helligdager**: `helligdager_ekstra` i `dso.py` (f.eks. `["12-24", "12-31"]` for BKK) skal kun legges til når en ekte faktura fra DSO-en bekrefter at hele dagen behandles som natt-tariff. Default er kun offisielle norske helligdager.
- **Månedsskifte**: ikke nullstill `_daily_max_power`, `_monthly_consumption` eller `_previous_month_*` manuelt. Skjer automatisk.
- **Kursarkiv (kjør månedlig)**: `just snapshot-kurs` arkiverer Nord Pools daglige `exchangeRate` og de publiserte NOK-kvarterprisene i `_private/Måleverdier/`. Gratis-API-et rekker bare ~2 måneder bakover, så kjør den hver gang du er i repoet (minst månedlig) før fakturamånedene faller ut. Kvarterprisene er fasiten BKK fakturerer fra; med dem reproduseres Norgespris-linjen eksakt (verifisert juni 2026). HA-recorderen lagrer prisene slik de så ut ved publisering og kan ha foreløpig valutakurs på søndager, så den duger ikke som fasit. Bakgrunn: [docs/research/norgespris-eksakt-match.md](docs/research/norgespris-eksakt-match.md).

## Dokumentasjon

- [docs/domain-rules.md](docs/domain-rules.md): domene-regler, avgifter, sjekklister, kilder
- [docs/beregninger.md](docs/beregninger.md): formler og sensorer
- [docs/sensorer.md](docs/sensorer.md): sensorer og attributter
- [docs/input-sensorer.md](docs/input-sensorer.md): hva integrasjonen trenger som input (effekt, energi, spotpris)
- [docs/development.md](docs/development.md): arkitektur
- [docs/testing.md](docs/testing.md): test-guide
- [docs/contributing.md](docs/contributing.md): oppdatere priser, rapportere feil
