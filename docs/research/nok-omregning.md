# NOK-omregning og Norgespris-restavviket

Undersøkelse av hvorfor vår beregning av Norgespris-kompensasjon avviker 2,92 kr (0,2 %) fra BKKs faktura april 2026.

> Status: konklusjon 2026-05-22, åpne spørsmål gjenstår. Reproduserbar via `scripts/research/eur_nok_april_2026.py`.

## Avviket

Fra verifisering av april 2026:

| Måling                  | Vår beregning | Faktura     | Avvik            |
| ----------------------- | ------------- | ----------- | ---------------- |
| Norgespris-kompensasjon | -1430,81 kr   | -1427,89 kr | +2,92 kr (0,2 %) |

Alle andre fakturalinjer matchet innenfor 0,01 kr. Spørsmålet: hvor kommer 2,92 kr fra.

## Hva vi visste på forhånd

- Vår beregning bruker `sensor.nord_pool_no5_current_price` (HA-integrasjonen `nordpool`)
- BKK regner Norgespris-kompensasjon som (Norgespris - snittspot) × forbruk
- Norgespris-fastpris er 0,50 kr/kWh inkl. mva i sør-Norge
- Vi hadde bekreftet at HA-integrasjonen returnerer pris eks. mva (vektet snitt × 1,25 matcher fakturas implisitte snitt)

## Hva vi gjorde

1. Eksporterte hourly spotpriser og hourly forbruk for april 2026 fra `home-assistant_v2.db`
2. Beregnet forbruksvektet snitt: `sum(spot × kwh) / sum(kwh)` for hele måneden
3. Reverse-utledet fakturaens implisitte snittspot fra Norgespris-linjen
4. Hentet daglige EUR/NOK-kurser fra Norges Bank for april 2026
5. Konverterte begge tall til implisitt EUR/MWh og sammenlignet

## Dataene

### HA-cache (forbruksvektet snitt april 2026)

- 1,2284 NOK/kWh eks. mva
- Kilde: 720 timesverdier fra `sensor.nord_pool_no5_current_price.mean`, vektet med tpi-diff per time

### Faktura (implisitt snittspot)

- Norgespris-rate på faktura: -1,0333 kr/kWh inkl. mva
- Implisitt snittspot inkl. mva: 0,50 - (-1,0333) = 1,5333 kr/kWh
- Implisitt snittspot eks. mva: 1,5333 / 1,25 = 1,2266 NOK/kWh

### Norges Bank EUR/NOK april 2026

19 bankdager, ECB-konsertasjonskurs 14:15 CET.

- Første (01.04): 11,2080 NOK/EUR
- Siste (30.04): 10,9123 NOK/EUR
- Aritmetisk snitt: 11,0229 NOK/EUR
- Trend: krona styrket seg fra 11,21 til 10,91 i løpet av måneden

## Resultater

| Mål                               | Verdi              |
| --------------------------------- | ------------------ |
| Differanse NOK/kWh eks. mva       | +0,0018 (+0,143 %) |
| Implisitt EUR/MWh fra HA-cache    | 111,441            |
| Implisitt EUR/MWh fra faktura     | 111,281            |
| Differanse EUR/MWh                | +0,160 (+0,143 %)  |
| Implisitt EUR/NOK BKK må ha brukt | 11,0387            |
| Avvik vs NB-snitt                 | +0,0158 NOK/EUR    |

## Konklusjon

Restavviket på 2,92 kr i Norgespris-kompensasjonen kommer fra vekslingskurs-håndtering, ikke fra feil i integrasjonens logikk. Avviket utgjør 0,14 % av snittprisen, som er innenfor variasjon mellom forskjellige snittberegninger av samme grunnkurs.

To plausible forklaringer som passer dataene:

1. BKK forbruksvekter kursen. Hvis kunden brukte mer strøm tidlig i måneden da kursen var 11,21 og mindre senere når kursen var 10,91, vil forbruksvektet snitt bli høyere enn aritmetisk snitt.
2. HA og BKK bruker forskjellige kurskilder. HA's Nord Pool-integrasjon kan bruke kursene Nord Pool selv publiserer, som kan avvike marginalt fra Norges Banks publiserte kurs.

Avviket er for lite til å skille mellom disse. Begge er innenfor 0,2 %.

## Hvorfor 0,14 % på spot blir 0,2 % på Norgespris-kompensasjon

Norgespris-kompensasjon er en differanse: `(0,50 - spot) × kWh`. En liten endring i spot gir relativt større endring i differansen fordi 0,50-konstanten ikke endres.

- Spot 1,2284: kompensasjon (1,2284 × 1,25 - 0,50) × kWh = 1,0355 × kWh
- Spot 1,2266: kompensasjon (1,2266 × 1,25 - 0,50) × kWh = 1,0333 × kWh
- Diff per kWh: 0,0022
- Over 1381,8 kWh: 3,04 kr (≈ vårt observerte 2,92 kr)

## Hva vi ikke vet

- Hvilken EUR/NOK-kilde Nord Pool-integrasjonen i HA bruker
- Hvilken EUR/NOK-kilde BKK bruker
- Hvilken snittberegningsmetode BKK bruker (aritmetisk, forbruksvektet, time-vektet)
- Om Nord Pool publiserer NOK-priser direkte, eller om HA-integrasjonen gjør egen omregning

Disse er ikke kritiske å løse. Avviket på 0,2 % er innenfor praktisk presisjon for fakturakontroll.

## Hvis du vil gå dypere

For å lukke gapet helt må vi:

1. Hente rå EUR/MWh-priser fra Nord Pool eller ENTSO-E (krever security token for ENTSO-E)
2. Bygge egen NOK-omregning med flere forskjellige kurser
3. Kjøre alle varianter mot fakturaen til vi finner perfekt match
4. Konfrontere BKK kundeservice med funnet

Overkill for å validere integrasjonen. Ligger på prosjekt-todo som [fakturaverifisering-prosjekt.md fase 4](../fakturaverifisering-prosjekt.md) hvis vi vil.

## Reprodusering

```bash
python3 scripts/research/eur_nok_april_2026.py
```

Krever internett (slår opp Norges Bank API). Bruker kun standardbiblioteket.

For å gjenta for andre måneder, dupliser scriptet og endre datoperiode + HA-cache-snittet.

## Referanser

- Norges Bank SDMX-JSON: https://data.norges-bank.no/api/data/EXR/
- ECB-konsertasjonskurs: publiseres daglig 14:15 CET, brukes som referansekurs av Nord Pool m.fl.
- HA `nordpool`-integrasjon: https://github.com/custom-components/nordpool
- Faktura: `Fakturaer/Receipt-2735-6144-7538.pdf` eller tilsvarende (BKK 000000000)
- Fixture: `tests/fixtures/bkk_april_2026_hourly.json`
