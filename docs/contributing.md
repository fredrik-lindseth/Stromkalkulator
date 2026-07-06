# Bidra

Alle norske nettselskaper er støttet, men priser endres årlig og feil kan forekomme.

## Rapportere feil

Fant du feil priser?

1. **Issue** med lenke til korrekte priser, eller
2. **PR** med oppdaterte priser (se under)

## Verifisere fakturaen din

Vil du bekrefte at integrasjonen regner riktig? Se [verifiser-din-faktura.md](fakturaer/verifiser-din-faktura.md).

Foreløpig er kun BKK (NO5) verifisert. Vi trenger fakturadata fra andre nettselskap. Bruk [issue-malen](../.github/ISSUE_TEMPLATE/faktura-verifisering.md).

## Oppdatere priser (PR)

Åpne `custom_components/stromkalkulator/dso.py`, finn `DSO_LIST`, oppdater prisene.

```python
"ditt_nettselskap": {
    "name": "Eksempel Nett",
    "prisomrade": "NO1",
    "supported": True,
    "energiledd_dag_eks_mva": 0.2877,   # NOK/kWh, ren nettleie eks. avgifter
    "energiledd_natt_eks_mva": 0.105,   # NOK/kWh, ren nettleie eks. avgifter
    "url": "https://www.eksempelnett.no/nettleiepriser",
    "kapasitetstrinn": [
        (2, 150),                       # 0-2 kW: 150 kr/mnd
        (5, 250),
        (10, 400),
        (15, 600),
        (20, 800),
        (25, 1000),
        (50, 1800),
        (75, 2600),
        (100, 3500),
        (float("inf"), 7000),
    ],
},
```

`energiledd_dag_eks_mva` og `energiledd_natt_eks_mva` er ren nettleie i NOK/kWh, **eks. forbruksavgift, Enova og mva**. Integrasjonen legger på avgifter og mva selv basert på avgiftssone. Finn beløpet «energiledd» eller «overføring» på prislisten din, før avgifter og mva.

### Spesielle tilfeller

Flat sats (ingen dag/natt-forskjell):

```python
"energiledd_dag_eks_mva": 0.1556,
"energiledd_natt_eks_mva": 0.1556,
```

Nord-Norge (NO3, NO4, mva-fritak): bruk de samme eks-mva-verdiene. Integrasjonen detekterer prisområdet og hopper over mva-påslag.

Tiltakssonen (Finnmark + Nord-Troms): legg til `"tiltakssone": True`. Fritak for forbruksavgift og MVA.

Glitre Nett, Tensio TN/TS har `helg_som_natt: False` (kun klokkeslett styrer dag/natt).

Julaften og nyttårsaften som lavtariff: legg til `"helligdager_ekstra": ["12-24", "12-31"]`. Skal kun gjøres når en ekte faktura fra DSO-en bekrefter at hele dagen behandles som natt-tariff. Default er offisielle norske helligdager, som ikke inkluderer 24.12 eller 31.12.

## Testing

```bash
python3 -m py_compile custom_components/stromkalkulator/dso.py
pipx run pytest tests/ -v
```

## PR

1. Fork
2. Endringer
3. Verifiser syntaks
4. PR med: navn på nettselskap, lenke til prisside, hva som er endret

## Fusjon av nettselskaper

```python
DSO_MIGRATIONS: Final[list[DSOFusjon]] = [
    DSOFusjon(gammel="skiakernett", ny="vevig"),
    DSOFusjon(gammel="norgesnett", ny="glitre"),
]
```

Fjern også gammel oppføring fra `DSO_LIST`. Brukere migreres automatisk.

## Årlige oppdateringer

Nettleiepriser endres typisk ved nyttår. Oppdateres i januar. Hjelp er velkommen.
