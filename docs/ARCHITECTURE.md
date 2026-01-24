# Arkitektur og Design

Dette dokumentet beskriver arkitekturen til Stromkalkulator og fungerer som en guide for a gjenskape eller videreutvikle integrasjonen.

## Formal

**Problemet:** Home Assistant viser bare spotpris (fra Nord Pool/Tibber), men norske stromfakturaer inneholder mange flere komponenter.

**Losningen:** En integrasjon som beregner faktisk totalpris inkludert:
- Spotpris (fra ekstern sensor)
- Energiledd (fra nettselskap, varierer dag/natt)
- Kapasitetsledd (basert pa topp-3 effektdager)
- Offentlige avgifter (forbruksavgift, Enova, MVA)
- Stromstotte (90% over 91,25 ore/kWh)

## Prosjektstruktur

```
stromkalkulator/
├── custom_components/stromkalkulator/   # HA-integrasjon
│   ├── __init__.py                      # Oppsett, PLATFORMS
│   ├── config_flow.py                   # UI-konfigurasjon
│   ├── const.py                         # TSO-data, konstanter
│   ├── coordinator.py                   # DataUpdateCoordinator
│   ├── sensor.py                        # Alle sensorer
│   └── manifest.json                    # HACS-metadata
├── packages/                            # Valgfrie YAML-pakker
│   ├── stromkalkulator_utility.yaml     # Utility meter dag/natt
│   └── stromkalkulator_test.yaml        # Valideringssensorer
├── tests/                               # pytest unit-tester
│   ├── test_stromstotte.py
│   ├── test_avgifter.py
│   ├── test_energiledd.py
│   └── test_kapasitetstrinn.py
└── docs/                                # Dokumentasjon
    ├── beregninger.md                   # Formler og eksempler
    ├── CONTRIBUTING.md                  # Legge til nettselskap
    ├── DEVELOPMENT.md                   # Utviklerinfo
    ├── TESTING.md                       # Testguide
    └── ARCHITECTURE.md                  # Dette dokumentet
```

## Kjernekomponenter

### 1. Coordinator (`coordinator.py`)

**Formal:** Sentral datahub som oppdateres hvert minutt.

**Ansvar:**
- Lese effekt fra brukerens sensor (W)
- Lese spotpris fra Nord Pool-sensor
- Beregne alle verdier (stromstotte, kapasitet, etc.)
- Lagre topp-3 effektdager til disk (persistens)

**Viktige metoder:**
```python
async def _async_update_data(self) -> dict:
    # 1. Les effekt og spotpris
    # 2. Oppdater daglig maks-effekt
    # 3. Beregn kapasitetstrinn
    # 4. Beregn stromstotte
    # 5. Beregn alle priser
    return data_dict
```

**Persistens:**
- Data lagres i `/config/.storage/stromkalkulator_{tso_id}`
- Format: `{"daily_max_power": {"2026-01-15": 5.2, ...}, "current_month": 1}`
- Nullstilles automatisk ved manedsskifte

### 2. Sensorer (`sensor.py`)

**22 sensorer gruppert i 3 devices:**

| Device | Sensorer |
|--------|----------|
| Nettleie | energiledd, energiledd_dag, energiledd_natt_helg, tariff, kapasitetstrinn, kapasitetstrinn_nummer, kapasitetstrinn_intervall, toppforbruk_1/2/3, snitt_toppforbruk, offentlige_avgifter, forbruksavgift, enovaavgift |
| Stromstotte | stromstotte, spotpris_etter_stotte, total_strompris_etter_stotte, stromstotte_aktiv |
| Norgespris | total_strompris_norgespris, prisforskjell_norgespris |

**Sensor-arkitektur:**
```python
class NettleieBaseSensor(CoordinatorEntity, SensorEntity):
    # Felles base for alle sensorer
    # Henter data fra coordinator.data dict
```

### 3. Config Flow (`config_flow.py`)

**Steg 1:** Velg nettselskap (TSO)
**Steg 2:** Velg avgiftssone (standard/nord_norge/tiltakssone)
**Steg 3:** Velg effektsensor (W)
**Steg 4:** Velg spotpris-sensor (NOK/kWh)
**Steg 5:** (Valgfritt) Velg stromselskap-pris-sensor

### 4. Konstanter (`const.py`)

**TSO_LIST:** Dict med alle nettselskaper og deres priser:
```python
TSO_LIST = {
    "bkk": {
        "name": "BKK",
        "prisomrade": "NO5",
        "supported": True,
        "energiledd_dag": 0.4613,
        "energiledd_natt": 0.2329,
        "kapasitetstrinn": [(2, 155), (5, 250), ...],
        "url": "https://...",
    },
    ...
}
```

**Avgiftssoner:**
```python
AVGIFTSSONER = {
    "standard": {"forbruksavgift": 0.0713, "mva": 0.25},
    "nord_norge": {"forbruksavgift": 0.0713, "mva": 0.0},
    "tiltakssone": {"forbruksavgift": 0.0, "mva": 0.0},
}
```

## Beregningsflyt

```
┌─────────────┐     ┌─────────────┐
│ Effektsensor│     │ Spotpris    │
│    (W)      │     │  (NOK/kWh)  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
       ┌─────────────────┐
       │   Coordinator   │ (oppdateres hvert minutt)
       └────────┬────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌───────┐  ┌─────────┐  ┌──────────┐
│ Topp-3│  │ Strom-  │  │ Energi-  │
│ effekt│  │ stotte  │  │ ledd     │
└───┬───┘  └────┬────┘  └────┬─────┘
    │           │            │
    ▼           ▼            ▼
┌─────────────────────────────────┐
│     total_strompris_etter_stotte│
│  = (spot - stotte) + energiledd │
│    + kapasitet/kWh + avgifter   │
└─────────────────────────────────┘
```

## Nodvendig for a gjenskape

### Steg 1: Grunnstruktur (manifest.json, __init__.py)

```python
# manifest.json
{
    "domain": "stromkalkulator",
    "name": "Stromkalkulator",
    "version": "1.0.0",
    "config_flow": true,
    "iot_class": "local_polling"
}

# __init__.py
PLATFORMS = ["sensor"]

async def async_setup_entry(hass, entry):
    coordinator = StromkalkulatorCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
```

### Steg 2: Config Flow

1. Lag schema med voluptuous
2. Bruk `selector` for a liste sensorer
3. Lagre config i `entry.data`

### Steg 3: Coordinator

1. Arv fra `DataUpdateCoordinator`
2. Sett `update_interval=timedelta(minutes=1)`
3. Implementer `_async_update_data()` som returnerer dict
4. Bruk `Store` for persistens

### Steg 4: Sensorer

1. Arv fra `CoordinatorEntity` og `SensorEntity`
2. Les fra `self.coordinator.data["key"]`
3. Sett `device_info` for groupering

### Steg 5: TSO-data

1. Samle priser fra nettselskapenes nettsider
2. Struktur: energiledd_dag, energiledd_natt, kapasitetstrinn-liste
3. Oppdater arlig (priser endres 1. januar)

## Viktige formler

### Stromstotte
```python
# 2025: Terskel 75 øre eks. mva × 1,25 = 93,75 øre inkl. mva
stromstotte = max(0, (spotpris - 0.9375) * 0.90)
```

### Kapasitetsledd per kWh
```python
kapasitet_per_kwh = (kapasitetsledd_mnd / dager_i_maned) / 24
```

### Totalpris
```python
total = (spotpris - stromstotte) + energiledd + kapasitet_per_kwh
```

### Dag/natt-tariff
```python
def is_day_rate(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # Lordag/sondag
        return False
    if is_holiday(dt):
        return False
    return 6 <= dt.hour < 22
```

## Testing

### Unit-tester (lokalt)
```bash
pipx run pytest tests/ -v
```

### Live-tester (HA)
Kopier `packages/stromkalkulator_test.yaml` og sjekk `sensor.test_alle_tester_ok`.

## Fremtidige forbedringer

### Planlagt
- [ ] Akkumulert kostnad med Riemann sum
- [ ] Custom dashboard-kort
- [ ] Automatisk utility_meter-oppsett via config_flow

### Vurdert
- [ ] Historikk-graf for stromstotte
- [ ] Varsel nar kapasitetstrinn oker
- [ ] Faktura-import for validering

## Kilder

- [NVE Nettleiestatistikk](https://www.nve.no/reguleringsmyndigheten/publikasjoner-og-data/statistikk/)
- [Skatteetaten Forbruksavgift](https://www.skatteetaten.no/satser/elektrisk-kraft/)
- [Stromstotte.no](https://www.stromstotte.no/)
- [Elhub Norgespris](https://elhub.no/norgespris/)
