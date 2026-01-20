# Beregninger i Nettleie

Dokumentasjon av hvordan alle beregninger utføres i Nettleie-integrasjonen.

Integrasjonen beregner:
- **Nettleie** - Kapasitetsledd og energiledd fra ditt nettselskap
- **Strømstøtte** - Automatisk beregning av statlig strømstøtte
- **Norgespris** - Sammenligning med Elhubs fastprisprodukt
- **Offentlige avgifter** - Forbruksavgift, Enova-avgift og mva

## Nettleie

Nettleien består av to deler: kapasitetsledd og energiledd.

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
Kapasitetstrinn: 2-5 kW → 250 kr/mnd
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

#### Fastledd per kWh

Kapasitetsleddet omregnes til per kWh:

```
fastledd_per_kwh = (kapasitetsledd / dager_i_måned) / 24
```

**Eksempel:**
```
Kapasitetsledd: 400 kr/mnd
Dager i måned: 30
fastledd_per_kwh = (400 / 30) / 24 = 0.56 kr/kWh
```

### Energiledd

Energileddet varierer basert på tidspunkt:

- **Dag**: Mandag-fredag 06:00-22:00 (ikke helligdager)
- **Natt/Helg**: 22:00-06:00, helger og helligdager

## Offentlige avgifter

Energileddet fra nettselskapet inkluderer følgende offentlige avgifter:

### Enova-avgift
- **Sats**: 1,0 øre/kWh eks. mva (fast)
- Går til Enova SF for energieffektivisering
- Gjelder hele landet

### Forbruksavgift (elavgift)

Fra 2026 er forbruksavgiften forenklet med flat sats hele året (ingen sesongvariasjon).

#### Satser for 2026 (husholdninger)

| Område | Sats | Merknad |
|--------|------|---------|
| Sør-Norge (NO1, NO2, NO5) | 7,13 øre/kWh | Alminnelig sats |
| Nord-Norge (NO3, NO4) | 7,13 øre/kWh | Alminnelig sats (samme som Sør-Norge fra 2026) |
| Tiltakssonen | 0 øre/kWh | Fritak for husholdninger |

#### Hva er nytt fra 2026?

Før 2026 var det:
- **Sesongvariasjon**: Høyere sats om vinteren (jan-mar), lavere om sommeren (apr-des)
- **Geografisk forskjell**: Nord-Norge hadde redusert sats sammenlignet med Sør-Norge

Fra 2026:
- **Flat sats hele året**: 7,13 øre/kWh (ingen sesongvariasjon)
- **Lik sats for alle husholdninger**: Ingen forskjell mellom Sør-Norge og Nord-Norge
- **Tiltakssonen beholder fritak**: Husholdninger i Finnmark og Nord-Troms har fortsatt fritak

#### Historiske satser (for referanse)

| År | Sør-Norge (vinter) | Sør-Norge (sommer) | Nord-Norge |
|----|--------------------|--------------------|------------|
| 2025 | 15,41 øre | 9,91 øre | 9,16 øre |
| 2026 | 7,13 øre | 7,13 øre | 7,13 øre |

**Kilde:** [Skatteetaten - Avgift på elektrisk kraft](https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/saravgifter/om/elektrisk-kraft/)

**For oppdaterte satser:** [Skatteetaten - Satser elektrisk kraft](https://www.skatteetaten.no/satser/elektrisk-kraft/)

### Merverdiavgift (mva)

MVA-satsen varierer basert på geografisk område:

| Område               | MVA-sats    |
|----------------------|-------------|
| Sør-Norge (standard) | 25%         |
| Nord-Norge           | 0% (fritak) |
| Tiltakssonen         | 0% (fritak) |

## Avgiftssoner

Integrasjonen støtter tre avgiftssoner som påvirker beregning av forbruksavgift og MVA.

**Merk:** Fra 2026 er forbruksavgiften lik for Standard og Nord-Norge (7,13 øre/kWh). Forskjellen mellom sonene er nå primært MVA-fritak.

### Standard (Sør-Norge)

Gjelder prisområdene NO1, NO2 og NO5.

- **Forbruksavgift**: 7,13 øre/kWh eks. mva (2026)
- **MVA**: 25%

### Nord-Norge

Gjelder prisområdene NO3 og NO4, unntatt kommuner i tiltakssonen.

- **Forbruksavgift**: 7,13 øre/kWh eks. mva (2026, samme som Sør-Norge)
- **MVA**: 0% (fritak)

Merverdiavgiftsfritaket for Nord-Norge ble innført i 2024 og gjelder:
- Nordland fylke
- Troms fylke (unntatt tiltakssonen)

### Tiltakssonen

Tiltakssonen har fritak for både forbruksavgift og MVA på elektrisk kraft.

- **Forbruksavgift**: 0 øre/kWh (fritak)
- **MVA**: 0% (fritak)

#### Kommuner i tiltakssonen

Tiltakssonen omfatter hele Finnmark fylke, samt følgende kommuner i Nord-Troms:

| Kommune       | Fylke    |
|---------------|----------|
| Hele Finnmark | Finnmark |
| Kåfjord       | Troms    |
| Skjervøy      | Troms    |
| Nordreisa     | Troms    |
| Kvænangen     | Troms    |
| Karlsøy       | Troms    |
| Lyngen        | Troms    |
| Storfjord     | Troms    |

**Kilde:** [Regjeringen - Tiltakssonen](https://www.regjeringen.no/no/tema/kommuner-og-regioner/regional--og-distriktspolitikk/Tiltakssonen-for-Finnmark-og-Nord-Troms/id2362289/)

### Eksempel: Totale avgifter per sone (2026)

Fra 2026 er det flat sats hele året (ingen sesongforskjell).

| Avgiftssone  | Forbruksavgift | Enova    | Sum eks. mva | MVA | **Sum inkl. mva** |
|--------------|----------------|----------|--------------|-----|-------------------|
| Standard     | 7,13 øre       | 1,00 øre | 8,13 øre     | 25% | **10,16 øre/kWh** |
| Nord-Norge   | 7,13 øre       | 1,00 øre | 8,13 øre     | 0%  | **8,13 øre/kWh**  |
| Tiltakssonen | 0 øre          | 1,00 øre | 1,00 øre     | 0%  | **1,00 øre/kWh**  |

**Merk:** Forskjellen mellom Standard og Nord-Norge er nå kun MVA (2,03 øre/kWh).

### Formel (2026)

```python
# Satser 2026
FORBRUKSAVGIFT_ALMINNELIG = 0.0713  # 7,13 øre/kWh (husholdninger)
ENOVA_AVGIFT = 0.01                  # 1,00 øre/kWh

def get_forbruksavgift(avgiftssone: str, month: int) -> float:
    """Returnerer forbruksavgift i NOK/kWh.
    
    Fra 2026: Flat sats hele året (month-parameter ikke lenger brukt).
    """
    if avgiftssone == "tiltakssone":
        return 0.0  # Fritak for husholdninger
    # Standard og Nord-Norge har samme sats fra 2026
    return 0.0713  # 7,13 øre/kWh

def get_mva_sats(avgiftssone: str) -> float:
    """Returnerer MVA-sats (0.0 eller 0.25)."""
    if avgiftssone in ("nord_norge", "tiltakssone"):
        return 0.0  # MVA-fritak
    return 0.25     # 25% MVA
```

**Merk:** Disse avgiftene er allerede inkludert i energiledd-prisene fra nettselskapene. Sensoren "Offentlige avgifter" viser dem separat for informasjonsformål.

#### Helligdager

Følgende dager regnes som natt/helg-rate (lavere pris):

**Faste helligdager:**
- 1. januar (Nyttårsdag)
- 1. mai (Arbeidernes dag)
- 17. mai (Grunnlovsdag)
- 25. desember (1. juledag)
- 26. desember (2. juledag)

**Bevegelige helligdager (oppdateres årlig):**
- Skjærtorsdag, Langfredag, 1. og 2. påskedag
- Kristi himmelfartsdag
- 1. og 2. pinsedag

## Total strømpris

### Uten strømstøtte
```
total_pris = spotpris + energiledd + fastledd_per_kwh
```

### Med strømstøtte
```
total_pris_etter_stotte = (spotpris - strømstøtte) + energiledd + fastledd_per_kwh
```

## Strømselskap-pris

Hvis du har konfigurert en pris-sensor fra strømselskapet (f.eks. Tibber), beregnes totalpris slik:

```
electricity_company_total = strømselskap_pris + energiledd + fastledd_per_kwh
```

**Merk:** Strømselskap-prisen inkluderer ofte spotpris + påslag + evt. mva. Denne sensoren legger til nettleie (energiledd + kapasitetsledd) på toppen.

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

## Komplett eksempel

**Forutsetninger:**
- Spotpris: 1.20 NOK/kWh
- Energiledd (dag): 0.4613 NOK/kWh
- Kapasitetsledd: 400 kr/mnd
- Dager i måned: 30
- Avgiftssone: Standard (Sør-Norge)

**Beregninger:**
1. **Fastledd per kWh**: (400 / 30) / 24 = 0.56 NOK/kWh
2. **Strømstøtte**: (1.20 - 0.70) * 0.90 = 0.45 NOK/kWh
3. **Totalpris uten støtte**: 1.20 + 0.4613 + 0.56 = 2.22 NOK/kWh
4. **Totalpris med støtte**: (1.20 - 0.45) + 0.4613 + 0.56 = 1.77 NOK/kWh

**Offentlige avgifter (inkludert i energileddet, 2026-satser):**
- Forbruksavgift: 7,13 øre/kWh eks. mva
- Enova-avgift: 1,00 øre/kWh eks. mva
- Sum eks. mva: 8,13 øre/kWh
- MVA (25%): 2,03 øre/kWh
- **Sum inkl. mva: 10,16 øre/kWh**

## Sammenligning av avgiftssoner (2026)

Dette eksempelet viser hvordan samme strømforbruk gir ulik totalpris avhengig av avgiftssone.

**Felles forutsetninger:**
- Spotpris: 1.50 NOK/kWh
- Energiledd (dag): 0.45 NOK/kWh (eks. avgifter for sammenligning)
- Kapasitetsledd: 400 kr/mnd → 0.56 NOK/kWh
- Forbruk: 1000 kWh

### Steg 1: Beregn strømstøtte (lik for alle)

```
Strømstøtte = (1.50 - 0.70) * 0.90 = 0.72 NOK/kWh
Spotpris etter støtte = 1.50 - 0.72 = 0.78 NOK/kWh
```

### Steg 2: Beregn avgifter per sone (2026-satser)

| Komponent | Standard | Nord-Norge | Tiltakssonen |
|-----------|----------|------------|--------------|
| Forbruksavgift eks. mva | 7,13 øre | 7,13 øre | 0 øre |
| Enova-avgift eks. mva | 1,00 øre | 1,00 øre | 1,00 øre |
| Sum eks. mva | 8,13 øre | 8,13 øre | 1,00 øre |
| MVA-sats | 25% | 0% | 0% |
| **Avgifter inkl. mva** | **10,16 øre** | **8,13 øre** | **1,00 øre** |

### Steg 3: Beregn totalpris per kWh

| Komponent | Standard | Nord-Norge | Tiltakssonen |
|-----------|----------|------------|--------------|
| Spotpris etter støtte | 0.78 kr | 0.78 kr | 0.78 kr |
| Energiledd | 0.45 kr | 0.45 kr | 0.45 kr |
| Kapasitetsledd per kWh | 0.56 kr | 0.56 kr | 0.56 kr |
| Avgifter (inkl. i energiledd) | 0.1016 kr | 0.0813 kr | 0.0100 kr |
| **Totalpris per kWh** | **1.79 kr** | **1.77 kr** | **1.79 kr** |

**Merk:** Energileddet fra nettselskapet inkluderer allerede avgiftene, så de varierer mellom nettselskaper i ulike soner. Tabellen over viser komponentene separat for å illustrere forskjellen.

### Steg 4: Beregn månedskostnad (1000 kWh)

For å se den reelle besparelsen må vi se på hva nettselskapene faktisk tar i energiledd. Her er et realistisk eksempel med 2026-satser:

| Avgiftssone | Energiledd (reelt) | Totalpris/kWh | Månedskostnad (1000 kWh) |
|-------------|-------------------|---------------|--------------------------|
| Standard (BKK) | 0.4613 kr | 1.80 kr | **1 800 kr** |
| Nord-Norge (Arva) | 0.3119 kr | 1.65 kr | **1 650 kr** |
| Tiltakssonen (hypotetisk) | 0.20 kr | 1.54 kr | **1 540 kr** |

**Besparelse sammenlignet med Standard:**
- Nord-Norge: 150 kr/mnd (1 800 kr/år) - primært pga. MVA-fritak
- Tiltakssonen: 260 kr/mnd (3 120 kr/år) - pga. fritak for både forbruksavgift og MVA

### Forklaring av forskjellen (2026)

Fra 2026 er forbruksavgiften lik for Standard og Nord-Norge. Forskjellen skyldes nå primært:

1. **MVA-fritak**
   - Standard: 25% MVA på alle komponenter
   - Nord-Norge: 0% MVA (fritak fra 2024)
   - Tiltakssonen: 0% MVA (fritak)

2. **Forbruksavgift**
   - Standard og Nord-Norge: 7,13 øre/kWh (lik sats fra 2026)
   - Tiltakssonen: 0 øre/kWh (fritak for husholdninger)

3. **Praktisk effekt**
   - Nord-Norge sparer ca. 2 øre/kWh sammenlignet med Standard (kun MVA-forskjell)
   - Tiltakssonen sparer ca. 9 øre/kWh sammenlignet med Standard

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

## Noter

- Alle priser er i NOK/kWh
- Strømforbruk konverteres fra W til kW (/1000)
- Beregningene følger norske regler for strømstøtte
- Kapasitetstrinn varierer mellom nettselskaper
- Norgespris er fast 50 øre/kWh fra Elhub (ingen strømstøtte)
