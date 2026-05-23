# Utvikling

## Arkitektur

Home Assistant viser bare spotpris. Norske strømfakturaer har flere komponenter (energiledd, kapasitetsledd, avgifter, strømstøtte). Strømkalkulator beregner faktisk totalpris.

### Filstruktur

```
custom_components/stromkalkulator/
├── __init__.py      # oppsett, registrer platforms
├── config_flow.py   # UI-konfigurasjon
├── const.py         # konstanter, avgifter, helligdager
├── dso.py           # nettselskap-data
├── coordinator.py   # DataUpdateCoordinator, beregningslogikk
├── sensor.py        # alle sensorer
├── diagnostics.py   # HA diagnostikk
├── strings.json     # oversettbare strenger
├── translations/    # nb.json, en.json
└── manifest.json    # HACS-metadata
```

Coordinator oppdateres hvert minutt, leser effekt og spotpris fra brukerens sensorer, beregner alle verdier og lagrer topp-3 effektdager til disk. Sensorer er gruppert i fem devices, arver fra `CoordinatorEntity` + `SensorEntity` og leser fra `coordinator.data["key"]`.

DSO-data (`dso.py`) er en dict med alle nettselskaper, energiledd dag/natt og kapasitetstrinn. Tidligere kalt `tso.py`. `CONF_DSO` beholder strengverdien `"tso"` for bakoverkompatibilitet.

### Beregningsflyt

```
Effektsensor (W) + Spotpris (NOK/kWh)
              │
              ▼
        Coordinator (1 min)
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
git clone https://github.com/fredrik-lindseth/Stromkalkulator.git
cd Stromkalkulator
pip install ruff pytest
pipx run pytest tests/ -v
ruff check custom_components/stromkalkulator/
```

## Deploy til HA (utvikling)

```bash
for f in __init__.py config_flow.py const.py dso.py coordinator.py sensor.py manifest.json; do
  ssh ha-local "cat > /config/custom_components/stromkalkulator/$f" < custom_components/stromkalkulator/$f
done
ssh ha-local "ha core restart"
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

Tilbake til HACS:

```bash
ssh ha-local "rm -rf /config/custom_components/stromkalkulator"
ssh ha-local "ha core restart"
# I HA UI: HACS > Integrations > Stromkalkulator > Download, restart igjen
```

## Vanlige oppgaver

- Oppdatere nettleiepriser: sjekkliste i [domain-rules.md](domain-rules.md#oppdatere-satser-årlig-ved-nyttår)
- Legge til sensor: sjekkliste i [domain-rules.md](domain-rules.md#legge-til-ny-sensor)
- Formler: [beregninger.md](beregninger.md)

## Feilsøking

```bash
ssh ha-local "ha core logs --follow"
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

| Feil                 | Årsak                     | Løsning                             |
| -------------------- | ------------------------- | ----------------------------------- |
| `ImportError`        | fil på HA er utdatert     | kopier oppdatert fil                |
| `Entity unavailable` | kildesensor mangler       | sjekk effekt/spotpris-sensor finnes |
| Feil kapasitetstrinn | data bygges over tid      | vent eller opprett testdata         |
| Feil dag/natt        | helligdag ikke registrert | beregnes fra påskeformelen          |

### Testdata for kapasitetstrinn

Lagringsfiler nøkles med `entry_id`. Finn din i HA under Innstillinger > Integrasjoner > Strømkalkulator.

```bash
ssh ha-local 'cat > /config/.storage/stromkalkulator_<entry_id> << EOF
{
  "version": 1,
  "data": {
    "daily_max_power": {
      "2026-01-17": {"kw": 5.2, "hour": 17},
      "2026-01-18": {"kw": 3.8, "hour": 7},
      "2026-01-19": {"kw": 4.5, "hour": 18}
    },
    "current_month": "2026-01"
  }
}
EOF'
```

## Kilder

- [Skatteetaten, forbruksavgift](https://www.skatteetaten.no/satser/elektrisk-kraft/)
- [NVE, nettleiestatistikk](https://www.nve.no/reguleringsmyndigheten/publikasjoner-og-data/statistikk/)
- [Stromstotte.no](https://www.stromstotte.no/)
- [Elhub, Norgespris](https://elhub.no/norgespris/)
