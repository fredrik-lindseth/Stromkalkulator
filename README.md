# Stromkalkulator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg)](https://github.com/fredrik-lindseth/Stromkalkulator/releases)

Home Assistant-integrasjon som beregner **faktisk strompris** i Norge - inkludert nettleie, avgifter og stromstotte.

![Integrasjon](images/integration.png)

## Hva dette gir deg

En sensor (`sensor.total_strompris_etter_stotte`) som viser din **faktiske strompris per kWh**, inkludert:

- Spotpris fra Nord Pool
- Nettleie (energiledd dag/natt + kapasitetsledd)
- Offentlige avgifter (forbruksavgift + Enova)
- Minus stromstotte (90% over 96,25 ore/kWh inkl. mva)

## Installasjon

### Via HACS

1. HACS > Integrations > Meny (tre prikker) > Custom repositories
2. Legg til `https://github.com/fredrik-lindseth/Stromkalkulator` som "Integration"
3. Last ned "Stromkalkulator"
4. Start Home Assistant pa nytt

### Manuell

Kopier `custom_components/stromkalkulator` til `/config/custom_components/`

## Konfigurasjon

**Settings > Devices & Services > Add Integration > Stromkalkulator**

Du trenger:
- **Effektsensor** - Stromforbruk i Watt (f.eks. Tibber Pulse)
- **Spotpris-sensor** - Nord Pool "Current price" (f.eks. `sensor.nord_pool_no5_current_price`)

### Oppsett basert pa din stromavtale

#### Med Norgespris (fra nettselskapet)

Hvis du har valgt [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/) hos nettselskapet:

1. **Konfigurer integrasjonen** med "Jeg har Norgespris" avkrysset
2. Bruker fast pris: **50 ore/kWh** (Sor-Norge) eller **40 ore/kWh** (Nord-Norge/Tiltakssonen)
3. Ingen stromstotte - Norgespris erstatter bade spotpris og stotte
4. Bruk `sensor.total_strompris_etter_stotte` i Energy Dashboard

> **Merk:** Norgespris inkluderer mva. Nord-Norge har mva-fritak, derfor lavere pris.

#### Med spotpris og stromstotte (standard)

Hvis du har vanlig spotprisavtale med stromstotte:

1. Bruk `sensor.total_strompris_etter_stotte` i Energy Dashboard
2. Sensor `sensor.stromstotte` viser stottebelop per kWh
3. Stotten (90% over 96,25 ore/kWh) trekkes automatisk fra i totalprisen

![Stromstotte](images/sensor_strømstøtte.png)

#### Uten stromstotte

Hvis du ikke har stromstotte (f.eks. naring, hytte, eller Nord-Norge med lave priser):

1. Bruk `sensor.total_strompris_for_stotte` for totalpris uten stotte
2. Eller bruk `sensor.nettleie_total` hvis du kun vil se nettleie

### Sammenligne spotpris vs Norgespris

Usikker pa om Norgespris lønner seg for deg?

- `sensor.prisforskjell_norgespris` viser forskjellen mellom spotpris og Norgespris
- Positiv verdi = du sparer med Norgespris
- Negativ verdi = spotpris er billigere

### Begrensninger

Denne integrasjonen stotter **privatboliger med eget stromabonnement**.

**Forenklet modell:**
- **Forbruk over 5000 kWh/mnd**: Integrasjonen beregner stromstotte pa alt forbruk. I virkeligheten far du kun stotte pa de forste 5000 kWh. For de fleste husholdninger er dette ikke et problem.
- **Norgespris over 5000 kWh**: Samme forenkling - vi antar at alt forbruk far Norgespris.

**Ikke stottet:**
- **Fritidsbolig** - Har 1000 kWh grense for stromstotte (ikke 5000 kWh)
- **Naringsliv** - Har andre stonadssatser
- **Fjernvarme/narvarme** - Egen stotteordning
- **Borettslag med fellesmaling** - Stotte utbetales til borettslaget

## Energy Dashboard

For a vise faktisk strompris i Energy Dashboard:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Velg din kWh-sensor (f.eks. `sensor.tibber_pulse_*_accumulated_consumption`)
4. **"Use an entity with current price"**: Velg `sensor.total_strompris_etter_stotte`

## Sensorer

| Sensor                                | Beskrivelse                                           |
|---------------------------------------|-------------------------------------------------------|
| `sensor.total_strompris_etter_stotte` | Din faktiske totalpris (for Energy Dashboard)         |
| `sensor.stromstotte`                  | Stotte per kWh                                        |
| `sensor.kapasitetstrinn`              | Manedlig kapasitetskostnad                            |
| `sensor.tariff`                       | "dag" eller "natt" (natt er ogsa helg og helligdager) |
| `sensor.prisforskjell_norgespris`     | Sammenligning med Norgespris                          |

![Nettleie](images/sensor_nettleie.png)
![Norgespris](images/sensor_norgespris.png)

Se [docs/beregninger.md](docs/beregninger.md) for alle sensorer og formler.

## Verifisere mot faktura

For a sjekke at integrasjonen beregner riktig, kan du sammenligne med fakturaen fra nettselskapet:

### Hva du trenger

1. **Faktura fra nettselskapet** - Viser energiledd, kapasitetsledd og forbruk
2. **Utility meter-sensorer** - For a splitte forbruk pa dag/natt (se nedenfor)
3. **Tilgang til HA-historikk** - For a finne manedens verdier

### Slik sammenligner du

1. **Energiledd (variabel del)**
   - Finn dag-forbruk og natt-forbruk fra utility meter-sensorer
   - Gang med energiledd-sats fra nettselskapets prisliste
   - Sammenlign med "Energiledd" pa fakturaen

2. **Kapasitetsledd (fast del)**
   - Sjekk `sensor.kapasitetstrinn` ved manedens slutt
   - Denne skal matche "Kapasitetsledd" pa fakturaen
   - Merk: Trinn bestemmes av snitt av 3 hoyeste effekttopper

3. **Avvik a forvente**
   - 1-5% avvik er normalt (avrunding, maleravvik)
   - Storre avvik kan skyldes feil priser i integrasjonen

### Eksempel

```
Faktura januar 2026:
- Energiledd dag: 450 kWh x 0,3640 kr = 163,80 kr
- Energiledd natt: 320 kWh x 0,2640 kr = 84,48 kr
- Kapasitetsledd (5-10 kW): 300 kr

Stromkalkulator:
- sensor.forbruk_dag: 452 kWh (OK, 0,4% avvik)
- sensor.forbruk_natt: 318 kWh (OK, 0,6% avvik)
- sensor.kapasitetstrinn: 300 kr (eksakt match)
```

## Utility Meter (valgfritt)

For a splitte forbruk pa dag/natt-tariff:

1. Kopier `packages/stromkalkulator_utility.yaml` til `/config/packages/`
2. Erstatt `sensor.BYTT_EFFEKT_SENSOR` med din sensor
3. Aktiver packages i `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

## Stottede nettselskaper

Arva, Barents Nett, BKK, Elinett, Elmea, Elvia, Fagne, Foie, Glitre Nett, Griug, Lede, Linea, Linja, Lnett, Mellom, Midtnett, Nettselskapet, Noranett, Norgesnett, Nordvest Nett, Tensio, Vevig, + Egendefinert

Mangler ditt? Se [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

## Dokumentasjon

| Dokument                                | Innhold                          |
|-----------------------------------------|----------------------------------|
| [beregninger.md](docs/beregninger.md)   | Formler, avgiftssoner, eksempler |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Legge til nettselskap            |
| [TESTING.md](docs/TESTING.md)           | Validere beregninger             |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md)   | Utviklerinfo                     |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arkitektur og design             |

## Lisens

MIT
