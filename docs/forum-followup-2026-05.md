# Follow-up post: Home Assistant Community forum

Target thread: https://community.home-assistant.io/t/stromkalkulator-true-electricity-cost-for-norway-all-grid-companies/1000314

---

**A lot has changed since the original post. Quick highlights from v1.2.0 through v1.13.0:**

**Now invoice-accurate**

Six BKK invoices replayed hour-by-hour from October 2025 through April 2026. Every nettleie line matches within 0,01-0,02 kr. With an energy meter sensor configured, monthly consumption matches the DSO invoice to the watt-hour (same numbers as Elhub). Spot price, strømstøtte and Norgespris-compensation are checked against the same source data.

**Bugs that moved real money**

- Spot price VAT handling. HA-core Nordpool delivers ex. VAT, the integration assumed incl. VAT. Sør-Norge users on spot saw 25 % off in strømstøtte and Norgespris comparison. Auto-migrated. (v1.12)
- NO3 VAT classification. ~14 DSOs in Trøndelag and Møre og Romsdal were treated as VAT-exempt by mistake. (v1.11)
- Double-counted Forbruksavgift and Enova-avgift in monthly totals, about 150 kr/month too high for a typical household. (v1.7)
- Kapasitetstrinn used instant power instead of hourly energy average. Now matches how the DSO derives the step from Elhub. (v1.7)
- Tariff corrections for Lnett, Lede, Elvia 2026, triple-verified against official price lists. (v1.13)
- Spot sensor validation in config flow. If you point the spot price input at a kr-sensor or a kWh meter, setup now rejects it instead of accepting it silently. Previously some Elvia users ended up with strømstøtte at 182 469 kr/month. (v1.13)

**More robust**

- Survives HA restarts and long downtime. Accumulators persist to disk, consumption in the restart window is no longer lost. Before the fix: 36 % of a month's Norgespris compensation went missing on a real setup. (v1.13)
- Energy meter as input (v1.13). Point to your kWh meter (Pow-U, Tibber Pulse, ESPHome). Uses register deltas instead of Riemann-summing the power sensor. This is now the recommended setup; without it expect 1-5 % drift from the invoice over a month.
- Caches spot price and provider price across sensor dropouts, no more holes in the graph. (v1.4, v1.5)

**New features**

- Solar export for plusskunder: exported kWh, income at spot, net cost. (v1.8)
- Fritidsbolig and hytte support with correct kWh caps for strømstøtte and Norgespris. (v1.6)
- Accumulated cost sensor for the Energy Dashboard, includes capacity step. (v1.9)
- Norgespris compensation in kroner, directly comparable to the invoice line. (v1.8)
- Per-DSO weekend tariff and VAT zone overrides (v1.11), plus per-DSO `helligdager_ekstra` so BKK gets 24.12/31.12 as low-tariff while other DSOs stay on default holidays until invoice data confirms otherwise (v1.13).

**Trust the numbers**

- Invoice verification button on the "Previous month" device. Generates a ready-to-paste report you can submit if your DSO is not yet in the verified table.
- Signed releases, SHA256 plus `gh attestation verify` on every zip.

All release notes: https://github.com/fredrik-lindseth/Stromkalkulator/releases
