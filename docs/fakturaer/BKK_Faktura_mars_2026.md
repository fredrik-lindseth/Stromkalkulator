# Verifiseringsrapport: BKK-faktura mars 2026

**Fakturanr:** 064202476
**Periode:** 01.03.2026 - 01.04.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-04-07

## Fakturadata

| Priselement           | Forbruk      | Pris            | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ------------ | --------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 831.768 kWh  | 35.963 øre/kWh  | 299.13       | 299.13             | 0.00     |
| Energiledd natt/helg  | 721.449 kWh  | 13.125 øre/kWh  | 94.69        | 94.69              | 0.00     |
| Kapasitet 2-5 kW      | 31 dager     | 250 kr/mnd      | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 1553.217 kWh | 8.913 øre/kWh   | 138.43       | 138.43             | 0.00     |
| Enovaavgift           | 1553.217 kWh | 1.25 øre/kWh    | 19.41        | 19.42              | 0.01     |
| **Nettleie subtotal** |              |                 | **801.66**   | **801.67**         | **0.01** |
| Norgespris            | 1553.217 kWh | -99.837 øre/kWh | -1550.68     | -1550.68           | 0.00     |
| **Total**             |              |                 | **-749.02**  | **-749.01**        | **0.01** |
| Herav MVA             |              |                 | 160.33       | 160.33             | 0.00     |

**Resultat:** Alle linjer matcher innenfor avrundingsfeil (< 0.01 kr).

## Kapasitetstrinn-verifisering

| Faktura                                   | Vår beregning                 | Match?                                   |
| ----------------------------------------- | ----------------------------- | ---------------------------------------- |
| Maks effekt 1: 4.798 kW (25.03 kl. 16:00) | Spores via `_daily_max_power` | N/A (vi sporer effekt, ikke klokkeslett) |
| Maks effekt 2: 4.557 kW (06.03 kl. 17:00) | Spores via `_daily_max_power` | N/A                                      |
| Maks effekt 3: 4.534 kW (26.03 kl. 19:00) | Spores via `_daily_max_power` | N/A                                      |
| Snitt: 4.630 kW                           | `avg_top_3_kw`                | Beregnes identisk                        |
| Trinn: 2-5 kW (trinn 2)                   | `kapasitetstrinn_nummer: 2`   | Match                                    |
| Pris: 250 kr/mnd                          | `kapasitetsledd: 250`         | Match                                    |

Kapasitetstrinn gikk ned fra 5-10 kW (415 kr/mnd) i februar til 2-5 kW (250 kr/mnd) i mars — en besparelse på 165 kr/mnd.

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
| Kompensasjon        | -99.837 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Norgespris-kompensasjonslinjen (-1550.68 kr) beregnes av BKK basert på time-for-time spotpriser gjennom hele måneden. Gjennomsnittlig spotpris i mars var ca. 149.8 øre/kWh inkl. mva (utledet fra kompensasjonen: 50 + 99.837 = 149.837 øre/kWh).

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 | —                 | Ja     |

## Sammenligning med februar 2026

| Parameter               | Februar          | Mars            | Endring            |
| ----------------------- | ---------------- | --------------- | ------------------ |
| Totalt forbruk          | 1673.786 kWh     | 1553.217 kWh    | -120.6 kWh (-7.2%) |
| Dag-forbruk             | 893.615 kWh      | 831.768 kWh     | -61.8 kWh          |
| Natt-forbruk            | 780.171 kWh      | 721.449 kWh     | -58.7 kWh          |
| Maks effekt (topp 1)    | 5.909 kW         | 4.798 kW        | -1.111 kW          |
| Kapasitetstrinn         | 5-10 kW (415 kr) | 2-5 kW (250 kr) | -165 kr            |
| Nettleie                | 1008.86 kr       | 801.66 kr       | -207.20 kr         |
| Norgespris-kompensasjon | -1821.64 kr      | -1550.68 kr     | +270.96 kr         |
| Total                   | -812.78 kr       | -749.02 kr      | +63.76 kr          |

## Tester

17 tester verifiserer alle fakturalinjer: `tests/test_faktura_mars_2026.py`

## Konklusjon

Integrasjonen beregner nettleie korrekt for mars 2026. Alle fakturaposter matcher innenfor avrundingsfeil (maks 0.01 kr på en faktura på 801.66 kr nettleie). Satsene i dso.py og const.py er konsistente med det BKK fakturerer.
