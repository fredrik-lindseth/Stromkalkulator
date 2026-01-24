<p align="center">
  <img src="images/logo.png" alt="Strømkalkulator" width="400">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/releases"><img src="https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg" alt="GitHub release"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator"><img src="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator/graph/badge.svg" alt="codecov"></a>
</p>

Home Assistant-integrasjon som beregner **faktisk strømpris** i Norge - inkludert nettleie, avgifter og strømstøtte.

![Oppsett](images/setup.png)

## Hva dette gir deg

En sensor (`sensor.total_strompris_etter_stotte`) som viser din **faktiske strømpris per kWh**. Sensoren tilpasser seg automatisk til din konfigurasjon:

**Med Norgespris:**
- Fast pris (50 øre Sør-Norge / 40 øre Nord-Norge)
- Nettleie (energiledd + kapasitetsledd)

**Med spotpris (standard):**
- Spotpris fra Nord Pool
- Nettleie (energiledd + kapasitetsledd)
- Minus strømstøtte (90% over 96,25 øre/kWh)

## Installasjon

### Via HACS

1. HACS > Integrations > Meny (tre prikker) > Custom repositories
2. Legg til `https://github.com/fredrik-lindseth/Stromkalkulator` som "Integration"
3. Last ned "Strømkalkulator"
4. Start Home Assistant på nytt

### Manuell

Kopier `custom_components/stromkalkulator` til `/config/custom_components/`

## Konfigurasjon

**Settings > Devices & Services > Add Integration > Strømkalkulator**

Du trenger:
- **Effektsensor** - Strømforbruk i Watt (f.eks. Tibber Pulse)
- **Spotpris-sensor** - Nord Pool "Current price" (f.eks. `sensor.nord_pool_no5_current_price`)

### Oppsett basert på din strømavtale

#### Med Norgespris (fra nettselskapet)

Hvis du har valgt [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/) hos nettselskapet:

1. **Konfigurer integrasjonen** med "Jeg har Norgespris" avkrysset
2. Bruker fast pris: **50 øre/kWh** (Sør-Norge) eller **40 øre/kWh** (Nord-Norge/Tiltakssonen)
3. Ingen strømstøtte - Norgespris erstatter både spotpris og støtte
4. Bruk `sensor.total_strompris_etter_stotte` i Energy Dashboard

> **Merk:** Norgespris inkluderer mva. Nord-Norge har mva-fritak, derfor lavere pris.

#### Med spotpris og strømstøtte (standard)

Hvis du har vanlig spotprisavtale med strømstøtte:

1. Bruk `sensor.total_strompris_etter_stotte` i Energy Dashboard
2. Sensor `sensor.stromstotte` viser støttebeløp per kWh
3. Støtten (90% over 96,25 øre/kWh) trekkes automatisk fra i totalprisen

![Strømstøtte](images/strømstøtte.png)

#### Uten strømstøtte

Hvis du ikke har strømstøtte (f.eks. næring, hytte, eller Nord-Norge med lave priser):

1. Bruk `sensor.total_strompris_for_stotte` for totalpris uten støtte
2. Eller bruk `sensor.nettleie_total` hvis du kun vil se nettleie

### Sammenligne spotpris vs Norgespris

Usikker på om Norgespris lønner seg for deg?

- `sensor.prisforskjell_norgespris` viser forskjellen mellom spotpris og Norgespris
- Positiv verdi = du sparer med Norgespris
- Negativ verdi = spotpris er billigere

### Begrensninger

Denne integrasjonen støtter **privatboliger med eget strømabonnement**.

**Forenklet modell:**
- **Forbruk over 5000 kWh/mnd**: Integrasjonen beregner strømstøtte på alt forbruk. I virkeligheten får du kun støtte på de første 5000 kWh. For de fleste husholdninger er dette ikke et problem.
- **Norgespris over 5000 kWh**: Samme forenkling - vi antar at alt forbruk får Norgespris.

**Ikke støttet:**
- **Fritidsbolig** - Har 1000 kWh grense for strømstøtte (ikke 5000 kWh)
- **Næringsliv** - Har andre stønadssatser
- **Fjernvarme/nærvarme** - Egen støtteordning
- **Borettslag med fellesmåling** - Støtte utbetales til borettslaget

## Energy Dashboard

For å vise faktisk strømpris i Energy Dashboard:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Velg din kWh-sensor (f.eks. `sensor.tibber_pulse_*_accumulated_consumption`)
4. **"Use an entity with current price"**: Velg `sensor.total_strompris_etter_stotte`

## Sensorer

| Sensor                                | Beskrivelse                                           |
|---------------------------------------|-------------------------------------------------------|
| `sensor.total_strompris_etter_stotte` | Din faktiske totalpris (for Energy Dashboard)         |
| `sensor.stromstotte`                  | Støtte per kWh                                        |
| `sensor.kapasitetstrinn`              | Månedlig kapasitetskostnad                            |
| `sensor.tariff`                       | "dag" eller "natt" (natt er også helg og helligdager) |
| `sensor.prisforskjell_norgespris`     | Sammenligning med Norgespris                          |

![Nettleie sensorer](images/nettleie_sensors.png)
![Nettleie diagnostikk](images/nettleie_diagnostic.png)
![Norgespris](images/norgespris.png)

Se [docs/beregninger.md](docs/beregninger.md) for alle sensorer og formler.

## Verifisere mot faktura

For å sjekke at integrasjonen beregner riktig, sammenlign med fakturaen fra nettselskapet.

### Komplett oppsett for faktura-verifisering

1. **Kopier utility-pakken:**
   ```bash
   cp packages/stromkalkulator_utility.yaml /config/packages/
   ```

2. **Rediger filen** - bytt ut `sensor.BYTT_EFFEKT_SENSOR` med din effekt-sensor (W)

3. **Aktiver packages** i `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

4. **Start Home Assistant på nytt**

### Automasjoner som følger med

Pakken inkluderer to automasjoner som kjører automatisk:

| Automasjon                        | Trigger                | Funksjon                              |
|-----------------------------------|------------------------|---------------------------------------|
| `stromkalkulator_tariff_bytte`    | `sensor.tariff` endres | Oppdaterer utility_meter til dag/natt |
| `stromkalkulator_tariff_oppstart` | HA starter             | Setter riktig tariff ved oppstart     |

> Du trenger ikke gjøre noe manuelt - tariff-byttet skjer automatisk.

### Sensorer du får

Etter oppsett får du disse sensorene for faktura-sammenligning:

| Sensor                                   | Beskrivelse          | Matcher faktura-post      |
|------------------------------------------|----------------------|---------------------------|
| `sensor.strom_maanedlig_dag`             | kWh på dag-tariff    | Energiledd dag (forbruk)  |
| `sensor.strom_maanedlig_natt`            | kWh på natt-tariff   | Energiledd natt (forbruk) |
| `sensor.maanedlig_energiledd_dag`        | Energiledd dag i kr  | Energiledd dag (sum)      |
| `sensor.maanedlig_energiledd_natt`       | Energiledd natt i kr | Energiledd natt (sum)     |
| `sensor.kapasitetstrinn`                 | Kapasitetsledd i kr  | Kapasitetsledd            |
| `sensor.maanedlig_forbruksavgift`        | Forbruksavgift i kr  | Forbruksavgift            |
| `sensor.maanedlig_enovaavgift`           | Enova-avgift i kr    | Enovaavgift               |
| `sensor.maanedlig_stromstotte`           | Strømstøtte i kr     | Midlert. strømstønad      |
| `sensor.maanedlig_nettleie_etter_stotte` | Totalt å betale      | Å betale                  |

### Eksempel: BKK-faktura desember 2025

```
Faktura fra BKK:                      Strømkalkulator:
─────────────────────────────────────────────────────────────────
Energiledd dag:    667 kWh = 240 kr   sensor.maanedlig_energiledd_dag: ~240 kr
Energiledd natt:   887 kWh = 211 kr   sensor.maanedlig_energiledd_natt: ~211 kr
Kapasitetsledd:    5-10 kW = 415 kr   sensor.kapasitetstrinn: 415 kr
Forbruksavgift:   1555 kWh = 244 kr   sensor.maanedlig_forbruksavgift: ~244 kr
Enovaavgift:      1555 kWh =  19 kr   sensor.maanedlig_enovaavgift: ~19 kr
Strømstøtte:      1107 kWh = -122 kr  sensor.maanedlig_stromstotte: ~122 kr
─────────────────────────────────────────────────────────────────
Å betale:                  1006 kr    sensor.maanedlig_nettleie_etter_stotte: ~1006 kr
```

### Forventet avvik

- **1-5% avvik er normalt** - skyldes avrunding og måleravvik
- **Strømstøtte kan avvike mer** - fakturaen bruker time-for-time priser, vi bruker gjennomsnitt
- **Større avvik?** Sjekk at energiledd-satsene i integrasjonen matcher nettselskapets prisliste

## Støttede nettselskaper

Arva, Barents Nett, BKK, Elinett, Elmea, Elvia, Fagne, Føie, Glitre Nett, Griug, Lede, Linea, Linja, Lnett, Mellom, Midtnett, Nettselskapet, Noranett, Norgesnett, Nordvest Nett, Tensio, Vevig, + Egendefinert

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
