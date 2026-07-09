# Måleverdier fra Elhub

Time-for-time forbruksdata for målepunkt 707000000000000000 (<adresse>), eksportert fra Elhub kundeportal. Brukes som referansedata for å validere at integrasjonens beregninger matcher ekte fakturadata.

## Målepunkt-metadata

| Felt                 | Verdi                            |
| -------------------- | -------------------------------- |
| Adresse              | <adresse>                        |
| Strømkunde           | <kunde>                          |
| Nettselskap          | BKK AS (fra 27.07.2019)          |
| Strømleverandør      | Tibber Norge AS (fra 06.09.2019) |
| Målernummer          | 6970000000000000                 |
| Målepunkt-ID         | 707000000000000000               |
| Forventet årsforbruk | 16 854 kWh                       |
| Målerkonstant        | 1,00000                          |
| Nettområde           | BKKN1                            |
| Prisområde           | NO5                              |
| Målepunkttype        | Forbruk                          |
| Avregningsmetode     | Timesavregnet                    |
| Næringskode          | Husholdning                      |
| Forbrukskode         | Husholdninger                    |
| MVA                  | 25 %                             |
| Elsertifikatandel    | 100 %                            |
| Lagringsperiode      | 10 år                            |

## Filer

CSV-innholdet (timestamps + kWh) inneholder ikke personlig info, men vi committer kun én demo-måned for å reprodusere verifiseringen (se [neste-maaned-prosedyre.md](../docs/fakturaer/neste-maaned-prosedyre.md)). Øvrige måneder ligger kun lokalt i `_private/Måleverdier/` (gitignored).

| Fil               | Periode                 | Rader (data) | Total kWh (m/ekstra dager) |
| ------------------ | ----------------------- | ------------ | -------------------------- |
| `elhub_april.csv` | 01.04.2026 – 01.05.2026 | 743          | 1423,885                   |

Filtrer på "Fra"-kolonne for å plukke kun den tilsiktede måneden (Elhub-eksporten inkluderer alltid noen ekstra dager fra påfølgende måned). Totalen over inkluderer disse ekstra dagene, så summen ligger noen kWh høyere enn den filtrerte måneds-summen i `tests/fixtures/README.md`.

## Format

CSV med BOM, semikolon-separert. Norsk desimaltegn (komma).

| Kolonne                | Beskrivelse                        | Eksempel                    |
| ---------------------- | ---------------------------------- | --------------------------- |
| Fra                    | Time-start, lokal tid med tidssone | `2026-04-01T00:00:00+02:00` |
| Til                    | Time-slutt                         | `2026-04-01T01:00:00+02:00` |
| Målenavn               | Måletype                           | `KWH 60 Forbruk`            |
| Volum                  | Forbruk i timen                    | `2,949`                     |
| Enhet                  | Enhet                              | `kWh`                       |
| Kvalitet               | Datakvalitet                       | `Målt`                      |
| Registreringstidspunkt | Når Elhub mottok                   | `2026-04-02T12:47:05+02:00` |

`KWH 60 Forbruk` betyr 60-minutters intervall forbruksmåling.

`Kvalitet = Målt` betyr ekte måleverdi. Andre verdier kan være `Beregnet` (interpolert ved nedetid) eller `Estimert`.

## Verifisering mot faktura

April 2026 verifisert:

- Elhub total = faktura total = 1381,827 kWh (0 avvik)
- Elhub topp 3 timer per unike dag = faktura topp 3 (5,939 / 4,779 / 4,262 på 06.04 13:00 / 04.04 16:00 / 11.04 11:00)

Se [`docs/research/elhub-vs-han-vs-faktura.md`](../docs/research/elhub-vs-han-vs-faktura.md) for detaljert analyse.

## Hvordan andre kan hente sine data

1. Logg inn på [elhub.no](https://elhub.no) (BankID)
2. Velg "Min strøm" eller tilsvarende
3. Velg målepunkt
4. Last ned timesverdier som CSV/Excel for ønsket periode

Lagringsperioden er 10 år, så historiske data er tilgjengelige.

## Personvern

Innholdet i Elhub-CSV-filene (`Fra`, `Til`, `Volum`, `Enhet`, `Kvalitet`, `Registreringstidspunkt`) inneholder ingen personlig info, kun målerverdier. Filnavnet og metadata i denne README-en er anonymisert.

Eier av repoet har originalfilene fra flere måneder lagret lokalt i `_private/` (gitignored). For å reprodusere verifisering på din egen faktura, kjør `scripts/anonymize_invoices.py --inplace` etter å ha utvidet `.anonymize_config.json` med dine egne mappings.
