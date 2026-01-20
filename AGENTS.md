# Agent-instruksjoner for Nettleie

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
- Spør alltid før push til remote
- Bump versjon i `manifest.json` ved nye releases
- Følg semantic versioning (MAJOR.MINOR.PATCH)

## Viktige filer
| Fil | Beskrivelse |
|-----|-------------|
| `custom_components/nettleie/const.py` | TSO-priser, helligdager, strømstøtte-terskel |
| `custom_components/nettleie/coordinator.py` | Beregningslogikk |
| `custom_components/nettleie/sensor.py` | Sensor-definisjoner |
| `custom_components/nettleie/manifest.json` | Versjon og avhengigheter |
| `beregninger.md` | Formler og beregningslogikk |

## TSO-priser
Prisene for nettselskaper (TSO) oppdateres årlig (vanligvis 1. januar). Ved oppdatering:
1. Verifiser priser mot offisielle nettsider
2. Oppdater både energiledd (dag/natt) og kapasitetstrinn
3. Legg til kommentar med årstall og kilde

## Testing
- Kjør `pytest` før commit hvis det finnes tester
- Verifiser at Home Assistant-integrasjonen laster uten feil
