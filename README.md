# Nettleie

![AI SLOP](https://raw.githubusercontent.com/kluzzebass/ai-slop/refs/heads/main/ai-slop-05-chaos.svg)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg)](https://github.com/fredrik-lindseth/Stromkalkulator/releases)
[![GitHub stars](https://img.shields.io/github/stars/fredrik-lindseth/Stromkalkulator.svg?style=social)](https://github.com/fredrik-lindseth/Stromkalkulator/stargazers)

Home Assistant-integrasjon for komplett oversikt over strømkostnader i Norge. Beregner nettleie, strømstøtte og sammenligner med Norgespris - alt i én integrasjon.

## Hva gir denne integrasjonen deg?

### Nettleie
- **Energiledd** - Variabel pris per kWh basert på tid (dag/natt/helg/helligdager)
- **Kapasitetsledd** - Månedlig fastbeløp basert på dine 3 høyeste forbrukstopper
- **Offentlige avgifter** - Forbruksavgift, Enova-avgift og mva (inkludert i energileddet)

### Strømstøtte
- **Automatisk beregning** - 90% av spotpris over terskel (91,25 øre/kWh)
- **Spotpris etter støtte** - Se hva du faktisk betaler for strømmen
- **Total pris etter støtte** - Komplett pris inkludert nettleie

### Norgespris-sammenligning
- **Norgespris totalpris** - Hva du ville betalt med Norgespris (50 øre/kWh fast)
- **Prisforskjell** - Se om din avtale eller Norgespris er billigst akkurat nå

### Strømselskap-integrasjon
- **Valgfri kobling** - Koble til prissensor fra Tibber, Fjordkraft, etc.
- **Total pris med påslag** - Se reell totalpris inkludert strømselskapets påslag og nettleie

## Støttede nettselskaper

| Nettselskap | Region |
|-------------|--------|
| BKK | Vestland |
| Elvia | Oslo, Viken, Innlandet |
| Glitre Nett | Drammen, Buskerud |
| Tensio | Trøndelag |
| Egendefinert | Sett inn egne priser |

> **Mangler ditt nettselskap?** Se [Bidra](#bidra) for hvordan du legger til det!

Se [beregninger.md](beregninger.md) for detaljert dokumentasjon av alle formler og beregninger.


## Krav

- Nordpool-integrasjon eller en annen integrasjon som gir spotpris i strømsonen din.
- Strømforbruk-sensor i sanntid, f.eks:
  - [Tibber Pulse](https://tibber.com/no/pulse)
  - [AMS-leser.no](https://ams-leser.no/)
  - HAN-bussleser (tredjepart)
  - Sensor fra nettselskapet

Testet på Home Assistant 2026.1.2

## Installasjon

### Installasjon via HACS 

1. Åpne HACS i Home Assistant
2. Klikk på "Integrations"
3. Klikk på de tre prikkene øverst til høyre og velg "Custom repositories"
4. Legg til `https://github.com/fredrik-lindseth/Stromkalkulator` og velg "Integration" som kategori
5. Finn "Nettleie" i listen og klikk "Download"
6. Start Home Assistant på nytt (eller bruk Quick Reload under Developer Tools)

### Manuell installasjon

1. Kopier `custom_components/nettleie` mappen til din `config/custom_components/` mappe
2. Start Home Assistant på nytt

## Konfigurasjon

1. Gå til Settings → Devices & Services
2. Klikk "Add Integration"
3. Søk etter "Nettleie"
4. Velg nettselskap (f.eks BKK)
5. Velg din strømforbruk-sensor (f.eks. Tibber Pulse)
6. Velg Nord Pool **"Current price"** sensor (f.eks. `sensor.nord_pool_no5_current_price`)

**Viktig:** Velg "Current price" - IKKE "Today lowest" eller "Today average". "Current price" gir deg spotprisen for nåværende time, som er korrekt for strømstøtte-beregninger.

![integration](./integration.png)

### Sensors Dashboard
![sensors](./sensors.png)

## Sensorer

### Nettleie - Kapasitet

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.kapasitetstrinn` | Kapasitetsledd i kr/mnd |
| `sensor.trinn_nummer` | Kapasitetstrinn-nummer (1-10) |
| `sensor.trinn_intervall` | Kapasitetstrinn-intervall (f.eks. "5-10 kW") |
| `sensor.gjennomsnitt_forbruk` | Snitt av topp 3 forbruksdager (kW) |
| `sensor.maks_forbruk_1` | Toppforbruk #1 denne måneden (kW) |
| `sensor.maks_forbruk_2` | Toppforbruk #2 denne måneden (kW) |
| `sensor.maks_forbruk_3` | Toppforbruk #3 denne måneden (kW) |

### Nettleie - Energiledd

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.energiledd` | Energiledd i NOK/kWh (varierer dag/natt) |
| `sensor.offentlige_avgifter` | Forbruksavgift + Enova-avgift inkl. mva |

### Strømpriser

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.total_price` | Total strømpris FØR støtte (spotpris + nettleie) |
| `sensor.electricity_company_total` | Total strømpris fra strømavtale + nettleie |

### Strømstøtte

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.stromstotte` | Strømstøtte per kWh (90% over terskel) |
| `sensor.spotpris_etter_stotte` | Spotpris etter strømstøtte |
| `sensor.total_pris_etter_stotte` | Total strømpris ETTER støtte (dette betaler du) |

### Norgespris

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.total_pris_norgespris` | Total pris med Norgespris (50 øre/kWh + nettleie) |
| `sensor.prisforskjell_norgespris` | Forskjell mellom din pris og Norgespris |

### Sensor-attributter

Hver sensor har ekstra attributter som gir mer detaljer. Disse kan brukes i templates og automatiseringer.

<details>
<summary>Klikk for å se alle attributter</summary>

#### Kapasitetstrinn (`sensor.kapasitetstrinn`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `trinn` | Kapasitetstrinn-nummer (1-10) |
| `intervall` | Intervall (f.eks. "5-10 kW") |
| `gjennomsnitt_kw` | Snitt av topp 3 dager |
| `current_power_kw` | Nåværende forbruk |
| `maks_1_dato`, `maks_1_kw` | Dato og verdi for toppdag #1 |
| `maks_2_dato`, `maks_2_kw` | Dato og verdi for toppdag #2 |
| `maks_3_dato`, `maks_3_kw` | Dato og verdi for toppdag #3 |
| `tso` | Nettselskap |

#### Energiledd (`sensor.energiledd`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `is_day_rate` | `true` hvis dagpris |
| `rate_type` | "dag" eller "natt/helg" |
| `energiledd_dag` | Dagpris (NOK/kWh) |
| `energiledd_natt` | Nattpris (NOK/kWh) |
| `tso` | Nettselskap |

#### Total strømpris (`sensor.total_price`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `spot_price` | Spotpris fra Nord Pool |
| `energiledd` | Energiledd (NOK/kWh) |
| `kapasitetsledd_per_kwh` | Kapasitetsledd per kWh |
| `tso` | Nettselskap |

#### Strømstøtte (`sensor.stromstotte`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `spotpris` | Nåværende spotpris |
| `terskel` | 0.70 (70 øre/kWh) |
| `dekningsgrad` | "90%" |

#### Total strømpris etter støtte (`sensor.total_pris_etter_stotte`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `spotpris` | Spotpris |
| `stromstotte` | Strømstøtte beløp |
| `spotpris_etter_stotte` | Spotpris minus støtte |
| `energiledd` | Energiledd |
| `kapasitetsledd_per_kwh` | Kapasitetsledd per kWh |

#### Toppforbruk (`sensor.maks_forbruk_1/2/3`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `dato` | Datoen for toppforbruket |

#### Offentlige avgifter (`sensor.offentlige_avgifter`)
| Attributt | Beskrivelse |
|-----------|-------------|
| `forbruksavgift_eks_mva` | Forbruksavgift uten mva |
| `forbruksavgift_inkl_mva` | Forbruksavgift med mva |
| `enova_avgift_eks_mva` | Enova-avgift uten mva |
| `enova_avgift_inkl_mva` | Enova-avgift med mva |
| `mva_sats` | MVA-sats (25%) |
| `note` | Forklaring |

</details>

## Hvilken strømpris-sensor bør du bruke?

### Anbefalte sensorer for vanlig bruk:

| Bruksområde                | Anbefalt sensor                    | Hvorfor?                                                           |
|----------------------------|------------------------------------|--------------------------------------------------------------------|
| **Din faktiske strømpris** | `sensor.total_pris_etter_stotte`   | Viser hva du faktisk betaler per kWh inkl. nettleie og strømstøtte |
| **Strømstøtte**            | `sensor.stromstotte`               | Viser hvor mye du får tilbake per kWh                              |
| **Spotpris**               | `sensor.spotpris_etter_stotte`     | Spotpris etter strømstøtte, uten nettleie                          |

### For spesielle behov:

| Situasjon                          | Sensor                             | Forklaring                                |
|------------------------------------|------------------------------------|-------------------------------------------|
| **Har strømselskap**               | `sensor.electricity_company_total` | Total strømpris (strømavtale)             |
| **Vil sammenligne med norgespris** | `sensor.total_pris_norgespris`     | Total strømpris (norgespris)              |
| **Vil se prisforskjell**           | `sensor.prisforskjell_norgespris`  | Prisforskjell (norgespris)                |

### Om Norgespris-sensorer
`sensor.total_pris_norgespris` 

- Fast pris: 50 øre/kWh (inkl. mva)
- Kan **IKKE** kombineres med strømstøtte
- Gjelder for strømforbruk hjemme og på hytte

`sensor.prisforskjell_norgespris`

- **Positiv verdi**: Du betaler mer enn norgespris (norgespris er billigere)
- **Negativ verdi**: Du betaler mindre enn norgespris (din avtale er billigere)


## Konfigurasjonsfelt

| Felt                         | Beskrivelse                                                                              | Påkrevd |
|------------------------------|------------------------------------------------------------------------------------------|:-------:|
| **Nettselskap**              | Velg ditt nettselskap fra listen, eller "Egendefinert" for manuelle priser               |   Ja    |
| **Strømforbruk-sensor**      | Sensor som viser nåværende strømforbruk i W (f.eks. Tibber Pulse)                        |   Ja    |
| **Spotpris-sensor**          | Nord Pool "Current price" sensor (f.eks. `sensor.nord_pool_no5_current_price`)           |   Ja    |
| **Strømselskap-pris-sensor** | Sensor fra strømselskap med total pris (f.eks. Tibber). Brukes for `sensor.electricity_company_total` |   Nei   |
| **Energiledd dag**           | Manuell energiledd-pris for dag (kun ved "Egendefinert")                                 |   Nei   |
| **Energiledd natt**          | Manuell energiledd-pris for natt/helg (kun ved "Egendefinert")                           |   Nei   |

## Bidra

Vil du legge til støtte for ditt nettselskap? Følg guiden under og opprett en PR!

### Legge til nytt nettselskap (TSO)

1. Åpne `custom_components/nettleie/const.py`
2. Finn `TSO_LIST` dictionary
3. Legg til ditt nettselskap med følgende format:

```python
"ditt_nettselskap": {
    "name": "BKK",
    "energiledd_dag": 0.4613,      # NOK/kWh inkl. avgifter
    "energiledd_natt": 0.2329,     # NOK/kWh inkl. avgifter
    "url": "https://www.bkk.no/nettleiepriser/priser-privatkunder",
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



### Sjekkliste for PR

Før du sender inn en PR, sjekk at:

1. Nettselskapet er lagt til i `TSO_LIST` i `const.py`
2. `url` peker til nettselskapets offisielle prisside
3. Prisene er i **NOK/kWh** (f.eks. `0.45`, ikke 45 øre)
4. Prisene **inkluderer avgifter** (Enova, elavgift, mva)
5. Alle kapasitetstrinn er med (typisk 8-10 trinn)
6. Siste trinn bruker `float("inf")` som øvre grense