# Bidra

Nettselskapslisten har 74 oppføringer med satser, som dekker 72 norske nettselskap, og Egendefinert dekker resten. Priser endres årlig og feil kan forekomme.

## Egendefinert nettselskap

Er ikke nettselskapet ditt i listen, eller vil du teste egne satser uten å vente på en PR, velg Egendefinert nederst i nettselskap-listen under oppsett. Du får da et eget steg der du legger inn energiledd dag og natt (NOK/kWh, eks. mva og avgifter) og avgiftssone. Integrasjonen legger på forbruksavgift, Enova og mva selv. Send gjerne satsene inn som en PR etterpå, så slipper andre i samme nettselskap å fylle inn manuelt.

## Rapportere feil

Fant du feil priser, åpne et issue med lenke til korrekte priser, eller send en PR med
prisene oppdatert (se under).

## Verifisere fakturaen din

Vil du bekrefte at integrasjonen regner riktig, se [verifiser-din-faktura.md](fakturaer/verifiser-din-faktura.md).

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

`energiledd_dag_eks_mva` og `energiledd_natt_eks_mva` er ren nettleie i NOK/kWh, eks. forbruksavgift, Enova og mva. Integrasjonen legger på avgifter og mva selv basert på avgiftssone. Finn beløpet «energiledd» eller «overføring» på prislisten din, før avgifter og mva.

### Spesielle tilfeller

Flat sats (ingen dag/natt-forskjell):

```python
"energiledd_dag_eks_mva": 0.1556,
"energiledd_natt_eks_mva": 0.1556,
```

Nord-Norge (Nordland, Troms, mva-fritak): bruk de samme eks-mva-verdiene. Integrasjonen detekterer avgiftssone og hopper over mva-påslag. Default følger prisområde (NO4 → Nord-Norge, NO3 → Sør-Norge/25 % mva, siden NO3 i hovedsak er Trøndelag/Møre og Romsdal). For DSO-er i NO3 med mva-fritak (f.eks. Bindal), sett `"avgiftssone": "nord_norge"` eksplisitt.

Tiltakssonen (Finnmark + Nord-Troms): legg til `"tiltakssone": True`. Fritak for forbruksavgift og mva.

Glitre Nett, Tensio TN/TS, Nettselskapet og Stannum har `helg_som_natt: False` (kun klokkeslett styrer dag/natt).

Julaften og nyttårsaften som lavtariff: legg til `"helligdager_ekstra": ["12-24", "12-31"]`. Skal kun gjøres når en ekte faktura fra DSO-en bekrefter at hele dagen behandles som natt-tariff. Default er offisielle norske helligdager, som ikke inkluderer 24.12 eller 31.12.

## Sesongpriser

Bytter nettselskapet energiledd mellom sommer og vinter, legg til `energiledd_perioder`. Hver periode har `fra`/`til` som `"MM-DD"` (begge inkludert), pluss `dag_eks_mva` og `natt_eks_mva`:

```python
"energiledd_perioder": [
    {"fra": "11-01", "til": "04-30", "dag_eks_mva": 0.127, "natt_eks_mva": 0.027},
    {"fra": "05-01", "til": "10-31", "dag_eks_mva": 0.116, "natt_eks_mva": 0.016},
],
```

Periodene må dekke hele året uten overlapp. Krysser en periode nyttår (`fra` > `til`), tolkes det som fra `fra`-dato til årsslutt pluss fra årets start til `til`-dato. `energiledd_dag_eks_mva` og `energiledd_natt_eks_mva` beholdes som fallback for datoer ingen periode dekker. Satsene er eks. mva og avgifter, som de vanlige energiledd-feltene, og krever bekreftelse fra DSO-ens prisliste.

## Drift-vakten mot fri-nettleie

`scripts/sjekk_mot_fri_nettleie.py` sammenligner `dso.py` mot
[fri-nettleie](https://github.com/kraftsystemet/fri-nettleie) og kjøres ukentlig
i CI. Kjør den lokalt før du endrer satser:

```bash
uv run --with pyyaml python scripts/sjekk_mot_fri_nettleie.py --bare-avvik
```

Hvert nettselskap får ett av tre utfall, og exit-koden er det verste av dem:

| Utfall | Exit | Betyr |
| --- | --- | --- |
| verifisert | 0 | alle feltene vi kan sammenligne stemmer |
| avvik | 1 | energiledd, fastledd eller fastledd-metode spriker mer enn toleransen |
| ufullstendig | 2 | kontrollen ble ikke gjort: ingen match i fri-nettleie, 404, nettverksfeil, ingen aktiv tariff, manglende energiledd, ukartlagt fastledd-metode, ugyldig `--dso` |

Ufullstendig slår avvik i exit-koden. En kjøring som ikke vet hva den ikke
sjekket, har ikke lov å si «alt i orden». Begge listene står i rapporten og i
`--json-ut`, så ingenting forsvinner av at 2 vinner over 1.

### Kjente avvik har utløpsdato

`KJENTE_AVVIK` i scriptet demper funn vi har tatt stilling til: enten et avvik
der vi bevisst følger nettselskapets egen prisside, eller et hull i dekningen
der fri-nettleie ikke har noe å sammenligne med. En oppføring er et `Unntak` med
felt, signatur, begrunnelse og `gyldig_til`:

```python
"telemark_nett": (
    Unntak(
        felt=FELT_MATCH,
        signatur="ingen match i fri-nettleie",
        gyldig_til=date(2027, 3, 1),
        grunn="fri-nettleie hadde telemark.yml 2026-07-28, men filen er borte ...",
    ),
),
```

Tre regler gjør at et unntak ikke kan bli liggende og dempe for alltid:

- Det demper bare det ene feltet, med den ene signaturen. Endrer tallet seg, er
  det et nytt funn og rapporteres. Den gamle listen dempet alt hos
  nettselskapet, og et injisert energiledd på 100 kr/kWh hos Fjellnett ble grønt.
- Etter `gyldig_til` demper det ingenting. Står avviket fortsatt der, blir
  kjøringen rød igjen.
- Er det utløpt og treffer ingenting, melder det seg selv som ufullstendig, så
  det blir fjernet framfor å ligge som støy.

Et unntak som fortsatt er gyldig, men ikke treffer noe funn, skrives ut som
«kan trolig fjernes» uten å felle kjøringen.

### Når vakten er rød

CI-jobben feiler, og workflowen oppretter ett issue med etiketten `pris-drift`
og de berørte nettselskapene i tittelen. Samme funn neste uke gir en kommentar
på det samme issuet framfor et nytt, og etter tre uker får issuet etiketten
`pris-drift-eskalert` og en kommentar til repo-eier. Issuet lukkes kun av en
fullstendig kjøring (uten `--dso`-filter) med exit 0; en filtrert kjøring vet
ingenting om resten av listen og får ikke lukke noe.

## Testing

```bash
python3 -m py_compile custom_components/stromkalkulator/dso.py
pipx run --with hypothesis --with pyyaml pytest tests/ -v
```

## PR

Fork repoet, gjør endringen og verifiser syntaksen. Oppgi navn på nettselskap, lenke til
prisside og hva som er endret i PR-en.

## Fusjon av nettselskaper

```python
DSO_MIGRATIONS: Final[list[DSOFusjon]] = [
    DSOFusjon(gammel="skiakernett", ny="vevig"),
]
```

Fjern også gammel oppføring fra `DSO_LIST`. Brukere migreres automatisk.

Fusjoner kan reverseres: norgesnett ble kort innfusjonert i glitre, men er aktiv DSO igjen i dag. Fjern oppføringen fra `DSO_MIGRATIONS` og legg tilbake den gamle `DSO_LIST`-oppføringen hvis det skjer. Sjekk `dso.py` for hva som faktisk gjelder nå.

## Årlige oppdateringer

Nettleiepriser endres typisk ved nyttår. Oppdateres i januar. Hjelp er velkommen.
