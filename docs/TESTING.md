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

| Testfil                   | Beskrivelse                                  |
|---------------------------|----------------------------------------------|
| `test_stromstotte.py`     | Strømstøtte-beregning (90% over 96,25 øre)   |
| `test_avgifter.py`        | Forbruksavgift, Enova-avgift og MVA per sone |
| `test_energiledd.py`      | Dag/natt-tariff inkl. helligdager            |
| `test_kapasitetstrinn.py` | Kapasitetstrinn og topp-3-beregning          |

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
| Man-Fre 06:00-21:59 | dag              |
| Man-Fre 22:00-05:59 | natt             |
| Lør-Søn hele døgnet | natt             |
| Helligdager         | natt             |

### 3. Energiledd

Sjekk at:
- `sensor.energiledd` = `sensor.energiledd_dag` når tariff er "dag"
- `sensor.energiledd` = `sensor.energiledd_natt_helg` når tariff er "natt"

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

- Sjekk `sensor.snitt_toppforbruk` - viser gjennomsnittet av topp 3
- Data lagres per måned og nullstilles ved månedsskift
- Ved ny installasjon tar det tid å bygge opp data
