# Sammenligning med andre HA-integrasjoner

**Dato:** 2026-04-05

---

## Ting vi bør ta tak i

Disse tingene gjør andre bedre enn oss, eller har vi ikke i det hele tatt:

| Hva                                  | Hvem                                     | Status                     |
| ------------------------------------ | ---------------------------------------- | -------------------------- |
| Energisensor-støtte (kWh direkte)    | Dynamic Energy Cost                      | Issue `3gwr9a`             |
| Kalibrering mot faktura              | TNB Calculator (MY), Dynamic Energy Cost | Issue `2vljri`             |
| Ukentlig/årlig kostnadssensor        | Dynamic Energy Cost                      | Issue `3y56lf`             |
| Selektiv sensor-oppretting           | Dynamic Energy Cost                      | Issue `5urvhh`             |
| Event-driven (ikke polling)          | Dynamic Energy Cost                      | Ikke undersøkt ennå        |
| Automatisk enhetskonvertering        | Dynamic Energy Cost                      | Henger sammen med `3gwr9a` |
| Koble sensorer til kilde-device i HA | Dynamic Energy Cost                      | Ikke undersøkt ennå        |

## Ting som er interessante men utenfor scope

| Hva                            | Hvem                                |
| ------------------------------ | ----------------------------------- |
| AI-prisprediksjon (5 dager)    | Energi Data Service (DK) via Carnot |
| CO2-sensor                     | Energi Data Service (DK)            |
| Optimal starttid for apparater | EPEX Spot, PriceAnalyzer            |
| Solproduksjon/NEM-tracking     | Belgium Energy Costs, TNB, WattKost |

## Ting ingen andre gjør

Disse er ikke noe vi trenger å gjøre noe med, men er nyttig kontekst for å vite hva som er unikt:

- Komplett DSO-database for et helt land
- Strømstøtte-beregning (eneste aktive — nederlandske Prijsplafond ble avviklet)
- Norgespris-sammenligning
- Kombinasjonen kapasitetsledd + avgiftssoner + boligtyper
- DSO-migrasjoner

---

## Dynamic Energy Cost — detaljert

**Kilde:** https://github.com/martinarva/dynamic_energy_cost (v1.1.3)

Generisk «pris × forbruk = kostnad». Virker i alle land, men beregner ikke nettleie, avgifter eller subsidier.

### Arkitektur-forskjeller

| Aspekt      | Dynamic Energy Cost         | Strømkalkulator           |
| ----------- | --------------------------- | ------------------------- |
| Oppdatering | Event-driven (state_change) | Polling (1 min)           |
| Beregning   | Delta-akkumulering          | Coordinator + Riemann-sum |
| Lagring     | RestoreEntity               | Persistent JSON-filer     |
| Sensorer    | 8 per entry, valgfrie       | 44 faste (32 aktivert)    |
| Services    | reset_cost, calibrate       | Ingen                     |
| Land        | Alle                        | Norge                     |

### Ting de gjør bedre

- **Energisensor-path**: Støtter kWh-sensorer direkte med automatisk enhetskonvertering. Vi krever W og gjør Riemann-sum. Men: kWh gir ikke momentan effekt, så kapasitetsledd krever fortsatt W-sensor.
- **Event-driven**: Reagerer på state_change i stedet for 1-min polling. Mindre overhead.
- **Valgfrie sensorer**: Bruker velger hvilke som opprettes. Vi lager 44 (32 aktivert).

### Ting vi gjør bedre

- Faktisk totalkostnad (nettleie, avgifter, strømstøtte)
- 31 testfiler vs ingen synlige tester
- Persistent lagring med validering og outlier-deteksjon

---

## Øvrige integrasjoner

### Komplette kostnadskalkulatorer (andre land)

| Integrasjon                                                                                    | Land | Stars | Nettleie                   | Avgifter          | Subsidier     |
| ---------------------------------------------------------------------------------------------- | ---- | ----- | -------------------------- | ----------------- | ------------- |
| [Energi Data Service](https://github.com/MTrab/energidataservice)                              | DK+  | 265   | Auto (DK DSO)              | MVA               | Nei           |
| [Octopus Energy](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy)                 | UK   | 894   | Inkludert                  | Inkludert         | Nei           |
| [Belgium Energy Costs](https://github.com/ddebaets/belgium-energy-costs)                       | BE   | 0     | Distribusjon + transmisjon | Ja                | Solproduksjon |
| [Ontario Energy Board](https://github.com/jrfernandes/ontario_energy_board)                    | CA   | 66    | TOU-rater                  | Global adjustment | Nei           |
| [Taipower Bimonthly](https://github.com/cnstudio/Taipower-Bimonthly-Energy-Cost-homeassistant) | TW   | 77    | Trinnpriser                | Inkludert         | Nei           |
| [TNB Calculator](https://github.com/salihinsaealal/home-assistant-tnb-calculator)              | MY   | 6     | TOU + trinn                | Inkludert         | NEM solar     |

- **Energi Data Service** er nærmest oss — henter automatisk nettleie fra danske DSO-er.
- **TNB Calculator** har kalibrering mot faktura.
- **Prijsplafond (NL)** var eneste andre subsidie-kalkulator, nå avviklet.

### Norske integrasjoner (delvis overlapp)

| Integrasjon                                                                    | Fokus                                              | Stars | Aktiv?         |
| ------------------------------------------------------------------------------ | -------------------------------------------------- | ----- | -------------- |
| [EnergyTariff](https://github.com/epaulsen/energytariff)                       | Kapasitetstrinn-overvåking, topp-3-tracking        | 35    | Ja (mars 2026) |
| [PriceAnalyzer](https://github.com/erlendsellie/priceanalyzer)                 | Spot + templates for nettleie, VVB-styring         | 72    | Nov 2025       |
| [ha-elvia](https://github.com/sindrebroch/ha-elvia)                            | Elvia-spesifikk nettleie + kapasitet               | 16    | Inaktiv (2023) |
| [Glitre](https://github.com/Danielhiversen/home_assistant_glitre)              | Glitre-spesifikk forbruksledd                      | 4     | Inaktiv (2023) |
| [Nordpool Additional Cost](https://github.com/ArveVM/nordpool_additional_cost) | Jinja2-makroer for totalpris + strømstøtte (3 DSO) | 1     | Inaktiv (2023) |
| [Grid Tariff](https://codeberg.org/siljelb/grid_tariff)                        | Generisk nettleie per kWh (tid/sesong)             | 1     | Mai 2025       |

- **EnergyTariff** er eneste aktive — fokuserer på kapasitetstrinn. Komplementær.
- Enkelt-DSO-integrasjoner (Elvia, Glitre) er alle inaktive.

### Europeiske pris-integrasjoner (spotpris + templates)

| Integrasjon                                                                              | Land      | Stars | Nettleie?               |
| ---------------------------------------------------------------------------------------- | --------- | ----- | ----------------------- |
| [Nord Pool (HACS)](https://github.com/custom-components/nordpool)                        | Norden/EU | 558   | Via templates           |
| [EPEX Spot](https://github.com/mampfes/ha_epex_spot)                                     | DE/AT/EU  | 290   | Konfigurerbar surcharge |
| [ENTSO-e](https://github.com/JaccoR/hass-entso-e)                                        | Hele EU   | 262   | Via templates           |
| [Spotprices2ha](https://github.com/T3m3z/spotprices2ha)                                  | FI        | 137   | Konfigurerbar           |
| [CZ Energy Spot Prices](https://github.com/rnovacek/homeassistant_cz_energy_spot_prices) | CZ        | 128   | Via templates           |

Henter spotpriser og lar brukeren legge til nettleie/avgifter via Jinja2-templates.

### Land-spesifikke tariff-integrasjoner

| Integrasjon                                                                             | Land | Hva den gjør                                   | Stars |
| --------------------------------------------------------------------------------------- | ---- | ---------------------------------------------- | ----- |
| [Slovenian Network Tariff](https://github.com/frlequ/home-assistant-network-tariff)     | SI   | Tariffperiode basert på tid/sesong/helligdager | 54    |
| [BG Electricity Regulated](https://github.com/avataar/bg_electricity_regulated_pricing) | BG   | Dag/natt-tariff per leverandør (3 stk)         | 24    |
| [ERSE](https://github.com/dgomes/ha_erse)                                               | PT   | Tariff-ID + kostnadssimulering                 | 52    |
| [PVPC](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/)                 | ES   | Regulert timepris (HA Core)                    | Core  |
| [CEZ Distribuce HDO](https://github.com/Cmajda/ha_cez_distribuce)                       | CZ   | Dag/natt-skjema fra CEZ                        | 30    |
| [Göteborg Energi](https://github.com/bratland/goteborg-energi-ha)                       | SE   | Spot + nettleie + skatt for Göteborg           | 1     |
| [EffektGuard](https://github.com/enoch85/EffektGuard)                                   | SE   | Topp-3 effekt-tracking for varmepumpe          | 2     |

---

## Alle undersøkte integrasjoner

Komplett liste over integrasjoner som ble gjennomgått (april 2026):

### Norge
1. [EnergyTariff](https://github.com/epaulsen/energytariff) — kapasitetstrinn-overvåking
2. [PriceAnalyzer](https://github.com/erlendsellie/priceanalyzer) — spot + templates + VVB-styring
3. [ha-elvia](https://github.com/sindrebroch/ha-elvia) — Elvia-spesifikk nettleie
4. [Glitre](https://github.com/Danielhiversen/home_assistant_glitre) — Glitre-spesifikk forbruksledd
5. [NettleieElvia](https://github.com/uphillbattle/NettleieElvia) — Elvia API (AppDaemon)
6. [Nordpool Additional Cost](https://github.com/ArveVM/nordpool_additional_cost) — Jinja2-makroer for totalpris
7. [Grid Tariff](https://codeberg.org/siljelb/grid_tariff) — generisk nettleie per kWh

### Danmark
8. [Energi Data Service](https://github.com/MTrab/energidataservice) — spot + auto-nettleie fra DK DSO-er
9. [Eloverblik](https://github.com/JonasPed/homeassistant-eloverblik) — forbruk + tariff fra eloverblik.dk
10. [NRGI Prices](https://github.com/RasmusGodske/homeassistant-nrgiprices) — NRGI spotpriser

### Finland
11. [Spotprices2ha](https://github.com/T3m3z/spotprices2ha) — finske spotpriser
12. [Nordpool Predict FI](https://github.com/vividfog/nordpool-predict-fi-hacs) — AI-prisprediksjon

### Sverige
13. [Göteborg Energi](https://github.com/bratland/goteborg-energi-ha) — spot + nettleie for Göteborg
14. [EffektGuard](https://github.com/enoch85/EffektGuard) — topp-3 effekt-tracking
15. [Elpriser](https://github.com/henrikhjelmse/elpriser) — spotpriser SE1-SE4

### Norden/Europa (flernasjonale)
16. [Nord Pool (HACS)](https://github.com/custom-components/nordpool) — spotpriser + templates
17. [EPEX Spot](https://github.com/mampfes/ha_epex_spot) — markedspriser DE/AT/EU
18. [ENTSO-e](https://github.com/JaccoR/hass-entso-e) — spotpriser hele EU
19. [Dynamic Energy Cost](https://github.com/martinarva/dynamic_energy_cost) — generisk pris × forbruk
20. [Tibber Prices](https://github.com/jpawlowski/hass.tibber_prices) — kvartalsvis spotpris

### UK
21. [Octopus Energy](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy) — komplett Octopus-integrasjon
22. [Octopus Agile](https://github.com/markgdev/home-assistant_OctopusAgile) — Agile-tariff (forlatt)
23. [EDF FreePhase](https://github.com/jswilkinson851/ha-edf-freephase-dynamic-tariff) — EDF dynamisk tariff

### Nederland
24. [WattKost](https://github.com/roblomq/ha-wattkost) — fastpris-kontrakt + nettmåling
25. [Prijsplafond](https://github.com/rbrink/Home-Assistant-Prijsplafond) — pristak-kalkulator (avviklet)
26. [Zonneplan ONE](https://github.com/fsaris/home-assistant-zonneplan-one) — Zonneplan dynamisk tariff
27. [Frank Energie](https://github.com/bajansen/home-assistant-frank_energie) — Frank Energie priser

### Belgia
28. [Belgium Energy Costs](https://github.com/ddebaets/belgium-energy-costs) — ENGIE + nett + avgifter

### Sør-Europa
29. [PVPC](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/) — Spania, regulert timepris (HA Core)
30. [ERSE](https://github.com/dgomes/ha_erse) — Portugal, tariff + kostnadssimulering

### Sentral-/Øst-Europa
31. [CZ Energy Spot Prices](https://github.com/rnovacek/homeassistant_cz_energy_spot_prices) — Tsjekkia, spotpriser
32. [CEZ Distribuce HDO](https://github.com/Cmajda/ha_cez_distribuce) — Tsjekkia, dag/natt-skjema
33. [BG Electricity Regulated](https://github.com/avataar/bg_electricity_regulated_pricing) — Bulgaria, regulert pris
34. [Slovenian Network Tariff](https://github.com/frlequ/home-assistant-network-tariff) — Slovenia, tariffperioder

### Østerrike/Tyskland/Sveits
35. [EKZ Tariffs](https://github.com/schmidtfx/ekz-tariffs) — Sveits, EKZ-priser
36. [Energierechner-HA](https://github.com/PowderK/Energierechner-HA) — Tyskland, flerperiode-kalkulator
37. [PV Management](https://github.com/hoizi89/pv_management) — AT/DE/CH, solcellestyring

### Asia
38. [Taipower Bimonthly](https://github.com/cnstudio/Taipower-Bimonthly-Energy-Cost-homeassistant) — Taiwan, faktura-kalkulator
39. [TNB Calculator](https://github.com/salihinsaealal/home-assistant-tnb-calculator) — Malaysia, TOU + kalibrering

### Nord-Amerika
40. [Ontario Energy Board](https://github.com/jrfernandes/ontario_energy_board) — Canada, TOU + regulering

### Oseania
41. [Localvolts](https://github.com/gurrier/localvolts) — Australia, grossistpris + nettavgifter

### Generiske verktøy
42. [Energy Meter](https://github.com/zeronounours/HA-custom-component-energy-meter) — kostnad per tariffperiode
43. [Utility Meter Evolved](https://github.com/cabberley/utility_meter_evolved) — forbedret utility meter
