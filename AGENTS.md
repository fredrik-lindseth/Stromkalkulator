# Agent-instruksjoner for Strømkalkulator

## Prosjektbeskrivelse
Home Assistant-integrasjon for komplett oversikt over strømkostnader i Norge:
- **Nettleie** - Kapasitetsledd og energiledd fra norske nettselskaper
- **Strømstøtte** - Automatisk beregning av statlig strømstøtte (90% over terskel)
- **Norgespris** - Sammenligning med Elhubs fastprisprodukt (50 øre/kWh)
- **Offentlige avgifter** - Forbruksavgift, Enova-avgift og mva

## Språk
- Kode: Engelsk (variabelnavn, funksjoner, kommentarer i kode)
- Commit-meldinger: Norsk
- Dokumentasjon: Norsk (README, beregninger.md)
- Kommunikasjon: Norsk

## Git-preferanser
- Skriv commit-meldinger på norsk med beskrivende body
- Spør alltid før push til remote (push betyr ny release)
- Bump versjon i `manifest.json` ved nye releases
- Følg semantic versioning (MAJOR.MINOR.PATCH)

## Viktige filer
| Fil | Beskrivelse |
|-----|-------------|
| `custom_components/stromkalkulator/const.py` | TSO-priser, helligdager, strømstøtte-terskel |
| `custom_components/stromkalkulator/coordinator.py` | Beregningslogikk |
| `custom_components/stromkalkulator/sensor.py` | Sensor-definisjoner |
| `custom_components/stromkalkulator/manifest.json` | Versjon og avhengigheter |
| `beregninger.md` | Formler og beregningslogikk |

## Nettleie-priser
Prisene for nettleien oppdateres årlig (vanligvis 1. januar). Ved oppdatering:
1. Verifiser priser mot offisielle nettsider
2. Oppdater både energiledd (dag/natt) og kapasitetstrinn
3. Legg til kommentar med årstall og kilde

## Testing
- Verifiser at Home Assistant-integrasjonen laster uten feil
