# Testing

## Unit-tester

```bash
pipx run pytest tests/ -v
```

Eller i venv: `python -m pytest tests/ -v`.

### Hva som dekkes

| Område                              | Testfil                                                      |
| ----------------------------------- | ------------------------------------------------------------ |
| Strømstøtte (formel, tak)           | `test_stromstotte_tak.py`                                    |
| Dag/natt-tariff og helligdager      | `test_energiledd.py`                                         |
| Kapasitetstrinn, topp-3, varsel     | `test_kapasitetstrinn.py`                                    |
| Norgespris og akkumulert besparelse | `test_norgespris.py`, `test_norgespris_akkumulert.py`        |
| Faktura-verifisering 2026           | `test_faktura_februar_2026.py`, `test_faktura_mars_2026.py`  |
| Validering av nye fakturafelter     | `test_faktura_validering_nye_felter.py`                      |
| Månedsskifte                        | `test_month_transition_integration.py`                       |
| DSO-migrering ved fusjoner          | `test_dso_migration.py`                                      |
| DSO-data validering                 | `test_dso_data_validation.py`                                |
| Property-baserte tester             | `test_property.py`                                           |
| Lagringsnøkkel-isolasjon            | `test_storage_key.py`                                        |
| Config flow struktur                | `test_config_flow.py`                                        |
| Setup/unload                        | `test_init_setup.py`                                         |
| Diagnostics                         | `test_diagnostics.py`                                        |
| Sensor None-håndtering, units       | `test_sensor_classes.py`                                     |
| Lagring (save/load, korrupsjon)     | `test_persistens.py`                                         |
| Coordinator end-to-end              | `test_coordinator_update.py`                                 |
| Robustness (cache, clamping)        | `test_coordinator_robustness.py`                             |
| Månedlige sensorer, estimat         | `test_monthly_sensors.py`                                    |
| Passthrough-sensorer                | `test_passthrough_sensors.py`                                |
| Bugfiks-dekning                     | `test_coverage_gaps.py`                                      |
| Strømpris per kWh                   | `test_strompris_per_kwh.py`                                  |
| DST, helligdager 2031+              | `test_edge_cases.py`                                         |
| Solcelle-eksport                    | `test_eksport.py`                                            |
| Akkumulert kostnad                  | `test_akkumulert_kostnad.py`                                 |
| Boligtype-avhengige tak             | `test_boligtype.py`                                          |

### Begrensninger

Kjører uten Home Assistant installert (HA mockes i `conftest.py`). Krever `pytest-homeassistant-custom-component` for: config flow multi-step, options flow med reload, end-to-end setup, repair flow. Lav prioritet, statiske tester + coordinator-tester dekker beregningslogikken.

## Live-tester i Home Assistant

`packages/stromkalkulator_test.yaml` gir test-sensorer som kjører i HA.

```bash
ssh ha-local "cat > /config/packages/stromkalkulator_test.yaml" < packages/stromkalkulator_test.yaml
ssh ha-local "ha core restart"
```

Pass på at packages er aktivert i `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

I Developer Tools > States, filtrer på `test_`. `sensor.test_alle_tester_ok` viser samlet status. Resultater: `OK`, `FEIL` eller `MANGLER DATA`. Ved FEIL, sjekk attributtene `forventet`, `faktisk`, `differanse`.

| Sensor                                 | Sjekker                      |
| -------------------------------------- | ---------------------------- |
| `sensor.test_stromstotte_beregning`    | strømstøtte-formelen         |
| `sensor.test_spotpris_etter_stotte`    | spotpris - strømstøtte       |
| `sensor.test_tariff_korrekt`           | dag/natt/helg-tariff         |
| `sensor.test_energiledd_korrekt`       | energiledd-valg              |
| `sensor.test_total_pris_etter_stotte`  | totalpris                    |
| `sensor.test_forbruksavgift`           | forbruksavgift (7,13 øre)    |
| `sensor.test_enova_avgift`             | Enova-avgift (1,0 øre)       |
| `sensor.test_norgespris_sammenligning` | prisforskjell mot Norgespris |
| `sensor.test_kapasitetstrinn`          | kapasitetstrinn              |
| `sensor.test_alle_tester_ok`           | samlet status (X/8 OK)       |

## Manuell sjekk

Strømstøtte (2026): `max(0, (spotpris - 0.9625) * 0.90)`.

| Spotpris | Strømstøtte |
| -------- | ----------- |
| 0.50 kr  | 0.00 kr     |
| 0.96 kr  | 0.00 kr     |
| 1.00 kr  | 0.03 kr     |
| 1.50 kr  | 0.48 kr     |
| 2.00 kr  | 0.93 kr     |

Tariff:

| Tidspunkt           | Tariff |
| ------------------- | ------ |
| Man-fre 06:00-22:00 | dag    |
| Man-fre 22:00-06:00 | natt   |
| Lør-søn alle timer  | natt   |
| Helligdager         | natt   |

Kapasitetstrinn (BKK):

| Snitt topp-3 | Trinn | Pris       |
| ------------ | ----- | ---------- |
| 0-2 kW       | 1     | 155 kr/mnd |
| 2-5 kW       | 2     | 250 kr/mnd |
| 5-10 kW      | 3     | 415 kr/mnd |
| 10-15 kW     | 4     | 600 kr/mnd |

Avgifter (2026):

| Avgift         | Forventet                            |
| -------------- | ------------------------------------ |
| Forbruksavgift | 0.0891 kr/kWh (7,13 øre × 1.25 mva)  |
| Enova-avgift   | 0.0125 kr/kWh (1,0 øre × 1.25 mva)   |

## Feilsøking

Sensor viser FEIL: sjekk attributtene for differansen, sjekk logger, verifiser kilde-sensorer (Nord Pool, strømmåler).

Sensor viser unavailable: verifiser at integrasjonen er lastet (`ssh ha-local "ha core logs" | grep -i "Setting up stromkalkulator"`), sjekk at kilde-sensorer finnes.

Kapasitetstrinn er feil: "Snitt toppforbruk" viser snittet av topp-3. Data lagres per måned, nullstilles ved månedsskifte. Ny installasjon trenger tid på å bygge data.
