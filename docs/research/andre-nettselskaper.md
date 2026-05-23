# Verifisering av andre nettselskaper enn BKK

Forsker på presisjon for de største nettselskapene utenom BKK. Kun BKK er
verifisert mot faktura. Andre er sjekket mot publiserte tariffer 2026.

Hentet 2026-05-23 fra DSO-ene egne sider og kraftsystemet.no.

## Hovedfunn

Vi treffer godt på de aller største (Elvia, Tensio TS, Tensio TN, Glitre).
Lnett og Lede har vesentlig feil priser i `dso.py`, vi har antakelig
gamle tall (2024 eller tidligere).

Ingen avvik på avregningsmodell: alle store DSO-er bruker "snitt av de
tre høyeste døgnmaks" eller "snitt av tre høyeste timer i forskellige
døgn", funksjonelt identisk med vår implementasjon i
`_get_top_3_days()` + `_handle_month_rollover()`.

## Per nettselskap

### Elvia (NO1) - Norges største

Kilde: [Tariffblad 1.0 standard tariff privat 2026-01-01 (PDF)](https://www.elvia.no/siteassets/dokumenter/priser/2026/tariffblad_1_0_standard-tariff_privat_20260101.pdf)

**Energiledd:** match
- Dag (inkl. alt): 36,40 øre/kWh. Vår dag eks. mva eks. avgifter: 20,99 -> regnet
  ut blir det 20,99 + 8,13 = 29,12 eks. mva -> 36,40 inkl. mva. Stemmer.
- Natt/helg (inkl. alt): 26,40 -> 12,99 ren nettleie. Stemmer.

**Tidspunkter:** dag hverdager 06-22, natt hverdager 22-06, helg lørdag/
søndag/helligdager hele døgnet. Match med `_is_day_rate()`.

**Kapasitetstrinn:** AVVIK på trinn 6-10
| Trinn | kW | Elvia 2026 | Vår dso.py | Diff   |
|-------|----|------------|------------|--------|
| 1     | 0-2 | 125       | 125        | 0      |
| 2     | 2-5 | 190       | 190        | 0      |
| 3     | 5-10 | 300      | 300        | 0      |
| 4     | 10-15 | 410     | 410        | 0      |
| 5     | 15-20 | 520     | 520        | 0      |
| 6     | 20-25 | 630     | 655        | +25    |
| 7     | 25-50 | 1 175   | 1 135      | -40    |
| 8     | 50-75 | 1 720   | 1 750      | +30    |
| 9     | 75-100 | 2 270  | 2 370      | +100   |
| 10    | 100+ | 4 570    | 4 225      | -345   |

Kommentaren i dso.py:108 sier trinn 6-10 er "fra PDF
tariffblad_1_0_standard-tariff_privat_20260101.pdf" - men tallene
matcher ikke aktuell PDF. Enten leste vi feil eller PDFen har endret seg.

**Avregning:** "Gjennomsnittet av de tre høyeste døgnmaksene i måneden" -
match med vår `_get_top_3_days()`. Døgnmaks = "klokketimen i løpet av et
døgn med høyest kWh-forbruk" - match med vårt `_current_hour_energy`.

### Tensio TN (NO3) - Trøndelag nord

Kilde: [Tensio nettleiepriser privat](https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat),
[kraftsystemet.no Tensio TN](https://kraftsystemet.no/fri-nettleie/tariffer/tensio-tn.html)

**Energiledd:** match
- Dag: 25,902 øre/kWh eks. mva eks. avgifter (kraftsystemet.no, "u/ alle avgifter")
- Natt: 13,006 øre/kWh eks. mva eks. avgifter
- Vår dso.py: 25,902 / 13,006, match.

**Tidspunkter:** dag 06-22, natt 22-06. Match.

**Helg/helligdag:** Tensios egen side: "Energileddet varierer bare mellom
dag- og nattpris, vi har ikke ulike priser for helg eller helligdager."
Vår `helg_som_natt: False` - match.

**Kapasitetstrinn:** kunne ikke verifisere kr/mnd-tallene direkte fra
Tensios side (vises ikke på nettsiden uten konkrete tabeller). Vi har
beregnet fra kr/år-tabell. Bør verifiseres mot ekte faktura før vi kan
si noe sikkert.

### Tensio TS (NO3) - Trøndelag sør

Kilde: [kraftsystemet.no Tensio TS](https://kraftsystemet.no/fri-nettleie/tariffer/tensio-ts.html)

**Energiledd:** match
- Dag: 20,702 øre/kWh eks. mva eks. avgifter
- Natt: 10,206 øre/kWh eks. mva eks. avgifter
- Vår dso.py: 20,702 / 10,206, match.

**Tidspunkter, helg:** samme som TN.

**Kapasitetstrinn:** samme forbehold som TN.

### Glitre Nett (NO1)

Kilde: [Glitre Nett nettleiepriser privat](https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde)

**Energiledd:** match
- Dag (06-22): 24,6 øre/kWh eks. mva. Vår: 24,598 (avrunding på 0,002 øre, neglisjerbart)
- Natt (22-06): 12,6 øre/kWh eks. mva. Vår: 12,598 (samme)

**Avregning:** "Snittet av de tre høyeste døgnmaksene" - match.

**Helg/helligdag:** Glitres side nevner ikke spesiell helgebehandling, vår
`helg_som_natt: False` - virker riktig, men bør dobbeltsjekkes mot faktura.

**Kapasitetstrinn:** match alle ti trinn.

### Lnett (NO2) - Stavanger-området

Kilde: [Lnett tariffhefte 2026 (PDF)](https://www.l-nett.no/getfile.php/131569206-1764934863/Tariffhefte%20fra%201.%20januar%202026.pdf),
[Lnett priser privat](https://www.l-nett.no/nettleie/priser-og-vilkar-privat/)

**Energiledd:** STORT AVVIK
| | Lnett 2026 | Vår dso.py | Diff       |
|-|-----------|------------|------------|
| Dag eks. mva | 25,60 øre | 17,47 øre | +8,13 øre (~46% feil) |
| Natt eks. mva | 13,60 øre | 5,47 øre | +8,13 øre (~149% feil) |

Avviket på nøyaktig 8,13 øre = forbruksavgift (7,13) + Enova (1,0).
Mistanke: vi har feiltrekt fra avgiftene to ganger, trakk dem ut én gang
men dato-en stemmer ikke. Eller vi har gamle tall.

**Kapasitetstrinn:** AVVIK på høyere trinn
| Trinn | kW | Lnett 2026 | Vår dso.py |
|-------|----|----|------------|
| 1 | 0-2 | 150 | 150 |
| 2 | 2-5 | 250 | 250 |
| 3 | 5-10 | 400 | 400 |
| 4 | 10-15 | 650 | 650 |
| 5 | 15-20 | 900 | 900 |
| 6 | 20-25 | 1 150 | 1 150 |
| 7 | 25-50 | 2 150 | --- (mangler, slutter på 1150) |
| 8 | 50-75 | 3 150 | --- |
| 9 | 75-100 | 4 150 | --- |
| 10 | 100+ | 7 000 | --- |

Vår dso.py:248 har `(float("inf"), 1150)` - alle kunder over 25 kW
faktureres feil i vår implementasjon. Mistolket "20-25 kW" som siste
trinn.

**Avregning:** "Snittet av de tre høyeste timesforbrukene ('døgnmakser')
forrige måned" - match.

### Lede (NO2)

Kilde: [Lede nettleie privatkunder](https://lede.no/priser/nettleie-privatkunder/)

**Energiledd:** AVVIK
- Lede 2026: 14,26 øre/kWh (flat, ingen dag/natt)
- Vår dso.py: 24,382 (flat), **+10,12 øre for høyt**.

Vi har antakelig 2025-tall eller eldre. Verdt å notere: Lede har ikke
dag/natt-differensiering for husholdning (kun for effekttariff på næring).

**Kapasitetstrinn:** AVVIK
| kW | Lede 2026 | Vår dso.py |
|-|-|-|
| 0-5 | 268,75 | 294 |
| 5-10 | 458,75 | 503 |
| 10-15 | 647,50 | 708 |
| 15-20 | 837,50 | 916 |
| 20-25 | 1 027,50 | 1 124 |
| 25-50 | 1 596,25 | 1 746 |

Alle våre tall er ~9-10% for høye. Match med kraftsystemet 2025?
Nettsiden har endret seg ifølge dso.py-kommentaren ("Kilde:
kraftsystemet 2026"), men tallene matcher ikke faktiske 2026-priser.

### Norgesnett (NO1)

Kilde: [Norgesnett nettleie privat](https://norgesnett.no/nettleie-privat/)

**Energiledd:** AVVIK
- Norgesnett 2026 inkl. mva: 44,36 (dag) / 33,46 (natt) øre/kWh
- Inkl. mva -> eks. mva: 35,49 / 26,77 øre/kWh
- Eks. mva -> ren nettleie (-8,13): **27,36 / 18,64** øre/kWh
- Vår dso.py: **20,262 / 13,286**, for lavt med 7+ øre

Antakelig 2025-tall.

## Forbruksavgift 2026 - sjekk const.py

Statsbudsjettet 2026 foreslår 8,9125 øre/kWh inkl. mva = **7,13 øre/kWh
eks. mva**. Skatteetaten bekrefter dette. Vår `const.py:181` har
`FORBRUKSAVGIFT_ALMINNELIG = 0.0713` - korrekt.

Lnett og Glitre nevner i sine prislister at 2026-avgiftene "ikke er
vedtatt" formelt - merk for framtiden hvis dette endres i vedtatt
statsbudsjett.

## Enova-avgift 2026 - sjekk const.py

Glitre og Lnett rapporterer **1,25 øre/kWh inkl. mva = 1,0 øre/kWh eks. mva**.
Vår `const.py:182` har `ENOVA_AVGIFT = 0.01` - korrekt.

## Bugs i dso.py

1. **Lnett (linje 235-250)**: kapasitetstrinn mangler trinn over 25 kW.
   Siste tuple `(float("inf"), 1150)` skal være `(50, 2150), (75, 3150),
   (100, 4150), (float("inf"), 7000)`. Påvirker brukere på trinn 7-10.

2. **Lnett (linje 239-240)**: energiledd er ~46-149% for lavt. Skal være
   0,2560 / 0,1360, ikke 0,1747 / 0,0547.

3. **Lede (linje 223-224)**: energiledd 0,24382 (flat) skal være 0,1426.

4. **Lede (linje 226-233)**: kapasitetstrinn ~9-10% for høyt.

5. **Norgesnett (linje 148-149)**: energiledd 0,20262 / 0,13286 skal være
   ~0,2736 / 0,1864 (basert på inkl-mva-tall fra 2026).

6. **Elvia (linje 114-118)**: trinn 6-10 har avvik 25-345 kr/mnd. Mest
   sannsynlig leste vi PDF-en feil eller den var en eldre versjon. Verifisert
   PDF nå viser: 630, 1175, 1720, 2270, 4570.

7. **Asker Nett (linje 515-516)**: bør re-verifiseres mot 2026-prisliste -
   sannsynligvis samme mønster som Norgesnett siden Asker er nytt
   selskap med separat tariff.

## Mer subtile risikomomenter

### Helg-flagg ikke konsistent

Glitre `helg_som_natt: False` - men Glitres egen side viser ikke entydig
om dag-prisen gjelder helg. Trenger faktura-verifisering. Hvis Glitre
faktisk har helg = natt, blir vi for høye på helger.

Tensios egen side er entydig: ingen helg-rabatt. `helg_som_natt: False`
korrekt for begge Tensio TS og TN.

Elvia har eksplisitt "Lørdag og søndag samt helligdager" = natt/helg.
Vår dso.py for Elvia mangler `helg_som_natt`-felt - default er True
ifølge `dso.py:50`. Default-oppførselen behandler helg som natt, så
det blir riktig for Elvia. Bra.

### Tensio kapasitetstrinn-formulering

Kraftsystemet.no skriver "tre høyeste timer i forskjellige døgn". Vår
implementasjon plukker `daily_max_power` (én verdi per dag) og snitter
topp 3. Funksjonelt likt - hvis du har to høye timer på samme dag, regnes
kun den høyeste. Det er Tensios intensjon (forskjellige døgn).

Risiko: hvis et nettselskap faktisk snitter "topp 3 timer på 3
forskjellige dager der dag-2-time kan være lavere enn dag-1-time-2",
treffer vi feil. Ingen DSO så langt har den formuleringen.

### Forbruksavgift "ikke vedtatt"

Lnett og Glitre flagger 2026-avgiftene som "ikke vedtatt" (statsbudsjettet
er ikke endelig). Skatteetaten oppgir 7,13 øre eks. mva som gjeldende.
Hvis Stortinget endrer dette i desember 2026, må vi oppdatere const.py
- ingen krise i mai 2026.

## Anbefaling

**Avgrense scope er ikke realistisk** - vi har allerede 30+ DSO-er i
dso.py, og brukere har valgt dem i config. Å fjerne støtte for alle
utenom BKK ville bryte eksisterende oppsett.

**Bør fikse de fem konkrete buggene** i prioritert rekkefølge:

| Prioritet | Bug | Konsekvens for bruker |
|-----------|-----|-----------------------|
| P1 | Lnett: trinn over 25 kW mangler | Helt feil pris for store husholdninger |
| P1 | Lnett: energiledd er ~46% for lavt | Konsistent for lav nettleie hver måned |
| P1 | Lede: energiledd ~70% for høyt | Konsistent for høy nettleie hver måned |
| P2 | Lede: kapasitetstrinn ~10% for høyt | Mindre, men systematisk feil |
| P2 | Norgesnett: energiledd ~30% for lavt | Konsistent for lav nettleie |
| P3 | Elvia: kapasitetstrinn 6-10 har små avvik | Kun for husholdninger med >20 kW snitt |
| P3 | Asker Nett: verifiseres mot 2026 | Sannsynligvis lignende feil |

Bør også **legge til disclaimer** i `docs/begrensninger.md` om at kun
BKK er faktura-verifisert og at andre DSO-er er sjekket mot publiserte
tariffer som kan ha avvik vi ikke ser før noen verifiserer mot faktura.

**For framtiden:** automatisk parsing av PDF-er fra DSO-er er ikke
realistisk (alle har forskjellig format), men vi kunne ha en `scripts/
research/verify_dso_prices.py` som henter prisene fra DSO-ens HTML når
mulig og flagger avvik. Manuell oppdatering 1-2 ganger i året er
sannsynligvis bra nok.
