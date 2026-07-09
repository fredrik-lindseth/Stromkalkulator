# Testing

## Unit-tester

```bash
pipx run --with hypothesis pytest tests/ -v
```

Eller i venv: `python -m pytest tests/ -v`.

### Hva som dekkes

Testsuiten (`ls tests/test_*.py` for aktuell liste) er organisert i nivåer i stedet for en fil-per-fil-tabell — filnavn endres oftere enn testnivåene gjør:

- **Golden faktura**: beregninger verifisert mot ekte fakturafelt og publiserte tall. `test_faktura_bkk.py` (BKK 2025 og 2026), `test_research_reproducibility.py` (research-rapportene skal reproduseres eksakt ved regenerering).
- **Hourly replay**: en hel måneds fixtur-data mates time for time gjennom `NettleieCoordinator`, og de akkumulerte sluttverdiene sjekkes mot fasit. `test_coordinator_replay.py`.
- **Property-baserte tester**: Hypothesis genererer tilfeldige input og sjekker invarianter som ikke-negativitet og monotonisitet. `test_property.py`.
- **Kontrakt**: kjører en reell coordinator-oppdatering og fôrer resultatet inn i sensorklassene, for å fange typemismatch mellom coordinator og sensor før det når produksjon. `test_coordinator_sensor_contract.py`.
- **Migrering**: config entry-migrering (v1→v2→v3), lagringsnøkkel-isolasjon mellom entries (se [incident 001](incidents/001-delt-data-mellom-instanser.md)), og lagring/gjenoppretting av persistert data. `test_config_migration.py`, `test_storage_key.py`, `test_persistens.py`.
- **DST og kalender**: sommertid-overgang, helligdager langt fram i tid, sesongstyrte energiledd-perioder. `test_dst_overgang.py`, `test_edge_cases.py`, `test_energiledd_perioder.py`.
- **Unit**: resten — beregningslogikk per komponent (energiledd, kapasitetstrinn, strømstøtte inkl. tak, Norgespris-kompensasjon inkl. tak, spotpris/mva, solcelle-eksport, energisensor-delta), DSO-datavalidering og 2026-tariffer, entity-oppsett (config flow, options flow, setup/unload, diagnostics, button, sensorklasser, månedlige og passthrough-sensorer) og robusthet/coverage-gap-regresjoner.

Nye tester legges i nivået de hører til. Denne listen skal ikke oppdateres for hver ny eller slettet testfil.

### Begrensninger

Kjører uten Home Assistant installert (HA mockes i `conftest.py`). `pytest-homeassistant-custom-component` er ikke en avhengighet i dette prosjektet — options flow med reload, end-to-end setup/unload og repair-issue-flows er allerede dekket via mock-basert HA (`test_config_flow_options.py`, `test_init_setup.py`, `test_config_migration.py`). Unntaket er ekte multi-step config-flow-kjøring: `test_config_flow.py` bruker regex mot kildekoden (bevisst skjørt, se filens docstring) fordi vi ikke kjører en reell `ConfigFlow`-instans.

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

| Avgift         | Forventet                           |
| -------------- | ----------------------------------- |
| Forbruksavgift | 0.0891 kr/kWh (7,13 øre × 1.25 mva) |
| Enova-avgift   | 0.0125 kr/kWh (1,0 øre × 1.25 mva)  |

## Feilsøking

Sensor viser FEIL: sjekk attributtene for differansen, sjekk logger, verifiser kilde-sensorer (Nord Pool, strømmåler).

Sensor viser unavailable: verifiser at integrasjonen er lastet (`ssh ha-local "ha core logs" | grep -i "Setting up stromkalkulator"`), sjekk at kilde-sensorer finnes.

Kapasitetstrinn er feil: "Snitt toppforbruk" viser snittet av topp-3. Data lagres per måned, nullstilles ved månedsskifte. Ny installasjon trenger tid på å bygge data.
