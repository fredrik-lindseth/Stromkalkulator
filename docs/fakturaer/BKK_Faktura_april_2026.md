# Verifiseringsrapport: BKK-faktura april 2026

**Fakturanr:** 64489074
**Periode:** 01.04.2026 - 01.05.2026 (30 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-05-09

## Fakturadata

| Priselement           | Forbruk      | Pris            | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ------------ | --------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 620.83 kWh   | 35.963 øre/kWh  | 223.26       | 223.27             | 0.01     |
| Energiledd natt/helg  | 761.00 kWh   | 13.125 øre/kWh  | 99.88        | 99.88              | 0.00     |
| Kapasitet 2-5 kW      | 30 dager     | 250 kr/mnd      | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 1381.83 kWh  | 8.913 øre/kWh   | 123.16       | 123.18             | 0.02     |
| Enovaavgift           | 1381.83 kWh  | 1.25 øre/kWh    | 17.28        | 17.27              | 0.01     |
| **Nettleie subtotal** |              |                 | **713.58**   | **713.60**         | **0.02** |
| Norgespris            | 1381.83 kWh  | -1.0334 kr/kWh* | -1427.89     | -1427.89           | 0.00     |
| **Total**             |              |                 | **-714.31**  | **-714.29**        | **0.02** |
| Herav MVA             |              |                 | 142.72       | 142.72             | 0.00     |

\* Faktura viser avrundet rate -1.03 kr/kWh, men reell rate utledet fra beløp er -1.0334 kr/kWh.

**Resultat:** Alle linjer matcher innenfor avrundingsfeil (< 0.02 kr).

## Kapasitetstrinn-verifisering

| Faktura                  | Vår beregning                | Match? |
| ------------------------ | ---------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2)  | `kapasitetstrinn_nummer: 2`  | Match  |
| Pris: 250 kr/mnd         | `kapasitetsledd: 250`        | Match  |

Kapasitetstrinn uendret fra mars (2-5 kW, 250 kr/mnd).

## Satsverifisering mot dso.py

| Komponent                 | Faktura (øre inkl. mva) | Vårt tall | Beregning             |
| ------------------------- | ----------------------- | --------- | --------------------- |
| Energiledd dag            | 35.963                  |           |                       |
| + Forbruksavgift          | 8.913                   |           | 7.13 \* 1.25 = 8.9125 |
| + Enovaavgift             | 1.25                    |           | 1.0 \* 1.25 = 1.25    |
| **= dso energiledd_dag**  | **46.126**              | **46.13** | Match (avrunding)     |
|                           |                         |           |                       |
| Energiledd natt           | 13.125                  |           |                       |
| + Forbruksavgift          | 8.913                   |           |                       |
| + Enovaavgift             | 1.25                    |           |                       |
| **= dso energiledd_natt** | **23.288**              | **23.29** | Match (avrunding)     |

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -103.34 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Gjennomsnittlig spotpris i april utledet fra kompensasjonen: 50 + 103.34 = 153.34 øre/kWh inkl. mva. Litt høyere enn mars (149.84), litt lavere enn februar.

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

## Sammenligning med mars 2026

| Parameter               | Mars            | April           | Endring             |
| ----------------------- | --------------- | --------------- | ------------------- |
| Antall dager            | 31              | 30              | -1 dag              |
| Totalt forbruk          | 1553.22 kWh     | 1381.83 kWh     | -171.39 kWh (-11%)  |
| Dag-forbruk             | 831.77 kWh      | 620.83 kWh      | -210.94 kWh         |
| Natt-forbruk            | 721.45 kWh      | 761.00 kWh      | +39.55 kWh          |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret             |
| Nettleie                | 801.66 kr       | 713.58 kr       | -88.08 kr           |
| Norgespris-kompensasjon | -1550.68 kr     | -1427.89 kr     | +122.79 kr          |
| Total                   | -749.02 kr      | -714.31 kr      | +34.71 kr           |

Påsken (2.–6. april) ga 5 ekstra natt/helg-dager, som forklarer hvorfor natt-forbruket gikk opp mens dag-forbruket falt kraftig, selv om totalt forbruk gikk ned.

## Konklusjon

Integrasjonen beregner nettleie korrekt for april 2026. Alle fakturaposter matcher innenfor avrundingsfeil (maks 0.02 kr på en faktura med 713.58 kr nettleie). Satsene i dso.py og const.py er konsistente med det BKK fakturerer.
