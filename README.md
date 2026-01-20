# Strømkalkulator

![AI SLOP](https://raw.githubusercontent.com/kluzzebass/ai-slop/refs/heads/main/ai-slop-05-chaos.svg)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg)](https://github.com/fredrik-lindseth/Stromkalkulator/releases)
[![GitHub stars](https://img.shields.io/github/stars/fredrik-lindseth/Stromkalkulator.svg?style=social)](https://github.com/fredrik-lindseth/Stromkalkulator/stargazers)

Home Assistant-integrasjon for komplett oversikt over strømkostnader i Norge. Beregner nettleie, strømstøtte og sammenligner med Norgespris - alt i én integrasjon.

## Hva gir denne integrasjonen deg?

### Nettleie
- **Energiledd** - Variabel pris per kWh basert på tid (dag/natt/helg/helligdager)
- **Kapasitetsledd** - Månedlig fastbeløp basert på dine 3 høyeste forbrukstopper
- **Offentlige avgifter** - Forbruksavgift, Enova-avgift og mva (regionbasert)

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

| Nettselskap                                                                                  |
|----------------------------------------------------------------------------------------------|
| [Arva](https://www.arva.no/kunde/nettleie/nettleiepriser)                                    |
| [BKK](https://www.bkk.no/nettleiepriser/priser-privatkunder)                                 |
| [Elinett](https://www.elinett.no/kunde/nettleie-2/nettleie)                                  |
| [Elvia](https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/)                  |
| [Fagne](https://fagne.no/kunde-og-nettleie/nettleie-priser-og-vilkar/priser-privatkunder/)   |
| [Føie](https://www.foie.no/nettleie/priser)                                                  |
| [Glitre Nett](https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde) |
| [Lede](https://www.lede.no/nettleie/nettleiepriser)                                          |
| [Linea](https://www.linea.no/no/kunde/nettleie/nettleiepriser)                               |
| [Linja](https://www.linja.no/nettleige)                                                      |
| [Lnett](https://www.l-nett.no/nettleie/nettleiepriser-privat)                                |
| [Mellom](https://mellom.no/nettleiepriser/)                                                  |
| [Nettselskapet](https://nettselskapet.as/strompris)                                          |
| [Noranett](https://www.noranett.no/nettleiepriser/category2415.html)                         |
| [Norgesnett](https://norgesnett.no/kunde/nettleie/nettleiepriser/)                           |
| [Tensio](https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat)                  |
| Egendefinert                                                                                 |

> **Mangler ditt nettselskap?** Se [Bidra](#bidra) for hvordan du legger til det!

<details>
<summary><b>Nettselskaper som trenger bidrag (55 stk)</b></summary>

Disse nettselskapene er registrert med prisområde, men mangler priser. Bidra gjerne!

| Nettselskap               | Prisområde |
|---------------------------|------------|
| Alut                      | NO4        |
| Area Nett                 | NO4        |
| Asker Nett                | NO1        |
| Barents Nett              | NO4        |
| Bindal Kraftnett          | NO3        |
| Breheim Nett              | NO5        |
| Bømlo Kraftnett           | NO5        |
| De Nett                   | NO2        |
| Elmea                     | NO4        |
| Enida                     | NO2        |
| Everket                   | NO2        |
| Fjellnett                 | NO3        |
| Føre                      | NO2        |
| Griug                     | NO1        |
| Haringnett                | NO5        |
| Havnett                   | NO5        |
| Høland og Setskog Elverk  | NO1        |
| Indre Hordaland Kraftnett | NO5        |
| Jæren Everk               | NO2        |
| KE Nett                   | NO2        |
| Klive                     | NO3        |
| Kystnett                  | NO4        |
| Lucerna                   | NO4        |
| Lysna                     | NO5        |
| Meløy Energi              | NO4        |
| Midtnett                  | NO1        |
| Modalen Kraftlag          | NO5        |
| Netera                    | NO3        |
| Noranett Andøy            | NO4        |
| Noranett Hadsel           | NO4        |
| Nordvest Nett             | NO3        |
| Norefjell Nett            | NO1        |
| R-Nett                    | NO1        |
| Rakkestad Energi          | NO1        |
| RK Nett                   | NO2        |
| Romsdalsnett              | NO3        |
| S-Nett                    | NO3        |
| Skjåkernett               | NO3        |
| Stannum                   | NO2        |
| Stram                     | NO4        |
| Straumen Nett             | NO3        |
| Straumnett                | NO5        |
| Svabo Industrinett        | NO4        |
| Sygnir                    | NO5        |
| Sør Aurdal Energi         | NO1        |
| Telemark Nett             | NO2        |
| Tendranett                | NO5        |
| Uvdal Kraftforsyning      | NO1        |
| Vang Energiverk           | NO1        |
| Vestall                   | NO4        |
| Vestmar Nett              | NO2        |
| Vevig                     | NO3        |
| Viermie                   | NO3        |
| Vissi                     | NO4        |

</details>

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
5. Finn "Strømkalkulator" i listen og klikk "Download"
6. Start Home Assistant på nytt (eller bruk Quick Reload under Developer Tools)

### Manuell installasjon

1. Kopier `custom_components/stromkalkulator` mappen til din `config/custom_components/` mappe
2. Start Home Assistant på nytt

## Konfigurasjon

1. Gå til Settings → Devices & Services
2. Klikk "Add Integration"
3. Søk etter "Strømkalkulator"
4. Velg nettselskap (f.eks BKK)
5. Velg din strømforbruk-sensor (f.eks. Tibber Pulse)
6. Velg Nord Pool **"Current price"** sensor (f.eks. `sensor.nord_pool_no5_current_price`)

**Viktig:** Velg "Current price" - IKKE "Today lowest" eller "Today average". "Current price" gir deg spotprisen for nåværende time, som er korrekt for strømstøtte-beregninger.

![integration](./integration.png)

### Sensors Dashboard

![Nettleie](./sensor_nettleie.png)
![Strømstøtte](./sensor_strømstøtte.png)
![Norgespris](./sensor_norgespris.png)

## Sensorer

### Nettleie - Kapasitet

| Sensor                        | Beskrivelse                                  |
|-------------------------------|----------------------------------------------|
| `sensor.kapasitetstrinn`      | Kapasitetsledd i kr/mnd                      |
| `sensor.trinn_nummer`         | Kapasitetstrinn-nummer (1-10)                |
| `sensor.trinn_intervall`      | Kapasitetstrinn-intervall (f.eks. "5-10 kW") |
| `sensor.gjennomsnitt_forbruk` | Snitt av topp 3 forbruksdager (kW)           |
| `sensor.maks_forbruk_1`       | Toppforbruk #1 denne måneden (kW)            |
| `sensor.maks_forbruk_2`       | Toppforbruk #2 denne måneden (kW)            |
| `sensor.maks_forbruk_3`       | Toppforbruk #3 denne måneden (kW)            |

### Nettleie - Energiledd

| Sensor                       | Beskrivelse                              |
|------------------------------|------------------------------------------|
| `sensor.energiledd`          | Energiledd i NOK/kWh (varierer dag/natt) |
| `sensor.offentlige_avgifter` | Forbruksavgift + Enova-avgift inkl. mva  |

### Strømpriser

| Sensor                             | Beskrivelse                                      |
|------------------------------------|--------------------------------------------------|
| `sensor.total_price`               | Total strømpris FØR støtte (spotpris + nettleie) |
| `sensor.electricity_company_total` | Total strømpris fra strømavtale + nettleie       |

### Strømstøtte

| Sensor                           | Beskrivelse                                     |
|----------------------------------|-------------------------------------------------|
| `sensor.stromstotte`             | Strømstøtte per kWh (90% over terskel)          |
| `sensor.spotpris_etter_stotte`   | Spotpris etter strømstøtte                      |
| `sensor.total_pris_etter_stotte` | Total strømpris ETTER støtte (dette betaler du) |

### Norgespris

| Sensor                            | Beskrivelse                                       |
|-----------------------------------|---------------------------------------------------|
| `sensor.total_pris_norgespris`    | Total pris med Norgespris (50 øre/kWh + nettleie) |
| `sensor.prisforskjell_norgespris` | Forskjell mellom din pris og Norgespris           |

### Sensor-attributter

Hver sensor har ekstra attributter som gir mer detaljer. Disse kan brukes i templates og automatiseringer.

<details>
<summary>Klikk for å se alle attributter</summary>

#### Kapasitetstrinn (`sensor.kapasitetstrinn`)
| Attributt                  | Beskrivelse                   |
|----------------------------|-------------------------------|
| `trinn`                    | Kapasitetstrinn-nummer (1-10) |
| `intervall`                | Intervall (f.eks. "5-10 kW")  |
| `gjennomsnitt_kw`          | Snitt av topp 3 dager         |
| `current_power_kw`         | Nåværende forbruk             |
| `maks_1_dato`, `maks_1_kw` | Dato og verdi for toppdag #1  |
| `maks_2_dato`, `maks_2_kw` | Dato og verdi for toppdag #2  |
| `maks_3_dato`, `maks_3_kw` | Dato og verdi for toppdag #3  |
| `tso`                      | Nettselskap                   |

#### Energiledd (`sensor.energiledd`)
| Attributt         | Beskrivelse             |
|-------------------|-------------------------|
| `is_day_rate`     | `true` hvis dagpris     |
| `rate_type`       | "dag" eller "natt/helg" |
| `energiledd_dag`  | Dagpris (NOK/kWh)       |
| `energiledd_natt` | Nattpris (NOK/kWh)      |
| `tso`             | Nettselskap             |

#### Total strømpris (`sensor.total_price`)
| Attributt                | Beskrivelse            |
|--------------------------|------------------------|
| `spot_price`             | Spotpris fra Nord Pool |
| `energiledd`             | Energiledd (NOK/kWh)   |
| `kapasitetsledd_per_kwh` | Kapasitetsledd per kWh |
| `tso`                    | Nettselskap            |

#### Strømstøtte (`sensor.stromstotte`)
| Attributt      | Beskrivelse        |
|----------------|--------------------|
| `spotpris`     | Nåværende spotpris |
| `terskel`      | 0.70 (70 øre/kWh)  |
| `dekningsgrad` | "90%"              |

#### Total strømpris etter støtte (`sensor.total_pris_etter_stotte`)
| Attributt                | Beskrivelse            |
|--------------------------|------------------------|
| `spotpris`               | Spotpris               |
| `stromstotte`            | Strømstøtte beløp      |
| `spotpris_etter_stotte`  | Spotpris minus støtte  |
| `energiledd`             | Energiledd             |
| `kapasitetsledd_per_kwh` | Kapasitetsledd per kWh |

#### Toppforbruk (`sensor.maks_forbruk_1/2/3`)
| Attributt | Beskrivelse              |
|-----------|--------------------------|
| `dato`    | Datoen for toppforbruket |

#### Offentlige avgifter (`sensor.offentlige_avgifter`)
| Attributt                 | Beskrivelse                                         |
|---------------------------|-----------------------------------------------------|
| `avgiftssone`             | Valgt avgiftssone (standard/nord_norge/tiltakssone) |
| `sesong`                  | Gjeldende sesong (vinter/sommer)                    |
| `forbruksavgift_eks_mva`  | Forbruksavgift uten mva                             |
| `forbruksavgift_inkl_mva` | Forbruksavgift med mva                              |
| `enova_avgift_eks_mva`    | Enova-avgift uten mva                               |
| `enova_avgift_inkl_mva`   | Enova-avgift med mva                                |
| `mva_sats`                | MVA-sats (0% eller 25%)                             |
| `note`                    | Forklaring                                          |

</details>

## Hvilken strømpris-sensor bør du bruke?

### Anbefalte sensorer for vanlig bruk:

| Bruksområde                | Anbefalt sensor                  | Hvorfor?                                                           |
|----------------------------|----------------------------------|--------------------------------------------------------------------|
| **Din faktiske strømpris** | `sensor.total_pris_etter_stotte` | Viser hva du faktisk betaler per kWh inkl. nettleie og strømstøtte |
| **Strømstøtte**            | `sensor.stromstotte`             | Viser hvor mye du får tilbake per kWh                              |
| **Spotpris**               | `sensor.spotpris_etter_stotte`   | Spotpris etter strømstøtte, uten nettleie                          |

### For spesielle behov:

| Situasjon                          | Sensor                             | Forklaring                    |
|------------------------------------|------------------------------------|-------------------------------|
| **Har strømselskap**               | `sensor.electricity_company_total` | Total strømpris (strømavtale) |
| **Vil sammenligne med norgespris** | `sensor.total_pris_norgespris`     | Total strømpris (norgespris)  |
| **Vil se prisforskjell**           | `sensor.prisforskjell_norgespris`  | Prisforskjell (norgespris)    |

### Om Norgespris-sensorer
`sensor.total_pris_norgespris` 

- Fast pris: 50 øre/kWh (inkl. mva)
- Kan **IKKE** kombineres med strømstøtte
- Gjelder for strømforbruk hjemme og på hytte

`sensor.prisforskjell_norgespris`

- **Positiv verdi**: Du betaler mer enn norgespris (norgespris er billigere)
- **Negativ verdi**: Du betaler mindre enn norgespris (din avtale er billigere)


## Konfigurasjonsfelt

| Felt                         | Beskrivelse                                                                                           | Påkrevd |
|------------------------------|-------------------------------------------------------------------------------------------------------|:-------:|
| **Nettselskap**              | Velg ditt nettselskap fra listen, eller "Egendefinert" for manuelle priser                            |   Ja    |
| **Avgiftssone**              | Velg avgiftssone for korrekt forbruksavgift og MVA (se tabell under)                                  |   Ja    |
| **Strømforbruk-sensor**      | Sensor som viser nåværende strømforbruk i W (f.eks. Tibber Pulse)                                     |   Ja    |
| **Spotpris-sensor**          | Nord Pool "Current price" sensor (f.eks. `sensor.nord_pool_no5_current_price`)                        |   Ja    |
| **Strømselskap-pris-sensor** | Sensor fra strømselskap med total pris (f.eks. Tibber). Brukes for `sensor.electricity_company_total` |   Nei   |
| **Energiledd dag**           | Manuell energiledd-pris for dag (kun ved "Egendefinert")                                              |   Nei   |
| **Energiledd natt**          | Manuell energiledd-pris for natt/helg (kun ved "Egendefinert")                                        |   Nei   |

### Avgiftssoner

Avgiftssonen bestemmer hvilken forbruksavgift og MVA-sats som brukes i beregningene.

| Avgiftssone      | Forbruksavgift (2026) | MVA | Gjelder                                  |
|------------------|----------------------|-----|------------------------------------------|
| **Standard**     | 7,13 øre/kWh         | 25% | Sør-Norge (NO1, NO2, NO5)                |
| **Nord-Norge**   | 7,13 øre/kWh         | 0%  | Nordland og Troms (unntatt tiltakssonen) |
| **Tiltakssonen** | Fritak               | 0%  | Finnmark + 7 kommuner i Nord-Troms       |

**Nytt fra 2026:** Forbruksavgiften er nå lik for Standard og Nord-Norge (7,13 øre/kWh). Forskjellen mellom sonene er primært MVA-fritak.

**Velg riktig avgiftssone:**
- Bor du i Sør-Norge → **Standard**
- Bor du i Nordland eller Troms → **Nord-Norge** (MVA-fritak)
- Bor du i Finnmark, Kåfjord, Skjervøy, Nordreisa, Kvænangen, Karlsøy, Lyngen eller Storfjord → **Tiltakssonen**

Se [beregninger.md](beregninger.md) for detaljert informasjon om avgiftssoner og satser.

## Bidra

Vil du legge til støtte for ditt nettselskap? Følg guiden under og opprett en PR!

### Legge til nytt nettselskap (TSO)

1. Åpne `custom_components/stromkalkulator/const.py`
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
- `url` skal peke til nettselskapets offisielle prisside
- Siste trinn bruker `float("inf")` som øvre grense