# Kjente testdekningshull

Dokumenterer kode som **bevisst** ikke er dekket av tester, og hvorfor. Oppdateres ved test-review.

Sist oppdatert: 2026-04-01

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

## Mulig fremtidig forbedring

Hvis vi legger til `pytest-homeassistant-custom-component` som dev-dependency, kan vi:

1. Teste config flow steg-for-steg med ekte HA-kontekst
2. Teste options flow med unikhetsvalidering mot flere config entries
3. Teste at sensor.async_setup_entry registrerer riktig antall entiteter
4. Teste DsoMigrationRepairFlow

Prioritet: Lav. Statiske tester + coordinator-tester dekker all beregningslogikk. Config flow bugs viser seg typisk som krasj ved oppsett, som brukere rapporterer umiddelbart.
