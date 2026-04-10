# Kjente testdekningshull

Dokumenterer kode som **bevisst** ikke er dekket av tester, og hvorfor. Oppdateres ved test-review.

Sist oppdatert: 2026-04-10

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
- `test_forrige_maaned.py` -- 95% redundant med test_monthly_sensors.py, test_kapasitetstrinn.py
- `test_quality_r3.py` -- 50%+ duplisert med test_coverage_gaps.py, unike tester flyttet dit
- `test_stromstotte.py` -- slatt sammen med test_stromstotte_tak.py

### Fjernet fra filer
- Tautologier i test_property.py (test_tariff_always_boolean, test_norgespris_independent_of_spot, etc.)
- Ore-til-NOK-konverteringstester i test_avgifter.py
- Dataclass-strukturtester i test_dso_migration.py
- Passthrough native_value-tester i test_sensor_classes.py
- Redundante beregningsduplikater i test_offentlige_avgifter_sensor.py
- `_expected_total()` helper i test_monthly_sensors.py (dupliserte sensorlogikk)

### Lagt til
- `test_edge_cases.py` -- DST, helligdager 2031+, stromstotte-grensepresisjon
- Konstantvalidering (threshold, rate, cap) i test_stromstotte_tak.py

## Konsolideringslogg (2026-04-10)

### Slettet (redundant)
- `test_avgifter.py` -- testet lokale reimplementeringer, ikke produksjonskoden. Dekket av test_passthrough_sensors.py og test_property.py
- `test_offentlige_avgifter_sensor.py` -- redundant med test_passthrough_sensors.py og test_avgifter.py
- `test_faktura_validering.py` -- 2025-satser, erstattet av test_faktura_februar_2026.py/mars_2026.py
- `test_margin_neste_trinn.py` -- konsolidert inn i test_kapasitetstrinn.py

### Fjernet fra filer
- test_property.py: 8 exhaustive tier-2 tester (redundant med test_dso_data_validation.py og test_passthrough_sensors.py)
- test_config_flow.py: TestCoordinatorFloatProtection (fragil regex-sjekk, dekket av coordinator_robustness)
- test_edge_cases.py: TestStromstotteThresholdPrecision (flyttet til test_stromstotte_tak.py)

### Lagt til
- test_eksport.py: eksport-sensor feilhandtering (ValueError, inf, >500kW clamp)
- test_persistens.py: _validate_daily_max_power edge cases, korrupt storage
- test_coordinator_update.py: kapasitetsvarsel for hoyeste trinn
- test_stromstotte_tak.py: floating-point grensepresisjon
