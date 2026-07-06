# Verifiseringsrapport: BKK-faktura mai 2026

**Fakturanr:** 012345684
**Periode:** 01.05.2026 - 01.06.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-06-20

## Fakturadata

| Priselement           | Forbruk     | Pris             | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ----------- | ---------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 518.142 kWh | 35.963 øre/kWh   | 186.34       | 186.34             | 0.00     |
| Energiledd natt/helg  | 661.161 kWh | 13.125 øre/kWh   | 86.77        | 86.78              | 0.01     |
| Kapasitet 2-5 kW      | 31 dager    | 250 kr/mnd       | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 1179.303 kWh | 8.913 øre/kWh   | 105.10       | 105.11             | 0.01     |
| Enovaavgift           | 1179.303 kWh | 1.25 øre/kWh    | 14.74        | 14.74              | 0.00     |
| **Nettleie subtotal** |             |                  | **642.95**   | **642.97**         | **0.02** |
| Norgespris            | 1179.303 kWh | -0.87557 kr/kWh\* | -1032.56    | -1032.56           | 0.00     |
| **Total**             |             |                  | **-389.61**  | **-389.59**        | **0.02** |
| Herav MVA             |             |                  | 128.59       | 128.59             | 0.00     |

\* Fakturaen oppgir Norgespris-snittrate direkte som -87,557 øre/kWh. Til
forskjell fra april-fakturaen (som viste avrundet -1,03 kr/kWh) er denne
allerede oppgitt med full presisjon.

**Resultat:** Alle linjer matcher innenfor avrundingsfeil (< 0.02 kr). Avviket
sitter i forbruksavgift og natt-energiledd, der BKK runder hver linje før
summering. Samme mønster som april.

## Kapasitetstrinn-verifisering

| Faktura                 | Vår beregning               | Match? |
| ----------------------- | --------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2) | `kapasitetstrinn_nummer: 2` | Match  |
| Pris: 250 kr/mnd        | `kapasitetsledd: 250`       | Match  |

Maks effekt fra fakturaen (timesnitt-kW, topp 3 dager):

- 5,167 kW, målt 14.05.2026 kl. 12:00
- 4,553 kW, målt 29.05.2026 kl. 12:00
- 4,357 kW, målt 30.05.2026 kl. 11:00

Snitt topp 3 = 4,692 kW, godt innenfor 2-5 kW-trinnet. Uendret fra april
(som lå på 4,993 kW, akkurat under 5,0 kW-grensen). Mai ligger tryggere
midt i trinnet.

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -87,557 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Implisitt snittspot mai utledet fra kompensasjonen: 50 + 87,557 = 137,557
øre/kWh inkl. mva (110,05 øre/kWh eks. mva). Lavere enn april (153,34 inkl.
mva), som forventet inn i vårsesongen med lavere spotpriser.

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

Satsene er uendret fra april. Mai er fortsatt sommersats for forbruksavgift
(8,913 øre/kWh inkl. mva).

## Sammenligning med april 2026

| Parameter               | April           | Mai             | Endring             |
| ----------------------- | --------------- | --------------- | ------------------- |
| Antall dager            | 30              | 31              | +1 dag              |
| Totalt forbruk          | 1381.83 kWh     | 1179.30 kWh     | -202.53 kWh (-15 %) |
| Dag-forbruk             | 620.83 kWh      | 518.14 kWh      | -102.69 kWh         |
| Natt-forbruk            | 761.00 kWh      | 661.16 kWh      | -99.84 kWh          |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret             |
| Nettleie                | 713.58 kr       | 642.95 kr       | -70.63 kr           |
| Norgespris-kompensasjon | -1427.89 kr     | -1032.56 kr     | +395.33 kr          |
| Total                   | -714.31 kr      | -389.61 kr      | +324.70 kr          |

Forbruket faller jevnt inn i mai (varmere, mindre oppvarming). Både dag og
natt går ned omtrent like mye. Norgespris-kompensasjonen krymper både fordi
forbruket er lavere og fordi spotprisen falt, så nettoutbetalingen er nesten
halvert mot april.

## Status og gjenstående

Dette er en linje-for-linje-attest: integrasjonens satser og formler
reproduserer fakturaen innenfor avrundingsfeil. Verifisert via
`tests/test_faktura_bkk.py` (fixture `FAKTURA_MAI_2026`).

Time-for-time-verifisering ble utført 2026-07-06 (sammen med juni):
HAN-eksporten (`tests/fixtures/bkk_mai_2026_hourly.json`, 744 timer) matcher
fakturaen på alle linjer. Total kWh treffer på 4 Wh, nettleie på 0.02 kr.
Norgespris-kompensasjonen avviker 0.55 kr med HA-recorderens priser og 0.35
kr med Nord Pools publiserte Final-priser (juni traff eksakt med samme
metode). Restavviket skyldes ikke kWh-støy eller kurskilden; mest sannsynlig
er det mai-kWh-serien mot Elhub, eller at Nord Pool korrigerte priser etter
BKKs fakturakjøring. Se
[research/norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).
Coordinator-replay dekkes av `tests/test_coordinator_replay.py`.
Elhub-CSV for mai (krever BankID) er neste steg for å lukke de 0.35 kr.

## Konklusjon

Integrasjonen beregner nettleie korrekt for mai 2026. Alle fakturaposter
matcher innenfor avrundingsfeil (maks 0.02 kr på en faktura med 642.95 kr
nettleie). Satsene i dso.py og const.py er konsistente med det BKK fakturerer,
uendret fra april.
