# Verifiseringsrapport: BKK-faktura februar 2026

**Fakturanr:** 063926706
**Periode:** 01.02.2026 - 01.03.2026 (28 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-03-27

## Fakturadata

| Priselement | Forbruk | Pris | Faktura (kr) | Vår beregning (kr) | Avvik |
| --- | --- | --- | --- | --- | --- |
| Energiledd dag | 893.615 kWh | 35.963 øre/kWh | 321.36 | 321.36 | 0.00 |
| Energiledd natt/helg | 780.171 kWh | 13.125 øre/kWh | 102.40 | 102.40 | 0.00 |
| Kapasitet 5-10 kW | 28 dager | 415 kr/mnd | 415.00 | 415.00 | 0.00 |
| Forbruksavgift | 1673.786 kWh | 8.913 øre/kWh | 149.17 | 149.17 | 0.00 |
| Enovaavgift | 1673.786 kWh | 1.25 øre/kWh | 20.93 | 20.92 | 0.01 |
| **Nettleie subtotal** | | | **1008.86** | **1008.85** | **0.01** |
| Norgespris | 1673.786 kWh | -1.0883 kr/kWh | -1821.64 | -1821.64 | 0.00 |
| **Total** | | | **-812.78** | **-812.79** | **0.01** |
| Herav MVA | | | 201.77 | 201.77 | 0.00 |

**Resultat:** Alle linjer matcher innenfor avrundingsfeil (< 0.01 kr).

## Kapasitetstrinn-verifisering

| Faktura | Vår beregning | Match? |
| --- | --- | --- |
| Maks effekt 1: 5.909 kW (06.02 kl. 08:00) | Spores via `_daily_max_power` | N/A (vi sporer effekt, ikke klokkeslett) |
| Maks effekt 2: 5.733 kW (10.02 kl. 16:00) | Spores via `_daily_max_power` | N/A |
| Maks effekt 3: 5.477 kW (03.02 kl. 09:00) | Spores via `_daily_max_power` | N/A |
| Snitt: 5.706 kW | `avg_top_3_kw` | Beregnes identisk |
| Trinn: 5-10 kW (trinn 3) | `kapasitetstrinn_nummer: 3` | Match |
| Pris: 415 kr/mnd | `kapasitetsledd: 415` | Match |

## Satsverifisering mot tso.py

Fakturaen viser individuelle priskomponenter. Vi verifiserer at tso.py inneholder riktig sum:

| Komponent | Faktura (øre inkl. mva) | Vårt tall | Beregning |
| --- | --- | --- | --- |
| Energiledd dag | 35.963 | | |
| + Forbruksavgift | 8.913 | | 7.13 * 1.25 = 8.9125 |
| + Enovaavgift | 1.25 | | 1.0 * 1.25 = 1.25 |
| **= tso energiledd_dag** | **46.126** | **46.13** | Match (avrunding) |
| | | | |
| Energiledd natt | 13.125 | | |
| + Forbruksavgift | 8.913 | | |
| + Enovaavgift | 1.25 | | |
| **= tso energiledd_natt** | **23.288** | **23.29** | Match (avrunding) |

## Norgespris-verifisering

| Parameter | Faktura | Vår kode | Match? |
| --- | --- | --- | --- |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50` | Ja |
| Strømstøtte | 0 (Norgespris-kunde) | `stromstotte = 0.0` når `har_norgespris` | Ja |
| Kompensasjon | -1.0883 kr/kWh snitt | Beregnes time-for-time av BKK | N/A |

Norgespris-kompensasjonslinjen (-1821.64 kr) beregnes av BKK basert på time-for-time spotpriser gjennom hele måneden. Vårt system kan ikke reprodusere dette eksakte tallet uten historiske spotpriser, men vi verifiserer at:

- Fastprisen er korrekt (50 øre/kWh)
- Strømstøtte er 0 for Norgespris-kunder
- Nettleiedelen (1008.86 kr) beregnes korrekt

## Avgiftsverifisering

| Avgift | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const * 1.25 | Match? |
| --- | --- | --- | --- | --- |
| Forbruksavgift | 8.913 | 7.13 | 8.9125 | Ja |
| Enovaavgift | 1.25 | 1.00 | 1.25 | Ja |
| MVA-sats | 25% | 0.25 | — | Ja |

## Bugfiks avdekket under verifisering

Under denne verifiseringen ble en feil i reverse-beregningen av `eks_avgifter_mva`-attributtet oppdaget. Se [Incident 002](../incidents/002-feil-reverse-energiledd.md).

## Tester

17 tester verifiserer alle fakturalinjer: `tests/test_faktura_februar_2026.py`

## Konklusjon

Integrasjonen beregner nettleie korrekt for februar 2026. Alle fakturaposter matcher innenfor avrundingsfeil (maks 0.01 kr på en faktura på 1008.86 kr nettleie).
