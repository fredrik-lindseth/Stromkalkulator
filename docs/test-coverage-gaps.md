# Kjente testdekningshull

Dokumenterer kode som **bevisst** ikke er dekket av tester, og hvorfor. Oppdateres ved test-review.

Sist oppdatert: 2026-04-02

## Krever Home Assistant testinfrastruktur

Disse kan ikke testes uten `pytest-homeassistant-custom-component` eller tilsvarende HA-testramme. Vi mocker HA-moduler i `conftest.py`, men det gir ikke tilgang til HA sine flyt-mekanismer.

### Config flow runtime (`config_flow.py`)

- **`NettleieConfigFlow`** (`async_step_user`, `async_step_sensors`, `async_step_pricing`, `_create_entry`):
  Kræver HA sin `config_entries.ConfigFlow`-infrastruktur for å kjore steg-for-steg flyten.
  Vi tester statisk (NumberSelector step-verdier, translation-nokler, energiledd-presisjon) men ikke selve flyten.

- **`NettleieOptionsFlow.async_step_init`**:
  Kræver `config_entries.OptionsFlow` + `hass.config_entries.async_entries()` for unikhetsvalidering.
  Effektsensor-unikhet ble lagt til i `a197f14` men kan kun verifiseres i HA-miljo.

### Sensor-oppsett (`sensor.py`)

- **`sensor.async_setup_entry`** (linje 47-108):
  Registrerer 38 sensor-entiteter. Kræver `AddEntitiesCallback` fra HA.
  Vi tester alle individuelle sensorer via mocks, men ikke selve registreringsflyten.

### Repair flow (`__init__.py`)

- **`DsoMigrationRepairFlow.async_step_confirm`** og **`async_create_fix_flow`**:
  Kræver `data_entry_flow.FlowHandler` fra HA. Lav risiko — veldig enkel kode (2 linjer logikk).

## Kjente begrensninger

| Begrensning | Dokumentert i test |
|---|---|
| Bevegelige helligdager er kun forhåndskompilert for 2025-2030 | `test_edge_cases.py::TestHolidaysBeyond2030` — dokumenterer at 2031+ ikke fanges |
| Config flow regex-tester er fragile ved refaktorering | `test_config_flow.py` docstring |

## Mulig fremtidig forbedring

Hvis vi legger til `pytest-homeassistant-custom-component` som dev-dependency, kan vi:

1. Teste config flow steg-for-steg med ekte HA-kontekst
2. Teste options flow med unikhetsvalidering mot flere config entries
3. Teste at sensor.async_setup_entry registrerer riktig antall entiteter
4. Teste DsoMigrationRepairFlow

Prioritet: Lav. Statiske tester + coordinator-tester dekker all beregningslogikk. Config flow bugs viser seg typisk som krasj ved oppsett, som brukere rapporterer umiddelbart.

## Konsolideringslogg (2026-04-02)

Følgende endringer ble gjort under test-review:

### Slettet (redundant)
- `test_forrige_maaned.py` — 95% redundant med test_monthly_sensors.py, test_kapasitetstrinn.py
- `test_quality_r3.py` — 50%+ duplisert med test_coverage_gaps.py, unike tester flyttet dit
- `test_stromstotte.py` — slått sammen med test_stromstotte_tak.py

### Fjernet fra filer
- Tautologier i test_property.py (test_tariff_always_boolean, test_norgespris_independent_of_spot, etc.)
- Øre-til-NOK-konverteringstester i test_avgifter.py
- Dataclass-strukturtester i test_dso_migration.py
- Passthrough native_value-tester i test_sensor_classes.py
- Redundante beregningsduplikater i test_offentlige_avgifter_sensor.py
- `_expected_total()` helper i test_monthly_sensors.py (dupliserte sensorlogikk)

### Lagt til
- `test_edge_cases.py` — DST, helligdager 2031+, strømstøtte-grensepresisjon
- Konstantvalidering (threshold, rate, cap) i test_stromstotte_tak.py
