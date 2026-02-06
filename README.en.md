<p align="center">
  <img src="images/logo.png" alt="Strømkalkulator" width="400">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/releases"><img src="https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg" alt="GitHub release"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator"><img src="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator/graph/badge.svg" alt="codecov"></a>
</p>

**[Norsk versjon / Norwegian version](README.md)**

Home Assistant integration that calculates the **actual electricity price** in Norway - including grid tariffs, taxes, and government subsidies.

## What You Get

This integration provides sensors showing your **actual electricity cost** - not just the spot price. It calculates:

- **Grid tariffs** - Energy component (day/night rates) and capacity component from your grid company
- **Electricity subsidy** - Automatic calculation (90% above 96.25 øre/kWh)
- **Total price** - Everything included, ready for Energy Dashboard
- **Monthly consumption** - Tracks usage and costs per month
- **Invoice verification** - Compare with your invoice when it arrives

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

You need:
- **Power sensor** - Electricity consumption in Watts (e.g., from Tibber Pulse, P1 Reader, or Elhub)
- **Spot price sensor** - From the Nord Pool integration

Select your grid company from the list. All 71 Norwegian grid companies are supported!

## Devices and Sensors

The integration creates five devices with sensors:

### Grid Tariff (Nettleie)

Real-time prices and calculations for grid tariffs, electricity subsidy, and total price.

![Grid tariff](images/nettleie.png)

### Electricity Subsidy (Strømstøtte)

Shows how much you receive in electricity subsidy (90% above 96.25 øre/kWh).

![Electricity subsidy](images/strømstøtte.png)

### Norway Price (Norgespris)

Compares your spot price contract with Norgespris - so you can see what's more economical.

![Norgespris](images/norgespris.png)

### Monthly Consumption (Månedlig forbruk)

Tracks consumption and costs for the current month, split by day and night/weekend tariff.

![Monthly consumption](images/månedlig_forbruk.png)

### Previous Month (Forrige måned)

Stores previous month's data for easy invoice verification.

![Previous month](images/forrige_måned.png)

## Using with Energy Dashboard

To see actual electricity cost in Energy Dashboard:

1. **Settings > Dashboards > Energy**
2. Under "Electricity grid" > "Add consumption"
3. Select your kWh sensor (consumption meter)
4. **"Use an entity with current price"**: Select **Total price incl. taxes**

The dashboard now shows what your electricity actually costs - including grid tariffs, taxes, and subsidies.

**Tip:** Want to see price components (spot price, grid tariff, taxes) separately? Use a custom dashboard card like ApexCharts with the sensors from this integration.

## Electricity Plans

### Spot Price (most common)

If you have a regular spot price contract:
- The electricity subsidy (90% above 96.25 øre) is automatically deducted
- The "Electricity Subsidy" sensor shows how much you receive

### Norway Price (Norgespris)

Have you chosen [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) from your grid company?

1. Check "I have Norgespris" during setup
2. Fixed price is used: 50 øre (Southern Norway) or 40 øre (Northern Norway)
3. No subsidy - Norgespris replaces spot price and subsidy

### Comparing Plans

Not sure what's best for you? The "Price Difference Norgespris" sensor shows:
- **Positive value** = You save with Norgespris
- **Negative value** = Spot price is cheaper right now

## Verifying Against Invoice

When your grid tariff invoice arrives, you can easily verify the numbers:

1. Go to **Settings > Devices & Services > Strømkalkulator**
2. Click on the "Previous Month" device
3. Compare the values with your invoice

**Tip:** Click on a sensor to see details like top-3 power days and costs split by day/night.

![Grid tariff diagnostics](images/nettleie_diagnostic.png)

## Supported Grid Companies

**All 71 Norwegian grid companies are supported!** 🎉

Prices are updated annually at the start of each year. Found an error or outdated prices? [Create a PR](docs/CONTRIBUTING.md) or open an issue!

## Limitations

This integration is designed for **residential homes with individual electricity subscriptions**.

**Simplified model:**
- Electricity subsidy is calculated on all consumption (in reality max 5000 kWh/month)
- For most households this isn't an issue

**Not supported (yet):**
- Holiday homes (have 1000 kWh limit)
- Commercial use (different subsidy rates)
- Housing cooperatives with shared metering

**Future ideas:**
- Alert when capacity tier increases
- Support for holiday homes and commercial use
- Invoice import (PDF/CSV)

## Documentation

| Document                                | Content                    |
|-----------------------------------------|----------------------------|
| [SENSORS.md](docs/SENSORS.md)           | All sensors and attributes |
| [beregninger.md](docs/beregninger.md)   | Formulas and tax zones     |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Update prices / report errors |
| [TESTING.md](docs/TESTING.md)           | Validating calculations    |

## License

MIT
