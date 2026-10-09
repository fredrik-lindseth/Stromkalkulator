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

## Grid tariff (Nettleie)

Main device, named "Nettleie ({grid company})".

### Energy component

| Sensor     | Unit    | Description                                                      |
| ---------- | ------- | ---------------------------------------------------------------- |
| Energiledd | NOK/kWh | What you pay per kWh right now (switches between day/night rate) |
| Tariff     | -       | "dag" (day) or "natt" (night), controls the utility_meter        |

Day: Mon-Fri 06-22 (not holidays). Night: 22-06, weekends, holidays.

### Capacity

| Sensor                                   | Unit     | Description                                                       |
| ---------------------------------------- | -------- | ----------------------------------------------------------------- |
| Kapasitetstrinn                          | kr/month | Fixed monthly cost based on the average of the top-3 power days   |
| Snitt toppforbruk                        | kW       | Average of the top-3, determines the tier                         |
| Toppforbruk #1, #2, #3                   | kW       | The three highest power days this month                           |
| Margin til neste trinn                   | kW       | How much more you can use before the next (more expensive) tier   |
| Kapasitetsvarsel (binary_sensor)         | on/off   | On when the margin is below the threshold, for alerts/automations |
| _(optional)_ Kapasitetstrinn (nummer)    | -        | The tier you're on (1, 2, 3, ...)                                 |
| _(optional)_ Kapasitetstrinn (intervall) | -        | The kW range for your tier (e.g. "2-5 kW")                        |

Toppforbruk #1-3 have the attributes `dato` (YYYY-MM-DD) and `time` (0-23).

### Electricity price

| Sensor                                     | Unit    | Description                                                |
| ------------------------------------------ | ------- | ---------------------------------------------------------- |
| Total strømpris (før støtte)               | NOK/kWh | Spot price + grid tariff, before the subsidy is deducted   |
| Strømpris per kWh                          | NOK/kWh | Spot price + energy component, without the capacity charge |
| _(optional)_ Total strømpris (strømavtale) | NOK/kWh | Using your provider's price instead of the spot price      |

### Diagnostics (taxes)

| Sensor                            | Unit    | Description                                |
| --------------------------------- | ------- | ------------------------------------------ |
| _(optional)_ Energiledd dag       | NOK/kWh | Day rate incl. all taxes and VAT           |
| _(optional)_ Energiledd natt/helg | NOK/kWh | Night/weekend rate incl. all taxes and VAT |
| _(optional)_ Offentlige avgifter  | NOK/kWh | Consumption tax + Enova levy incl. VAT     |
| _(optional)_ Forbruksavgift       | NOK/kWh | Electricity tax incl. VAT                  |
| _(optional)_ Enovaavgift          | NOK/kWh | Enova levy incl. VAT                       |

## Electricity subsidy (Strømstøtte)

| Sensor                                        | Unit    | Description                                                                                                                                                                          |
| --------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Strømstøtte                                   | NOK/kWh | The government subsidy per kWh when the spot price is above 96.25 øre (90% of the excess)                                                                                            |
| Spotpris etter støtte                         | NOK/kWh | Spot price minus the subsidy                                                                                                                                                         |
| Total strømpris etter støtte                  | NOK/kWh | The real total price: spot price + grid tariff - subsidy                                                                                                                             |
| Totalpris inkl. avgifter                      | NOK/kWh | Price sensor for the Energy Dashboard. Capacity charge spread per kWh (inaccurate with deviating consumption). For a correct total: use [Akkumulert strømkostnad](#energy-dashboard) |
| Strømstøtte aktiv nå (binary_sensor)          | on/off  | On when the spot price is above the threshold                                                                                                                                        |
| Strømstøtte gjenstående kWh                   | kWh     | How much of the monthly subsidy cap remains (residence=5000, holiday home=0)                                                                                                         |
| _(optional)_ Strømpris per kWh (etter støtte) | NOK/kWh | Like "Strømpris per kWh", but with the subsidy deducted                                                                                                                              |

## Norgespris

| Sensor                           | Unit    | Description                                                                     |
| -------------------------------- | ------- | ------------------------------------------------------------------------------- |
| Total strømpris (norgespris)     | NOK/kWh | What you'd pay with Norgespris: fixed 50 øre + grid tariff                      |
| Strømpris (Norgespris-ordningen) | NOK/kWh | The pure electricity component: fixed 50 øre under the cap, spot price above it |
| Prisforskjell (norgespris)       | NOK/kWh | Positive = you pay more than Norgespris (Norgespris is cheaper)                 |
| Norgespris aktiv nå              | on/off  | On if you have selected Norgespris                                              |

kWh cap: residence=5000, holiday home=1000. Above the cap, you pay the spot price.

## Monthly consumption

Resets automatically at the change of month.

### Consumption

| Sensor                     | Unit | Description                                        |
| -------------------------- | ---- | -------------------------------------------------- |
| Månedlig forbruk dagtariff | kWh  | Consumption on the day tariff this month           |
| Månedlig forbruk natt/helg | kWh  | Consumption on the night/weekend tariff this month |
| Månedlig forbruk totalt    | kWh  | Sum of day and night                               |

Attributes on "Månedlig forbruk totalt": `dag_kwh`, `natt_kwh`, `dag_pct`, `natt_pct`.

### Costs

| Sensor                               | Unit | Description                                                        |
| ------------------------------------ | ---- | ------------------------------------------------------------------ |
| Månedlig nettleie total              | NOK  | The bottom line: grid tariff + taxes - subsidy                     |
| Dagens kostnad                       | NOK  | Accumulated cost since midnight                                    |
| Estimert månedskostnad               | NOK  | Forecast for the whole month, based on consumption so far          |
| Norgespris besparelse                | NOK  | Accumulated savings/loss vs. the alternative plan                  |
| Norgespris-kompensasjon              | NOK  | Accumulated (norgespris - spot price) x kWh this month             |
| _(optional)_ Månedlig nettleie       | NOK  | Booked grid tariff so far: energy component + capacity charge      |
| _(optional)_ Månedlig avgifter       | NOK  | Booked consumption tax + Enova levy incl. VAT                      |
| _(optional)_ Månedlig strømstøtte    | NOK  | Booked subsidy this month                                          |
| _(optional)_ Akkumulert strømkostnad | NOK  | For the Energy Dashboard with correct monthly totals               |

Attributes on "Akkumulert strømkostnad": `strompris_kr`, `energiledd_kr`, `kapasitetsledd_kr`, `total_kwh`.

Attributes on "Månedlig nettleie total": `nettleie_kr`, `stromstotte_kr`, `forbruk_dag_kwh`, `forbruk_natt_kwh`, `forbruk_total_kwh`, `vektet_snittpris_kr_per_kwh`.

Attributes on "Månedlig nettleie": `energiledd_dag_kr`, `energiledd_natt_kr`, `avgifter_kr`, `kapasitetsledd_kr`. The split follows the invoice: the energy components exclude the public levies, which are listed separately. The four add up to the sensor value.

Attributes on "Månedlig avgifter": `forbruksavgift_kr`, `enovaavgift_kr`, `avgiftssone`. The bookkeeping records the two levies together, so the split is the total distributed by the ratio between the rates. When the consumption tax changes mid-month (New Year and 1 April), the split is an estimate while the total is exact.

All the monthly sensors above read kroner the cost core has booked per settled interval. They do not multiply rates by the month's kilowatt-hours, so they stay correct when a rate or the subsidy changed during the month.

## Previous month (Forrige måned)

Stored at the change of month. Used for invoice verification.

| Sensor                                | Unit | Description                                        |
| ------------------------------------- | ---- | -------------------------------------------------- |
| Forrige måned forbruk dagtariff       | kWh  | Day consumption last month                         |
| Forrige måned forbruk natt/helg       | kWh  | Night/weekend consumption last month               |
| Forrige måned forbruk totalt          | kWh  | Total consumption last month                       |
| Forrige måned nettleie                | NOK  | Compare with the invoice                           |
| Forrige måned toppforbruk             | kW   | Average of the top-3, determined the capacity tier |
| Forrige måned Norgespris-kompensasjon | NOK  | Norgespris compensation for the previous month     |

All have a `maaned` attribute (e.g. "januar 2026").

The "Forrige måned nettleie" sensor also has `energiledd_dag_kr`, `energiledd_natt_kr`, `avgifter_kr`, `stromstotte_kr`, `kapasitetsledd_kr`, `snitt_topp_3_kw`, `norgespris_differanse_kr` and `bokforte_kroner`.

The sensor sums booked amounts from the monthly archive and adds the full monthly capacity charge. Rate changes during the month are preserved. An older archive without booked components is shown as unknown with `bokforte_kroner: false`; the next month rollover creates a complete archive.

Delayed readings can also correct the previous month's peak hours and fixed charge. The calculation basis and tariff are frozen at month rollover. Older storage may lack this basis for annual weighted charges; a late correction then makes the grid tariff unknown with `fastledd_grunnlag_bekreftet: false`, because later annual peaks cannot establish the historical charge.

These snapshots set `last_reset` to the start of the current month. The value is replaced wholesale at the change of month, and without `last_reset` the HA statistics would record the difference between two months as a delta.

The "Forrige måned toppforbruk" sensor has `maaned`, `topp_1_dato`, `topp_1_kw`, `topp_1_time`, `topp_2_dato`, `topp_2_kw`, `topp_2_time`, `topp_3_dato`, `topp_3_kw`, `topp_3_time`.

## Export (Eksport, solar)

For prosumers. Requires a configured export power sensor. All disabled by default.

| Sensor                                     | Unit | Description                           |
| ------------------------------------------ | ---- | ------------------------------------- |
| _(optional)_ Månedlig eksport kWh          | kWh  | Exported energy this month            |
| _(optional)_ Månedlig eksport inntekt      | NOK  | Revenue (spot price x kWh)            |
| _(optional)_ Månedlig nettokostnad         | NOK  | Consumption cost minus export revenue |
| _(optional)_ Forrige måned eksport kWh     | kWh  | Exported energy last month            |
| _(optional)_ Forrige måned eksport inntekt | NOK  | Export revenue last month             |

Export revenue uses the spot price for the quarter-hour when the energy was supplied. Zero and negative prices are valid. With missing price coverage, revenue and net cost are unknown; revenue attributes show the known subtotal and `kwh_uten_pris`. Net cost also requires a known fixed charge.

## Measurement data watchdog

| Sensor                                   | Unit   | Description                        |
| ---------------------------------------- | ------ | ---------------------------------- |
| Measurement data problem (binary_sensor) | on/off | On when an input sensor has failed |

The sensor is `device_class: problem` and sits under Diagnostics. It is never
gated on the spot price: a spot price outage is exactly one of the cases it
reports, so it has to work when the price is missing.

Three things turn it on:

- Outage: a configured input has been `unavailable` or `unknown` for more
  than 30 minutes. The limit is fixed and covers HA restarts, integration
  updates and a network hiccup.
- Frozen energy counter: the energy meter reports, but the number has not
  increased for more hours than the threshold. Set it under Configure, default
  three hours. Raise it for a cabin or site that sits idle for stretches.
- Expired spot price: the spot price has been gone longer than the two hour
  cache. Consumption, grid charges, taxes and known Norgespris below the
  consumption cap are still booked. Spot-dependent energy cost, subsidy and
  the Norgespris comparison lack a price basis; missing coverage remains visible
  in data quality.

Attributes:

| Attribute               | Contents                                                         |
| ----------------------- | ---------------------------------------------------------------- |
| `problemer`             | One row per active problem: type, input, entity_id, since, hours |
| `antall_problemer`      | Number of active problems                                        |
| `berorte_inputer`       | The failing roles, e.g. `["energi"]`                             |
| `sist_energi_okning`    | When the energy counter last increased                           |
| `spotpris_gyldig`       | Whether the spot price can be used right now                     |
| `leverandorpris_gyldig` | Whether the provider sensor delivers, `null` if it is not set up |
| `frossen_terskel_timer` | The threshold in effect                                          |

Each problem also raises a notice under Settings > Repairs, so you see it
without having set anything up. It clears itself once the input returns. A jump
in the energy counter that was discarded (meter swap, sensor glitch, or real
usage arriving all at once) gets its own notice with the kWh figure, which you
confirm yourself.

The electricity provider sensor is listed but never alarms: it only feeds the
comparison sensor "Total strømpris (strømavtale)".

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

### Capacity alert and recovery

Use the existing **Capacity warning** binary sensor: it follows the threshold
in Configure (default 2.0 kW), so the automation does not need its own threshold.
The example below replaces the same Home Assistant notification when the alert
clears. It works with Home Assistant **2025.1 and later**. Paste it into an
automation’s YAML editor. Replace the entity ID with your own; IDs depend on
the setup language, grid company and any names you have changed.

```yaml
alias: Capacity warning
triggers:
  - trigger: state
    entity_id: binary_sensor.nettleie_bkk_capacity_warning
    to: "on"
    id: warning
  - trigger: state
    entity_id: binary_sensor.nettleie_bkk_capacity_warning
    from: "on"
    to: "off"
    id: cleared
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: warning
        sequence:
          - action: persistent_notification.create
            data:
              notification_id: stromkalkulator_bkk_kapasitet
              title: "Capacity warning"
              message: "{{ state_attr('binary_sensor.nettleie_bkk_capacity_warning', 'margin_kw') }} kW to the next capacity tier."
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - action: persistent_notification.create
            data:
              notification_id: stromkalkulator_bkk_kapasitet
              title: "Capacity alert cleared"
              message: "The capacity warning is no longer active."
mode: queued
```

Recovery requires `on` → `off`: missing data (`unknown`/`unavailable`) is
not reported as recovery. Use a separate notification ID for each installation.
This is an alert about the calculated monthly tier margin, not a forecast of
how much load you can add for the rest of the hour. Load control belongs in
Effektvakt.

In Home Assistant **2026.7**, purpose-specific triggers and conditions became
the default in the automation editor. From **2026.10**, the editor lets you
pick the trigger directly in **Triggered by**, without typing an ID. The YAML
above uses explicit IDs, which also work on earlier versions. See the official
[July release notes](https://www.home-assistant.io/blog/2026/07/01/release-20267/)
and [October release notes](https://www.home-assistant.io/blog/2026/10/07/release-202610/).

### Margin gauge

```yaml
type: gauge
entity: sensor.nettleie_bkk_margin_to_next_tier
name: Margin to next tier
min: 0
max: 10
needle: true
severity:
  red: 0
  yellow: 1
  green: 2
```

Small margins are red; larger margins are green. Adjust the scale and color
thresholds to your setup; `severity` is display only and does not change the
alert threshold. The card works in **2025.1**; the refreshed appearance from
[2026.4](https://www.home-assistant.io/blog/2026/04/01/release-20264/#gauge-card-redesign)
is automatic. In the highest tier or with a fixed charge without measured
power tiers, the margin may be 0 without a more expensive tier existing;
check Capacity warning as well.

### Measurement problems on the dashboard

Show this card while **Measurement data problem** is on. Tap the entity to
inspect the `problemer` attribute; repairs are also listed in Settings.

```yaml
type: conditional
conditions:
  - entity: binary_sensor.nettleie_bkk_measurement_data_problem
    state: "on"
card:
  type: entities
  title: Check the input sensors
  entities:
    - entity: binary_sensor.nettleie_bkk_measurement_data_problem
    - entity: binary_sensor.nettleie_bkk_capacity_warning
```

This card works in **2025.1**. In **2026.10**, the card editor’s Visibility
tab supports the conditions from the automation editor and shows whether each
condition passes. For this example, a simple state condition is enough. See
[the visibility improvements](https://www.home-assistant.io/blog/2026/10/07/release-202610/#show-a-card-only-when-it-matters).

## Invoice verification

| Invoice line item    | Sensor                          | Where                           |
| -------------------- | ------------------------------- | ------------------------------- |
| Energy day (kWh)     | Forrige måned forbruk dagtariff | State                           |
| Energy night (kWh)   | Forrige måned forbruk natt/helg | State                           |
| Energy day (kr)      | Forrige måned nettleie          | Attribute: `energiledd_dag_kr`  |
| Energy night (kr)    | Forrige måned nettleie          | Attribute: `energiledd_natt_kr` |
| Capacity charge (kr) | Forrige måned nettleie          | Attribute: `kapasitetsledd_kr`  |
| Capacity tier (kW)   | Forrige måned toppforbruk       | State (avg. top-3)              |

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

| Field                            | Type   | Description                                   |
| -------------------------------- | ------ | --------------------------------------------- |
| `daily_max_power`                | dict   | `{"YYYY-MM-DD": {"kw": float, "hour": int}}`  |
| `weekly_max_power`               | dict   | Fjellnett only: weekly peaks, keyed on Monday |
| `monthly_consumption`            | dict   | `{"dag": float, "natt": float}` (kWh)         |
| `current_month`                  | string | `"YYYY-MM"`                                   |
| `daily_cost`                     | float  | Today's accumulated cost (kr)                 |
| `monthly_accumulated_cost`       | float  | Accumulated monthly cost (kr)                 |
| `previous_month_consumption`     | dict   | Consumption last month                        |
| `previous_month_top_3`           | dict   | Top-3 last month                              |
| `previous_month_fastledd_snapshot` | dict/null | Historical tariff and peak basis for late corrections |
| `previous_month_fastledd_grunnlag_bekreftet` | bool | Whether the historical fixed charge can be verified |
| `previous_month_kapasitetsledd`  | int    | Capacity charge last month (kr/month)         |
| `previous_month_kapasitetstrinn` | string | Tier range last month (e.g. `"5-10 kW"`)      |
| `monthly_export_kwh`             | float  | Export this month                             |
| `monthly_export_revenue`         | float  | Export revenue this month                     |
| `eksportbok`                     | dict   | Export price slots, energy and monthly balances |
| `ferdige_sum`                    | dict   | Consumption and price coverage outside the short interval window |
| `monthly_cost`                   | float  | Total consumption cost this month (kr)        |

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
