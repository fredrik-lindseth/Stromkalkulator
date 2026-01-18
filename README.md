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
- Strømforbruk-sensor i sanntid, f.eks:
  - [Tibber Pulse](https://tibber.com/no/pulse)
  - [AMS-leser.no](https://ams-leser.no/)
  - HAN-bussleser (tredjepart)
  - Sensor fra nettselskapet

## Installasjon

### HACS (anbefalt)

1. Åpne HACS i Home Assistant
2. Klikk på "Integrations"
3. Klikk på de tre prikkene øverst til høyre og velg "Custom repositories"
4. Legg til `https://github.com/fredrik-lindseth/strompris` og velg "Integration" som kategori
5. Finn "Nettleie" i listen og klikk "Download"
6. Start Home Assistant på nytt (eller bruk Quick Reload under Developer Tools)

### Manuell installasjon

1. Kopier `custom_components/nettleie` mappen til din `config/custom_components/` mappe
2. Start Home Assistant på nytt

## Konfigurasjon

1. Gå til Settings → Devices & Services
2. Klikk "Add Integration"
3. Søk etter "Nettleie"
4. Velg nettselskap (BKK, Elvia, Glitre Nett, Tensio eller Egendefinert)
5. Velg din strømforbruk-sensor (f.eks. Tibber Pulse)
6. Velg Nord Pool **"Current price"** sensor (f.eks. `sensor.nord_pool_no5_current_price`)
   - ⚠️ **Viktig:** Bruk "Current price", ikke "Highest/Lowest/Next price"
7. (Valgfritt) Angi egne energiledd-priser

## Sensorer

| Sensor                             | Beskrivelse                              |
|------------------------------------|------------------------------------------|
| `sensor.energiledd`                | Energiledd i NOK/kWh                     |
| `sensor.kapasitetstrinn`           | Kapasitetsledd i kr/mnd                  |
| `sensor.strompris_ink_avgifter`    | Total strømpris i NOK/kWh                |
| `sensor.maks_forbruk_1`            | Høyeste forbruk denne måneden (kW)       |
| `sensor.maks_forbruk_2`            | Nest høyeste forbruk denne måneden (kW)  |
| `sensor.maks_forbruk_3`            | Tredje høyeste forbruk denne måneden (kW)|
| `sensor.gjennomsnitt_maks_forbruk` | Gjennomsnitt av topp 3 (kW)              |

## Støttede nettselskaper

### BKK
Priser fra [BKK](https://www.bkk.no/nettleiepriser/priser-privatkunder)
- Dag: 46,13 øre/kWh | Natt: 23,29 øre/kWh
- Kapasitet: 155-6900 kr/mnd

### Elvia
Priser fra [Elvia](https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/)
- Dag: 39,79 øre/kWh | Natt: 24,79 øre/kWh
- Kapasitet: 176-6836 kr/mnd

### Glitre Nett
Priser fra [Glitre Nett](https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde)
- Dag: 40,91 øre/kWh | Natt: 25,91 øre/kWh
- Kapasitet: 160-6250 kr/mnd

### Tensio
Priser fra [Tensio](https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat)
- Dag: 38,50 øre/kWh | Natt: 23,50 øre/kWh
- Kapasitet: 175-6125 kr/mnd

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
    "name": "Ditt Nettselskap",
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