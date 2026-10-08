_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` (krever de private prisarkivene, se `just snapshot-kurs`).

| Måned | Faktura (kr) | HAN x HA-recorder | Avvik | HAN x Final | Avvik | Elhub x Final | Avvik |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mai_2026 | -1032.56 | -1033.11 | -0.55 | -1032.91 | -0.35 | -1032.56 | -0.001 |
| juni_2026 | -363.54 | -363.39 | +0.15 | -363.54 | +0.00 | -363.53 | +0.005 |
| juli_2026 | -807.50 | (delvis) |  | (delvis) |  | -807.50 | +0.003 |
| august_2026 | -986.38 | (delvis) |  | (delvis) |  | -986.38 | +0.000 |
| september_2026 | -1140.51 | (delvis) |  | (delvis) |  | -1140.51 | -0.004 |

HAN-fixturen mangler timer i: juli_2026 (62 timer); august_2026 (177 timer); september_2026 (1 timer). Måneder med full Elhub-CSV står likevel i tabellen; HAN-kolonnene deres er merket (delvis) og Elhub-kolonnen dekker hele måneden.

Prisårgang-dager (HA-recorderen har foreløpig kurs, publisert er Final):

| Dag | Ukedag | HA/publisert | Timer |
| --- | --- | ---: | ---: |
| 2026-05-02 | lør | 0.99892 | 24 |
| 2026-05-03 | søn | 1.00055 | 24 |
| 2026-05-10 | søn | 1.00444 | 24 |
| 2026-05-17 | søn | 1.00164 | 24 |
| 2026-05-24 | søn | 0.99696 | 21 |
| 2026-05-25 | man | 0.99673 (varierende) | 23 |
| 2026-05-31 | søn | 0.99769 | 24 |
| 2026-06-14 | søn | 0.99558 | 24 |
| 2026-06-21 | søn | 1.00304 | 24 |
| 2026-07-05 | søn | 1.00174 | 24 |
| 2026-07-12 | søn | 1.00243 | 24 |
| 2026-07-19 | søn | 1.00274 | 24 |
| 2026-07-26 | søn | 0.99394 | 20 |
| 2026-08-16 | søn | 1.00281 | 24 |
| 2026-09-06 | søn | 1.00242 | 24 |
| 2026-09-07 | man | 1.00242 | 24 |
| 2026-09-13 | søn | 1.00059 | 24 |
| 2026-09-14 | man | 1.00059 | 24 |
| 2026-09-15 | tir | 0.99974 | 24 |
| 2026-09-16 | ons | 0.99930 | 24 |
| 2026-09-17 | tor | 1.00061 | 24 |
| 2026-09-20 | søn | 0.99865 | 20 |
| 2026-09-23 | ons | 1.00098 | 24 |
| 2026-09-24 | tor | 0.99969 | 24 |
| 2026-09-25 | fre | 0.99769 | 24 |
| 2026-09-26 | lør | 1.00044 | 24 |
| 2026-09-27 | søn | 1.00090 | 24 |
| 2026-09-28 | man | 1.00088 | 20 |

Symmetri: mai_2026 har 35 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -20.61 kr); juni_2026 har 83 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -27.61 kr). BKK fakturerer symmetrisk.
