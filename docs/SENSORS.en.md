# Sensors

Complete overview of all sensors and devices in Stromkalkulator.

## Overview

The integration creates **5 devices** with a total of **44 sensors**. Of these, **32 are active** by default — the rest are disabled and can be enabled as needed.

| Device             | Description                      | Active | Total |
|--------------------|----------------------------------|--------|-------|
| Grid tariff        | Energy component, capacity, taxes | 11    | 19    |
| Electricity subsidy | Subsidy and total price          | 6     | 7     |
| Norgespris         | Norgespris comparison            | 3     | 3     |
| Monthly consumption | Consumption and costs this month | 7     | 10    |
| Previous month     | Consumption and costs last month | 5     | 5     |

### Enabling more sensors

Go to **Settings > Devices > Stromkalkulator > (select device) > Entities**. Click on a disabled sensor and toggle "Enabled". The sensor will start updating at the next minute.

Sensors marked *(optional)* are disabled by default. Disabling a sensor does not affect calculations — the coordinator computes all values regardless. Sensors are display only.

---

## Device: Grid tariff (Nettleie)

Main device with grid tariff prices, capacity tiers, and public taxes. Named "Nettleie ({your grid company})".

### Energy component

| Sensor             | Unit   | Description                                                                                    |
|--------------------|--------|------------------------------------------------------------------------------------------------|
| Energiledd         | kr/kWh | What you pay per kWh to the grid company right now (switches between day and night rate)        |
| Tariff             | -      | Which tariff period is active right now: "dag" (day) or "natt" (night) — controls utility_meter |

**Tariff rules:**
- **Day**: Mon-Fri 06:00-22:00 (not public holidays)
- **Night**: 22:00-06:00, weekends, and public holidays

### Capacity

| Sensor                       | Unit   | Description                                                                                  |
|------------------------------|--------|----------------------------------------------------------------------------------------------|
| Kapasitetstrinn              | kr/mo  | Fixed monthly cost based on your highest power usage (average of your 3 peak days)            |
| Snitt toppforbruk            | kW     | Average of your 3 highest power days this month — this determines your capacity tier          |
| *(optional)* Kapasitetstrinn (nummer)     | -      | Which tier you are on now (1, 2, 3, ...) — lower is cheaper                                 |
| *(optional)* Kapasitetstrinn (intervall)  | -      | The kW range for your active tier (e.g. "2-5 kW")                                           |
| Toppforbruk #1               | kW     | Your highest power day this month — the day you used the most electricity                    |
| Toppforbruk #2               | kW     | Second highest power day this month                                                          |
| Toppforbruk #3               | kW     | Third highest power day this month                                                           |
| Margin til neste trinn       | kW     | How much more power you can use before you move up to the next (more expensive) capacity tier |
| Kapasitetsvarsel             | -      | Turns "on" when you are close to the next capacity tier — use for alerts/automation           |

### Electricity price

| Sensor                        | Unit   | Description                                                                                       |
|-------------------------------|--------|---------------------------------------------------------------------------------------------------|
| Total strompris (for stotte)  | kr/kWh | Everything you pay per kWh right now: spot price + grid tariff (before any subsidy is deducted)    |
| *(optional)* Total strompris (stromavtale) | kr/kWh | Same as above, but with your provider's price instead of spot price (optional — needs price sensor) |
| Strompris per kWh             | kr/kWh | Spot price + energy component without capacity fee — the variable cost per kWh you use             |

### Diagnostics (taxes)

| Sensor               | Unit   | Description                                                                                |
|-----------------------|--------|--------------------------------------------------------------------------------------------|
| *(optional)* Energiledd dag        | kr/kWh | Grid tariff rate for daytime hours (weekdays 06-22), including all taxes and VAT            |
| *(optional)* Energiledd natt/helg  | kr/kWh | Grid tariff rate for night/weekend/holidays, including all taxes and VAT                    |
| *(optional)* Offentlige avgifter   | kr/kWh | Sum of consumption tax and Enova levy incl. VAT — the government's surcharge per kWh        |
| *(optional)* Forbruksavgift        | kr/kWh | Electricity consumption tax (government tax on electricity usage) incl. VAT                  |
| *(optional)* Enovaavgift           | kr/kWh | Enova levy (funds energy efficiency programs) incl. VAT                                      |

---

## Device: Electricity subsidy (Stromstotte)

Sensors for subsidy calculation and total price incl. all taxes.

| Sensor                            | Unit   | Description                                                                                    |
|-----------------------------------|--------|------------------------------------------------------------------------------------------------|
| Stromstotte                       | kr/kWh | Government subsidy per kWh when spot price exceeds 96.25 ore (you get 90% of the excess)       |
| Spotpris etter stotte             | kr/kWh | What the spot price effectively costs you after the subsidy is deducted                        |
| Total strompris etter stotte      | kr/kWh | Your actual total price right now: spot price + grid tariff - subsidy                          |
| Totalpris inkl. avgifter          | kr/kWh | Can be used in Energy Dashboard — your total electricity price incl. grid, taxes & subsidy. Capacity charge is spread per kWh and [becomes inaccurate with varying consumption](../README.en.md#capacity-charge-in-energy-dashboard). |
| Stromstotte aktiv na              | -      | "Yes" / "No" — whether the current spot price is high enough for you to receive subsidy         |
| Stromstotte gjenstaaende kWh      | kWh    | How many kWh remain before you hit the subsidy cap (5000 kWh/month)                             |
| *(optional)* Strompris per kWh (etter stotte)  | kr/kWh | Spot price + energy component - subsidy, without capacity fee — variable kWh cost after subsidy  |

---

## Device: Norgespris

Comparison between your spot price contract and Norgespris (fixed 50 ore/kWh).

| Sensor                              | Unit   | Description                                                                                     |
|-------------------------------------|--------|-------------------------------------------------------------------------------------------------|
| Total strompris (norgespris)        | kr/kWh | What you would pay per kWh with Norgespris: fixed 50 ore + grid tariff                          |
| Prisforskjell (norgespris)          | kr/kWh | How much you save/lose per kWh compared to Norgespris (positive = you pay more)                  |
| Norgespris aktiv na                 | -      | "Yes" / "No" — whether you have opted for Norgespris as your electricity contract               |
| Maanedlig Norgespris-differanse     | kr     | Accumulated savings/loss in NOK this month compared to the alternative contract                   |

**Price difference interpretation:**
- **Positive value** = You pay more than Norgespris (Norgespris is cheaper)
- **Negative value** = You pay less than Norgespris (spot price is cheaper)

---

## Device: Monthly consumption (Maanedlig forbruk)

Tracks consumption and costs for the current month. Resets automatically at month change.

### Consumption

| Sensor                     | Unit | Description                                                                              |
|----------------------------|------|------------------------------------------------------------------------------------------|
| Maanedlig forbruk dagtariff | kWh  | Electricity used on day tariff this month (weekdays 06:00-22:00, not public holidays)    |
| Maanedlig forbruk natt/helg | kWh  | Electricity used on night/weekend tariff this month (nights, weekends, public holidays)   |
| Maanedlig forbruk totalt    | kWh  | All electricity consumption this month — sum of day and night                             |

### Costs

| Sensor                    | Unit | Description                                                                                          |
|---------------------------|------|------------------------------------------------------------------------------------------------------|
| *(optional)* Maanedlig nettleie        | kr   | Grid tariff so far this month: energy component (day + night) + capacity fee                          |
| *(optional)* Maanedlig avgifter        | kr   | Public taxes so far: consumption tax + Enova levy incl. VAT                                           |
| *(optional)* Maanedlig stromstotte     | kr   | Estimated subsidy earned this month (actual subsidy is calculated hourly)                              |
| Maanedlig nettleie total  | kr   | The bottom line: grid tariff + taxes - subsidy — what you actually pay for the grid portion            |
| Dagens kostnad            | kr   | What electricity has cost you today — accumulated cost since midnight                                  |
| Estimert maanedskostnad   | kr   | Forecast for what the whole month will cost, based on usage so far (gets more accurate each day)       |

### Attributes

**Maanedlig forbruk totalt** has:
- `dag_kwh` - Consumption on day tariff
- `natt_kwh` - Consumption on night/weekend tariff
- `dag_pct` - Percentage of consumption on day tariff
- `natt_pct` - Percentage of consumption on night/weekend tariff

**Maanedlig nettleie** has:
- `energiledd_dag_kr` - Cost for day consumption
- `energiledd_natt_kr` - Cost for night consumption
- `kapasitetsledd_kr` - Capacity component

**Maanedlig nettleie total** has:
- `nettleie_kr` - Grid tariff portion of total cost
- `avgifter_kr` - Tax portion of total cost
- `stromstotte_kr` - Subsidy deduction
- `forbruk_dag_kwh` / `forbruk_natt_kwh` / `forbruk_total_kwh` - Consumption
- `vektet_snittpris_kr_per_kwh` - Weighted average price per kWh for the entire month

---

## Device: Previous month (Forrige maaned)

Stores previous month's data for invoice verification. Updated automatically at month change.

### Consumption

| Sensor                          | Unit | Description                                                                    |
|---------------------------------|------|--------------------------------------------------------------------------------|
| Forrige maaned forbruk dagtariff | kWh  | Electricity used on day tariff last month (weekdays 06:00-22:00)              |
| Forrige maaned forbruk natt/helg | kWh  | Electricity used on night/weekend tariff last month (nights, weekends, holidays) |
| Forrige maaned forbruk totalt    | kWh  | Total electricity consumption last month                                       |

### Costs and power

| Sensor                    | Unit | Description                                                                                  |
|---------------------------|------|----------------------------------------------------------------------------------------------|
| Forrige maaned nettleie   | kr   | What you paid in grid tariff last month — use to compare with your invoice                    |
| Forrige maaned toppforbruk | kW   | Average of the 3 highest power days last month — this determined your capacity tier           |

### Attributes

All sensors have:
- `maaned` - Which month the data is for (e.g. "januar 2026")

**Grid tariff sensor also has:**
- `energiledd_dag_kr` - Cost for day consumption
- `energiledd_natt_kr` - Cost for night consumption
- `kapasitetsledd_kr` - Capacity component
- `snitt_topp_3_kw` - Average of top 3 power days
- `norgespris_differanse_kr` - Norgespris difference for the month

**Peak power sensor also has:**
- `topp_1_dato`, `topp_1_kw` - Highest day
- `topp_2_dato`, `topp_2_kw` - Second highest day
- `topp_3_dato`, `topp_3_kw` - Third highest day

---

## Usage scenarios

### Energy Dashboard

Energy Dashboard needs two things: a **consumption meter** (kWh) and a **price sensor** (NOK/kWh).

| Energy Dashboard field        | What to select                   | Source              |
|-------------------------------|----------------------------------|---------------------|
| **Consumed energy**           | Your kWh consumption sensor      | AMS meter via HAN port |
| **Use an entity with current price** | **Totalpris inkl. avgifter** | Stromkalkulator     |

**Step by step:**
1. **Settings > Dashboards > Energy**
2. Under **Electricity grid**, click **Add consumption**
3. **Consumed energy** — select your kWh sensor (e.g. from Tibber Pulse or AMS reader)
4. Enable **Use an entity with current price**
5. Select **Totalpris inkl. avgifter** (`sensor.totalpris_inkl_avgifter_*`)

> **Note:** Stromkalkulator provides the price — the consumption meter (kWh) comes from your AMS reader (e.g. Tibber Pulse).

> **Important:** The capacity charge (fixed kr/month) is spread as øre per kWh in this sensor. The Energy Dashboard multiplies price x kWh, so the capacity portion comes out wrong unless consumption matches the distribution key. For accurate monthly costs, use "Månedlig nettleie total". See [details](../README.en.md#capacity-charge-in-energy-dashboard).

### Comparing Norgespris

Use **Prisforskjell (norgespris)** to see if Norgespris is worth it:

```yaml
# Example: Alert when Norgespris is cheaper
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.prisforskjell_norgespris
        above: 0.10  # 10 ore cheaper
    action:
      - service: notify.mobile_app
        data:
          message: "Norgespris is now 10+ ore cheaper than spot price"
```

### Invoice verification

Use the "Previous month" sensors when the invoice arrives:

| Invoice line item     | Sensor                        | Where                           |
|-----------------------|-------------------------------|---------------------------------|
| Energy day (kWh)      | Forrige maaned forbruk dagtariff | State                        |
| Energy night (kWh)    | Forrige maaned forbruk natt/helg | State                        |
| Energy day (kr)       | Forrige maaned nettleie       | Attribute: `energiledd_dag_kr`  |
| Energy night (kr)     | Forrige maaned nettleie       | Attribute: `energiledd_natt_kr` |
| Capacity charge (kr)  | Forrige maaned nettleie       | Attribute: `kapasitetsledd_kr`  |
| Capacity tier (kW)    | Forrige maaned toppforbruk    | State (avg top 3)               |

---

## Technical details

### Update frequency

- All sensors update **every minute**
- Monthly consumption is calculated using Riemann sum from the power sensor
- Peak power is stored per day and resets at month change

### Persistence

- All data is saved to disk and survives restarts
- Storage format: `/config/.storage/stromkalkulator_<entry_id>` (unique per instance)

### Accuracy

- **1-5% deviation from invoice is normal** due to Riemann sum vs. the electricity meter's kWh counter
- Electricity subsidy may deviate more (invoices use hourly prices)
- Consumption is calculated from power, not from the electricity meter
- **Capacity charge in Energy Dashboard can deviate much more** — the capacity charge is a fixed monthly amount, but is spread as kr/kWh in the total price sensor. See [explanation](../README.en.md#capacity-charge-in-energy-dashboard)

See [beregninger.md](beregninger.md) for detailed formulas.
