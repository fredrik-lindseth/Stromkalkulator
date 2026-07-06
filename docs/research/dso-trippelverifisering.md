# Trippelverifisering av DSO-tariffer 2026

Sjekk av flaggede feil i `dso.py` mot tre uavhengige kilder per
nettselskap. Verdier i `dso.py` er **ren nettleie eks. mva og eks.
forbruksavgift/Enova** for energiledd, og **kr/mnd inkl. mva** for
kapasitetsledd.

Hentet 2026-05-23.

## Konklusjoner

| DSO | Status | Endring |
|---|---|---|
| Lnett | Feil bekreftet | Energiledd + manglende trinn 7-10 |
| Lede | Feil bekreftet | Energiledd + kapasitetstrinn 9-10 % for høyt |
| Norgesnett | Ingen feil | Tidligere flagging var feil, eksisterende verdi stemmer |
| Asker Nett | Ingen feil | Tariff matcher 2026 |
| Elvia | Feil bekreftet | Kapasitetstrinn 6-10 |

## Lnett (NO2)

**Kilder:**
- Primær: [Lnett tariffhefte 2026 PDF (siteid 131569206)](https://www.l-nett.no/getfile.php/131569206-1764934863/Tariffhefte%20fra%201.%20januar%202026.pdf)
- Sekundær: [Lnett HTML prisside](https://www.l-nett.no/nettleie/priser-og-vilkar-privat/)
- Tertiær: [kraftsystemet.no/lnett](https://kraftsystemet.no/fri-nettleie/tariffer/lnett.html)

### Energiledd (øre/kWh eks. mva og avgifter)

| Sats | Vår dso.py | Primær (PDF) | Sekundær (HTML) | Tertiær | Valgt |
|---|---|---|---|---|---|
| Dag | 17,47 | 25,60 | 25,60 | 25,60 | **25,60** |
| Natt | 5,47 | 13,60 | 13,60 | 13,60 | **13,60** |

### Kapasitetsledd (kr/mnd inkl. mva)

| Trinn | kW | Vår dso.py | Primær | Sekundær | Tertiær | Valgt |
|---|---|---|---|---|---|---|
| 1 | 0-2 | 150 | 150 | 150 | 150 | 150 |
| 2 | 2-5 | 250 | 250 | 250 | 250 | 250 |
| 3 | 5-10 | 400 | 400 | 400 | 400 | 400 |
| 4 | 10-15 | 650 | 650 | 650 | 650 | 650 |
| 5 | 15-20 | 900 | 900 | 900 | 900 | 900 |
| 6 | 20-25 | 1150 | 1150 | 1150 | 1150 | 1150 |
| 7 | 25-50 | mangler | 2150 | (kun PDF) | 2150 | **2150** |
| 8 | 50-75 | mangler | 3150 | (kun PDF) | 3150 | **3150** |
| 9 | 75-100 | mangler | 4150 | (kun PDF) | 4150 | **4150** |
| 10 | 100+ | mangler | 7000 | (kun PDF) | 7000 | **7000** |

HTML-prisliste viser bare trinn 1-6, PDF og kraftsystemet bekrefter trinn
7-10. Tre kilder enige.

## Lede (NO2)

**Kilder:**
- Primær: [Lede prisside privatkunder](https://lede.no/priser/nettleie-privatkunder/)
- Sekundær: [Lede prisside oversikt](https://lede.no/priser/)
- Tertiær: [kraftsystemet.no/lede](https://kraftsystemet.no/fri-nettleie/tariffer/lede.html)

### Energiledd (øre/kWh eks. mva og avgifter)

| Sats | Vår dso.py | Primær (HTML) | Sekundær | Tertiær (kraftsystemet) | Valgt |
|---|---|---|---|---|---|
| Flat | 24,382 | 14,26 (inkl. mva ÷ 1,25 = 11,408) | ikke spesifisert | 11,41 (u/ avgifter) | **11,41** |

Lede oppgir 14,26 øre/kWh merket "ekskl. mva" på egen side, men merkingen
stemmer ikke: 11,41 × 1,25 = 14,26, så tallet er inkl. mva og ekskl.
avgifter. Kraftsystemet.no detaljerer alle nivåer eksplisitt:
11,41 u/ avgifter, 12,41 m/ Enova, 19,54 m/ Enova og forbruksavgift, 24,42
m/ alle avgifter og mva.

Matematisk verifikasjon: (11,41 + 1,0 + 7,13) × 1,25 = 24,425 ≈ 24,42
matcher Lede-faktura. Tre kilder enige om at ren nettleie er **11,41
øre/kWh**.

Vår eksisterende verdi 24,382 er prisen **inkl. mva og avgifter**, ikke
ren nettleie. Feil semantikk.

### Kapasitetsledd (kr/mnd inkl. mva)

| kW | Vår dso.py | Primær (Lede HTML) | Sekundær (kraftsystemet, årspris inkl. mva ÷ 12) | Valgt |
|---|---|---|---|---|
| 0-5 | 294 | 268,75 | 3225/12 = 268,75 | **269** |
| 5-10 | 503 | 458,75 | 5505/12 = 458,75 | **459** |
| 10-15 | 708 | 647,50 | 7770/12 = 647,50 | **648** |
| 15-20 | 916 | 837,50 | 10050/12 = 837,50 | **838** |
| 20-25 | 1124 | 1027,50 | 12330/12 = 1027,50 | **1028** |
| 25-50 | 1746 | 1596,25 | 19155/12 = 1596,25 | **1596** |
| 50-75 | mangler | (eget prisark) | 30540/12 = 2545,00 | **2545** |
| 75-100 | mangler | (eget prisark) | 41910/12 = 3492,50 | **3493** |
| 100-150 | mangler | (eget prisark) | 58980/12 = 4915,00 | **4915** |
| 150-200 | mangler | (eget prisark) | 81720/12 = 6810,00 | **6810** |
| 200+ | mangler | (eget prisark) | 115860/12 = 9655,00 | **9655** |

Lede HTML viser tier 0-50 kW direkte. Kraftsystemet gir alle 11 trinn.
Tre kilder enige der de overlapper.

## Norgesnett (NO1), Ingen endring

**Kilder:**
- Primær: [Norgesnett kunde-prisside](https://norgesnett.no/kunde/nettleie-privat/)
- Sekundær: [Norgesnett PDF 2026](https://norgesnett.no/wp-content/uploads/Nettleiepriser-privat-naering-1.jan-2026.pdf) (begrenset til avgiftsinfo)
- Tertiær: [kraftsystemet.no/norgesnett](https://kraftsystemet.no/fri-nettleie/tariffer/norgesnett.html)

### Energiledd (øre/kWh eks. mva og avgifter)

| Sats | Vår dso.py | Primær (HTML, inkl. alt) | Beregnet eks. mva og avgifter | Tertiær | Valgt |
|---|---|---|---|---|---|
| Dag | 20,262 | 35,49 inkl. alt | (35,49/1,25) - 7,13 - 1,0 = 20,262 | 20,26 | **20,262** |
| Natt | 13,286 | 26,77 inkl. alt | (26,77/1,25) - 7,13 - 1,0 = 13,286 | 13,29 | **13,286** |

Tidligere tolkning leste 35,49 / 26,77 som "eks. mva" og kom til 27,36/18,64.
Norgesnetts egen side er entydig: "Disse prisene inneholder forbruksavgift
(8,9125 øre/kWh), Enova-avgift (1,25 øre/kWh), og 25% mva." Vår verdi er
korrekt, ingen endring.

### Kapasitetsledd

Alle 10 trinn matcher Norgesnetts egen tabell innenfor 1 kr/mnd (vi har
avrundet til hele kroner; Norgesnett oppgir desimaler).

## Asker Nett (NO1), Ingen endring

**Kilder:**
- Primær: [Asker Nett prisliste 2026](https://askernett.no/prisliste-for-privatkunder-i-2026/)
- Sekundær: [Asker Nett prisjustering 2026](https://askernett.no/prisjustering-pa-nettleien-fra-1-januar-2026/)
- Tertiær: websøk-bekreftelse

### Energiledd

| Sats | Vår dso.py | Primær (inkl. alt) | Beregnet eks. mva og avgifter | Valgt |
|---|---|---|---|---|
| Dag | 23,87 | 40,00 | (40/1,25) - 7,13 - 1,0 = 23,87 | **23,87** |
| Natt | 15,87 | 30,00 | (30/1,25) - 7,13 - 1,0 = 15,87 | **15,87** |

Alle 10 kapasitetstrinn matcher Asker Nett-siden eksakt. Vår dso.py er
korrekt.

## Elvia (NO1)

**Kilder:**
- Primær: [Elvia tariffblad 2026 PDF](https://www.elvia.no/siteassets/dokumenter/priser/2026/tariffblad_1_0_standard-tariff_privat_20260101.pdf)
- Sekundær: [Elvia HTML prisside](https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/)
- Tertiær: [kraftsystemet.no/elvia](https://kraftsystemet.no/fri-nettleie/tariffer/elvia.html)

### Energiledd

| Sats | Vår dso.py | Primær (PDF) | Beregnet eks. mva og avgifter | Valgt |
|---|---|---|---|---|
| Dag | 20,99 | 36,40 inkl. alt | (36,40/1,25) - 7,13 - 1,0 = 20,99 | **20,99** |
| Natt | 12,99 | 26,40 inkl. alt | (26,40/1,25) - 7,13 - 1,0 = 12,99 | **12,99** |

### Kapasitetsledd (kr/mnd inkl. mva)

| Trinn | kW | Vår dso.py | Primær (PDF) | Sekundær (HTML) | Tertiær | Valgt |
|---|---|---|---|---|---|---|
| 1 | 0-2 | 125 | 125 | 125 | 125 | 125 |
| 2 | 2-5 | 190 | 190 | 190 | 190 | 190 |
| 3 | 5-10 | 300 | 300 | 300 | 300 | 300 |
| 4 | 10-15 | 410 | 410 | 410 | 410 | 410 |
| 5 | 15-20 | 520 | 520 | 520 | 520 | 520 |
| 6 | 20-25 | 655 | **630** | (PDF-referert) | 630 | **630** |
| 7 | 25-50 | 1135 | **1175** | (PDF-referert) | 1175 | **1175** |
| 8 | 50-75 | 1750 | **1720** | (PDF-referert) | 1720 | **1720** |
| 9 | 75-100 | 2370 | **2270** | (PDF-referert) | 2270 | **2270** |
| 10 | 100+ | 4225 | **4570** | (PDF-referert) | 4570 | **4570** |

Trinn 1-5 enige på tvers av kilder. Trinn 6-10 avviker mellom vår dso.py
og PDF, PDF og kraftsystemet enige. PDF har dato `20260101` i URL og
oppgir eksplisitt "Tariffer gjeldende fra: 01.01.2026". Velger PDF-tall.

## Avgifter (uendret)

- Forbruksavgift alminnelig: 7,13 øre/kWh eks. mva (8,9125 inkl. mva)
- Enova: 1,0 øre/kWh eks. mva (1,25 inkl. mva)
- Mva: 25 % (gjelder ikke Nord-Norge/tiltakssone)

PDF-er fra Lnett, Norgesnett og Glitre flagger at 2026-avgiftene "ikke er
vedtatt" formelt. Skatteetaten oppgir 7,13 som gjeldende, beholder
const.py uendret.
