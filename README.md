# Stromkalkulator

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg)](https://github.com/fredrik-lindseth/Stromkalkulator/releases)

Home Assistant-integrasjon som beregner **faktisk strompris** i Norge - inkludert nettleie, avgifter og stromstotte.

## Hva dette gir deg

En sensor (`sensor.total_strompris_etter_stotte`) som viser din **faktiske strompris per kWh**, inkludert:

- Spotpris fra Nord Pool
- Nettleie (energiledd dag/natt + kapasitetsledd)
- Offentlige avgifter (forbruksavgift + Enova)
- Minus stromstotte (90% over 91,25 ore/kWh)

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

## Energy Dashboard

For a vise faktisk strompris i Energy Dashboard:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Velg din kWh-sensor (f.eks. `sensor.tibber_pulse_*_accumulated_consumption`)
4. **"Use an entity with current price"**: Velg `sensor.total_strompris_etter_stotte`

## Sensorer

| Sensor | Beskrivelse |
|--------|-------------|
| `sensor.total_strompris_etter_stotte` | Din faktiske totalpris (for Energy Dashboard) |
| `sensor.stromstotte` | Stotte per kWh |
| `sensor.kapasitetstrinn` | Manedlig kapasitetskostnad |
| `sensor.tariff` | "dag" eller "natt" |
| `sensor.prisforskjell_norgespris` | Sammenligning med Norgespris |

Se [docs/beregninger.md](docs/beregninger.md) for alle sensorer og formler.

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

| Dokument | Innhold |
|----------|---------|
| [beregninger.md](docs/beregninger.md) | Formler, avgiftssoner, eksempler |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Legge til nettselskap |
| [TESTING.md](docs/TESTING.md) | Validere beregninger |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Utviklerinfo |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arkitektur og design |

## Lisens

MIT
