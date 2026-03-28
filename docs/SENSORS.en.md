# Sensors

Complete overview of all sensors and devices in Strømkalkulator.

## Overview

The integration creates **5 devices** with a total of **36 sensors**:

| Device             | Description                      | Number of sensors |
|--------------------|----------------------------------|-------------------|
| Grid tariff        | Energy component, capacity, taxes | 16               |
| Electricity subsidy | Subsidy and total price          | 5                |
| Norgespris         | Norgespris comparison            | 3                |
| Monthly consumption | Consumption and costs this month | 7                |
| Previous month     | Consumption and costs last month | 5                |

---

## Device: Grid tariff (Nettleie)

Main device with grid tariff prices, capacity tiers, and public taxes. Named "Nettleie ({your grid company})".

### Energy component

| Sensor             | Unit   | Description                          |
|--------------------|--------|--------------------------------------|
| Energiledd         | kr/kWh | Active energy component (day or night) |
| Tariff             | -      | "dag" or "natt"                      |

**Tariff rules:**
- **Day**: Mon-Fri 06:00-22:00 (not public holidays)
- **Night**: 22:00-06:00, weekends, and public holidays

### Capacity

| Sensor                       | Unit   | Description                               |
|------------------------------|--------|-------------------------------------------|
| Kapasitetstrinn              | kr/mo  | Monthly capacity cost based on top 3      |
| Snitt toppforbruk            | kW     | Average of 3 highest power days           |
| Kapasitetstrinn (nummer)     | -      | Active tier (1, 2, 3, ...)               |
| Kapasitetstrinn (intervall)  | -      | Tier range (e.g. "2-5 kW")              |
| Toppforbruk #1               | kW     | Highest power day this month              |
| Toppforbruk #2               | kW     | Second highest power day                  |
| Toppforbruk #3               | kW     | Third highest power day                   |

### Electricity price

| Sensor                        | Unit   | Description                                           |
|-------------------------------|--------|-------------------------------------------------------|
| Total strømpris (før støtte)  | kr/kWh | Spot price + grid tariff (before subsidy)             |
| Total strømpris (strømavtale) | kr/kWh | Provider price + grid tariff (optional, requires sensor) |

### Diagnostics (taxes)

| Sensor               | Unit   | Description                                   |
|-----------------------|--------|-----------------------------------------------|
| Energiledd dag        | kr/kWh | Day rate energy component (incl. taxes)       |
| Energiledd natt/helg  | kr/kWh | Night rate energy component (incl. taxes)     |
| Offentlige avgifter   | kr/kWh | Sum of consumption tax + Enova incl. VAT      |
| Forbruksavgift        | kr/kWh | Consumption tax (electricity tax) incl. VAT   |
| Enovaavgift           | kr/kWh | Enova levy incl. VAT                          |

---

## Device: Electricity subsidy (Strømstøtte)

Sensors for subsidy calculation and total price incl. all taxes.

| Sensor                       | Unit   | Description                                     |
|------------------------------|--------|-------------------------------------------------|
| Strømstøtte                  | kr/kWh | Subsidy per kWh (90% above 96.25 øre)           |
| Spotpris etter støtte        | kr/kWh | Spot price minus subsidy                        |
| Total strømpris etter støtte | kr/kWh | Spot price + grid tariff - subsidy              |
| Totalpris inkl. avgifter     | kr/kWh | **Recommended for Energy Dashboard** - incl. all |
| Strømstøtte aktiv nå         | -      | "Yes" / "No" - whether spot price exceeds threshold |

---

## Device: Norgespris

Comparison between your spot price contract and Norgespris.

| Sensor                       | Unit   | Description                                      |
|------------------------------|--------|--------------------------------------------------|
| Total strømpris (norgespris) | kr/kWh | Norgespris + grid tariff                         |
| Prisforskjell (norgespris)   | kr/kWh | Difference between your price and Norgespris     |
| Norgespris aktiv nå          | -      | "Yes" / "No" - whether you have opted for Norgespris |

**Price difference interpretation:**
- **Positive value** = You pay more than Norgespris (Norgespris is cheaper)
- **Negative value** = You pay less than Norgespris (spot price is cheaper)

---

## Device: Monthly consumption (Månedlig forbruk)

Tracks consumption and costs for the current month. Resets automatically at month change.

### Consumption

| Sensor                     | Unit | Description                                        |
|----------------------------|------|----------------------------------------------------|
| Månedlig forbruk dagtariff | kWh  | Consumption on day tariff (weekdays 06:00-22:00)   |
| Månedlig forbruk natt/helg | kWh  | Consumption on night/weekend tariff (incl. holidays) |
| Månedlig forbruk totalt    | kWh  | Total consumption this month                       |

### Costs

| Sensor                  | Unit | Description                              |
|-------------------------|------|------------------------------------------|
| Månedlig nettleie       | kr   | Grid tariff (energy + capacity component) |
| Månedlig avgifter       | kr   | Consumption tax + Enova levy             |
| Månedlig strømstøtte    | kr   | Estimated electricity subsidy            |
| Månedlig nettleie total | kr   | Total grid tariff after subsidy          |

### Attributes

Cost sensors have extra attributes:
- `energiledd_dag_kr` - Cost for day consumption
- `energiledd_natt_kr` - Cost for night consumption
- `kapasitetsledd_kr` - Capacity component

---

## Device: Previous month (Forrige måned)

Stores previous month's data for invoice verification. Updated automatically at month change.

### Consumption

| Sensor                          | Unit | Description                                        |
|---------------------------------|------|----------------------------------------------------|
| Forrige måned forbruk dagtariff | kWh  | Consumption on day tariff (weekdays 06:00-22:00)   |
| Forrige måned forbruk natt/helg | kWh  | Consumption on night/weekend tariff (incl. holidays) |
| Forrige måned forbruk totalt    | kWh  | Total consumption                                  |

### Costs and power

| Sensor                    | Unit | Description                      |
|---------------------------|------|----------------------------------|
| Forrige måned nettleie    | kr   | Grid tariff incl. capacity component |
| Forrige måned toppforbruk | kW   | Average of top 3 power days      |

### Attributes

All sensors have:
- `måned` - Which month the data is for (e.g. "januar 2026")

**Grid tariff sensor also has:**
- `energiledd_dag_kr` - Cost for day consumption
- `energiledd_natt_kr` - Cost for night consumption
- `kapasitetsledd_kr` - Capacity component
- `snitt_topp_3_kw` - Average of top 3 power days

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
| **Consumed energy**           | Your kWh consumption sensor      | Tibber, P1, Elhub   |
| **Use an entity with current price** | **Totalpris inkl. avgifter** | Strømkalkulator     |

**Step by step:**
1. **Settings > Dashboards > Energy**
2. Under **Electricity grid**, click **Add consumption**
3. **Consumed energy** — select your kWh sensor (e.g. from Tibber Pulse, P1 meter, or Elhub)
4. Enable **Use an entity with current price**
5. Select **Totalpris inkl. avgifter** (`sensor.totalpris_inkl_avgifter_*`)

> **Note:** Strømkalkulator provides the price — the consumption meter (kWh) comes from your power meter integration (Tibber, P1, Elhub, etc.).

### Comparing Norgespris

Use **Prisforskjell (norgespris)** to see if Norgespris is worth it:

```yaml
# Example: Alert when Norgespris is cheaper
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.prisforskjell_norgespris
        above: 0.10  # 10 øre cheaper
    action:
      - service: notify.mobile_app
        data:
          message: "Norgespris is now 10+ øre cheaper than spot price"
```

### Invoice verification

Use the "Previous month" sensors when the invoice arrives:

| Invoice line item     | Sensor                        | Where                           |
|-----------------------|-------------------------------|---------------------------------|
| Energy day (kWh)      | Forrige måned forbruk dagtariff | State                         |
| Energy night (kWh)    | Forrige måned forbruk natt/helg | State                         |
| Energy day (kr)       | Forrige måned nettleie        | Attribute: `energiledd_dag_kr`  |
| Energy night (kr)     | Forrige måned nettleie        | Attribute: `energiledd_natt_kr` |
| Capacity charge (kr)  | Forrige måned nettleie        | Attribute: `kapasitetsledd_kr`  |
| Capacity tier (kW)    | Forrige måned toppforbruk     | State (avg top 3)               |

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

- **1-5% deviation from invoice is normal** (rounding, measurement error)
- Electricity subsidy may deviate more (invoices use hourly prices)
- Consumption is calculated from power, not from the electricity meter

See [beregninger.md](beregninger.md) for detailed formulas.
