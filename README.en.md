<p align="center">
  <img src="images/logo.png" alt="Strømkalkulator" width="400">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/releases"><img src="https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg" alt="GitHub release"></a>
  <img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.stromkalkulator.total" alt="Installs">
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml/badge.svg" alt="Hassfest"></a>
  <a href="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator"><img src="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator/graph/badge.svg" alt="codecov"></a>
</p>

**[Norsk versjon / Norwegian version](README.md)**

Home Assistant integration that calculates the actual electricity price in Norway, including grid tariffs, taxes, and government subsidies.

## What you get

Sensors showing what electricity actually costs, not just the spot price:

- Grid tariffs: energy component (day/night) and capacity component
- Electricity subsidy: automatic (90 % above 96.25 øre/kWh)
- Total price: everything included, usable in Energy Dashboard
- Monthly consumption and cost
- Invoice verification against the previous month
- Solar export (disabled by default)

## Installation

### Via HACS (recommended)

1. **HACS** > **Integrations** > Menu (three dots) > **Custom repositories**
2. Add `https://github.com/fredrik-lindseth/Stromkalkulator` as "Integration"
3. Download "Strømkalkulator"
4. Restart Home Assistant

### Manual

Copy `custom_components/stromkalkulator` to `/config/custom_components/`

## Setup

**Settings > Devices & Services > Add Integration > Strømkalkulator**

![Setup](images/setup.png)

### Step 1: Select grid company

Select your grid company from the dropdown. Tax zone (VAT and consumption tax) is set automatically based on your grid company.

### Property type

| Property type | Electricity subsidy | Norgespris cap | Source |
|---------------|---------------------|----------------|--------|
| Residence (default) | 5000 kWh/month | 5000 kWh/month | [Regulation § 5](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Holiday home | None | 1000 kWh/month | [Regulation § 3](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Holiday home (permanent residence) | 5000 kWh/month | 5000 kWh/month | [Regulation § 11](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |

Above the Norgespris kWh cap, you pay spot price for the rest of the month. Holiday homes are not entitled to electricity subsidy unless you live there permanently (§ 11).

### Step 2: Select sensors

- Power meter (W): current consumption in watts, typically from an AMS reader via the HAN port (e.g. Tibber Pulse).
- Spot price sensor (NOK/kWh): usually "Current price" from the [Nord Pool integration](https://www.home-assistant.io/integrations/nordpool/). It delivers prices excluding VAT, which is what the integration expects. If your sensor already includes VAT, tick "Spot price sensor delivers prices incl. VAT".
- Electricity provider sensor (optional): total price from your provider (e.g. Tibber), to compare with what you actually pay.

All Norwegian grid companies are supported.

### Tax zones

The tax zone determines VAT and consumption tax, and is set automatically from your grid company. You can override in settings if needed.

| Tax zone          | Price areas    | Consumption tax | VAT  |
|-------------------|----------------|-----------------|------|
| Southern Norway   | NO1, NO2, NO5 | 7.13 øre/kWh   | 25%  |
| Northern Norway   | NO3, NO4      | 7.13 øre/kWh   | 0%   |
| Tiltakssonen      | Finnmark/Nord-Troms | 0 øre      | 0%   |

## Devices and Sensors

The integration creates five devices with sensors:

### Grid tariff (Nettleie)

Prices and calculations for grid tariffs, electricity subsidy, and total price.

![Grid tariff](images/nettleie.png)

### Electricity subsidy (Strømstøtte)

How much you receive in electricity subsidy (90 % above 96.25 øre/kWh).

![Electricity subsidy](images/strømstøtte.png)

### Norway price (Norgespris)

Compares your spot price contract with Norgespris.

![Norgespris](images/norgespris.png)

### Monthly consumption (Månedlig forbruk)

Consumption and cost for the current month, split by day and night/weekend tariff.

![Monthly consumption](images/månedlig_forbruk.png)

### Previous month (Forrige måned)

Previous month's data for invoice verification.

![Previous month](images/forrige_måned.png)

## Using with Energy Dashboard

Energy Dashboard needs a **consumption meter** (kWh) and a **cost source**. Stromkalkulator provides two options for cost. The consumption meter comes from your power meter integration.

### Option 1: Price sensor (NOK/kWh)

Use **Totalpris inkl. avgifter** as a price sensor. Simplest to set up. The capacity charge is spread as kr/kWh, so the monthly total for that portion will be inaccurate.

| What                 | Sensor                         | Source                   |
|----------------------|--------------------------------|--------------------------|
| Consumption (kWh)    | Your consumption meter         | AMS meter via HAN port (e.g. Tibber Pulse)  |
| Price (NOK/kWh)      | **Total price incl. taxes**    | Stromkalkulator          |

1. **Settings > Dashboards > Energy**
2. Under **Electricity grid**, click **Add consumption**
3. **Consumed energy**: select your kWh consumption sensor
4. Enable **Use an entity with current price**
5. Select **Totalpris inkl. avgifter** (`sensor.totalpris_inkl_avgifter_*`)

### Option 2: Accumulated cost (recommended)

Use **Akkumulert stromkostnad** for correct monthly totals. The capacity charge is distributed linearly over time instead of per kWh, so the monthly total matches the invoice regardless of consumption. The sensor is disabled by default.

| What                 | Sensor                            | Source                   |
|----------------------|-----------------------------------|--------------------------|
| Consumption (kWh)    | Your consumption meter            | AMS meter via HAN port (e.g. Tibber Pulse)  |
| Cost (NOK)           | **Akkumulert stromkostnad**       | Stromkalkulator          |

1. Enable the sensor: **Settings > Devices > Monthly consumption > Entities > Akkumulert stromkostnad**
2. **Settings > Dashboards > Energy**
3. Under **Electricity grid**, click **Add consumption**
4. **Consumed energy**: select your kWh consumption sensor
5. Enable **Use an entity tracking total costs**
6. Select **Akkumulert stromkostnad** (`sensor.akkumulert_stromkostnad_*`)

> **Don't have a kWh sensor?** You need something that reads your AMS meter via the HAN port, e.g. a [Tibber Pulse](https://www.home-assistant.io/integrations/tibber/) or another AMS reader.

**Tip:** Want to see price components (spot price, grid tariff, taxes) separately? Use a custom dashboard card like ApexCharts with the sensors from this integration.

## Electricity plans

### Spot price

Electricity subsidy (90 % above 96.25 øre) is deducted automatically. The "Electricity subsidy" sensor shows the amount.

### Norgespris

If you have [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) with your grid company:

1. Tick "I have Norgespris" during setup
2. Fixed price is 50 øre in Southern Norway or 40 øre in Northern Norway
3. No subsidy (Norgespris replaces spot price and subsidy)

### Comparing plans

The "Price difference Norgespris" sensor shows whether Norgespris or spot price is cheaper right now. Positive value means you save with Norgespris.

## Verifying against invoice

When the grid tariff invoice arrives:

1. Go to Settings > Devices & Services > Strømkalkulator
2. Click on the "Previous month" device
3. Compare the values with your invoice

Click on a sensor for details like top-3 power days and costs split by day/night.

![Grid tariff diagnostics](images/nettleie_diagnostic.png)

## Supported grid companies

All Norwegian grid companies are supported. Prices are updated annually. Found an error, [create a PR](docs/CONTRIBUTING.md) or open an issue.

## Limitations

Designed for residential homes with individual electricity subscriptions. Not supported:

- Commercial use (different subsidy rates)
- Housing cooperatives with shared metering

## Frequently asked questions

**Why does the sensor show "natt" (night) in the middle of the day?**

The "natt" tariff is actually "natt/helg" (night/weekend):
- Nights (22:00-06:00)
- Weekends (Sat-Sun, all day)
- Public holidays (all day)

So on a Saturday at 14:00, "natt" tariff is correct.

**Why is "Totalpris inkl. avgifter" higher than the spot price?**

Spot price is just the electricity. Total price also includes grid tariff (energy + capacity), consumption tax, Enova levy, and VAT. Grid tariff and taxes typically make up 30-50% of the total.

**Electricity subsidy shows 0. Is that wrong?**

No. Subsidy applies only when spot price exceeds 96.25 øre/kWh (2026). Below the threshold, subsidy is 0.

**The numbers don't quite match my invoice?**

Some deviation is normal. The integration uses Riemann sum from the power sensor; the invoice uses the meter directly. Typically 1-5% difference. See [beregninger.md](docs/beregninger.md#accuracy).

<a id="capacity-charge-in-energy-dashboard"></a>
**Why does the Energy Dashboard show wrong capacity charges?**

Only applies with **Totalpris inkl. avgifter** (the price sensor method). The sensor spreads the capacity charge (fixed kr/month) across expected kWh. The Energy Dashboard multiplies this by actual consumption. Use more or less than the distribution assumes, and the capacity charge comes out wrong.

Example: March, capacity 250 kr/month, spread across 744 kWh (31 days x 24):
- You use 1553 kWh, Dashboard computes (250/744) x 1553 = **522 kr** for capacity
- Invoice says **250 kr**
- Error: +272 kr on capacity alone

**Solution:** Use **Akkumulert stromkostnad** instead. Capacity charge is distributed linearly over time, not per kWh. See [setup](#option-2-accumulated-cost-recommended).

"Maanedlig nettleie total" is also useful for invoice verification, but cannot be used directly in Energy Dashboard.

## Documentation

| Document                                | Content                    |
|-----------------------------------------|----------------------------|
| [SENSORS.en.md](docs/SENSORS.en.md)     | All sensors and attributes |
| [beregninger.md](docs/beregninger.md)   | Formulas and tax zones     |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Update prices / report errors |
| [TESTING.md](docs/TESTING.md)           | Validating calculations    |

## License

MIT
