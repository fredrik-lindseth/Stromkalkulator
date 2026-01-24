# Bidra til Strømkalkulator

Vil du legge til støtte for ditt nettselskap? Følg guiden under og opprett en PR!

## Legge til nytt nettselskap (TSO)

1. Åpne `custom_components/stromkalkulator/const.py`
2. Finn `TSO_LIST` dictionary
3. Finn ditt nettselskap (alle 71 norske nettselskaper er allerede registrert)
4. Oppdater oppføringen med priser fra nettselskapets nettside

### Eksempel

```python
"ditt_nettselskap": {
    "name": "Eksempel Nett",
    "prisomrade": "NO1",
    "supported": True,  # Endre fra False til True
    "energiledd_dag": 0.4613,      # NOK/kWh inkl. avgifter
    "energiledd_natt": 0.2329,     # NOK/kWh inkl. avgifter
    "url": "https://www.eksempelnett.no/nettleiepriser",
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

### Viktige retningslinjer

| Felt | Format | Beskrivelse |
|------|--------|-------------|
| `energiledd_dag` | NOK/kWh | Dagpris i NOK (ikke øre), inkl. avgifter |
| `energiledd_natt` | NOK/kWh | Nattpris i NOK (ikke øre), inkl. avgifter |
| `supported` | True/False | Sett til `True` når priser er lagt inn |
| `url` | URL | Lenke til nettselskapets offisielle prisside |
| `kapasitetstrinn` | Liste | Liste med tupler: `(kW-grense, kr/mnd)` |

### Dag/natt-tider

- **Dag**: Hverdager 06:00-22:00
- **Natt**: 22:00-06:00 + helg + helligdager

### Spesielle tilfeller

#### Nettselskap uten dag/natt-differensiering
Hvis nettselskapet har flat sats (ingen dag/natt-forskjell), bruk samme verdi for begge:

```python
"energiledd_dag": 0.2556,
"energiledd_natt": 0.2556,  # Flat sats
```

#### Nord-Norge (NO4) - MVA-fritak
Husholdninger i Nord-Norge har MVA-fritak. Bruk priser **eks mva** fra nettselskapets nettside.

#### Tiltakssonen (Finnmark + Nord-Troms)
Kunder i tiltakssonen har fritak for både forbruksavgift og MVA.

## Testing

Etter endringer, verifiser at syntaksen er korrekt:

```bash
python3 -m py_compile custom_components/stromkalkulator/const.py
```

## Opprett Pull Request

1. Fork repoet
2. Gjør endringene dine
3. Verifiser at syntaksen er korrekt
4. Opprett en PR med:
   - Navn på nettselskap
   - Lenke til prisside (kilde)
   - Prisene du har lagt inn

Vi setter pris på alle bidrag!
