<p align="center">
  <img src="images/logo.png" alt="Strømkalkulator" width="400">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/releases"><img src="https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg" alt="GitHub release"></a>
  <img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.stromkalkulator.total" alt="Installs">
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml/badge.svg" alt="Hassfest"></a>
  <a href="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator"><img src="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator/graph/badge.svg" alt="codecov"></a>
  <a href="SECURITY.md"><img src="https://slsa.dev/images/gh-badge-level1.svg" alt="SLSA 1"></a>
</p>

Home Assistant-integrasjon som beregner **faktisk strømpris** i Norge - inkludert nettleie, avgifter og strømstøtte.

## Hva du får

Integrasjonen gir deg sensorer som viser din **faktiske strømpris** - ikke bare spotprisen. Den regner ut:

- **Nettleie** - Energiledd (dag/natt) og kapasitetsledd fra ditt nettselskap
- **Strømstøtte** - Automatisk beregning (90% over 96,25 øre/kWh)
- **Totalpris** - Alt inkludert, klar for Energy Dashboard
- **Månedlig forbruk** - Sporer forbruk og kostnader per måned
- **Faktura-sjekk** - Sammenlign med fakturaen når den kommer

## Installasjon

### Via HACS (anbefalt)

1. Klikk på knappen under for å åpne integrasjonen i HACS:
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fredrik-lindseth&repository=Stromkalkulator&category=integration)
2. Klikk **Download**
3. Start Home Assistant på nytt

_Alternativt: HACS > Integrations > Explore & Download Repositories > Søk etter "Strømkalkulator"_

### Manuell

Kopier `custom_components/stromkalkulator` til `/config/custom_components/`

## Oppsett

**Settings > Devices & Services > Add Integration > Strømkalkulator**

![Oppsett](images/setup.png)

### Steg 1: Velg nettselskap

Velg nettselskapet ditt fra nedtrekkslisten. Avgiftssone (mva og forbruksavgift) settes automatisk basert på nettselskapet.

### Boligtype

| Boligtype | Strømstøtte | Norgespris-tak | Kilde |
|-----------|-------------|----------------|-------|
| Bolig (standard) | 5000 kWh/mnd | 5000 kWh/mnd | [Forskrift § 5](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Fritidsbolig | Ingen | 1000 kWh/mnd | [Forskrift § 3](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Fritidsbolig (fast bosted) | 5000 kWh/mnd | 5000 kWh/mnd | [Forskrift § 11](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |

Over kWh-taket for Norgespris betaler du spotpris for resten av måneden. Fritidsboliger har ikke rett på strømstøtte med mindre du bor der fast (§ 11).

### Steg 2: Velg sensorer

Du trenger to sensorer:

- **Effektmåler (W)** - Sensor som viser nåværende strømforbruk i watt. Typisk fra AMS-leser via HAN-porten (f.eks. Tibber Pulse).
- **Spotpris-sensor (NOK/kWh)** - Sensor med gjeldende spotpris. Vanligvis "Current price" fra [Nord Pool-integrasjonen](https://www.home-assistant.io/integrations/nordpool/).
- **Strømleverandør-sensor** (valgfri) - Totalpris fra strømselskapet (f.eks. Tibber). Brukes til å vise hva du faktisk betaler.

Alle norske nettselskaper er støttet!

### Avgiftssoner

Avgiftssonen bestemmer mva og forbruksavgift, og settes automatisk fra nettselskapet ditt. Du kan overstyre i innstillingene hvis nødvendig.

| Avgiftssone  | Strømsoner          | Forbruksavgift | MVA |
| ------------ | ------------------- | -------------- | --- |
| Sør-Norge    | NO1, NO2, NO5       | 7,13 øre/kWh   | 25% |
| Nord-Norge   | NO3, NO4            | 7,13 øre/kWh   | 0%  |
| Tiltakssonen | Finnmark/Nord-Troms | 0 øre          | 0%  |

## Devices og sensorer

Integrasjonen oppretter fem devices med sensorer:

### Nettleie

Sanntids priser og beregninger for nettleie, strømstøtte og totalpris.

![Nettleie](images/nettleie.png)

### Strømstøtte

Viser hvor mye du får i strømstøtte (90% over 96,25 øre/kWh).

![Strømstøtte](images/strømstøtte.png)

### Norgespris

Sammenligner din spotprisavtale med Norgespris - så du kan se hva som lønner seg.

![Norgespris](images/norgespris.png)

### Månedlig forbruk

Sporer forbruk og kostnader for inneværende måned, fordelt på dag- og natt/helg-tariff.

![Månedlig forbruk](images/månedlig_forbruk.png)

### Forrige måned

Lagrer forrige måneds data for enkel faktura-verifisering.

![Forrige måned](images/forrige_måned.png)

## Bruk med Energy Dashboard

Energy Dashboard trenger to ting: en **forbruksmåler** (kWh) og en **prissensor** (kr/kWh). Strømkalkulator gir deg prissensoren — forbruksmåleren kommer fra din strømmåler-integrasjon.

### Hva kommer fra hvor?

| Hva           | Sensor                       | Kommer fra                                     |
| ------------- | ---------------------------- | ---------------------------------------------- |
| Forbruk (kWh) | Din forbruksmåler            | Noe som leser fra HANporten, Tibber Pulse osv. |
| Pris (kr/kWh) | **Totalpris inkl. avgifter** | Strømkalkulator                                |

### Oppsett steg for steg

1. Gå til **Settings > Dashboards > Energy**
2. Under **Electricity grid**, klikk **Add consumption**
3. **Consumed energy** — velg din kWh-forbrukssensor (f.eks. `sensor.power_consumption` fra AMSleseren din)
4. Slå på **Use an entity with current price**
5. Velg **Totalpris inkl. avgifter** (`sensor.totalpris_inkl_avgifter_*`)
6. Klikk **Save**

Nå viser dashboardet hva strømmen faktisk koster deg — inkludert nettleie, avgifter og strømstøtte.

> **Har du ikke en kWh-sensor?** Du trenger noe som leser av strømmåleren din via HAN-porten, f.eks. en [Tibber Pulse](https://www.home-assistant.io/integrations/tibber/) eller en annen AMS-leser.

**Tips:** Vil du se priskomponentene (spotpris, nettleie, avgifter) separat? Bruk et custom dashboard-kort som ApexCharts med sensorene fra denne integrasjonen.

## Strømavtaler

### Spotpris (vanligste)

Hvis du har vanlig spotprisavtale:

- Strømstøtten (90% over 96,25 øre) trekkes automatisk fra
- Sensoren "Strømstøtte" viser hvor mye du får i støtte

### Norgespris

Har du valgt [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) hos nettselskapet?

1. Kryss av "Jeg har Norgespris" i oppsett
2. Fast pris brukes: 50 øre (Sør-Norge) eller 40 øre (Nord-Norge)
3. Ingen strømstøtte - Norgespris erstatter spotpris og støtte

### Sammenligne avtalene

Usikker på hva som lønner seg? Sensoren "Prisforskjell Norgespris" viser:

- **Positiv verdi** = Du sparer med Norgespris
- **Negativ verdi** = Spotpris er billigere akkurat nå

## Sjekke mot faktura

Når nettleie-fakturaen kommer, kan du enkelt sjekke at tallene stemmer:

1. Gå til **Settings > Devices & Services > Strømkalkulator**
2. Klikk på "Forrige måned"-devicen
3. Sammenlign verdiene med fakturaen

**Tips:** Klikk på en sensor for å se detaljer som topp-3 effektdager og kostnader fordelt på dag/natt.

![Nettleie diagnostikk](images/nettleie_diagnostic.png)

## Støttede nettselskaper

**Alle norske nettselskaper er støttet!** 🎉

Prisene oppdateres årlig ved nyttår. Finner du feil eller utdaterte priser? [Opprett en PR](docs/CONTRIBUTING.md) eller et issue!

## Fusjon av nettselskaper

Nettselskaper i Norge fusjonerer jevnlig. Integrasjonen håndterer dette automatisk — hvis nettselskapet ditt har fusjonert, oppdateres konfigurasjonen ved neste oppstart. Forbruksdata og historikk bevares. Du får en melding under **Settings > Repairs** som bekrefter endringen.

## Sensorer

Integrasjonen oppretter 32 aktive sensorer fordelt på 5 devices. 12 diagnostikk-sensorer (individuelle avgiftssatser, nedbrytninger) er deaktivert som standard — de kan slås på under **Settings > Devices > Entities**.

Å deaktivere en sensor påvirker ikke beregningene. All logikk kjører i bakgrunnen uansett — sensorene er bare visning.

Se [SENSORS.md](docs/SENSORS.md) for komplett oversikt.

## Begrensninger

Integrasjonen er laget for **privatboliger med eget strømabonnement**.

**Ikke støttet (ennå):**

- Næringsliv (andre stønadssatser)
- Borettslag med fellesmåling

## Ofte stilte spørsmål

**Hvorfor viser sensoren "natt" midt på dagen?**

"Natt"-tariffen gjelder ikke bare om natten. Den heter egentlig "natt/helg" og brukes på:

- Netter (22:00-06:00) alle dager
- Hele helger (lørdag og søndag, hele døgnet)
- Helligdager (hele døgnet)

Så på en lørdag kl. 14:00 er "natt"-tariff helt riktig — du betaler den lavere satsen.

**Hvorfor er "Totalpris inkl. avgifter" høyere enn spotprisen?**

Spotprisen er bare strømmen. Totalpris inkluderer også nettleie (energiledd + kapasitetsledd), forbruksavgift, Enova-avgift og mva. For de fleste utgjør nettleie og avgifter 30-50% av totalprisen.

**Strømstøtte viser 0 — er det feil?**

Nei. Strømstøtte utbetales kun når spotprisen er over 96,25 øre/kWh (2026). Når prisen er lavere, er støtten 0.

**Tallene stemmer ikke helt med fakturaen?**

1-5% avvik er normalt. Integrasjonen beregner forbruk fra effektsensoren (Riemann-sum), mens fakturaen bruker strømmålerens kWh-teller. Se [beregninger.md](docs/beregninger.md#nøyaktighet) for detaljer.

## Dokumentasjon

| Dokument                                | Innhold                            |
| --------------------------------------- | ---------------------------------- |
| [SENSORS.md](docs/SENSORS.md)           | Alle sensorer og attributter       |
| [beregninger.md](docs/beregninger.md)   | Formler og avgiftssoner            |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Oppdatere priser / rapportere feil |
| [TESTING.md](docs/TESTING.md)           | Validere beregninger               |

## Verifisering av releases

Alle releases har en kryptografisk attestasjon som beviser at ZIP-filen ble bygd fra kildekoden i dette repoet. Se [SECURITY.md](SECURITY.md) for detaljer.

```bash
gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
```

## Lisens

MIT
