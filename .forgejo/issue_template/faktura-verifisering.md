---
name: Faktura-verifisering (attest at det stemmer)
about: Bekreft at integrasjonen regner riktig for ditt nettselskap. Hver verifisering blir en attest som styrker tilliten for alle brukere.
title: "[Faktura] <Nettselskap> <måned år>"
labels: verifisering
---

## Konklusjon

- [ ] Fakturaen matcher integrasjonens beregninger (avrundingsavvik på øre-nivå er normalt)
- [ ] Det er avvik som bør undersøkes

## Nettselskap og periode

- **Nettselskap:**
- **Prisområde:** (NO1 / NO2 / NO3 / NO4 / NO5)
- **Avgiftssone:** (Standard / Nord-Norge / Tiltakssonen)
- **Periode:** (f.eks. 01.04.2026 - 01.05.2026)
- **Avtale:** (Spotpris+strømstøtte / Norgespris / annet)

## Fakturadata

Fyll inn én rad per linje på fakturaen. La «Vår beregning» stå tom, den fyller vi inn.

| Priselement          | Forbruk (kWh)  | Pris (øre/kWh) | Faktura (kr) | Vår beregning (kr) |
| -------------------- | -------------- | -------------- | ------------ | ------------------ |
| Energiledd dag       |                |                |              |                    |
| Energiledd natt/helg |                |                |              |                    |
| Forbruksavgift       |                |                |              |                    |
| Enovaavgift          |                |                |              |                    |
| Kapasitet X-Y kW     | (antall dager) | (kr/mnd)       |              |                    |
| Strømstøtte (hvis)   |                |                |              |                    |
| Norgespris (hvis)    |                |                |              |                    |
| **Sum**              |                |                |              |                    |

Spesifiser om prisene på fakturaen din er **eks** eller **inkl** MVA.

## Kapasitetstrinn (hvis tilgjengelig)

- **Trinn:** (f.eks. "2-5 kW", "trinn 2")
- **Snitt-effekt topp 3 dager:** (kW, hvis fakturaen viser det)

## Sensorverdier fra integrasjonen (valgfritt, men styrker attesten)

| Sensor                                   | Sensorverdi | Faktura |
| ---------------------------------------- | ----------- | ------- |
| `sensor.stromkalkulator_energiledd_dag`  |             |         |
| `sensor.stromkalkulator_energiledd_natt` |             |         |
| `sensor.stromkalkulator_forbruksavgift`  |             |         |
| `sensor.stromkalkulator_enovaavgift`     |             |         |
| `sensor.stromkalkulator_kapasitetstrinn` |             |         |

## Kreditt

Hvordan vil du krediteres i [REFERANSE.md](../../docs/fakturaer/REFERANSE.md)?

- Fornavn / alias / Forgejo-handle:
- Eller anonymt: [ ]

## Annet

(Eventuelle observasjoner, spørsmål.)

---

**Personvern:** Ikke ta med navn, adresse, kundenummer, fakturanummer, KID eller kontonummer.

Se [VERIFISER_DIN_FAKTURA.md](../../docs/fakturaer/VERIFISER_DIN_FAKTURA.md) for kontekst.
