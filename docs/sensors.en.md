# Sensors

6 devices, 53 sensors total (35 active by default).

| Device              | Active | Total |
| ------------------- | ------ | ----- |
| Grid tariff         | 11     | 19    |
| Electricity subsidy | 6      | 7     |
| Norgespris          | 4      | 4     |
| Monthly consumption | 8      | 12    |
| Previous month      | 6      | 6     |
| Export              | 0      | 5     |

Enable more: **Settings > Devices > Strømkalkulator > (device) > Entities**, toggle "Enabled". The coordinator computes everything regardless, sensors are display only.

Sensors marked _(optional)_ are disabled by default.

---

## Grid tariff (Nettleie)

Main device, named "Nettleie ({grid company})".

### Energy component

| Sensor     | Unit   | Description                                                     |
| ---------- | ------ | ---------------------------------------------------------------- |
| Energiledd | kr/kWh | What you pay per kWh right now (switches between day/night rate) |
| Tariff     | -      | "dag" (day) or "natt" (night), controls the utility_meter        |

Day: Mon-Fri 06-22 (not holidays). Night: 22-06, weekends, holidays.

### Capacity

| Sensor                                   | Unit     | Description                                                          |
| ----------------------------------------- | -------- | ---------------------------------------------------------------------- |
| Kapasitetstrinn                           | kr/month | Fixed monthly cost based on the average of the top-3 power days        |
| Snitt toppforbruk                         | kW       | Average of the top-3, determines the tier                              |
| Toppforbruk #1, #2, #3                    | kW       | The three highest power days this month                                |
| Margin til neste trinn                    | kW       | How much more you can use before the next (more expensive) tier        |
| Kapasitetsvarsel                          | -        | "on" when the margin is below the threshold, for alerts/automations    |
| _(optional)_ Kapasitetstrinn (nummer)     | -        | The tier you're on (1, 2, 3, ...)                                       |
| _(optional)_ Kapasitetstrinn (intervall)  | -        | The kW range for your tier (e.g. "2-5 kW")                              |

**Toppforbruk #1-3** have attributes `dato` (YYYY-MM-DD) and `time` (0-23).

### Electricity price

| Sensor                                       | Unit   | Description                                                |
| ---------------------------------------------- | ------ | -------------------------------------------------------------- |
| Total strømpris (før støtte)                   | kr/kWh | Spot price + grid tariff, before the subsidy is deducted       |
| Strømpris per kWh                              | kr/kWh | Spot price + energy component, without the capacity charge     |
| _(optional)_ Total strømpris (strømavtale)     | kr/kWh | Using your provider's price instead of the spot price          |

### Diagnostics (taxes)

| Sensor                             | Unit   | Description                                |
| ------------------------------------ | ------ | --------------------------------------------- |
| _(optional)_ Energiledd dag          | kr/kWh | Day rate incl. all taxes and VAT               |
| _(optional)_ Energiledd natt/helg    | kr/kWh | Night/weekend rate incl. all taxes and VAT     |
| _(optional)_ Offentlige avgifter     | kr/kWh | Consumption tax + Enova levy incl. VAT         |
| _(optional)_ Forbruksavgift          | kr/kWh | Electricity tax incl. VAT                      |
| _(optional)_ Enovaavgift             | kr/kWh | Enova levy incl. VAT                           |

---

## Electricity subsidy (Strømstøtte)

| Sensor                                          | Unit   | Description                                                                                                                                          |
| -------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strømstøtte                                        | kr/kWh | The government subsidy per kWh when the spot price is above 96.25 øre (90% of the excess)                                                                |
| Spotpris etter støtte                              | kr/kWh | Spot price minus the subsidy                                                                                                                              |
| Total strømpris etter støtte                       | kr/kWh | The real total price: spot price + grid tariff - subsidy                                                                                                  |
| Totalpris inkl. avgifter                           | kr/kWh | Price sensor for the Energy Dashboard. Capacity charge spread per kWh (inaccurate with deviating consumption). For a correct total: use [Akkumulert strømkostnad](#energy-dashboard) |
| Strømstøtte aktiv nå                               | -      | "Ja"/"Nei" whether the spot price is above the threshold                                                                                                  |
| Strømstøtte gjenstående kWh                        | kWh    | How much of the monthly subsidy cap remains (residence=5000, holiday home=0)                                                                              |
| _(optional)_ Strømpris per kWh (etter støtte)      | kr/kWh | Like "Strømpris per kWh", but with the subsidy deducted                                                                                                   |

---

## Norgespris

| Sensor                             | Unit   | Description                                                                      |
| ------------------------------------- | ------ | ------------------------------------------------------------------------------------ |
| Total strømpris (norgespris)          | kr/kWh | What you'd pay with Norgespris: fixed 50 øre + grid tariff                            |
| Strømpris (Norgespris-ordningen)      | kr/kWh | The pure electricity component: fixed 50 øre under the cap, spot price above it       |
| Prisforskjell (norgespris)            | kr/kWh | Positive = you pay more than Norgespris (Norgespris is cheaper)                       |
| Norgespris aktiv nå                   | -      | "Ja"/"Nei" whether you've selected Norgespris                                         |

kWh cap: residence=5000, holiday home=1000. Above the cap, you pay the spot price.

---

## Monthly consumption

Resets automatically at the change of month.

### Consumption

| Sensor                        | Unit | Description                                          |
| -------------------------------- | ---- | ---------------------------------------------------------- |
| Månedlig forbruk dagtariff        | kWh  | Consumption on the day tariff this month                    |
| Månedlig forbruk natt/helg        | kWh  | Consumption on the night/weekend tariff this month           |
| Månedlig forbruk totalt           | kWh  | Sum of day and night                                          |

Attributes on "Månedlig forbruk totalt": `dag_kwh`, `natt_kwh`, `dag_pct`, `natt_pct`.

### Costs

| Sensor                                    | Unit | Description                                                        |
| --------------------------------------------- | ---- | ------------------------------------------------------------------------ |
| Månedlig nettleie total                       | kr   | The bottom line: grid tariff + taxes - subsidy                           |
| Dagens kostnad                                | kr   | Accumulated cost since midnight                                           |
| Estimert månedskostnad                        | kr   | Forecast for the whole month, based on consumption so far                 |
| Norgespris besparelse                         | kr   | Accumulated savings/loss vs. the alternative plan                         |
| Norgespris-kompensasjon                       | kr   | Accumulated (norgespris - spot price) x kWh this month                    |
| _(optional)_ Månedlig nettleie                | kr   | Grid tariff so far: day + night energy component + capacity charge        |
| _(optional)_ Månedlig avgifter                | kr   | Consumption tax + Enova levy incl. VAT                                    |
| _(optional)_ Månedlig strømstøtte             | kr   | Estimated subsidy this month                                              |
| _(optional)_ Akkumulert strømkostnad          | kr   | For the Energy Dashboard with correct monthly totals                      |

Attributes on "Akkumulert strømkostnad": `strompris_kr`, `energiledd_kr`, `kapasitetsledd_kr`, `total_kwh`.

Attributes on "Månedlig nettleie total": `nettleie_kr`, `stromstotte_kr`, `forbruk_dag_kwh`, `forbruk_natt_kwh`, `forbruk_total_kwh`, `vektet_snittpris_kr_per_kwh`.

---

## Previous month (Forrige måned)

Stored at the change of month. Used for invoice verification.

| Sensor                                     | Unit | Description                                          |
| --------------------------------------------- | ---- | ---------------------------------------------------------- |
| Forrige måned forbruk dagtariff                | kWh  | Day consumption last month                                  |
| Forrige måned forbruk natt/helg                | kWh  | Night/weekend consumption last month                        |
| Forrige måned forbruk totalt                   | kWh  | Total consumption last month                                |
| Forrige måned nettleie                         | kr   | Compare with the invoice                                     |
| Forrige måned toppforbruk                      | kW   | Average of the top-3, determined the capacity tier          |
| Forrige måned Norgespris-kompensasjon          | kr   | Norgespris compensation for the previous month               |

All have a `maaned` attribute (e.g. "januar 2026").

**The "Forrige måned nettleie" sensor** also has: `energiledd_dag_kr`, `energiledd_natt_kr`, `kapasitetsledd_kr`, `snitt_topp_3_kw`, `norgespris_differanse_kr`.

**The "Forrige måned toppforbruk" sensor** has: `maaned`, `topp_1_dato`, `topp_1_kw`, `topp_1_time`, `topp_2_dato`, `topp_2_kw`, `topp_2_time`, `topp_3_dato`, `topp_3_kw`, `topp_3_time`.

---

## Export (Eksport, solar)

For prosumers. Requires a configured export power sensor. All disabled by default.

| Sensor                                        | Unit | Description                              |
| -------------------------------------------------- | ---- | --------------------------------------------- |
| _(optional)_ Månedlig eksport kWh                   | kWh  | Exported energy this month                     |
| _(optional)_ Månedlig eksport inntekt               | kr   | Revenue (spot price x kWh)                     |
| _(optional)_ Månedlig nettokostnad                  | kr   | Consumption cost minus export revenue          |
| _(optional)_ Forrige måned eksport kWh              | kWh  | Exported energy last month                     |
| _(optional)_ Forrige måned eksport inntekt          | kr   | Export revenue last month                      |

---

## Energy Dashboard

Two options for the cost component.

### Option 1: Price sensor

Use `Totalpris inkl. avgifter`. Simplest, but the capacity charge becomes wrong with deviating consumption.

1. **Settings > Dashboards > Energy > Add consumption**
2. Select your kWh sensor under "Consumed energy"
3. Enable "Use an entity with current price"
4. Select `Totalpris inkl. avgifter`

### Option 2: Accumulated cost (recommended)

Use `Akkumulert strømkostnad`. The capacity charge is distributed linearly over time, so the monthly total matches the invoice.

1. Enable it: **Settings > Devices > Månedlig forbruk > Entities > Akkumulert strømkostnad**
2. **Settings > Dashboards > Energy > Add consumption**
3. Select your kWh sensor under "Consumed energy"
4. Enable "Use an entity tracking total costs"
5. Select `Akkumulert strømkostnad`

The consumption meter (kWh) comes from your AMS reader, not Strømkalkulator.

---

## Examples

Top-3 power days as an entities card:

```yaml
type: entities
title: Topp-3 effektdager
entities:
  - entity: sensor.toppforbruk_1
    secondary_info: attribute
    attribute: dato
  - entity: sensor.toppforbruk_2
    secondary_info: attribute
    attribute: dato
  - entity: sensor.toppforbruk_3
    secondary_info: attribute
    attribute: dato
  - entity: sensor.snitt_toppforbruk
  - entity: sensor.kapasitetstrinn
```

Alert when approaching the next tier:

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.nettleie_bkk_margin_til_neste_trinn
        below: 1.0
    action:
      - service: notify.mobile_app
        data:
          message: "{{ states('sensor.nettleie_bkk_margin_til_neste_trinn') }} kW to next capacity tier."
```

---

## Invoice verification

| Invoice line item     | Sensor                            | Where                            |
| ------------------------ | ------------------------------------ | -------------------------------------- |
| Energy day (kWh)          | Forrige måned forbruk dagtariff       | State                                   |
| Energy night (kWh)        | Forrige måned forbruk natt/helg       | State                                   |
| Energy day (kr)           | Forrige måned nettleie                | Attribute: `energiledd_dag_kr`          |
| Energy night (kr)         | Forrige måned nettleie                | Attribute: `energiledd_natt_kr`         |
| Capacity charge (kr)       | Forrige måned nettleie                | Attribute: `kapasitetsledd_kr`          |
| Capacity tier (kW)         | Forrige måned toppforbruk             | State (avg. top-3)                       |

---

## Technical details

- Updates every minute
- Consumption with an energy sensor (recommended): delta from the meter register, exact against the invoice
- Consumption without an energy sensor: Riemann sum from the power sensor, 1-5 % deviation per month
- Storage: `/config/.storage/stromkalkulator_<entry_id>` (unique per instance)
- See [input-sensorer.md](input-sensorer.md) for sensor setup (Norwegian)

### Manually editing stored data

Stop HA first, otherwise your changes get overwritten.

```bash
ha core stop
# edit /config/.storage/stromkalkulator_<entry_id>
ha core start
```

Find the `entry_id` in the URL under Settings > Devices & Services > Strømkalkulator.

#### Fields

| Field                             | Type   | Description                                        |
| ------------------------------------ | ------ | -------------------------------------------------------- |
| `daily_max_power`                    | dict   | `{"YYYY-MM-DD": {"kw": float, "hour": int}}`               |
| `monthly_consumption`                | dict   | `{"dag": float, "natt": float}` (kWh)                       |
| `current_month`                      | string | `"YYYY-MM"`                                                 |
| `daily_cost`                          | float  | Today's accumulated cost (kr)                               |
| `monthly_accumulated_cost`           | float  | Accumulated monthly cost (kr)                               |
| `previous_month_consumption`         | dict   | Consumption last month                                      |
| `previous_month_top_3`               | dict   | Top-3 last month                                             |
| `previous_month_kapasitetsledd`      | int    | Capacity charge last month (kr/month)                        |
| `previous_month_kapasitetstrinn`     | string | Tier range last month (e.g. `"5-10 kW"`)                      |
| `monthly_export_kwh`                 | float  | Export this month                                            |
| `monthly_export_revenue`             | float  | Export revenue this month                                    |
| `monthly_cost`                       | float  | Total consumption cost this month (kr)                       |

#### Examples

Reset peak power:

```json
{ "daily_max_power": {} }
```

Correct a single day:

```json
{ "daily_max_power": { "2026-04-03": { "kw": 4.2, "hour": 17 } } }
```

Reset monthly consumption:

```json
{ "monthly_consumption": { "dag": 0.0, "natt": 0.0 } }
```

See [beregninger.md](beregninger.md) for formulas (Norwegian).
