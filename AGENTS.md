w# Agent-instruksjoner for Strømkalkulator

## Generelle regler
Se OpenCode "developer" agent for standard utviklingspraksis.

## Prosjektspesifikk

## Prosjektbeskrivelse
Home Assistant-integrasjon for komplett oversikt over strømkostnader i Norge:
- **Nettleie** - Kapasitetsledd og energiledd fra norske nettselskaper
- **Strømstøtte** - Automatisk beregning av statlig strømstøtte (90% over terskel)
- **Norgespris** - Sammenligning med Elhubs fastprisprodukt (50 øre/kWh)
- **Offentlige avgifter** - Forbruksavgift, Enova-avgift og mva

## Viktige filer
| Fil                                                | Beskrivelse                                  |
|----------------------------------------------------|----------------------------------------------|
| `custom_components/stromkalkulator/const.py`       | TSO-priser, helligdager, strømstøtte-terskel |
| `custom_components/stromkalkulator/coordinator.py` | Beregningslogikk                             |
| `custom_components/stromkalkulator/sensor.py`      | Sensor-definisjoner                          |
| `custom_components/stromkalkulator/manifest.json`  | Versjon og avhengigheter                     |
| `docs/beregninger.md`                              | Formler og beregningslogikk                  |

## Nettleie-priser
Prisene for nettleien oppdateres årlig (vanligvis 1. januar). Ved oppdatering:
1. Verifiser priser mot offisielle nettsider
2. Oppdater både energiledd (dag/natt) og kapasitetstrinn
3. Legg til kommentar med årstall og kilde

## Testing
- Verifiser at Home Assistant-integrasjonen laster uten feil

## Debugging og Deployment

### Lokasjon på Home Assistant
```
Integration:     /config/custom_components/stromkalkulator/
Loggfil:         Tilgjengelig via `ha core logs` (ingen fil på disk)
HA config:       /config/configuration.yaml
```

### SSH til Home Assistant
```bash
# Koble til
ssh ha-local

# Sjekk status
ha core info

# Se logger (live)
ha core logs --follow

# Se siste 100 linjer
ha core logs | tail -100

# Søk etter stromkalkulator-feil
ha core logs | grep -i stromkalkulator

# Restart HA
ha core restart
```

### Kopiere filer til HA
```bash
# Kopier enkeltfil (scp virker ikke, bruk ssh cat)
ssh ha-local "cat > /config/custom_components/stromkalkulator/sensor.py" < custom_components/stromkalkulator/sensor.py

# Kopier const.py
ssh ha-local "cat > /config/custom_components/stromkalkulator/const.py" < custom_components/stromkalkulator/const.py

# Kopier coordinator.py
ssh ha-local "cat > /config/custom_components/stromkalkulator/coordinator.py" < custom_components/stromkalkulator/coordinator.py
```

### Hva se etter i loggene
```
# FEIL - Må fikses:
ERROR (MainThread) [homeassistant.config_entries] Error setting up entry
ImportError: cannot import name 'X' from 'custom_components.stromkalkulator.const'

# ADVARSEL - OK, bare info om custom integrations:
WARNING (SyncWorker_0) [homeassistant.loader] We found a custom integration stromkalkulator

# SUKSESS - Integrasjonen lastet:
INFO [custom_components.stromkalkulator] Setting up Strømkalkulator
```

### Vanlige feil
| Feil                                  | Årsak                      | Løsning                                           |
|---------------------------------------|----------------------------|---------------------------------------------------|
| `ImportError: cannot import name 'X'` | const.py på HA er utdatert | Kopier oppdatert const.py                         |
| `Error setting up entry`              | Syntaksfeil i Python       | Kjør `ruff check` lokalt først                    |
| `Entity not available`                | Sensor-avhengighet mangler | Sjekk at power_sensor og spot_price_sensor finnes |

### Sjekkliste før deploy
```bash
# 1. Lint lokalt
ruff check custom_components/stromkalkulator/

# 2. Kopier filer
ssh ha-local "cat > /config/custom_components/stromkalkulator/sensor.py" < custom_components/stromkalkulator/sensor.py
ssh ha-local "cat > /config/custom_components/stromkalkulator/const.py" < custom_components/stromkalkulator/const.py

# 3. Restart eller reload
ssh ha-local "ha core restart"

# 4. Sjekk logger
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
