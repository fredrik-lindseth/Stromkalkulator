# Utvikling

Guide for utvikling og vedlikehold av Strømkalkulator.

## Arkitektur

### Formål

**Problemet:** Home Assistant viser bare spotpris, men norske strømfakturaer inneholder mange flere komponenter.

**Løsningen:** En integrasjon som beregner faktisk totalpris inkludert spotpris, energiledd, kapasitetsledd, offentlige avgifter og strømstøtte.

### Prosjektstruktur

```
custom_components/stromkalkulator/
├── __init__.py      # Oppsett, registrer platforms
├── config_flow.py   # UI-konfigurasjon
├── const.py         # Konstanter, avgifter, helligdager
├── tso.py           # Nettselskap-data (DSO_LIST)
├── coordinator.py   # DataUpdateCoordinator, beregningslogikk
├── sensor.py        # Alle sensorer
├── diagnostics.py   # HA diagnostikk-integrasjon
├── strings.json     # Oversettbare strenger
├── translations/    # Oversettelser (nb.json, en.json)
└── manifest.json    # HACS-metadata
```

### Kjernekomponenter

**Coordinator** (`coordinator.py`):
- Sentral datahub som oppdateres hvert minutt
- Leser effekt og spotpris fra brukerens sensorer
- Beregner alle verdier (strømstøtte, kapasitet, etc.)
- Lagrer topp-3 effektdager til disk (persistens)

**Sensorer** (`sensor.py`):
- 36 sensorer gruppert i 5 devices
- Arver fra `CoordinatorEntity` og `SensorEntity`
- Leser fra `coordinator.data["key"]`

**DSO-data** (`tso.py`):
- Dict med alle nettselskaper og deres priser + 1 egendefinert
- Energiledd dag/natt, kapasitetstrinn

### Beregningsflyt

```
Effektsensor (W) + Spotpris (NOK/kWh)
              │
              ▼
        Coordinator (oppdateres hvert minutt)
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
 Topp-3    Strøm-    Energi-
 effekt    støtte    ledd
    │         │         │
    └─────────┴─────────┘
              ▼
    total_strompris_etter_stotte
```

## Lokalt oppsett

```bash
# Klone repo
git clone https://github.com/fredrik-lindseth/Stromkalkulator.git
cd Stromkalkulator

# Installer dev-avhengigheter
pip install ruff pytest

# Kjør tester
pipx run pytest tests/ -v

# Lint
ruff check custom_components/stromkalkulator/
```

## Deploy til Home Assistant

### Kopiere filer (utvikling)

```bash
# Kopier alle filer
for f in __init__.py config_flow.py const.py tso.py coordinator.py sensor.py manifest.json; do
  ssh ha-local "cat > /config/custom_components/stromkalkulator/$f" < custom_components/stromkalkulator/$f
done

# Restart HA
ssh ha-local "ha core restart"

# Sjekk logger
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

### Gå tilbake til HACS (produksjon)

```bash
# 1. Slett manuelt kopiert integrasjon
ssh ha-local "rm -rf /config/custom_components/stromkalkulator"

# 2. Restart HA
ssh ha-local "ha core restart"

# 3. I HA UI: HACS → Integrations → Stromkalkulator → Download
# 4. Restart HA igjen
```

## Vanlige oppgaver

### Oppdatere nettleiepriser (årlig)

Se sjekklisten i [domain-rules.md](domain-rules.md#oppdatere-nettleiepriser).
Helligdager beregnes automatisk fra påskeformelen — ingen manuell oppdatering nødvendig.

### Legge til sensor

Se sjekklisten i [domain-rules.md](domain-rules.md#legge-til-ny-sensor).

## Viktige formler

Se [beregninger.md](beregninger.md) for alle formler og eksempler.

## Feilsøking

### Logger

```bash
# Se logger (live)
ssh ha-local "ha core logs --follow"

# Søk etter strømkalkulator
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

### Vanlige feil

| Feil                 | Årsak                     | Løsning                               |
|----------------------|---------------------------|---------------------------------------|
| `ImportError`        | Fil på HA er utdatert     | Kopier oppdatert fil                  |
| `Entity unavailable` | Kildesensor mangler       | Sjekk at power/spotpris-sensor finnes |
| Feil kapasitetstrinn | Data bygges over tid      | Vent eller opprett testdata           |
| Feil dag/natt        | Helligdag ikke registrert | Beregnes automatisk fra påskeformelen |

### Testdata for kapasitetstrinn

Lagringsfiler er nøklet med `entry_id` (ikke nettselskap). Finn din entry_id i HA under Innstillinger → Integrasjoner → Strømkalkulator.

```bash
# Erstatt <entry_id> med din faktiske entry_id
ssh ha-local 'cat > /config/.storage/stromkalkulator_<entry_id> << EOF
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

## Kilder

- [Skatteetaten - Forbruksavgift](https://www.skatteetaten.no/satser/elektrisk-kraft/)
- [NVE - Nettleiestatistikk](https://www.nve.no/reguleringsmyndigheten/publikasjoner-og-data/statistikk/)
- [Stromstotte.no](https://www.stromstotte.no/)
- [Elhub - Norgespris](https://elhub.no/norgespris/)
