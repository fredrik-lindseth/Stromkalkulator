# Agent-instruksjoner for Stromkalkulator

## Prosjektoversikt

Home Assistant HACS-integrasjon som beregner **faktisk strompris** i Norge.

**Hovedsensor:** `sensor.total_strompris_etter_stotte`

Inkluderer: spotpris + nettleie + avgifter - stromstotte

## Arkitektur

```
custom_components/stromkalkulator/
├── __init__.py      # Oppsett, registrer platforms
├── config_flow.py   # UI-konfigurasjon (velg nettselskap, sensorer)
├── const.py         # TSO-priser, helligdager, konstanter
├── coordinator.py   # DataUpdateCoordinator, all beregningslogikk
├── sensor.py        # 22 sensorer gruppert i 3 devices
└── manifest.json    # HACS-metadata, versjon
```

## Viktige filer

| Fil | Nar du endrer |
|-----|---------------|
| `const.py` | Legge til nettselskap, oppdatere priser, endre avgifter |
| `coordinator.py` | Endre beregningslogikk, legge til ny funksjonalitet |
| `sensor.py` | Legge til/endre sensorer |
| `config_flow.py` | Endre konfigurasjonsflyten |

## Nodvendige formler

```python
# Stromstotte (90% over 91.25 ore/kWh)
stromstotte = max(0, (spotpris - 0.9125) * 0.90)

# Kapasitetsledd per kWh
kapasitet_per_kwh = (kapasitetsledd_mnd / dager_i_maned) / 24

# Totalpris
total = (spotpris - stromstotte) + energiledd + kapasitet_per_kwh

# Dag/natt-tariff
is_day = weekday < 5 and not is_holiday and 6 <= hour < 22
```

## Testing

```bash
# Unit-tester (lokalt)
pipx run pytest tests/ -v

# Lint
ruff check custom_components/stromkalkulator/
```

## Deploy til Home Assistant

```bash
# Kopier filer (scp virker ikke, bruk ssh cat)
ssh ha-local "cat > /config/custom_components/stromkalkulator/sensor.py" < custom_components/stromkalkulator/sensor.py

# Restart HA
ssh ha-local "ha core restart"

# Sjekk logger
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

## Vanlige oppgaver

### Legge til nettselskap
1. Finn priser pa nettselskapets nettside
2. Legg til i `TSO_LIST` i `const.py`
3. Sett `supported: True`
4. Test at integrasjonen laster

### Oppdatere priser (arlig)
1. Sjekk nettselskapenes nettsider (priser endres ofte 1. januar)
2. Oppdater `energiledd_dag`, `energiledd_natt`, `kapasitetstrinn` i `const.py`
3. Oppdater avgiftssatser hvis endret (sjekk Skatteetaten)

### Legge til sensor
1. Definer sensor-klasse i `sensor.py`
2. Legg til i `async_setup_entry()`
3. Hent data fra `coordinator.data["key"]`

## Dokumentasjon

| Fil | Innhold |
|-----|---------|
| `docs/ARCHITECTURE.md` | Detaljert arkitektur og gjenskapingsguide |
| `docs/beregninger.md` | Alle formler, avgiftssoner, eksempler |
| `docs/CONTRIBUTING.md` | Guide for a legge til nettselskap |
| `docs/TESTING.md` | Testguide (unit + live) |

## Feilsoking

| Problem | Losning |
|---------|---------|
| `ImportError` | Kopier oppdatert fil til HA |
| `Entity unavailable` | Sjekk at kildesensorer finnes |
| Feil kapasitetstrinn | Data bygges over tid, nullstilles ved manedsskifte |
| Feil dag/natt | Sjekk helligdager i `const.py` |

## Avhengigheter

- **Effektsensor (W)** - Tibber Pulse, AMS-leser, etc.
- **Spotpris-sensor (NOK/kWh)** - Nord Pool-integrasjonen

Ingen Python-pakker (ren HA-integrasjon).
