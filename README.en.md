<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/logo-dark.png">
    <img src="images/logo-light.png" alt="Strømkalkulator" width="400">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/releases"><img src="https://img.shields.io/github/release/fredrik-lindseth/Stromkalkulator.svg" alt="GitHub release"></a>
  <img src="https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.stromkalkulator.total" alt="Installs">
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml"><img src="https://github.com/fredrik-lindseth/Stromkalkulator/actions/workflows/hassfest.yml/badge.svg" alt="Hassfest"></a>
  <a href="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator"><img src="https://codecov.io/gh/fredrik-lindseth/Stromkalkulator/graph/badge.svg" alt="codecov"></a>
  <a href="SECURITY.md"><img src="https://slsa.dev/images/gh-badge-level1.svg" alt="SLSA 1"></a>
</p>

**[Norsk versjon / Norwegian version](README.md)**

Home Assistant integration that calculates the actual electricity price in Norway, including grid tariffs, taxes, and government subsidies.

## What you get

Sensors showing what electricity actually costs, not just the spot price:

- Grid tariff: energy component (day/night) and capacity component from your grid company
- Electricity subsidy: automatic (90 % above 96.25 øre/kWh)
- Total price: everything included, usable in Energy Dashboard
- Monthly consumption and cost
- Invoice check against the previous month
- Solar export (disabled by default)

## Verified against real invoices

| Grid company | Price area | Verified months | Latest verification |
| ------------ | ---------- | ---------------- | -------------------- |
| BKK          | NO5        | 8                 | June 2026            |

Each report matches the integration's calculations line by line against a real invoice. See [docs/fakturaer/referanse.md](docs/fakturaer/referanse.md) (Norwegian).

**Precision:** The integration hits the invoice to the øre: within 50 Wh on monthly consumption, 1-2 øre on the grid tariff lines (BKK's internal rounding), and the Norgespris line is reproduced exactly against published Final prices (June 2026, see [docs/research/norgespris-eksakt-match.md](docs/research/norgespris-eksakt-match.md), Norwegian). The live sensor can deviate 0.04-0.05 % because Nord Pool may correct the exchange rate after publication. No configuration needed. Details per meter brand and HAN reader: [docs/begrensninger.md](docs/begrensninger.md) (Norwegian).

Verification was done on a Kaifa MA304H3E (3-phase, imported by Nuri Telecom) with a Pow-U HAN reader (AMSleser.no) and the official `nordpool` integration in HA. Aidon meters have the same broadcast timing (HH:00:10) and are expected to give the same precision. Other HAN readers and spot integrations may have different precision characteristics.

Using a different grid company? [Submit your invoice](docs/fakturaer/verifiser-din-faktura.md) and we'll confirm it.

## Installation

### Via HACS (recommended)

1. Click the button below to open the integration in HACS:
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fredrik-lindseth&repository=Stromkalkulator&category=integration)
2. Click **Download**
3. Restart Home Assistant

_Alternatively: HACS > Integrations > Explore & Download Repositories > Search for "Strømkalkulator"_

### Manual

Copy `custom_components/stromkalkulator` to `/config/custom_components/`

## Setup

**Settings > Devices & Services > Add Integration > Strømkalkulator**

![Setup](images/setup.png)

### Step 1: Select grid company

Select your grid company from the dropdown. Tax zone (VAT and consumption tax) is set automatically based on your grid company.

### Property type

| Property type                      | Electricity subsidy | Norgespris cap | Source                                                                      |
| ----------------------------------- | -------------------- | ---------------- | ----------------------------------------------------------------------------- |
| Residence (default)                 | 5000 kWh/month        | 5000 kWh/month    | [Regulation § 5](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)   |
| Holiday home                        | None                  | 1000 kWh/month    | [Regulation § 3](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)   |
| Holiday home (permanent residence)  | 5000 kWh/month        | 5000 kWh/month    | [Regulation § 11](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)  |

Above the Norgespris kWh cap, you pay spot price for the rest of the month. Holiday homes are not entitled to electricity subsidy unless you live there permanently (§ 11).

### Step 2: Select sensors

- Power meter (W): current consumption in watts, typically from an AMS reader via the HAN port (e.g. Tibber Pulse).
- Spot price sensor (NOK/kWh): usually "Current price" from the [Nord Pool integration](https://www.home-assistant.io/integrations/nordpool/). It delivers prices excluding VAT, which is what the integration expects. If your sensor already includes VAT, tick "Spotpris-sensor leverer priser inkl. mva".
- Electricity provider sensor (optional): total price from your provider (e.g. Tibber), to see what you actually pay.

All Norwegian grid companies are supported.

### Tax zones

The tax zone determines VAT and consumption tax, and is set automatically from your grid company. You can override it in settings if needed.

| Tax zone         | Price areas          | Consumption tax | VAT |
| ----------------- | --------------------- | ----------------- | ----- |
| Southern Norway    | NO1, NO2, NO5          | 7.13 øre/kWh        | 25% |
| Northern Norway    | Nordland, Troms       | 7.13 øre/kWh        | 0%  |
| Tiltakssonen       | Finnmark/Nord-Troms   | 0 øre               | 0%  |

## Devices and Sensors

The integration creates six devices with sensors:

### Grid tariff (Nettleie)

Prices and calculations for grid tariff, electricity subsidy, and total price.

![Grid tariff](images/nettleie.png)

### Electricity subsidy (Strømstøtte)

How much you receive in electricity subsidy (90 % above 96.25 øre/kWh).

![Electricity subsidy](images/strømstøtte.png)

### Norgespris

Compares your spot price plan with Norgespris.

![Norgespris](images/norgespris.png)

### Monthly consumption (Månedlig forbruk)

Consumption and cost for the current month, split by day and night/weekend.

![Monthly consumption](images/månedlig_forbruk.png)

### Previous month (Forrige måned)

Previous month's data for invoice verification.

![Previous month](images/forrige_måned.png)

### Export (Eksport)

Solar export for prosumers (disabled by default).

## Using with Energy Dashboard

The Energy Dashboard needs a consumption meter (kWh) and a cost source. The consumption meter comes from your power meter integration (AMS reader via HAN, e.g. Tibber Pulse). For the cost you have two options.

### Option 1: price sensor (kr/kWh)

Use **Totalpris inkl. avgifter**. Simplest to set up, but the capacity charge is spread per kWh, so the monthly total becomes inaccurate.

1. **Settings > Dashboards > Energy**
2. Under **Electricity grid**, click **Add consumption**
3. Select your kWh consumption sensor under **Consumed energy**
4. Enable **Use an entity with current price**
5. Select `sensor.totalpris_inkl_avgifter_*`

### Option 2: accumulated cost (recommended)

Use **Akkumulert strømkostnad**. The capacity charge is distributed linearly over time, so the monthly total matches the invoice regardless of consumption. The sensor is disabled by default.

1. Enable the sensor: **Settings > Devices > Monthly consumption > Entities > Akkumulert strømkostnad**
2. **Settings > Dashboards > Energy > Add consumption**
3. Select your kWh consumption sensor under **Consumed energy**
4. Enable **Use an entity tracking total costs**
5. Select `sensor.akkumulert_stromkostnad_*`

> Don't have a kWh sensor? You need something that reads the electricity meter via the HAN port, e.g. a [Tibber Pulse](https://www.home-assistant.io/integrations/tibber/) or another AMS reader.

Want to see the price components (spot price, grid tariff, taxes) separately? Use a custom dashboard card such as ApexCharts.

## Electricity plans

### Spot price

Electricity subsidy (90 % above 96.25 øre) is deducted automatically. The "Strømstøtte" sensor shows the amount.

### Norgespris

If you have [Norgespris](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) with your grid company:

1. Tick "Jeg har Norgespris" during setup
2. The fixed price is 50 øre in Southern Norway or 40 øre in Northern Norway
3. You get no electricity subsidy (Norgespris replaces spot price and subsidy)

### Comparing plans

The "Prisforskjell Norgespris" sensor shows whether Norgespris or spot price is cheapest right now. A positive value means you save with Norgespris.

## Checking against your invoice

When the grid tariff invoice arrives:

1. Go to Settings > Devices & Services > Strømkalkulator
2. Click on the "Forrige måned" device
3. Compare the values with your invoice

Click on a sensor for details like the top-3 power days and costs split by day/night.

![Grid tariff diagnostics](images/nettleie_diagnostic.png)

## Supported grid companies

All Norwegian grid companies are supported. Prices are updated annually at the start of the year. Found an error, [create a PR](docs/contributing.md) or open an issue.

## Grid company mergers

The integration handles mergers automatically. The configuration updates at the next restart; consumption data and history are preserved. You'll get a notification under Settings > Repairs.

## Sensors

35 active sensors across 6 devices. Diagnostic sensors are disabled by default and can be enabled under Settings > Devices > Entities. Disabling a sensor doesn't affect the calculations.

See [sensors.en.md](docs/sensors.en.md) for the complete overview.

## Limitations

Designed for residential homes with individual electricity subscriptions. Not supported:

- Commercial use (different subsidy rates)
- Housing cooperatives with shared metering

## Frequently asked questions

**Why does the sensor show "natt" (night) in the middle of the day?**

The "natt" tariff is actually "natt/helg" (night/weekend) and applies to:

- Nights (22:00-06:00) every day
- Entire weekends (Sat and Sun, all day)
- Public holidays (all day)

So on a Saturday at 14:00, "natt" tariff is correct.

**Why is "Totalpris inkl. avgifter" higher than the spot price?**

The spot price is just the electricity. Total price also includes grid tariff (energy component + capacity component), consumption tax, Enova levy, and VAT. For most people, grid tariff and taxes make up 30-50% of the total price.

**Electricity subsidy shows 0. Is that wrong?**

No. Electricity subsidy is only paid out when the spot price is above 96.25 øre/kWh (2026). Below the threshold, the subsidy is 0.

**The numbers don't quite match my invoice?**

You're probably missing an energy sensor (kWh meter) in your configuration. With an energy sensor, the integration reads consumption directly from the meter register and matches the invoice down to the last watt-hour. Without one, consumption is estimated via a Riemann sum of the power sensor, and you'll typically see a 1-5 % deviation over a month. See [input-sensorer.md](docs/input-sensorer.md) (Norwegian) for how to add one, and [beregninger.md](docs/beregninger.md#nøyaktighet) (Norwegian) for details.

<a id="capacity-charge-in-energy-dashboard"></a>
**Why does the Energy Dashboard show the wrong capacity charge?**

This only applies if you use **Totalpris inkl. avgifter** (the price sensor method). The total price sensor spreads the capacity charge over expected kWh. The Energy Dashboard multiplies this price by actual consumption. If you use more or less than the distribution assumes, the capacity charge comes out wrong.

Example: March, capacity charge 250 kr/month, spread over 744 kWh (31 days x 24):

- You use 1553 kWh, the Dashboard computes (250/744) x 1553 = **522 kr** for the capacity charge
- The invoice says **250 kr**
- Deviation: +272 kr on the capacity charge alone

**Solution:** Use **Akkumulert strømkostnad** instead. This sensor distributes the capacity charge linearly over time, not per kWh, and gives correct monthly totals regardless of consumption. See [setup](#option-2-accumulated-cost-recommended).

The "Månedlig nettleie total" sensor is also useful for invoice verification, but can't be used directly in the Energy Dashboard.

## Documentation

| Document                                     | Content                                    |
| --------------------------------------------- | ------------------------------------------- |
| [sensors.en.md](docs/sensors.en.md)           | All sensors and attributes                  |
| [beregninger.md](docs/beregninger.md)         | Formulas and tax zones (Norwegian)          |
| [contributing.md](docs/contributing.md)       | Update prices / report errors (Norwegian)   |
| [testing.md](docs/testing.md)                 | Validating calculations (Norwegian)         |

## Verifying releases

Every release has a cryptographic attestation proving the ZIP file was built from the source code in this repo. See [SECURITY.md](SECURITY.md) for details.

```bash
gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
```

## Data sources

Grid tariff prices are maintained in the integration and cross-checked against [fri-nettleie](https://github.com/kraftsystemet/fri-nettleie) from kraftsystemet, which serves as the reference for the rates. Their data is used under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Taxes come from the Norwegian Tax Administration, capacity tier structure from NVE.

## License

MIT
