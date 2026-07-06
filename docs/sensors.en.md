# Sensors

6 devices, 52 sensors total (34 active by default).

| Device              | Active | Total |
| ------------------- | ------ | ----- |
| Grid tariff         | 11     | 19    |
| Electricity subsidy | 6      | 7     |
| Norgespris          | 3      | 3     |
| Monthly consumption | 8      | 12    |
| Previous month      | 6      | 6     |
| Export              | 0      | 5     |

Enable more: **Settings > Devices > Stromkalkulator > (device) > Entities**, toggle "Enabled". The coordinator computes everything regardless, sensors are display only.

Sensors marked _(optional)_ are disabled by default.

---

## Grid tariff (Nettleie)

Main device, named "Nettleie ({grid company})".

### Energy component

| Sensor     | Unit   | Description                                           |
| ---------- | ------ | ----------------------------------------------------- |
| Energiledd | kr/kWh | What you pay per kWh now (switches between day/night) |
| Tariff     | -      | "dag" (day) or "natt" (night), controls utility_meter |

Day: Mon-Fri 06-22 (not holidays). Night: 22-06, weekends, holidays.

### Capacity

| Sensor                                   | Unit  | Description                                                |
| ---------------------------------------- | ----- | ---------------------------------------------------------- |
| Kapasitetstrinn                          | kr/mo | Fixed monthly cost based on average of top-3 power days    |
| Snitt toppforbruk                        | kW    | Average of top-3, determines the tier                      |
| Toppforbruk #1, #2, #3                   | kW    | The three highest power days this month                    |
| Margin til neste trinn                   | kW    | How much more before next (more expensive) tier            |
| Kapasitetsvarsel                         | -     | "on" when margin is below threshold, for alerts/automation |
| _(optional)_ Kapasitetstrinn (nummer)    | -     | Tier you're on (1, 2, 3, ...)                              |
| _(optional)_ Kapasitetstrinn (intervall) | -     | kW range for your tier (e.g. "2-5 kW")                     |

**Toppforbruk #1-3** have attributes `dato` (YYYY-MM-DD) and `time` (0-23).

### Electricity price

| Sensor                                     | Unit   | Description                              |
| ------------------------------------------ | ------ | ---------------------------------------- |
| Total price (before subsidy)               | kr/kWh | Spot + grid tariff, before subsidy       |
| Electricity price per kWh                          | kr/kWh | Spot + energy component, no capacity fee |
| _(optional)_ Total price (provider) | kr/kWh | With provider's price instead of spot    |

### Diagnostics (taxes)

| Sensor                            | Unit   | Description                                |
| --------------------------------- | ------ | ------------------------------------------ |
| _(optional)_ Energiledd dag       | kr/kWh | Day rate incl. all taxes and VAT           |
| _(optional)_ Energiledd natt/helg | kr/kWh | Night/weekend rate incl. all taxes and VAT |
| _(optional)_ Offentlige avgifter  | kr/kWh | Consumption tax + Enova levy incl. VAT     |
| _(optional)_ Forbruksavgift       | kr/kWh | Electricity tax incl. VAT                  |
| _(optional)_ Enovaavgift          | kr/kWh | Enova levy incl. VAT                       |

---

## Electricity subsidy (Strømstøtte)

| Sensor                                        | Unit   | Description                                                                                                                                       |
| --------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Electricity subsidy                                   | kr/kWh | Subsidy per kWh when spot > 96.25 øre (90% of excess)                                                                                             |
| Spotpris etter stotte                         | kr/kWh | Spot price minus subsidy                                                                                                                          |
| Total price after subsidy                  | kr/kWh | Real total: spot + grid - subsidy                                                                                                                 |
| Totalpris inkl. avgifter                      | kr/kWh | Price sensor for Energy Dashboard. Capacity fee spread per kWh (inaccurate). For correct totals: use [Accumulated electricity cost](#energy-dashboard) |
| Electricity subsidy active now                          | -      | "Yes"/"No" if spot is over threshold                                                                                                              |
| Electricity subsidy remaining                  | kWh    | Remaining kWh of monthly cap (residence=5000, holiday home=0)                                                                                     |
| _(optional)_ Electricity price per kWh (after subsidy) | kr/kWh | Like "Electricity price per kWh" but with subsidy                                                                                                         |

---

## Norgespris

| Sensor                       | Unit   | Description                                                     |
| ---------------------------- | ------ | --------------------------------------------------------------- |
| Total price (Norgespris) | kr/kWh | What you'd pay with Norgespris: fixed 50 øre + grid tariff      |
| Prisforskjell (norgespris)   | kr/kWh | Positive = you pay more than Norgespris (Norgespris is cheaper) |
| Norgespris aktiv na          | -      | "Yes"/"No" if Norgespris is selected                            |

kWh cap: residence=5000, holiday home=1000. Above the cap, you pay spot price.

---

## Monthly consumption

Resets automatically at month change.

### Consumption

| Sensor                      | Unit | Description                          |
| --------------------------- | ---- | ------------------------------------ |
| Monthly consumption day tariff | kWh  | Day-tariff consumption this month    |
| Monthly consumption night/weekend | kWh  | Night/weekend consumption this month |
| Monthly consumption total    | kWh  | Sum of day and night                 |

Attributes on "Monthly consumption total": `dag_kwh`, `natt_kwh`, `dag_pct`, `natt_pct`.

### Costs

| Sensor                               | Unit | Description                                         |
| ------------------------------------ | ---- | --------------------------------------------------- |
| Monthly grid tariff total             | kr   | Bottom line: grid tariff + taxes - subsidy          |
| Dagens kostnad                       | kr   | Accumulated cost since midnight                     |
| Estimated monthly cost              | kr   | Forecast for the whole month, based on usage so far |
| Norgespris savings      | kr   | Accumulated savings/loss vs alternative             |
| Norgespris-kompensasjon              | kr   | Accumulated (norgespris - spot) x kWh this month    |
| _(optional)_ Monthly grid tariff      | kr   | Grid tariff so far: day + night + capacity          |
| _(optional)_ Monthly fees      | kr   | Consumption tax + Enova incl. VAT                   |
| _(optional)_ Monthly electricity subsidy   | kr   | Estimated subsidy this month                        |
| _(optional)_ Accumulated electricity cost | kr   | For Energy Dashboard with correct monthly totals    |

Attributes on "Accumulated electricity cost": `strompris_kr`, `energiledd_kr`, `kapasitetsledd_kr`, `total_kwh`.

Attributes on "Monthly grid tariff total": `nettleie_kr`, `avgifter_kr`, `stromstotte_kr`, `forbruk_dag_kwh`, `forbruk_natt_kwh`, `forbruk_total_kwh`, `vektet_snittpris_kr_per_kwh`.

---

## Previous month (Forrige måned)

Stored at month change. Used for invoice verification.

| Sensor                                 | Unit | Description                                |
| -------------------------------------- | ---- | ------------------------------------------ |
| Last month consumption day tariff       | kWh  | Day consumption last month                 |
| Last month consumption night/weekend       | kWh  | Night/weekend consumption last month       |
| Last month consumption total          | kWh  | Total consumption last month               |
| Last month grid tariff                | kr   | Compare with invoice                       |
| Last month peak demand             | kW   | Average of top-3, determined capacity tier |
| Last month Norgespris compensation | kr   | Norgespris compensation for previous month |

All have `maaned` attribute (e.g. "januar 2026").

**Grid tariff sensor** also has: `energiledd_dag_kr`, `energiledd_natt_kr`, `kapasitetsledd_kr`, `snitt_topp_3_kw`, `norgespris_differanse_kr`.

**Peak power sensor** has: `topp_1_dato`, `topp_1_kw`, `topp_2_dato`, `topp_2_kw`, `topp_3_dato`, `topp_3_kw`.

---

## Export (Eksport)

For prosumers. Requires configured export power sensor. All disabled by default.

| Sensor                                      | Unit | Description                           |
| ------------------------------------------- | ---- | ------------------------------------- |
| _(optional)_ Monthly export          | kWh  | Exported energy this month            |
| _(optional)_ Monthly export revenue      | kr   | Revenue (spot price x kWh)            |
| _(optional)_ Monthly net cost         | kr   | Consumption cost minus export revenue |
| _(optional)_ Last month export     | kWh  | Exported energy last month            |
| _(optional)_ Last month export revenue | kr   | Export revenue last month             |

---

## Energy Dashboard

Two options for the cost portion.

### Option 1: Price sensor

Use `Totalpris inkl. avgifter`. Simplest, but capacity fee is wrong with deviating consumption.

1. **Settings > Dashboards > Energy > Add consumption**
2. Select your kWh sensor as "Consumed energy"
3. Enable "Use an entity with current price"
4. Select `Totalpris inkl. avgifter`

### Option 2: Accumulated cost (recommended)

Use `Accumulated electricity cost`. Capacity fee is distributed linearly over time, monthly total matches the invoice.

1. Enable: **Settings > Devices > Monthly consumption > Entities > Accumulated electricity cost**
2. **Settings > Dashboards > Energy > Add consumption**
3. Select your kWh sensor as "Consumed energy"
4. Enable "Use an entity tracking total costs"
5. Select `Accumulated electricity cost`

The kWh meter comes from your AMS reader, not Stromkalkulator.

---

## Comparing Norgespris

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.prisforskjell_norgespris
        above: 0.10
    action:
      - service: notify.mobile_app
        data:
          message: "Norgespris is now 10+ øre cheaper than spot"
```

---

## Invoice verification

| Invoice line item    | Sensor                           | Where                           |
| -------------------- | -------------------------------- | ------------------------------- |
| Energy day (kWh)     | Last month consumption day tariff | State                           |
| Energy night (kWh)   | Last month consumption night/weekend | State                           |
| Energy day (kr)      | Last month grid tariff          | Attribute: `energiledd_dag_kr`  |
| Energy night (kr)    | Last month grid tariff          | Attribute: `energiledd_natt_kr` |
| Capacity charge (kr) | Last month grid tariff          | Attribute: `kapasitetsledd_kr`  |
| Capacity tier (kW)   | Last month peak demand       | State (avg top-3)               |

---

## Technical details

- Updates every minute
- Consumption with energy sensor (recommended): delta from meter register, exact against invoice
- Consumption without energy sensor: Riemann sum from power sensor, 1-5 % deviation per month
- Storage: `/config/.storage/stromkalkulator_<entry_id>` (unique per instance)
- See [input-sensorer.md](input-sensorer.md) for sensor setup (Norwegian)

See [beregninger.md](beregninger.md) for formulas (Norwegian).
