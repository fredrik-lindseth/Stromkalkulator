# Nettleie

![AI SLOP](ai-slop-badge.svg)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integrasjon for beregning av nettleie for norske nettselskaper.

## Funksjoner

- **Støtte for flere nettselskaper**: BKK, eller egendefinert
- **Energiledd-sensor**: Viser gjeldende energiledd basert på tid (dag/natt/helg/helligdager)
- **Kapasitetstrinn-sensor**: Beregner kapasitetstrinn basert på de 3 høyeste timene på 3 ulike dager
- **Total strømpris-sensor**: Viser total strømpris inkludert spotpris, nettleie og strømstøtte
- **Konfigurerbare priser**: Kan overstyre energiledd dag/natt

## Krav

- Nordpool-integrasjon installert
- Strømmåler-sensor (f.eks. Tibber Pulse, AMS-måler)

## Installasjon

### HACS (anbefalt)

1. Åpne HACS i Home Assistant
2. Klikk på "Integrations"
3. Klikk på de tre prikkene øverst til høyre og velg "Custom repositories"
4. Legg til repository URL og velg "Integration" som kategori
5. Klikk "Install"
6. Start Home Assistant på nytt

### Manuell installasjon

1. Kopier `custom_components/nettleie` mappen til din `config/custom_components/` mappe
2. Start Home Assistant på nytt

## Konfigurasjon

1. Gå til Settings → Devices & Services
2. Klikk "Add Integration"
3. Søk etter "Nettleie"
4. Velg nettselskap (BKK eller Egendefinert)
5. Velg din strømforbruk-sensor (f.eks. Tibber Pulse)
6. Velg din spotpris-sensor (f.eks. Nordpool)
7. (Valgfritt) Angi egne energiledd-priser

## Sensorer

| Sensor                          | Beskrivelse               |
|---------------------------------|---------------------------|
| `sensor.energiledd`             | Energiledd i NOK/kWh      |
| `sensor.kapasitetstrinn`        | Kapasitetsledd i kr/mnd   |
| `sensor.strompris_ink_avgifter` | Total strømpris i NOK/kWh |

## Støttede nettselskaper

### BKK (Bergen)
Priser fra [BKK](https://www.bkk.no/nettleiepriser/priser-privatkunder)

#### Energiledd (2026)
- Dag (06-22, hverdager): 46,13 øre/kWh
- Natt/helg/helligdager: 23,29 øre/kWh

#### Kapasitetstrinn (2026)
| Trinn | kW     | kr/mnd |
|-------|--------|--------|
| 1     | 0-2    | 155    |
| 2     | 2-5    | 250    |
| 3     | 5-10   | 415    |
| 4     | 10-15  | 600    |
| 5     | 15-20  | 770    |
| 6     | 20-25  | 940    |
| 7     | 25-50  | 1800   |
| 8     | 50-75  | 2650   |
| 9     | 75-100 | 3500   |
| 10    | >100   | 6900   |

### Egendefinert
Velg "Egendefinert" for å angi dine egne energiledd-priser.

## Bidra

Vil du legge til støtte for ditt nettselskap? Følg guiden under og opprett en PR!

### Legge til nytt nettselskap (TSO)

1. Åpne `custom_components/nettleie/const.py`
2. Finn `TSO_LIST` dictionary
3. Legg til ditt nettselskap med følgende format:

```python
"ditt_nettselskap": {
    "name": "Ditt Nettselskap (By)",
    "energiledd_dag": 0.45,      # NOK/kWh inkl. avgifter
    "energiledd_natt": 0.22,     # NOK/kWh inkl. avgifter
    "url": "https://ditt-nettselskap.no/priser",
    "kapasitetstrinn": [
        (2, 150),      # 0-2 kW: 150 kr/mnd
        (5, 250),      # 2-5 kW: 250 kr/mnd
        (10, 400),     # 5-10 kW: 400 kr/mnd
        (15, 600),     # 10-15 kW: 600 kr/mnd
        (20, 800),     # 15-20 kW: 800 kr/mnd
        (25, 1000),    # 20-25 kW: 1000 kr/mnd
        (50, 1800),    # 25-50 kW: 1800 kr/mnd
        (75, 2600),    # 50-75 kW: 2600 kr/mnd
        (100, 3500),   # 75-100 kW: 3500 kr/mnd
        (float("inf"), 7000),  # >100 kW: 7000 kr/mnd
    ],
},
```

**Viktig:**
- `energiledd_dag` og `energiledd_natt` skal være i **NOK/kWh** (ikke øre)
- Prisene skal være **inkludert avgifter** (Enova, elavgift, mva)
- `kapasitetstrinn` er en liste med tupler: `(kW-grense, kr/mnd)`
- Dag = hverdager 06:00-22:00, Natt = 22:00-06:00 + helg + helligdager

### Legge til flere helligdager

1. Åpne `custom_components/nettleie/const.py`
2. Finn `HELLIGDAGER` listen
3. Legg til datoer i `MM-DD` format:

```python
HELLIGDAGER: Final = [
    "01-01",  # Nyttårsdag
    "05-01",  # Arbeidernes dag
    "05-17",  # Grunnlovsdag
    "12-25",  # 1. juledag
    "12-26",  # 2. juledag
    # Bevegelige helligdager (påske, pinse) må legges til manuelt per år
]
```

### Sjekkliste for PR

- [ ] Nettselskap lagt til i `TSO_LIST`
- [ ] `url` peker til nettselskapets prisside (for verifisering)
- [ ] `energiledd_dag` og `energiledd_natt` er i NOK/kWh (f.eks. 0.45, ikke 45 øre)
- [ ] Prisene inkluderer alle avgifter (Enova, elavgift, mva)
- [ ] Alle kapasitetstrinn er med (fra 0 kW til høyeste, typisk 8-10 trinn)
- [ ] Siste trinn bruker `float("inf")` som grense
- [ ] README oppdatert med nettselskap-info under "Støttede nettselskaper"