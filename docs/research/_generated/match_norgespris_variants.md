_Generert av_ `scripts/research/match_norgespris_variants.py --emit-markdown` (april 2026, NO5, kun lokale fixturer).

Faktura: forbruk 1381.830 kWh, Norgespris-kompensasjon -1427.89 kr. Implisitt snittspot eks. mva: 1.226666 NOK/kWh.

| Variant | Snitt eks. mva | Komp (kr) | Avvik (kr) | Avvik (%) |
| --- | ---: | ---: | ---: | ---: |
| A: Nord Pool EXR (daglig)  (proxy: NB same-day, snapshot mangler EXR) | 1.226212 | -1427.10 | +0.79 | +0.055 % |
| B: NB same-day forward-fill | 1.226212 | -1427.10 | +0.79 | +0.055 % |
| C: NB previous-bankday (T-1) | 1.227347 | -1429.07 | -1.18 | -0.082 % |
| D: NB aritmetisk månedssnitt | 1.221387 | -1418.77 | +9.12 | +0.639 % |
| E: NB forbruksvektet månedssnitt | 1.225652 | -1426.14 | +1.75 | +0.123 % |
| F: HKS NOK_per_kWh direkte  (proxy: NB same-day, snapshot mangler EXR) | 1.226212 | -1427.10 | +0.79 | +0.055 % |
| G: HKS NOK avrundet per time (4d)  (proxy: NB same-day, snapshot mangler EXR) | 1.226208 | -1427.10 | +0.79 | +0.055 % |
| H: HKS NOK avrundet per time (5d)  (proxy: NB same-day, snapshot mangler EXR) | 1.226211 | -1427.10 | +0.79 | +0.055 % |
| I: NB next-bankday (T+1) | 1.224821 | -1424.70 | +3.19 | +0.223 % |
| J: NB ukedag + NP-EXR helg  (proxy: NB same-day, snapshot mangler EXR) | 1.226212 | -1427.10 | +0.79 | +0.055 % |

**Beste variant:** A: Nord Pool EXR (daglig) (+0.79 kr / +0.055 %).

### Reverse-engineering

| Kurs | Verdi |
| --- | ---: |
| Forbruksvektet EUR/kWh | 0.110804 |
| Implisitt single-rate NOK/EUR | 11.0706 |
| Nord Pool EXR snitt (aritmetisk) | 11.0549 |
| Nord Pool EXR snitt (vektet) | 11.0614 |
| NB aritmetisk månedssnitt | 11.0229 |
| NB forbruksvektet snitt | 11.0614 |

> Kjørt i `--no-network`-modus. NP-snapshot inneholder kun rå EUR/MWh, ikke Nord Pools egen EXR. Variantene A, F, G, H, J bruker NB same-day som proxy for EXR (markert i tabellen). For nøyaktige tall mot Nord Pools faktiske valutakurs, kjør uten `--no-network` med live HKS-data.
