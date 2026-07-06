_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` (krever de private prisarkivene, se `just snapshot-kurs`).

| Måned | Faktura (kr) | HA-recorder (kr) | Avvik | Publisert Final (kr) | Avvik |
| --- | ---: | ---: | ---: | ---: | ---: |
| mai_2026 | -1032.56 | -1033.11 | -0.55 | -1032.91 | -0.35 |
| juni_2026 | -363.54 | -363.39 | +0.15 | -363.54 | +0.00 |

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

Symmetri: mai_2026 har 35 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -20.61 kr); juni_2026 har 83 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -27.61 kr). BKK fakturerer symmetrisk.
