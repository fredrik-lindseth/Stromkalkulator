# Sensorer

Komplett oversikt over alle sensorer og devices i Strømkalkulator.

## Oversikt

Integrasjonen oppretter **3 devices** med totalt **22 sensorer**:

| Device           | Beskrivelse                        | Antall sensorer |
|------------------|------------------------------------|-----------------|
| Strømkalkulator  | Priser, nettleie, strømstøtte      | 12              |
| Månedlig forbruk | Forbruk og kostnader denne måneden | 7               |
| Forrige måned    | Forbruk og kostnader forrige måned | 5               |

---

## Device: Strømkalkulator

Hovedsensorene for sanntids priser og beregninger.

### Prissensorer

| Sensor                                | Enhet  | Beskrivelse                                   |
|---------------------------------------|--------|-----------------------------------------------|
| `sensor.totalpris_inkl_avgifter`      | kr/kWh | **Anbefalt for Energy Dashboard** - inkl. alt |
| `sensor.total_strompris_etter_stotte` | kr/kWh | Spotpris + nettleie - strømstøtte             |
| `sensor.total_strompris_for_stotte`   | kr/kWh | Spotpris + nettleie (uten støtte-fratrekk)    |
| `sensor.spotpris_etter_stotte`        | kr/kWh | Spotpris minus strømstøtte                    |

### Strømstøtte

| Sensor                            | Enhet  | Beskrivelse                             |
|-----------------------------------|--------|-----------------------------------------|
| `sensor.stromstotte`              | kr/kWh | Støtte per kWh (90% over 96,25 øre)     |
| `sensor.prisforskjell_norgespris` | kr/kWh | Forskjell mellom spotpris og Norgespris |

**Prisforskjell tolkning:**
- **Positiv verdi** = Norgespris er billigere
- **Negativ verdi** = Spotpris er billigere

### Nettleie

| Sensor                   | Enhet  | Beskrivelse                                 |
|--------------------------|--------|---------------------------------------------|
| `sensor.nettleie_total`  | kr/kWh | Energiledd + kapasitetsledd per kWh         |
| `sensor.energiledd`      | kr/kWh | Aktivt energiledd (dag eller natt)          |
| `sensor.kapasitetstrinn` | kr/mnd | Månedlig kapasitetskostnad basert på topp-3 |

### Tariff og effekt

| Sensor                | Enhet | Beskrivelse                           |
|-----------------------|-------|---------------------------------------|
| `sensor.tariff`       | -     | "dag" eller "natt"                    |
| `sensor.snitt_topp_3` | kW    | Gjennomsnitt av 3 høyeste effektdager |

**Tariff-regler:**
- **Dag**: Man-fre 06:00-22:00 (ikke helligdager)
- **Natt**: 22:00-06:00, helger, og helligdager

### Diagnostikk

| Sensor                      | Enhet  | Kategori    | Beskrivelse                     |
|-----------------------------|--------|-------------|---------------------------------|
| `sensor.energiledd_dag`     | kr/kWh | Diagnostikk | Energiledd dagsats              |
| `sensor.energiledd_natt`    | kr/kWh | Diagnostikk | Energiledd nattsats             |
| `sensor.kapasitetsledd_kwh` | kr/kWh | Diagnostikk | Kapasitetsledd fordelt per time |

---

## Device: Månedlig forbruk

Sporer forbruk og kostnader for inneværende måned. Nullstilles automatisk ved månedsskifte.

### Forbruk

| Sensor                           | Enhet | Beskrivelse                                     |
|----------------------------------|-------|-------------------------------------------------|
| `sensor.manedlig_forbruk_dag`    | kWh   | Forbruk på dagtariff (hverdag 06:00-22:00)      |
| `sensor.manedlig_forbruk_natt`   | kWh   | Forbruk på natt/helg-tariff (inkl. helligdager) |
| `sensor.manedlig_forbruk_totalt` | kWh   | Totalt forbruk denne måneden                    |

### Kostnader

| Sensor                           | Enhet | Beskrivelse                            |
|----------------------------------|-------|----------------------------------------|
| `sensor.manedlig_nettleie`       | kr    | Nettleie (energiledd + kapasitetsledd) |
| `sensor.manedlig_avgifter`       | kr    | Forbruksavgift + Enova-avgift          |
| `sensor.manedlig_stromstotte`    | kr    | Estimert strømstøtte                   |
| `sensor.manedlig_nettleie_total` | kr    | Total nettleie etter støtte            |

### Attributter

Kostnadssensorene har ekstra attributter:
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd

---

## Device: Forrige måned

Lagrer forrige måneds data for faktura-verifisering. Oppdateres automatisk ved månedsskifte.

### Forbruk

| Sensor                                | Enhet | Beskrivelse                                     |
|---------------------------------------|-------|-------------------------------------------------|
| `sensor.forrige_maaned_forbruk_dag`   | kWh   | Forbruk på dagtariff (hverdag 06:00-22:00)      |
| `sensor.forrige_maaned_forbruk_natt`  | kWh   | Forbruk på natt/helg-tariff (inkl. helligdager) |
| `sensor.forrige_maaned_forbruk_total` | kWh   | Totalt forbruk                                  |

### Kostnader og effekt

| Sensor                              | Enhet | Beskrivelse                   |
|-------------------------------------|-------|-------------------------------|
| `sensor.forrige_maaned_nettleie`    | kr    | Nettleie inkl. kapasitetsledd |
| `sensor.forrige_maaned_toppforbruk` | kW    | Snitt av topp-3 effektdager   |

### Attributter

Alle sensorer har:
- `måned` - Hvilken måned dataene gjelder (f.eks. "januar 2026")

**Nettleie-sensor har også:**
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd

**Toppforbruk-sensor har også:**
- `topp_1_dato`, `topp_1_kw` - Høyeste dag
- `topp_2_dato`, `topp_2_kw` - Nest høyeste dag
- `topp_3_dato`, `topp_3_kw` - Tredje høyeste dag

---

## Bruksscenarier

### Energy Dashboard

Bruk `sensor.totalpris_inkl_avgifter` for korrekt totalpris:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Velg din kWh-sensor
4. **"Use an entity with current price"**: `sensor.totalpris_inkl_avgifter`

### Sammenligne Norgespris

Bruk `sensor.prisforskjell_norgespris` for å se om Norgespris lønner seg:

```yaml
# Eksempel: Varsle når Norgespris er billigere
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.prisforskjell_norgespris
        above: 0.10  # 10 øre billigere
    action:
      - service: notify.mobile_app
        data:
          message: "Norgespris er nå 10+ øre billigere enn spotpris"
```

### Faktura-verifisering

Bruk "Forrige måned"-sensorene når fakturaen kommer:

| Faktura-post          | Sensor                               | Hvor                            |
|-----------------------|--------------------------------------|---------------------------------|
| Energiledd dag (kWh)  | `sensor.forrige_maaned_forbruk_dag`  | State                           |
| Energiledd natt (kWh) | `sensor.forrige_maaned_forbruk_natt` | State                           |
| Energiledd dag (kr)   | `sensor.forrige_maaned_nettleie`     | Attributt: `energiledd_dag_kr`  |
| Energiledd natt (kr)  | `sensor.forrige_maaned_nettleie`     | Attributt: `energiledd_natt_kr` |
| Kapasitetsledd (kr)   | `sensor.forrige_maaned_nettleie`     | Attributt: `kapasitetsledd_kr`  |
| Kapasitetstrinn (kW)  | `sensor.forrige_maaned_toppforbruk`  | State (snitt topp-3)            |

---

## Tekniske detaljer

### Oppdateringsfrekvens

- Alle sensorer oppdateres **hvert minutt**
- Månedlig forbruk beregnes med Riemann-sum fra effekt-sensoren
- Makseffekt lagres per dag og nullstilles ved månedsskifte

### Persistens

- All data lagres til disk og overlever restart
- Lagringsformat: `/config/.storage/stromkalkulator_<tso_id>`

### Nøyaktighet

- **1-5% avvik fra faktura er normalt** (avrunding, målefeil)
- Strømstøtte kan avvike mer (fakturaen bruker time-for-time priser)
- Forbruk beregnes fra effekt, ikke fra strømmåler

Se [beregninger.md](beregninger.md) for detaljerte formler.
