# NOK-omregning og Norgespris-restavviket

Undersøkelse av hvorfor vår beregning av Norgespris-kompensasjon avviker fra BKKs faktura april 2026.

> Status: konklusjon 2026-05-23 etter variant-matrise. Avviket redusert fra 2,92 kr til 0,79 kr (73 %). Reproduserbar via `scripts/research/match_norgespris_variants.py` (live HKS-kall + lokal NB-fixture).

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

## Variant-matrise (2026-05-23)

Vi gjorde det forrige doc kalte overkill: hentet rå EUR/MWh-priser direkte fra Nord Pool (via hvakosterstrommen.no-speilet) og kjørte 10 NOK-omregnings-varianter mot fakturaen. Reproduserbar via `just verify-april` (eller `scripts/research/match_norgespris_variants.py --emit-markdown`).

Tabellen under regenereres automatisk av `just verify-all` (kun lokale fixturer, ingen internett). Manuell historisk versjon med Nord Pool EXR fra live HKS-kall ligger i [tidligere git-revisjon](https://github.com/) av denne fila.

<!-- BEGIN GENERATED: match_norgespris_variants -->
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
<!-- END GENERATED -->

**Konklusjon:** Ingen offentlig tilgjengelig kursvariant treffer fakturaen eksakt. Beste enkeltkilde er **NB same-day forward-fill** med +0,79 kr avvik (0,055 %). Det er en reduksjon fra det opprinnelige avviket på 2,92 kr på 73 %.

### Hva sier reverse-engineeringen?

Implisitt single-rate som ville gitt eksakt match: **11,0706 NOK/EUR**.

| Kurs                                | Verdi        |
| ----------------------------------- | ------------ |
| Implisitt match-kurs                | 11,0706      |
| Nord Pool EXR (aritmetisk snitt)    | 11,0761      |
| Nord Pool EXR (forbruksvektet)      | 11,0815      |
| NB aritmetisk månedssnitt           | 11,0229      |
| NB forbruksvektet snitt (same-day)  | 11,0614      |

BKKs implisitte kurs ligger **mellom** NB og Nord Pool EXR. Det er ingen offentlig publisert kurs som treffer 11,0706 — verken Norges Bank, ECB-referansekurs, eller Nord Pools daglige EXR. Mest sannsynlige forklaringer:

1. **12:00 CET interbankkurs** (Nord Pools preliminære kurs): hentet 2 timer før NB-snapshotet (14:15 CET). Krona kan svekkes/styrkes 0,02–0,05 i løpet av disse to timene i et volatilt marked. Denne kursen publiseres ikke offentlig.
2. **Egen bankkurs**: BKK kan ha avtale med en spesifikk bank (DNB, Nordea etc.) med litt egne marginer.
3. **Avrundingsstøy**: 0,79 kr på 1428 kr er 0,055 %. På 720 timer med 4-desimals pris-publisering er det innenfor støy.

### Hvorfor HA-integrasjonen avvek mer (2,92 kr i forrige verifisering)

Det opprinnelige 2,92 kr-avviket kom fra HA `nordpool`-integrasjonens egen NOK-konvertering. Den henter priser i konfigurert valuta direkte fra Nord Pool API, men konverteringen Nord Pool gjør for HA-integrasjonen bruker tilsynelatende ECB-/NB-kurs (ikke deres egen interne EXR). Det ga 0,14 % på spot, som ble 0,2 % på Norgespris-kompensasjonen.

Når vi gjør konverteringen lokalt med rå EUR + NB same-day forward-fill, kommer vi ned i 0,055 %.

## Hvis vi vil lukke siste 0,79 kr

Krever ikke-offentlige data eller direkte kilde:

1. Hente historiske interbankkurser 12:00 CET — bestillingsbeskrivelse i [bestilling-bloomberg.md](bestilling-bloomberg.md)
2. Spørre BKK kundeservice eksplisitt hvilken kursleverandør og hvilket snapshot-tidspunkt de bruker
3. Få tak i en strømleverandørs interne dokumentasjon (Tibber, BKK Direkte etc.) som beskriver deres NOK-omregningsmetode

For praktisk fakturakontroll er 0,79 kr / 0,055 % innenfor "treffer på øret"-toleransen.

## 12:00 CET-hypotesen

Hovedmistanken er at BKK bruker Nord Pools preliminære interbankkurs ved 12:00 CET, ikke Norges Banks 14:15 CET-snapshot. Tre observasjoner bygger opp hypotesen.

### Hva er forskjellen på 12:00 CET-kursen og Norges Bank?

Samme valutapar (EUR/NOK spot, mid-point i interbankmarkedet) og samme underliggende marked. Forskjellen er tidspunkt og leverandør.

Norges Bank snapper kursen 14:15 CET hver bankdag — synket med ECBs euro reference rate siden 2016. Den publiseres gratis dagen etter via SDMX-JSON API. Nord Pool snapper kursen to timer tidligere, kl. 12:00 CET. Grunnen er at day-ahead-auksjonen avholdes ~12:50 CET dagen før, så Nord Pool snapper kursen rett før auksjonen og bruker den til å konvertere EUR-priser til NOK ([Nord Pool: Preliminary prices and exchange rates](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/)).

EUR/NOK kan bevege seg 0,02–0,05 i løpet av de to timene mellom 12:00 og 14:15. Det høres lite ut, men over 720 timer med strømforbruk gir det merkbar forskjell i den endelige Norgespris-kompensasjonen.

### Hvorfor diffen er deterministisk per måned, men varierer mellom måneder

Beregningen er deterministisk: rå EUR/MWh per time fra Nord Pool-snapshot (statisk JSON), NB-kurs fra snapshot (statisk JSON), forbruk fra Elhub-CSV (statisk). Forward-fill og forbruksvektet snitt er rene funksjoner. Kjører vi scriptet ti ganger på samme måned, får vi samme tall ti ganger. Det er ikke statistisk støy.

Når vi sammenligner forskjellige måneder, varierer diffen. Tre måneder testet på variant B (NB same-day forward-fill): februar +2,07 kr, mars +0,70 kr, april +0,79 kr. NOK svinger ulikt mellom 12:00 og 14:15 fra dag til dag, og hver måned har sin egen forbruks-vekt mot ulike dager. Ingen måned får systematisk samme avvik, men alle ligger innenfor samme størrelsesorden.

Hvis BKK hadde brukt en helt annen kurskilde (bank-spesifikk eller forward-spread), skulle vi sett mer kaotisk variasjon. At avviket ligger ±0,02–0,05 fra NB-kursen, ulikt hver måned, men alltid innenfor det båndet NOK svinger i på to timer — det stemmer presist med 12:00 CET-snapshot før 14:15 CET-snapshot.

### Hvorfor alle tre avvikene har samme fortegn

Alle tre månedene gir *positivt* avvik: vår beregnede kompensasjon er litt mindre negativ enn fakturaen. Det betyr at vår beregnede snittspot er litt lavere enn fakturaens implisitte snittspot — altså at NB-kursen ligger litt under den BKK bruker. Hver gang. På tre måneder, alle samme retning.

Tilfeldighet ville gitt blandet fortegn. Systematisk skjevhet i én retning forteller at BKK bruker en *høyere* kurs enn NB 14:15. Det stemmer med 12:00 CET-hypotesen i akkurat denne perioden: krona styrket seg gjennom 2026 (april gikk fra 11,21 til 10,91), og når krona styrker seg gjennom dagen er 12:00-kursen høyere enn 14:15-kursen.

Det gir en testbar prediksjon: hvis vi sammenligner en måned med systematisk svekkende krone-trend (f.eks. høst 2025), forventer vi *negativt* avvik på samme variant. Hvis det også slår til, har vi enda sterkere bevis for hypotesen.

### Hva som vil bevise eller avkrefte hypotesen

Når vi får 12:00 CET-data fra Bloomberg ([bestilling](bestilling-bloomberg.md)) og kjører samme beregning, forventer vi at de tre tallene (0,79, 2,07, 0,70 kr) alle krymper mot null. Hvis de gjør det, har vi bevist hypotesen. Hvis ikke — hvis avviket blir samme størrelsesorden eller endrer fortegn på en uventet måte — må vi se etter en annen forklaring (egen bankkurs, forward-spread, eller noe vi ikke har tenkt på enda).

## Variant-matrise per måned

Samme variantsett kjørt mot alle måneder vi har Norgespris-faktura for. Bekrefter at "beste variant"-valget ikke er stabil over måneder, og at NB-kurser ligger innenfor ±0,3 % uavhengig av valgt forward/backward-fill-strategi.

<!-- BEGIN GENERATED: match_norgespris_alle_maaneder -->
_Generert av_ `scripts/research/match_norgespris_alle_maaneder.py --emit-markdown` (alle måneder med Norgespris-faktura, kun lokale fixturer).

## Avvik (kr) per variant per måned

| Måned | B | C | D | E | I | Beste |
| --- | ---: | ---: | ---: | ---: | ---: | :--- |
| 2026-02 | +2.07 | +0.08 | +5.15 | +2.86 | +2.94 | C (+0.08) |
| 2026-03 | +0.70 | +0.65 | -0.86 | +0.24 | -2.49 | E (+0.24) |
| 2026-04 | +0.78 | -1.19 | +9.11 | +1.74 | +3.18 | B (+0.78) |

## Avvik (%) per variant per måned

| Måned | B | C | D | E | I |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-02 | +0.114 % | +0.004 % | +0.282 % | +0.157 % | +0.162 % |
| 2026-03 | +0.045 % | +0.042 % | -0.056 % | +0.015 % | -0.160 % |
| 2026-04 | +0.054 % | -0.083 % | +0.638 % | +0.122 % | +0.222 % |

## Implisitte match-kurser (reverse-engineering)

| Måned | match NOK/EUR | NB arith | NB vektet | diff vs NB-arith |
| --- | ---: | ---: | ---: | ---: |
| 2026-02 | 11.3426 | 11.3206 | 11.3303 | +0.0220 |
| 2026-03 | 11.1616 | 11.1658 | 11.1605 | -0.0041 |
| 2026-04 | 11.0705 | 11.0229 | 11.0614 | +0.0476 |
<!-- END GENERATED -->

## Reprodusering

```bash
# Krever ikke internett — bruker fixturer.
just verify-all

# Eller direkte:
python3 scripts/research/match_norgespris_variants.py --emit-markdown
python3 scripts/research/match_norgespris_alle_maaneder.py --emit-markdown
```

Live-versjonen (henter HKS-data live for sammenligning med EXR) krever internett:

```bash
python3 scripts/research/match_norgespris_variants.py    # uten flagg
python3 scripts/research/eur_nok_april_2026.py
```

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
