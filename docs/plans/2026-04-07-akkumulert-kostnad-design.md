# Design: Akkumulert kostnadssensor for Energy Dashboard

**Dato:** 2026-04-07
**Issue:** hacs-strømkalkulator-rub3se

## Problem

Energy Dashboard ganger `pris × kWh` for hver oppdatering. Kapasitetsledd er en fast månedskostnad (f.eks. 250 kr/mnd) som ikke skalerer med forbruk. Fordelt som kr/kWh gir det feil månedstotal — overestimerer ved høyt forbruk, underestimerer ved lavt.

## Løsning

Ny akkumulerende kostnadssensor (`TOTAL_INCREASING`, `SensorDeviceClass.MONETARY`) som brukere velger som `stat_cost` i Energy Dashboard ("Use an entity tracking total costs").

## Beregning

Per oppdatering (hvert minutt):

```
delta_tid = sekunder siden siste oppdatering
delta_kwh = effekt × delta_tid (riemann sum, som eksisterende)

strompris = spotpris_eller_norgespris - stromstotte
delta_strom = delta_kwh × strompris
delta_energiledd = delta_kwh × energiledd_dag_eller_natt
delta_kapasitetsledd = delta_tid × (kapasitetsledd / sekunder_i_maaned)

delta_kostnad = delta_strom + delta_energiledd + delta_kapasitetsledd
```

Kapasitetsledd akkumuleres lineært gjennom hele måneden, uavhengig av forbruk — akkurat som på fakturaen. Ved månedsslutt har den akkumulert nøyaktig kapasitetsledd-beløpet.

## Sensor

- Navn: `Akkumulert strømkostnad`
- Device group: `DEVICE_MAANEDLIG`
- State class: `TOTAL_INCREASING`
- Device class: `MONETARY`
- Enhet: `kr`
- Enabled by default: Nei (proffløsning for de som vil ha korrekt Energy Dashboard)
- Nullstilles ved månedsskifte

## Attributter

| Attributt | Beskrivelse |
| --- | --- |
| `strompris_kr` | Akkumulert strømpris (spot/norgespris - støtte) |
| `energiledd_kr` | Akkumulert energiledd (dag + natt) |
| `kapasitetsledd_kr` | Akkumulert fast kapasitetsledd (lineært) |
| `total_kwh` | Akkumulert forbruk |

## Energy Dashboard oppsett

1. Consumed energy → AMS-leser kWh
2. Cost → "Use an entity tracking total costs" → `sensor.akkumulert_stromkostnad`

Månedstotalen matcher fakturaen fordi kapasitetsledd legges til tidsbasert, ikke per kWh.

## Berørte filer

- `coordinator.py` — ny akkumulator `_monthly_accumulated_cost` med breakdown
- `sensor.py` — ny sensor i `DEVICE_MAANEDLIG`, disabled by default
- `tests/` — tester for akkumulering, kapasitetsledd-lineæritiet, månedsskifte
