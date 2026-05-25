# Funn fra Home Assistant Community (community.home-assistant.io)

Oversikt over hva HA-miljøet internasjonalt har bygget i samme vertikalt. Undersøkt mai 2026.

Komplementært til [funn-fra-hjemmeautomasjon.md](funn-fra-hjemmeautomasjon.md) som dekker norsk forum.

## Eksisterende HACS-integrasjoner i samme rom

| Integrasjon | Scope | Overlapp med Strømkalkulator |
|---|---|---|
| [EnergyTariff (epaulsen)](https://github.com/epaulsen/energytariff) | Kun kapasitetstrinn-tracking via Jinja-templates. ~35 stars. Norsk. | Overlapper på kapasitetstrinn-delen. Mangler spot, nettleie, avgifter, Norgespris. Vi har dette pluss alt annet, ferdig per DSO. |
| [Dynamic Energy Cost (martinarva)](https://community.home-assistant.io/t/custom-integration-dynamic-energy-cost-track-real-time-and-interval-electricity-costs-per-device/726931) | Per-device kostnadstracking (15min/time/dag/uke/mnd/år) mot vilkårlig pris-sensor. | Komplementær. Vi gir totalpris-sensor, den bryter ned per device. Mulig: dokumentere kjeding fra vår totalpris-sensor inn i Dynamic Energy Cost. |
| [Grid Tariff (community)](https://community.home-assistant.io/t/custom-component-grid-tariff/884393) | Generisk dynamisk nettleie per kWh via templates. | Generisk, ikke DSO-spesifikk. Vi er ferdig oppsatt for alle 50+ norske DSO-er. |
| [ENTSO-e Day Ahead Energy Prices](https://community.home-assistant.io/t/custom-component-entso-e-day-ahead-energy-prices/467127) | Råpriser fra ENTSO-e Transparency Platform for hele EU. | Alternativ pris-input til Nordpool. Vi støtter Nordpool. Kunne være fallback. |
| [EPEX Spot / Awattar](https://community.home-assistant.io/t/epex-spot-and-awattar-electricity-prices/519151) | Sentral-Europa-priser (DE/AT). | Irrelevant for Norge. Viser at andre land har egne pris-integrasjoner. |
| [EMHASS](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126) | Linear-programming-optimering av batteri/PV/last mot dynamisk pris. | Stort scope-skille. Konsumerer pris-sensorer. Vi kunne mate den. |
| [Octopus Energy / Agile Tariff](https://community.home-assistant.io/t/octopus-energy-agile-tariff/160458) | UK-spesifikk Octopus-integrasjon. | UK-ekvivalent. Ikke direkte konkurranse. |

## Norske tråder på det internasjonale forumet

- **[Strømkalkulator — True electricity cost for Norway (all grid companies)](https://community.home-assistant.io/t/stromkalkulator-true-electricity-cost-for-norway-all-grid-companies/1000314)** — vår egen tråd. Brukerne ber om: salgsinntekt for plusskunder + sammenligning spot vs Norgespris, netto-kost (forbruk minus eksport), separat «forbruk-only»-pris uten kapasitetsestimat, strømstøtte parallelt med Norgespris.
- **[Any good ideas are welcome. Nordpool Energy Price per hour](https://community.home-assistant.io/t/any-good-ideas-are-welcome-nordpool-energy-price-per-hour/34646)** — 25+ sider, går tilbake til 2018. Hovedhubben for Nordpool-DIY internasjonalt, mye norsk innhold.
- **[Tibber, energy price and consumption visualization](https://community.home-assistant.io/t/tibber-energy-price-and-consumption-visualization-for-germany-sweden-and-norway/244623)** — delt template-pakke for Tibber-brukere i DE/SE/NO.
- **[Norway & Sweden electric meter reading (AMS HAN)](https://community.home-assistant.io/t/norway-sweden-electric-meter-reading-ams-han/384646)** — AMSHAN-integrasjonen. Leser Aidon/Kamstrup/Kaifa via HAN-port. Komplementær (input-data).
- **[Tibber Pulse MQTT — local MQTT integration](https://community.home-assistant.io/t/tibber-pulse-mqtt-local-mqtt-integration-with-optional-aws-iot-bridge-hacs/1006458)** — lokal Tibber Pulse uten sky-API. Også input-data.

**Gap før Strømkalkulator:** ingen norsk tråd dekket hele pakka (spot + nettleie + avgifter + Norgespris + plusskunde) på det internasjonale forumet. AMSHAN/Tibber Pulse leverer rådata, vi konsumerer.

## HA Blueprints relatert til strømstyring

Disse er ferdige automasjons-maler brukere kan importere direkte i HA. Bruker våre eller andre pris-sensorer.

- **[Nordpool cheapest hours, turn on devices](https://community.home-assistant.io/t/blueprint-that-uses-nordpool-and-lets-you-turn-on-devices-on-the-cheapest-hours-and-make-automations-based-on-that-information/646360)** — de facto-standarden. Rangerer timer fra billigst til dyrest, kjører handling i N billigste.
- **[Nordpool price cheap/expensive actions](https://community.home-assistant.io/t/nordpool-price-cheap-expensive-actions/498055)** — terskel-basert.
- **[Nordpool cheapest hours actions (15-min)](https://community.home-assistant.io/t/nordpool-cheapest-hours-actions/940421)** — nyere, støtter 15-min Nordpool.
- **[Warmwater boiler — cheapest hours via Nordpool](https://community.home-assistant.io/t/warmwater-boiler-run-only-during-cheapest-hours-based-on-nordpool/565021)** — VVB-styring via Shelly.
- **[Smart immersion heating for domestic hot water](https://community.home-assistant.io/t/smart-immersion-heating-for-domestic-hot-water/536281)** — VVB + solcelle-overskudd.
- **[Smart Energy Arbitrage (Octopus + Enphase + Solcast)](https://community.home-assistant.io/t/smart-energy-arbitrage-system-octopus-energy-enphase-solcast-996732)** — kjøp/selg/hold-beslutning for hjemmebatteri.

## Internasjonale features vi ikke har tenkt på

1. **Per-device kostnadssensorer** (Dynamic Energy Cost-mønsteret). Sensor-template som tar power-sensor + vår totalpris og produserer real-time kr/h per enhet.
2. **15-min spot-støtte.** Norge går mot 15-min avregning. Internasjonalt forum diskuterer aktivt, mange Nordpool-blueprints støtter både 1h og 15min.
3. **Negative priser / feed-in beslutning.** Sjeldent i Norge, men relevant for plusskunder med batteri.
4. **Solcelle-forecast som input** ([Solcast](https://community.home-assistant.io/t/solcast-global-solar-power-forecast-integration/334681), Forecast.Solar). Beslutning: vent med VVB til sol kommer, eller kjør nå?
5. **Arbitrage-beslutning** — kombiner pris + solprognose + batteri-SoC → kjøp/selg/hold.
6. **Battery dispatch-modeller** (EMHASS): MPC-optimering med dagens og morgendagens priser.
7. **«Pris-divisjons-signal»** ([nordpool_diff](https://github.com/jpulakka/nordpool_diff)): omformer spot til termostat-signal — peker mot derived control-sensorer.
8. **Energi-dashboard-helpers for dual/multi-tariff** ([Octopus Go guide](https://community.home-assistant.io/t/how-to-set-up-octopus-go-or-other-dual-rate-tariff-in-energy-dashboard/484105)) — mater riktig pris inn i Energy Dashboard per tidsperiode.

## Anbefalinger for utvidelse

Sortert etter brukerverdi vs scope-disiplin.

**Innenfor scope (data-integrasjon):**

1. **Plusskunde-eksportsensorer + Norgespris-sammenligning på salgssiden.** Etterspurt i vår egen HA-tråd. Lav-medium kompleksitet.
2. **Netto-kost-sensor** (forbruk-kostnad minus eksport-inntekt). Også etterspurt. Bygger på 1.
3. **Forbruk-only pris-sensor** (spot + energiledd + avgifter, uten kapasitetstrinn). Lett, ofte etterspurt.
4. **Eksplisitt 15-min Nordpool-støtte.** Norge går mot 15-min avregning. Mulig regresjon.
5. **Dokumentert integrasjon med Dynamic Energy Cost.** Pek på det, ikke bygg det selv.
6. **«Beste N timer»-sensor-attributter** — billigste *reelle* timer (inkl. nettleie dag/natt), ikke bare spot. Eksponer som attributter siden vi har totalpris.
7. **ENTSO-e fallback hvis Nordpool ned.** Liten innsats, god robustness.
8. **Solcelle-forecast som valgfri input** (Solcast/Forecast.Solar) for plusskunde-prediksjon. Større scope-utvidelse, vurder før du tar.

**Utenfor scope:**

- Faktisk last-styring (VVB/billader/varmeovner) — blueprint-territorium, ikke integrasjon. Bedre å dokumentere hvordan våre sensorer kobles til [cheapest-hours-blueprintet](https://community.home-assistant.io/t/blueprint-that-uses-nordpool-and-lets-you-turn-on-devices-on-the-cheapest-hours-and-make-automations-based-on-that-information/646360).
- Batteri-arbitrage / EMHASS-ekvivalent — eget produkt-rom.
- ApexCharts-kortet — leveres som dokumentert eksempel, ikke som integrasjon.

## Posisjon

Vi er den eneste norske «total kr/kWh»-integrasjonen (spot + nettleie + avgifter + Norgespris + plusskunde + DSO-helligdager + fakturaverifisert). Konkurrentene dekker delmengder. Hold scope der, eksporter rene sensorer som blueprint-økosystemet kan konsumere.
