# Utvikling

Guide for utvikling og vedlikehold av Stromkalkulator.

## Prosjektstruktur

```
custom_components/stromkalkulator/
├── __init__.py      # Oppsett, registrer platforms
├── config_flow.py   # UI-konfigurasjon
├── const.py         # Konstanter, avgifter, helligdager
├── tso.py           # Nettselskap-data (TSO_LIST)
├── coordinator.py   # DataUpdateCoordinator, beregningslogikk
├── sensor.py        # 22 sensorer
└── manifest.json    # HACS-metadata
```

## Lokalt oppsett

```bash
# Klone repo
git clone https://github.com/fredrik-lindseth/Stromkalkulator.git
cd Stromkalkulator

# Installer dev-avhengigheter
pip install ruff pytest

# Kjor tester
pipx run pytest tests/ -v

# Lint
ruff check custom_components/stromkalkulator/
```

## Deploy til Home Assistant

### Kopiere filer (utvikling)

```bash
# Kopier enkeltfil (scp virker ikke pa HA, bruk ssh cat)
ssh ha-local "cat > /config/custom_components/stromkalkulator/sensor.py" < custom_components/stromkalkulator/sensor.py

# Kopier alle filer
for f in __init__.py config_flow.py const.py tso.py coordinator.py sensor.py manifest.json; do
  ssh ha-local "cat > /config/custom_components/stromkalkulator/$f" < custom_components/stromkalkulator/$f
done

# Restart HA
ssh ha-local "ha core restart"

# Sjekk logger
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

### Ga tilbake til HACS (produksjon)

Nar du er ferdig med utvikling og vil bruke HACS igjen:

```bash
# 1. Slett manuelt kopiert integrasjon
ssh ha-local "rm -rf /config/custom_components/stromkalkulator"

# 2. Restart HA
ssh ha-local "ha core restart"

# 3. I HA UI: HACS → Integrations → Stromkalkulator → Download
# 4. Restart HA igjen
```

## Testdata for kapasitetstrinn

For a teste kapasitetstrinn-beregninger kan du opprette testdata manuelt:

```bash
ssh ha-local 'cat > /config/.storage/stromkalkulator_bkk << EOF
{
  "version": 1,
  "data": {
    "daily_max_power": {
      "2026-01-17": 5.2,
      "2026-01-18": 3.8,
      "2026-01-19": 4.5
    },
    "current_month": 1
  }
}
EOF'
```

Endre `stromkalkulator_bkk` til din TSO-id (f.eks. `stromkalkulator_tensio`).

## Vanlige oppgaver

### Legge til nettselskap

1. Apne `custom_components/stromkalkulator/tso.py`
2. Finn nettselskapet (alle er registrert, de fleste med `supported: False`)
3. Legg til priser fra nettselskapets nettside:
   - `energiledd_dag` og `energiledd_natt` i NOK/kWh
   - `kapasitetstrinn` som liste med tupler: `(kW-grense, kr/mnd)`
4. Sett `supported: True`
5. Test at integrasjonen laster

### Oppdatere priser (arlig)

Priser endres ofte 1. januar:

1. Sjekk nettselskapenes nettsider
2. Oppdater `energiledd_dag`, `energiledd_natt`, `kapasitetstrinn` i `tso.py`
3. Oppdater avgiftssatser i `const.py` hvis endret (sjekk Skatteetaten)
4. Oppdater helligdager for nytt ar i `const.py`

### Legge til sensor

1. Definer sensor-klasse i `sensor.py`
2. Legg til i `async_setup_entry()`
3. Hent data fra `coordinator.data["key"]`

## Viktige formler

```python
# Stromstotte (90% over 93.75 ore/kWh, 2025-sats)
stromstotte = max(0, (spotpris - 0.9375) * 0.90)

# Kapasitetsledd per kWh
kapasitet_per_kwh = (kapasitetsledd_mnd / dager_i_maned) / 24

# Totalpris
total = (spotpris - stromstotte) + energiledd + kapasitet_per_kwh

# Dag/natt-tariff
is_day = weekday < 5 and not is_holiday and 6 <= hour < 22
```

## Feilsoking

### Logger

```bash
# Se logger (live)
ssh ha-local "ha core logs --follow"

# Sok etter stromkalkulator
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

### Vanlige feil

| Feil | Arsak | Losning |
|------|-------|---------|
| `ImportError` | Fil pa HA er utdatert | Kopier oppdatert fil |
| `Entity unavailable` | Kildesensor mangler | Sjekk at power/spotpris-sensor finnes |
| Feil kapasitetstrinn | Data bygges over tid | Vent eller opprett testdata |
| Feil dag/natt | Helligdag ikke registrert | Oppdater HELLIGDAGER i const.py |

### Sjekkliste for deploy

```bash
# 1. Lint
ruff check custom_components/stromkalkulator/

# 2. Test
pipx run pytest tests/ -v

# 3. Kopier filer
ssh ha-local "cat > /config/..." < ...

# 4. Restart
ssh ha-local "ha core restart"

# 5. Sjekk logger
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

## Kilder

- [Skatteetaten - Forbruksavgift](https://www.skatteetaten.no/satser/elektrisk-kraft/)
- [NVE - Nettleiestatistikk](https://www.nve.no/reguleringsmyndigheten/publikasjoner-og-data/statistikk/)
- [Stromstotte.no](https://www.stromstotte.no/)
- [Elhub - Norgespris](https://elhub.no/norgespris/)
