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

19 bankdager. Norges Bank publiserer middelkurs (mid-point i interbankmarkedet) basert på samme 14:15 CET-snapshot som ECBs euro-referansekurs, med publisering ~16:00 CET. Norges Bank synket publiseringstidspunktet sitt til ECBs etter ECB-omleggingen 1. juli 2016.

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

Mest sannsynlige forklaring etter videre research: HA-integrasjonen og BKK bruker forskjellige kurskilder. Nord Pool publiserer NOK-priser direkte via sin egen kursmekanisme — preliminære kurser hentet 12:00 CET fra interbankmarkedet, deretter "official" kurser satt sammen med to banker for valutahedging. Det er **ikke** ECB-referansekursen. HA's `nordpool`-integrasjon henter priser i konfigurert valuta rett fra Nord Pools API (`DayAheadPrices`), så omregningen skjer hos Nord Pool, ikke i integrasjonen.

BKK bruker etter alt å dømme samme Elspot-NOK-pris time for time som er forskriftsfestet (se "Forskriften" nedenfor), men kan ha en marginalt annen håndtering av etter-publiserte korreksjoner eller offisiell-vs-preliminær kurs. Avviket på 0,14 % er for lite til å skille presis kilde.

## Hvorfor 0,14 % på spot blir 0,2 % på Norgespris-kompensasjon

Norgespris-kompensasjon er en differanse: `(0,50 - spot) × kWh`. En liten endring i spot gir relativt større endring i differansen fordi 0,50-konstanten ikke endres.

- Spot 1,2284: kompensasjon (1,2284 × 1,25 - 0,50) × kWh = 1,0355 × kWh
- Spot 1,2266: kompensasjon (1,2266 × 1,25 - 0,50) × kWh = 1,0333 × kWh
- Diff per kWh: 0,0022
- Over 1381,8 kWh: 3,04 kr (≈ vårt observerte 2,92 kr)

## Forskriften: hva sier loven om NOK-omregning?

Kort svar: **ingen** norsk lov eller forskrift sier eksplisitt hvilken EUR/NOK-kurs strømleverandører skal bruke.

- Avregningsforskriften ([FOR-1999-03-11-301](https://lovdata.no/dokument/SF/forskrift/1999-03-11-301)) inneholder ingen ord om valuta, kurs, omregning eller EUR. Forskriften regulerer måling, avregning og fakturering i NOK uten å spesifisere hvordan utenlandsk valuta skal håndteres.
- Norgespris-høringsnotatet ([Energidepartementet 10. mars 2025](https://www.regjeringen.no/contentassets/428d4ed2a03f47de9cc333609ff18106/horingsnotat-ny-lov-om-norgespris-og-stromstonad-til-husholdninger.pdf)) sier at beregningene gjøres **time for time**: "Prissikringsbeløp beregnes time for time. Det er differansen mellom spotprisen per time i budområdet og terskelverdi". Elspotpris er definert som "timespris i budområdet kunden tilhører". Ingen krav til snittberegning eller kurskilde — bare at det er den faktiske timespotprisen i budområdet som skal brukes.
- I praksis betyr det at strømleverandører bruker den NOK-prisen Nord Pool selv publiserer for budområdet (`NO5` for BKK-kunder i Bergen). Nord Pool har egen kursmekanisme (12:00 CET preliminær + to-banks-hedging for offisiell). Det er ikke regulert hvilken Nord Pool-kurs som skal brukes, men `data.nordpoolgroup.com` er den autoritative publiseringskanalen for sluttbruker-fakturering.

## Hva vi fortsatt ikke vet med sikkerhet

- Om BKK bruker Nord Pools "preliminary" NOK-pris (12:00 CET-rate) eller "official" NOK-pris (etter to-banks-hedging)
- Om BKK gjør egen runding per time eller jobber med flere desimaler

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

### Kurs-kilder

- [Norges Bank SDMX-JSON](https://data.norges-bank.no/api/data/EXR/): publiserer middelkurs (mid-point i interbankmarkedet) basert på 14:15 CET-snapshot, publisering ~16:00 CET (synket med ECB siden 1. juli 2016)
- [ECB euro foreign exchange reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html): basert på daglig "concertation procedure" mellom europeiske sentralbanker ~14:10 CET. Kursene reflekterer markedet 14:15 CET, publiseres ~16:00 CET. Brukes som informasjons-referanse, ikke for transaksjoner.
- [ECB framework-dokument (PDF)](https://www.ecb.europa.eu/stats/pdf/exchange/Frameworkfortheeuroforeignexchangereferencerates.en.pdf): metodebeskrivelse for konsertasjons-prosessen
- [Nord Pool: Preliminary prices and exchange rates](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/): Nord Pool henter interbankkurser 12:00 CET som preliminær kurs, kontakter to banker for valutahedging og setter offisiell kurs etter EUR-prisene er klare. **Ikke ECB-kurs.**

### Norsk regulering

- [Avregningsforskriften (FOR-1999-03-11-301)](https://lovdata.no/dokument/SF/forskrift/1999-03-11-301): regulerer fakturering, men ingen krav til valutakurs
- [Norgespris-høringsnotat (10. mars 2025)](https://www.regjeringen.no/contentassets/428d4ed2a03f47de9cc333609ff18106/horingsnotat-ny-lov-om-norgespris-og-stromstonad-til-husholdninger.pdf): "Prissikringsbeløp beregnes time for time", basert på "elspotpris i budområdet". Ingen krav til kurskilde.

### Integrasjon

- [HA `nordpool`-integrasjon](https://www.home-assistant.io/integrations/nordpool/): henter priser i konfigurert valuta direkte fra Nord Pool API (`DayAheadPrices`). EUR-NOK-omregningen skjer hos Nord Pool, ikke i integrasjonen.

### Verifikasjon

- Faktura: `Fakturaer/Receipt-2735-6144-7538.pdf` eller tilsvarende (BKK 000000000)
- Fixture: `tests/fixtures/bkk_april_2026_hourly.json`
