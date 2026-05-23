_Generert av_ `scripts/research/match_strommstotte_variants.py --emit-markdown` (april 2026, NO5, BKK; kun lokale fixturer).

Datapunkter: 720 timer (april 2026), total 1381.818 kWh. Vektet spot eks. mva: 1.228365 NOK/kWh. Vektet spot inkl. mva: 1.535457 NOK/kWh. Total spot uten støtte: 2121.72 kr.

Referansetall: BKK "uten Norgespris" = 1377.00 kr, brukers observerte fra vår kode = 1347.00 kr.

### A: time-for-time

| Variant | Netto (kr) | Δ BKK 1377 | Δ vår 1347 |
| --- | ---: | ---: | ---: |
| terskel=2023 (70 øre), rate=55 % | 1619.63 | +242.63 | +272.63 |
| terskel=2023 (70 øre), rate=75 % | 1437.05 | +60.05 | +90.05 |
| terskel=2023 (70 øre), rate=80 % | 1391.41 | +14.41 | +44.41 |
| terskel=2023 (70 øre), rate=90 % | 1300.12 | -76.88 | -46.88 |
| terskel=2023 (70 øre), rate=95 % | 1254.47 | -122.53 | -92.53 |
| terskel=2023 (70 øre), rate=100 % | 1208.83 | -168.17 | -138.17 |
| terskel=2024 (73 øre), rate=55 % | 1648.02 | +271.02 | +301.02 |
| terskel=2024 (73 øre), rate=75 % | 1475.77 | +98.77 | +128.77 |
| terskel=2024 (73 øre), rate=80 % | 1432.70 | +55.70 | +85.70 |
| terskel=2024 (73 øre), rate=90 % match vår | 1346.58 | -30.42 | -0.42 |
| terskel=2024 (73 øre), rate=95 % | 1303.51 | -73.49 | -43.49 |
| terskel=2024 (73 øre), rate=100 % | 1260.45 | -116.55 | -86.55 |
| terskel=2025 (75 øre), rate=55 % | 1666.95 | +289.95 | +319.95 |
| terskel=2025 (75 øre), rate=75 % | 1501.58 | +124.58 | +154.58 |
| terskel=2025 (75 øre), rate=80 % | 1460.23 | +83.23 | +113.23 |
| terskel=2025 (75 øre), rate=90 % match BKK | 1377.55 | +0.55 | +30.55 |
| terskel=2025 (75 øre), rate=95 % | 1336.20 | -40.80 | -10.80 |
| terskel=2025 (75 øre), rate=100 % | 1294.86 | -82.14 | -52.14 |
| terskel=2026 (77 øre), rate=55 % | 1685.88 | +308.88 | +338.88 |
| terskel=2026 (77 øre), rate=75 % | 1527.39 | +150.39 | +180.39 |
| terskel=2026 (77 øre), rate=80 % | 1487.76 | +110.76 | +140.76 |
| terskel=2026 (77 øre), rate=90 % | 1408.52 | +31.52 | +61.52 |
| terskel=2026 (77 øre), rate=95 % | 1368.90 | -8.10 | +21.90 |
| terskel=2026 (77 øre), rate=100 % | 1329.28 | -47.72 | -17.72 |

### B: månedsnitt

| Variant | Netto (kr) | Δ BKK 1377 | Δ vår 1347 |
| --- | ---: | ---: | ---: |
| snitt-basert: terskel=2023 (70 øre), rate=90 % | 1300.35 | -76.65 | -46.65 |
| snitt-basert: terskel=2024 (73 øre), rate=90 % match vår | 1346.99 | -30.01 | -0.01 |
| snitt-basert: terskel=2025 (75 øre), rate=90 % | 1378.08 | +1.08 | +31.08 |
| snitt-basert: terskel=2026 (77 øre), rate=90 % | 1409.17 | +32.17 | +62.17 |

### C: eks-mva

| Variant | Netto (kr) | Δ BKK 1377 | Δ vår 1347 |
| --- | ---: | ---: | ---: |
| eks-mva: terskel=70 øre, rate=90 % | 1300.12 | -76.88 | -46.88 |
| eks-mva: terskel=73 øre, rate=90 % match vår | 1346.58 | -30.42 | -0.42 |
| eks-mva: terskel=75 øre, rate=90 % match BKK | 1377.55 | +0.55 | +30.55 |
| eks-mva: terskel=77 øre, rate=90 % | 1408.52 | +31.52 | +61.52 |

### D: avrunding

| Variant | Netto (kr) | Δ BKK 1377 | Δ vår 1347 |
| --- | ---: | ---: | ---: |
| round_hour=None, round_day=None | 1408.52 | +31.52 | +61.52 |
| round_hour=None, round_day=2 | 1408.52 | +31.52 | +61.52 |
| round_hour=None, round_day=4 | 1408.52 | +31.52 | +61.52 |
| round_hour=4, round_day=None | 1408.52 | +31.52 | +61.52 |
| round_hour=4, round_day=2 | 1408.52 | +31.52 | +61.52 |
| round_hour=4, round_day=4 | 1408.52 | +31.52 | +61.52 |
| round_hour=5, round_day=None | 1408.52 | +31.52 | +61.52 |
| round_hour=5, round_day=2 | 1408.51 | +31.51 | +61.51 |
| round_hour=5, round_day=4 | 1408.52 | +31.52 | +61.52 |

### Brute-force minste avvik

| Søk | Beste verdi | Netto (kr) | Δ BKK |
| --- | ---: | ---: | ---: |
| Terskel (rate=90 % fast) | 0.9371 inkl. mva (74.968 øre) | 1377.05 | +0.05 |
| Rate (terskel=0.9625 fast) | 94 % | 1376.82 | -0.18 |
