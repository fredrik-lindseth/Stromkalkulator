# Testing av Strømkalkulator

Denne guiden beskriver hvordan du verifiserer at integrasjonen fungerer korrekt.

## Unit-tester (lokalt)

Kjør alle tester med pytest:

```bash
# Med pipx (anbefalt hvis du ikke har venv)
pipx run pytest tests/ -v

# Med pip i venv
python -m pytest tests/ -v
```

### Hva som testes

| Testfil                              | Beskrivelse                                  |
|--------------------------------------|----------------------------------------------|
| `test_stromstotte.py`               | Strømstøtte-beregning (90% over 96,25 øre)   |
| `test_avgifter.py`                  | Forbruksavgift, Enova-avgift og MVA per sone |
| `test_energiledd.py`                | Dag/natt-tariff inkl. helligdager            |
| `test_kapasitetstrinn.py`           | Kapasitetstrinn og topp-3-beregning          |
| `test_norgespris.py`                | Norgespris-beregning og sammenligning        |
| `test_faktura_validering.py`        | Faktura-verifisering mot beregninger         |
| `test_forrige_maaned.py`            | Forrige måned sensorer og månedsskifte       |
| `test_month_transition_integration.py` | Integrasjonstest for månedsskifte         |
| `test_tso_migration.py`             | DSO-migrering ved nettselskap-fusjoner       |
| `test_property.py`                  | Property-baserte tester (Hypothesis)         |
| `test_storage_key.py`               | Lagringsnøkkel-isolasjon mellom instanser    |
| `test_config_flow.py`               | Config flow struktur-validering              |
| `test_init_setup.py`                | Setup/unload/DSO-migrering                   |
| `test_diagnostics.py`               | Diagnostics-output struktur                  |
| `test_sensor_classes.py`            | Sensor native_value, attributter, unique_id  |
| `test_persistens.py`                | Lagring: save/load-syklus, migrering         |
| `test_coordinator_update.py`        | End-to-end coordinator update                |
| `test_coordinator_robustness.py`    | Spotpris-caching, clamping, validering       |
| `test_monthly_sensors.py`           | Månedlige sensorer (nettleie, avgifter)      |
| `test_offentlige_avgifter_sensor.py`| OffentligeAvgifterSensor                     |
| `test_passthrough_sensors.py`       | Passthrough-sensorer (dag/natt, avgifter)    |
| `test_quality_r3.py`               | R3: UpdateFailed, 500kW clamp, OSError m.m.  |
| `test_strompris_per_kwh.py`        | Strømpris per kWh uten kapasitetsledd        |
| `test_stromstotte_tak.py`          | 5000 kWh månedlig tak                        |
| `test_norgespris_akkumulert.py`    | Akkumulert Norgespris-besparelse             |
| `test_margin_neste_trinn.py`       | Margin til neste kapasitetstrinn             |
| `test_faktura_februar_2026.py`     | BKK-faktura feb 2026 (Norgespris)           |
| `test_tso_data_validation.py`      | Validering av alle TSO-oppføringer           |

### Kjente begrensninger

Testsuiten kjører uten Home Assistant installert (alle HA-moduler er mocket).
Dette betyr at noen ting ikke kan testes med dagens infrastruktur:

| Område | Begrunnelse |
|--------|------------|
| Config flow multi-step (user → sensors → pricing) | Trenger HA FlowHandler-infrastruktur |
| Options flow → reload → reberegning | Trenger HA config entry lifecycle |
| End-to-end setup → coordinator → sensor | Trenger HA platform setup |
| `CoordinatorSimulator` bruker int-måned (vs YYYY-MM) | Supplementær — ekte coordinator testes i `test_coordinator_update.py` |
| `test_forrige_maaned.py` tester Python-operasjoner, ikke produksjonskode | Tech debt — skader ikke, hjelper ikke |
| Regex-parsing av kildekode i `test_config_flow.py` | Fragilt men funksjonelt, lav regresjonsrisiko |
| Testdata bruker kun BKK kapasitetstrinn | Diminishing returns — property-tester dekker alle DSOer |

Vurdert 2026-04-01 via `/test-my-tests` (10 parallelle reviewers, 131 funn → 28 action points → 14 fikset).

## Live-tester i Home Assistant

Test-pakken gir sanntids-validering direkte i HA.

### Oppsett

1. **Kopier test-pakken til HA:**
   ```bash
   ssh ha-local "cat > /config/packages/stromkalkulator_test.yaml" < packages/stromkalkulator_test.yaml
   ```

2. **Sørg for at packages er aktivert** i `/config/configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. **Restart Home Assistant:**
   ```bash
   ssh ha-local "ha core restart"
   ```

4. **Sjekk testene** i Developer Tools → States:
   - Filtrer på `test_` for å se alle test-sensorer
   - `sensor.test_alle_tester_ok` viser samlet status

### Test-sensorer

| Sensor                                 | Beskrivelse                            |
|----------------------------------------|----------------------------------------|
| `sensor.test_stromstotte_beregning`    | Validerer strømstøtte-formelen         |
| `sensor.test_spotpris_etter_stotte`    | Validerer spotpris - strømstøtte       |
| `sensor.test_tariff_korrekt`           | Validerer dag/natt/helg-tariff         |
| `sensor.test_energiledd_korrekt`       | Validerer energiledd-valg              |
| `sensor.test_total_pris_etter_stotte`  | Validerer totalpris                    |
| `sensor.test_forbruksavgift`           | Validerer forbruksavgift (7,13 øre)    |
| `sensor.test_enova_avgift`             | Validerer Enova-avgift (1,0 øre)       |
| `sensor.test_norgespris_sammenligning` | Validerer prisforskjell mot Norgespris |
| `sensor.test_kapasitetstrinn`          | Validerer kapasitetstrinn              |
| `sensor.test_alle_tester_ok`           | Samlet status (X/8 OK)                 |

### Tolkning av resultater

- **OK** - Beregningen er korrekt
- **FEIL** - Beregningen avviker fra forventet
- **MANGLER DATA** - Sensor mangler (kapasitetstrinn)

Ved FEIL, sjekk attributtene på sensoren:
- `forventet` - Hva testen forventer
- `faktisk` - Hva sensoren rapporterer
- `differanse` - Avvik mellom forventet og faktisk

## Manuell validering

### 1. Strømstøtte

**Formel (2026):** `max(0, (spotpris - 0.9625) × 0.90)`

| Spotpris | Strømstøtte | Sjekk                      |
|----------|-------------|----------------------------|
| 0.50 kr  | 0.00 kr     | Under terskel              |
| 0.96 kr  | 0.00 kr     | Under terskel              |
| 1.00 kr  | 0.03 kr     | (1.00-0.9625)×0.9 = 0.0338 |
| 1.50 kr  | 0.48 kr     | (1.50-0.9625)×0.9 = 0.4838 |
| 2.00 kr  | 0.93 kr     | (2.00-0.9625)×0.9 = 0.9338 |

### 2. Tariff (dag/natt)

| Tidspunkt           | Forventet tariff |
|---------------------|------------------|
| Man-Fre 06:00-22:00 | dag              |
| Man-Fre 22:00-06:00 | natt             |
| Lør-Søn hele døgnet | natt             |
| Helligdager         | natt             |

### 3. Energiledd

Sjekk at:
- `sensor.energiledd` = `sensor.energiledd_dag` når tariff er "dag"
- `sensor.energiledd` = `sensor.energiledd_natt` når tariff er "natt"

### 4. Kapasitetstrinn (BKK)

| Gjennomsnitt topp-3 | Forventet trinn | Pris       |
|---------------------|-----------------|------------|
| 0-2 kW              | 1               | 155 kr/mnd |
| 2-5 kW              | 2               | 250 kr/mnd |
| 5-10 kW             | 3               | 415 kr/mnd |
| 10-15 kW            | 4               | 600 kr/mnd |

### 5. Norgespris-sammenligning

**Formel:** 
```
prisforskjell = total_pris_etter_stotte - total_pris_norgespris
```

- **Positiv verdi** → Du betaler mer enn Norgespris
- **Negativ verdi** → Du betaler mindre enn Norgespris

### 6. Offentlige avgifter (2026)

| Avgift         | Forventet                           |
|----------------|-------------------------------------|
| Forbruksavgift | 0.0891 kr/kWh (7,13 øre × 1.25 mva) |
| Enova-avgift   | 0.0125 kr/kWh (1,0 øre × 1.25 mva)  |

## Feilsøking

### Test viser FEIL

1. **Sjekk attributter** på test-sensoren for å se differansen
2. **Sjekk logger:**
   ```bash
   ssh ha-local "ha core logs" | grep -i stromkalkulator
   ```
3. **Verifiser kilde-sensorer** (Nord Pool, strømmåler)

### Sensorer viser "unavailable"

1. **Sjekk at integrasjonen er lastet:**
   ```bash
   ssh ha-local "ha core logs" | grep -i "Setting up stromkalkulator"
   ```
2. **Sjekk at kilde-sensorer finnes** (strømmåler, spotpris)

### Kapasitetstrinn er feil

- Sjekk "Snitt toppforbruk"-sensoren - viser gjennomsnittet av topp 3
- Data lagres per måned og nullstilles ved månedsskift
- Ved ny installasjon tar det tid å bygge opp data
