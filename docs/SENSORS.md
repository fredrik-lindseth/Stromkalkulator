# Sensorer

Komplett oversikt over alle sensorer og devices i Strømkalkulator.

## Oversikt

Integrasjonen oppretter **5 devices** med totalt **36 sensorer**:

| Device           | Beskrivelse                        | Antall sensorer |
|------------------|------------------------------------|-----------------|
| Nettleie         | Energiledd, kapasitet, avgifter    | 16              |
| Strømstøtte      | Strømstøtte og totalpris           | 5               |
| Norgespris       | Norgespris-sammenligning           | 3               |
| Månedlig forbruk | Forbruk og kostnader denne måneden | 7               |
| Forrige måned    | Forbruk og kostnader forrige måned | 5               |

---

## Device: Nettleie

Hoveddevicen med nettleie-priser, kapasitetstrinn og offentlige avgifter. Devicen navngis "Nettleie ({ditt nettselskap})".

### Energiledd

| Sensor         | Enhet  | Beskrivelse                        |
|----------------|--------|------------------------------------|
| Energiledd     | kr/kWh | Aktivt energiledd (dag eller natt) |
| Tariff         | -      | "dag" eller "natt"                 |

**Tariff-regler:**
- **Dag**: Man-fre 06:00-22:00 (ikke helligdager)
- **Natt**: 22:00-06:00, helger, og helligdager

### Kapasitet

| Sensor                       | Enhet  | Beskrivelse                              |
|------------------------------|--------|------------------------------------------|
| Kapasitetstrinn              | kr/mnd | Månedlig kapasitetskostnad basert på topp-3 |
| Snitt toppforbruk            | kW     | Gjennomsnitt av 3 høyeste effektdager    |
| Kapasitetstrinn (nummer)     | -      | Aktivt trinn (1, 2, 3, ...)             |
| Kapasitetstrinn (intervall)  | -      | Trinn-intervall (f.eks. "2-5 kW")       |
| Toppforbruk #1               | kW     | Høyeste effektdag denne måneden          |
| Toppforbruk #2               | kW     | Nest høyeste effektdag                   |
| Toppforbruk #3               | kW     | Tredje høyeste effektdag                 |

### Strømpris

| Sensor                        | Enhet  | Beskrivelse                                         |
|-------------------------------|--------|-----------------------------------------------------|
| Total strømpris (før støtte)  | kr/kWh | Spotpris + nettleie (uten støtte-fratrekk)          |
| Total strømpris (strømavtale) | kr/kWh | Strømselskap-pris + nettleie (valgfri, krever sensor) |

### Diagnostikk (avgifter)

| Sensor             | Enhet  | Beskrivelse                                 |
|--------------------|--------|---------------------------------------------|
| Energiledd dag     | kr/kWh | Energiledd dagsats (inkl. avgifter)         |
| Energiledd natt/helg | kr/kWh | Energiledd nattsats (inkl. avgifter)      |
| Offentlige avgifter | kr/kWh | Sum forbruksavgift + Enova inkl. mva       |
| Forbruksavgift     | kr/kWh | Forbruksavgift (elavgift) inkl. mva         |
| Enovaavgift        | kr/kWh | Enova-avgift inkl. mva                      |

---

## Device: Strømstøtte

Sensorer for strømstøtte-beregning og totalpris inkl. alle avgifter.

| Sensor                       | Enhet  | Beskrivelse                                   |
|------------------------------|--------|-----------------------------------------------|
| Strømstøtte                  | kr/kWh | Støtte per kWh (90% over 96,25 øre)           |
| Spotpris etter støtte        | kr/kWh | Spotpris minus strømstøtte                    |
| Total strømpris etter støtte | kr/kWh | Spotpris + nettleie - strømstøtte             |
| Totalpris inkl. avgifter     | kr/kWh | **Anbefalt for Energy Dashboard** - inkl. alt |
| Strømstøtte aktiv nå         | -      | "Ja" / "Nei" - om spotpris er over terskelen  |

---

## Device: Norgespris

Sammenligning mellom din spotprisavtale og Norgespris.

| Sensor                       | Enhet  | Beskrivelse                                      |
|------------------------------|--------|--------------------------------------------------|
| Total strømpris (norgespris) | kr/kWh | Norgespris + nettleie                            |
| Prisforskjell (norgespris)   | kr/kWh | Forskjell mellom din pris og Norgespris          |
| Norgespris aktiv nå          | -      | "Ja" / "Nei" - om du har valgt Norgespris        |

**Prisforskjell tolkning:**
- **Positiv verdi** = Du betaler mer enn Norgespris (Norgespris er billigere)
- **Negativ verdi** = Du betaler mindre enn Norgespris (spotpris er billigere)

---

## Device: Månedlig forbruk

Sporer forbruk og kostnader for inneværende måned. Nullstilles automatisk ved månedsskifte.

### Forbruk

| Sensor                     | Enhet | Beskrivelse                                     |
|----------------------------|-------|-------------------------------------------------|
| Månedlig forbruk dagtariff | kWh   | Forbruk på dagtariff (hverdag 06:00-22:00)      |
| Månedlig forbruk natt/helg | kWh   | Forbruk på natt/helg-tariff (inkl. helligdager) |
| Månedlig forbruk totalt    | kWh   | Totalt forbruk denne måneden                    |

### Kostnader

| Sensor                 | Enhet | Beskrivelse                            |
|------------------------|-------|----------------------------------------|
| Månedlig nettleie      | kr    | Nettleie (energiledd + kapasitetsledd) |
| Månedlig avgifter      | kr    | Forbruksavgift + Enova-avgift          |
| Månedlig strømstøtte   | kr    | Estimert strømstøtte                   |
| Månedlig nettleie total | kr   | Total nettleie etter støtte            |

### Attributter

Kostnadssensorene har ekstra attributter:
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd

---

## Device: Forrige måned

Lagrer forrige måneds data for faktura-verifisering. Oppdateres automatisk ved månedsskifte.

### Forbruk

| Sensor                              | Enhet | Beskrivelse                                     |
|-------------------------------------|-------|-------------------------------------------------|
| Forrige måned forbruk dagtariff     | kWh   | Forbruk på dagtariff (hverdag 06:00-22:00)      |
| Forrige måned forbruk natt/helg     | kWh   | Forbruk på natt/helg-tariff (inkl. helligdager) |
| Forrige måned forbruk totalt        | kWh   | Totalt forbruk                                  |

### Kostnader og effekt

| Sensor                     | Enhet | Beskrivelse                   |
|----------------------------|-------|-------------------------------|
| Forrige måned nettleie     | kr    | Nettleie inkl. kapasitetsledd |
| Forrige måned toppforbruk  | kW    | Snitt av topp-3 effektdager   |

### Attributter

Alle sensorer har:
- `måned` - Hvilken måned dataene gjelder (f.eks. "januar 2026")

**Nettleie-sensor har også:**
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd
- `snitt_topp_3_kw` - Gjennomsnitt av topp-3 effektdager

**Toppforbruk-sensor har også:**
- `topp_1_dato`, `topp_1_kw` - Høyeste dag
- `topp_2_dato`, `topp_2_kw` - Nest høyeste dag
- `topp_3_dato`, `topp_3_kw` - Tredje høyeste dag

---

## Bruksscenarier

### Energy Dashboard

Bruk **Totalpris inkl. avgifter** for korrekt totalpris:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Velg din kWh-sensor
4. **"Use an entity with current price"**: Velg "Totalpris inkl. avgifter"

### Sammenligne Norgespris

Bruk **Prisforskjell (norgespris)** for å se om Norgespris lønner seg:

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

| Faktura-post          | Sensor                        | Hvor                            |
|-----------------------|-------------------------------|---------------------------------|
| Energiledd dag (kWh)  | Forrige måned forbruk dagtariff | State                         |
| Energiledd natt (kWh) | Forrige måned forbruk natt/helg | State                         |
| Energiledd dag (kr)   | Forrige måned nettleie        | Attributt: `energiledd_dag_kr`  |
| Energiledd natt (kr)  | Forrige måned nettleie        | Attributt: `energiledd_natt_kr` |
| Kapasitetsledd (kr)   | Forrige måned nettleie        | Attributt: `kapasitetsledd_kr`  |
| Kapasitetstrinn (kW)  | Forrige måned toppforbruk     | State (snitt topp-3)            |

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
