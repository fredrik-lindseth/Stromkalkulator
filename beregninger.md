# Beregninger i Nettleie

Dokumentasjon av hvordan alle beregninger utføres i Nettleie-integrasjonen.

## Strømstøtte

Strømstøtten dekker 90% av spotpris over 70 øre/kWh.

### Formel

```
strømstøtte = max(0, (spotpris - 0.70) * 0.90)
```

### Parametere
- **Terskel**: 70 øre/kWh (0.70 NOK/kWh)
- **Dekningsgrad**: 90%
- **Basis**: Spotpris fra Nord Pool

### Eksempler

| Spotpris | Strømstøtte | Pris etter støtte |
|----------|-------------|-------------------|
| 0.50 NOK | 0.00 NOK    | 0.50 NOK          |
| 0.70 NOK | 0.00 NOK    | 0.70 NOK          |
| 1.00 NOK | 0.27 NOK    | 0.73 NOK          |
| 1.50 NOK | 0.72 NOK    | 0.78 NOK          |
| 2.00 NOK | 1.17 NOK    | 0.83 NOK          |

## Nettleie

Nettleien består av to deler: energiledd og kapasitetsledd.

### Energiledd

Energileddet varierer basert på tidspunkt:

- **Dag**: Mandag-fredag 06:00-22:00 (ikke helligdager)
- **Natt/Helg**: 22:00-06:00, helger og helligdager

### Kapasitetsledd

Kapasitetsleddet beregnes basert på de 3 høyeste strømforbrukstimene på 3 ulike dager.

#### Beregningsmetode
1. **Spor maksforbruk**: Hver dag lagres høyeste strømforbruk i kW
2. **Velg topp 3**: De 3 dagene med høyest maksforbruk velges
3. **Beregn gjennomsnitt**: Gjennomsnitt av de 3 dager
4. **Finn trinn**: Basert på gjennomsnittet finnes riktig kapasitetstrinn

#### Eksempel (BKK)
```
Dag 1: 4.2 kW
Dag 2: 3.8 kW  
Dag 3: 5.1 kW
Gjennomsnitt: 4.37 kW
Kapasitetstrinn: 5-10 kW → 250 kr/mnd
```

#### Kapasitetstrinn (BKK)
| Trinn | Intervall | Pris        |
|-------|-----------|-------------|
| 1     | 0-2 kW    | 150 kr/mnd  |
| 2     | 2-5 kW    | 250 kr/mnd  |
| 3     | 5-10 kW   | 400 kr/mnd  |
| 4     | 10-15 kW  | 600 kr/mnd  |
| 5     | 15-20 kW  | 800 kr/mnd  |
| 6     | 20-25 kW  | 1000 kr/mnd |
| 7     | 25-50 kW  | 1800 kr/mnd |
| 8     | 50-75 kW  | 2600 kr/mnd |
| 9     | 75-100 kW | 3500 kr/mnd |
| 10    | >100 kW   | 7000 kr/mnd |

### Fastledd per kWh

Kapasitetsleddet omregnes til per kWh:

```
fastledd_per_kwh = (kapasitetsledd / dager_i_måned) / 24
```

#### Eksempel
```
Kapasitetsledd: 400 kr/mnd
Dager i måned: 30
fastledd_per_kwh = (400 / 30) / 24 = 0.56 kr/kWh
```

## Total strømpris

### Uten strømstøtte
```
total_pris = spotpris + energiledd + fastledd_per_kwh
```

### Med strømstøtte
```
total_pris_etter_stotte = (spotpris - strømstøtte) + energiledd + fastledd_per_kwh
```

## Komplett eksempel

**Forutsetninger:**
- Spotpris: 1.20 NOK/kWh
- Energiledd (dag): 0.4613 NOK/kWh
- Kapasitetsledd: 400 kr/mnd
- Dager i måned: 30

**Beregninger:**
1. **Strømstøtte**: (1.20 - 0.70) * 0.90 = 0.45 NOK/kWh
2. **Fastledd per kWh**: (400 / 30) / 24 = 0.56 NOK/kWh
3. **Totalpris uten støtte**: 1.20 + 0.4613 + 0.56 = 2.22 NOK/kWh
4. **Totalpris med støtte**: (1.20 - 0.45) + 0.4613 + 0.56 = 1.77 NOK/kWh

## Datakilder

### Nødvendige sensorer
1. **Strømforbruk**: Sanntids sensor i Watt (W)
2. **Spotpris**: Nord Pool "Current price" i NOK/kWh
3. **Strømselskap (valgfri)**: Total pris fra strømselskap

### Oppdateringsfrekvens
- Alle beregninger oppdateres hvert minutt
- Maksforbruk lagres per dag og nulles ved månedsskifte

## Persistens

- Maksforbruk-data lagres til disk for å overleve restart
- Data nulles automatisk ved ny måned
- Lagret format: `{dag: maks_forbruk_kw}`

## Norgespris

Norgespris er et strømprodukt fra Elhub med fast pris på 50 øre/kWh inkl. mva.

### Egenskaper
- **Fast pris**: 50 øre/kWh (0.50 NOK/kWh) inkl. mva
- **Ingen strømstøtte**: Kan ikke kombineres med strømstøtte
- **Gjelder**: Strømforbruk hjemme og på hytte

### Formler
```
NORGESPRIS_FAST = 0.50  # 50 øre/kWh inkl. mva

total_pris_norgespris = NORGESPRIS_FAST + energiledd + fastledd_per_kwh

kroner_spart_per_kwh = total_pris_etter_stotte - total_pris_norgespris
```

### Eksempel
**Forutsetninger:**
- Din spotpris: 1.20 NOK/kWh
- Energiledd: 0.4613 NOK/kWh
- Fastledd: 0.56 NOK/kWh

**Beregninger:**
1. **Din strømstøtte**: (1.20 - 0.70) * 0.90 = 0.45 NOK/kWh
2. **Din totalpris etter støtte**: (1.20 - 0.45) + 0.4613 + 0.56 = 1.77 NOK/kWh
3. **Totalpris med norgespris**: 0.50 + 0.4613 + 0.56 = 1.52 NOK/kWh
4. **Prisforskjell**: 1.77 - 1.52 = 0.25 NOK/kWh (du betaler mer)

### Tolkning av prisforskjell
- **Positiv verdi**: Du betaler mer enn norgespris (norgespris er billigere)
- **Negativ verdi**: Du betaler mindre enn norgespris (din avtale er billigere)

## Noter

- Alle priser er i NOK/kWh
- Strømforbruk konverteres fra W til kW (/1000)
- Beregningene følger norske regler for strømstøtte
- Kapasitetstrinn varierer mellom nettselskaper
- Norgespris er fast 50 øre/kWh fra Elhub (ingen strømstøtte)
