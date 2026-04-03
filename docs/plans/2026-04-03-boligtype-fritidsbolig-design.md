# Design: Boligtype og fritidsbolig-stoette (issue #3)

Ref: https://github.com/fredrik-lindseth/Stromkalkulator/issues/3

## Bakgrunn

Stroemstotte og Norgespris har ulike kWh-tak avhengig av boligtype:

- **Bolig**: 5000 kWh/mnd stroemstotte, 5000 kWh/mnd Norgespris
- **Fritidsbolig**: Ingen stroemstotte (Forskrift SS 3), 1000 kWh/mnd Norgespris
- **Fritidsbolig (fast bosted)**: 5000 kWh/mnd begge (Forskrift SS 11)

I tillegg haandteres ikke Norgespris kWh-tak i koden i dag — Norgespris brukes ubegrenset uansett forbruk. Over taket skal man betale spotpris.

## Beslutninger

1. **Boligtype som dropdown med tre valg** — ikke fritt justerbart tak (lovfestede verdier)
2. **Haandheve Norgespris kWh-tak** — over taket betaler man spotpris
3. **Fritidsbolig faar ikke stroemstotte** — stroemstotte = 0, gjenstaaende = 0
4. **Bakoverkompatibilitet** — eksisterende config uten boligtype behandles som "bolig"

## Boligtype-konfigurasjon

Ny `CONF_BOLIGTYPE` i `const.py`:

| Verdi | Label | Stroemstotte-tak | Norgespris-tak | Kilde |
|-------|-------|------------------|----------------|-------|
| `bolig` | Bolig | 5000 kWh/mnd | 5000 kWh/mnd | Forskrift SS 5 |
| `fritidsbolig` | Fritidsbolig | 0 (ingen rett) | 1000 kWh/mnd | Forskrift SS 3 |
| `fritidsbolig_fast` | Fritidsbolig (fast bosted) | 5000 kWh/mnd | 5000 kWh/mnd | Forskrift SS 11 |

Hjelpefunksjoner:

```python
def get_norgespris_max_kwh(boligtype: str) -> int:
    if boligtype == "fritidsbolig":
        return 1000
    return 5000

def get_stromstotte_max_kwh(boligtype: str) -> int:
    if boligtype == "fritidsbolig":
        return 0
    return 5000
```

Default: `bolig`.

## Norgespris kWh-tak-haandhevelse

Ny logikk i `coordinator.py`. Naar maanedlig forbruk overstiger taket, bytter Norgespris-kunder til spotpris:

```python
norgespris_max = get_norgespris_max_kwh(self.boligtype)

if self.har_norgespris:
    if monthly_total_kwh >= norgespris_max:
        # Over taket: betaler spotpris
        total_price = spot_price + energiledd + fastledd_per_kwh
    else:
        total_price = norgespris + energiledd + fastledd_per_kwh
```

Stroemstotte bruker eget tak:

```python
stromstotte_max = get_stromstotte_max_kwh(self.boligtype)

if stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max:
    stromstotte = 0.0
elif spot_price > STROMSTOTTE_LEVEL:
    stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
else:
    stromstotte = 0.0
```

Gjenstaaende-sensor viser 0 for fritidsbolig, korrekt gjenstaaende for de to andre.

Norgespris-sammenligning beregnes alltid (ogsaa for spot-kunder), men med riktig kWh-tak.

## Config flow

Boligtype-velger i steg 1 (`async_step_user`), sammen med DSO og Norgespris-toggle.
Ogsaa tilgjengelig i options flow (`async_step_init`).

Hjelpetekst forklarer forskjellene med kildehenvisning til Forskrift SS 5, SS 3 og SS 11.

## Beroerte filer

| Fil | Endring |
|-----|---------|
| `const.py` | `CONF_BOLIGTYPE`, boligtype-konstanter, `get_norgespris_max_kwh()`, `get_stromstotte_max_kwh()` |
| `config_flow.py` | Boligtype-dropdown i steg 1 + options flow |
| `coordinator.py` | `self.boligtype`, dynamisk tak for stroemstotte og Norgespris |
| `sensor.py` | Oppdater attributter som hardkoder `STROMSTOTTE_MAX_KWH` |
| `strings.json` | Tekster og hjelpetekst for boligtype |
| `translations/nb.json` | Norsk |
| `translations/en.json` | Engelsk |
| `README.md` | Ny "Konfigurasjon"-seksjon, fjern fritidsbolig fra Begrensninger |
| `README.en.md` | Tilsvarende paa engelsk |
| `docs/beregninger.md` | Oppdater formler med boligtype |
| `docs/SENSORS.md` | Notere at tak varierer etter boligtype |

## Tester

**Nye tester:**

- Fritidsbolig stroemstotte = 0 (aldri stroemstotte)
- Fritidsbolig fast bosted = bolig (5000 kWh-tak for begge)
- Norgespris over tak -> spotpris (for bolig: 5000 kWh)
- Norgespris fritidsbolig 1000 kWh-tak
- Config flow bakoverkompatibilitet (manglende boligtype -> bolig)

**Oppdatere eksisterende tester:**

- `test_stromstotte_tak.py` — parametrisere med boligtype
- `test_coordinator_update.py` — legge til fritidsbolig-varianter

## README-endringer

Ny "Konfigurasjon"-seksjon som dokumenterer alle config flow-valg med standardverdier, beskrivelse og kilder. Fritidsbolig fjernes fra Begrensninger.

## Kilder

- Forskrift om stroemstoenad: https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791
- Regjeringens stroemtiltak (Norgespris): https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
