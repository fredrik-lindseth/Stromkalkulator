# Verifiseringsrapport: BKK-faktura juni 2026

**Fakturanr:** 012345685
**Periode:** 01.06.2026 - 01.07.2026 (30 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-07-06

## Fakturadata

| Priselement           | Forbruk      | Pris             | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ------------ | ---------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 590.646 kWh  | 35.963 øre/kWh   | 212.41       | 212.41             | 0.00     |
| Energiledd natt/helg  | 442.982 kWh  | 13.125 øre/kWh   | 58.14        | 58.14              | 0.00     |
| Kapasitet 2-5 kW      | 30 dager     | 250 kr/mnd       | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 1033.628 kWh | 8.913 øre/kWh    | 92.11        | 92.13              | 0.02     |
| Enovaavgift           | 1033.628 kWh | 1.25 øre/kWh     | 12.93        | 12.92              | 0.01     |
| **Nettleie subtotal** |              |                  | **625.59**   | **625.60**         | **0.01** |
| Norgespris            | 1033.628 kWh | -0.35171 kr/kWh  | -363.54      | -363.54            | 0.00     |
| **Total**             |              |                  | **262.05**   | **262.07**         | **0.02** |
| Herav MVA             |              |                  | 125.12       | 125.12             | 0.00     |

**Resultat:** Alle linjer matcher innenfor avrundingsfeil (< 0.02 kr). Avviket
sitter i forbruksavgift og Enova, der BKK runder hver linje før summering.
Samme mønster som april og mai.

Juni er den første måneden i 2026 med positivt fakturabeløp (262.05 kr å
betale): spotprisen har falt så mye at Norgespris-kompensasjonen ikke lenger
dekker nettleien.

## Time-for-time-verifisering

Utført med HAN-eksport fra HA-recorder (`tests/fixtures/bkk_juni_2026_hourly.json`,
720 timer) via `scripts/research/verify_invoice_hourly.py`:

| Linje                  | Beregnet | Faktura  | Avvik    |
| ---------------------- | -------- | -------- | -------- |
| Total kWh              | 1033.628 | 1033.628 | 0.000    |
| Forbruk dag kWh        | 590.626  | 590.646  | -0.020   |
| Forbruk natt kWh       | 443.002  | 442.982  | +0.020   |
| Nettleie sum           | 625.60   | 625.59   | +0.01    |
| Norgespris-komp        | -363.39  | -363.54  | +0.15    |
| Total inkl. Norgespris | 262.21   | 262.05   | +0.16    |

Alt innenfor toleranse. Norgespris-avviket på 0.15 kr (0.04 %) er den
dokumenterte kurs-/avrundingsstøyen. Dag/natt-splitten treffer på 20 Wh,
juni har ingen helligdager, så klassifiseringen er ren ukedag/helg.

## Kapasitetstrinn-verifisering

| Faktura                 | Vår beregning               | Match? |
| ----------------------- | --------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2) | `kapasitetstrinn_nummer: 2` | Match  |
| Pris: 250 kr/mnd        | `kapasitetsledd: 250`       | Match  |

Maks effekt fra fakturaen (timesnitt-kW, topp 3 dager):

- 5,227 kW, målt 28.06.2026 kl. 12:00
- 4,933 kW, målt 24.06.2026 kl. 09:00
- 4,227 kW, målt 27.06.2026 kl. 11:00

Snitt topp 3 = 4,796 kW, innenfor 2-5 kW-trinnet. Omtrent som mai (4,692 kW).
Replay av HAN-dataene gjennom coordinatoren gir 4,788 kW, 8 W under
fakturaen, innenfor dokumentert avvik (3-8 W per topp).

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -35,171 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Implisitt snittspot juni utledet fra kompensasjonen: 50 + 35,171 = 85,171
øre/kWh inkl. mva (68,14 øre/kWh eks. mva). Kraftig ned fra mai (137,557
inkl. mva), typisk sommerprisfall med høy magasinfylling.

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

Satsene er uendret fra mai. Juni er fortsatt sommersats for forbruksavgift
(8,913 øre/kWh inkl. mva).

## Sammenligning med mai 2026

| Parameter               | Mai             | Juni            | Endring             |
| ----------------------- | --------------- | --------------- | ------------------- |
| Antall dager            | 31              | 30              | -1 dag              |
| Totalt forbruk          | 1179.30 kWh     | 1033.63 kWh     | -145.67 kWh (-12 %) |
| Dag-forbruk             | 518.14 kWh      | 590.65 kWh      | +72.51 kWh          |
| Natt-forbruk            | 661.16 kWh      | 442.98 kWh      | -218.18 kWh         |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret             |
| Nettleie                | 642.95 kr       | 625.59 kr       | -17.36 kr           |
| Norgespris-kompensasjon | -1032.56 kr     | -363.54 kr      | +669.02 kr          |
| Total                   | -389.61 kr      | 262.05 kr       | +651.66 kr          |

Totalforbruket faller videre inn i sommeren, men dag-andelen øker: mai hadde
fem helligdager som ble klassifisert som natt-tariff (1., 14., 17., 24. og
25. mai), juni har ingen. Norgespris-kompensasjonen stuper med spotprisen,
og for første gang i 2026 er fakturaen et beløp å betale, ikke tilgode.

## Status og gjenstående

Dette er både en linje-for-linje-attest og en time-for-time-verifisering:
integrasjonens satser og formler reproduserer fakturaen innenfor
avrundingsfeil. Verifisert via `tests/test_faktura_bkk.py` (fixture
`FAKTURA_JUNI_2026`) og coordinator-replay i
`tests/test_coordinator_replay.py`.

Elhub-CSV-sammenligning (krever BankID-innlogging) gjenstår som frivillig
tilleggssjekk.

## Konklusjon

Integrasjonen beregner nettleie korrekt for juni 2026. Alle fakturaposter
matcher innenfor avrundingsfeil (maks 0.02 kr på en faktura med 625.59 kr
nettleie). Satsene i dso.py og const.py er konsistente med det BKK fakturerer,
uendret fra mai.
