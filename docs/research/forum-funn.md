# Funn fra HA-foraene

Hva andre i Home Assistant-miljøet har bygd for å løse deler av samme problem som Strømkalkulator. Brukes som referanse for hvor vi kan utvide og hvor vi bevisst lar være.

Tråder gjennomgått mai 2026. Norsk forum: hjemmeautomasjon.no. Internasjonalt forum: community.home-assistant.io.

## Eksisterende HACS-integrasjoner

| Integrasjon | Scope | Overlapp |
|---|---|---|
| [EnergyTariff (epaulsen)](https://github.com/epaulsen/energytariff) | Kapasitetstrinn-tracking via Jinja-templates. Norsk. ~35 stars. | Overlapper kun på kapasitetstrinn. Vi har dette pluss spot, nettleie, avgifter, Norgespris, ferdig per DSO. |
| [Dynamic Energy Cost (martinarva)](https://community.home-assistant.io/t/custom-integration-dynamic-energy-cost-track-real-time-and-interval-electricity-costs-per-device/726931) | Per-device kostnadstracking (15min/time/dag/uke/mnd/år) mot vilkårlig pris-sensor. | Komplementær. Vi gir totalpris-sensor, den bryter ned per enhet. Vi kan dokumentere kjeding fra vår sensor inn i denne. |
| [Grid Tariff (community)](https://community.home-assistant.io/t/custom-component-grid-tariff/884393) | Generisk dynamisk nettleie per kWh via templates. | Ikke DSO-spesifikk. Vi er ferdig oppsatt for alle 50+ norske DSO-er. |
| [ENTSO-e Day Ahead](https://community.home-assistant.io/t/custom-component-entso-e-day-ahead-energy-prices/467127) | Råpriser fra ENTSO-e for hele EU. | Alternativ pris-input til Nordpool. Kunne være fallback hos oss. |
| [EMHASS](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126) | Linear-programming-optimering av batteri/PV/last mot dynamisk pris. | Stort scope-skille. Konsumerer pris-sensorer. Vi kan mate den. |
| [AMSHAN](https://community.home-assistant.io/t/norway-sweden-electric-meter-reading-ams-han/384646) | Leser Aidon/Kamstrup/Kaifa via HAN-port. Norsk. | Input-data. Komplementær. |
| [Tibber Pulse MQTT](https://community.home-assistant.io/t/tibber-pulse-mqtt-local-mqtt-integration-with-optional-aws-iot-bridge-hacs/1006458) | Lokal Tibber Pulse uten sky-API. | Input-data. Komplementær. |

## Funksjoner andre har bygd

### Billigste/dyreste X timer

Mest etterspurt i forumet. Brukes til billader, varmtvannsbereder, varmekabler.

- [Tråd 12474: Howto: Finn laveste strømpris-timer (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/12474-howto-finn-laveste-strømpris-timer/): Node-RED-flow som henter priser fra hvakosterstrommen.no og setter globale variabler `lavPris` og `lavLavPris`.
- [Tråd 11669: Integrere strømpriser fra AMS-leser (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/11669-integrere-strømpriser-fra-amsleser-i-home-assistant/): Brukerne ber om sensorer for billigste/dyreste timer. Diskusjon om AMS-lesere som sletter historikk, som gjør "har bilen ladet i 3 eller 5 timer hittil i natt"-logikk vanskelig.

Status hos oss: ikke implementert.

### Per-time pris-sensorer

24 (eller 96 etter 15-min-overgangen) separate sensorer for prisen hver time.

- [Tråd 13540: Template sensor for timespriser nordpool (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/13540-template-sensor-for-timespriser-nordpool/): Template-sensorer per time fra Nordpool sine `today`/`tomorrow`-attributter. Trådkommentar peker på at logikken bryter etter 15-min-overgangen (24×4 elementer).

Status hos oss: ikke implementert.

### 15-min Nord Pool-prising

Nord Pool gikk over til kvartersbaserte day-ahead-priser høsten 2025.

- [Tråd 13363: 15 minutters interval på strømpris (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/13363-15-minutters-interval-på-strømpris/).
- [Tråd 13540 (samme som over)](https://www.hjemmeautomasjon.no/forums/topic/13540-template-sensor-for-timespriser-nordpool/): kommentar om at eksisterende kode brytes.

Status hos oss: coordinator leser gjeldende pris hvert minutt. Ikke verifisert mot 24×4-elementer i `today`/`tomorrow`-attributter. Mulig regresjon vi ikke har fanget.

### Prediktiv kapasitetstrinn-styring

Aktivt regulere forbrukere for å unngå å overskride neste effekttrinn.

- [Tråd 9253: Prediktiv reduksjon av strømbruk effektariff-nivå (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/9253-prediktiv-reduksjon-av-strømbruk-effektariff-nivå/): PID-regulator basert på Tibber Pulse 2,5s-effekt. Integrerer opp forventet timesforbruk, styrer 0–100 %-utgang som slår av/på forbrukere.

Status hos oss: vi har `kapasitet_varsel` (binær). Ikke prediktiv styring. Bevisst utenfor scope, egen integrasjon (Effektvakt) tar dette.

### Styring av forbrukere basert på pris

Slå av VVB og varmeovner i pristopper. Slå på når billig.

- [Tråd 12298: Styring av VVB med Nordpool og rene HA-automasjoner](https://www.hjemmeautomasjon.no/forums/topic/12298-styring-av-varmtvannsbereder-med-nordpool-og-rene-ha-automasjoner/): ESPHome + Dallas-temperatursensor + smart relé + Generic Thermostat helper. Ren HA-automasjon.
- [Tråd 11282: Styring av forbruk basert på strømpriser (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/11282-styring-av-forbuk-basert-på-strømpriser-leverandøruavhengig/): HomeSeer-plugin (PowerControl) som henter priser fra ENTSO-E, beregner når strømmen bør slås av, tar hensyn til VVB-begrensninger.
- [Tråd 10824: Flow til styring av VVB etter strømpriser](https://www.hjemmeautomasjon.no/forums/topic/10824-flow-til-styring-av-vvb-etter-strømpriser/).

Cheapest-hours-blueprintet på det internasjonale forumet dominerer:

- [Nordpool cheapest hours, turn on devices](https://community.home-assistant.io/t/blueprint-that-uses-nordpool-and-lets-you-turn-on-devices-on-the-cheapest-hours-and-make-automations-based-on-that-information/646360): de facto-standarden. Rangerer timer fra billigst til dyrest, kjører handling i N billigste.
- [Nordpool price cheap/expensive actions](https://community.home-assistant.io/t/nordpool-price-cheap-expensive-actions/498055): terskel-basert.
- [Nordpool cheapest hours (15-min)](https://community.home-assistant.io/t/nordpool-cheapest-hours-actions/940421): nyere, støtter 15-min.
- [Warmwater boiler, cheapest hours via Nordpool](https://community.home-assistant.io/t/warmwater-boiler-run-only-during-cheapest-hours-based-on-nordpool/565021).
- [Smart immersion heating](https://community.home-assistant.io/t/smart-immersion-heating-for-domestic-hot-water/536281): VVB + solcelle-overskudd.
- [Smart Energy Arbitrage](https://community.home-assistant.io/t/smart-energy-arbitrage-system-octopus-energy-enphase-solcast-996732): Octopus + Enphase + Solcast, kjøp/selg/hold-beslutning for hjemmebatteri.

Status hos oss: bevisst utenfor scope. Vi gir data, ikke styringslogikk.

### Tibber-totalpris

Tibber-integrasjonen viser kun råpris, ikke det brukerne ser i Tibber-appen.

- [Tråd 12029: Tibber med avgifter og nettleie som i Tibber-appen (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/12029-går-det-an-å-få-prisen-fra-tibber-med-avgifter-og-nettleie-som-i-tibber-appen/): Trådanbefaling går til HACS-integrasjonen [home_assistant_tibber_data](https://github.com/Danielhiversen/home_assistant_tibber_data).
- [Tibber visualization for DE/SE/NO](https://community.home-assistant.io/t/tibber-energy-price-and-consumption-visualization-for-germany-sweden-and-norway/244623): delt template-pakke.

Status hos oss: vi har "Total strømpris (strømavtale)"-sensor som dekker dette. Direkte konkurrent til `home_assistant_tibber_data`, men også for ikke-Tibber-brukere.

### Fargekodet pris-visualisering

Lovelace-kort som fargekoder strømpris dynamisk basert på dagens min/max/mean.

- [Tråd 12313: ApexChart med fargekoding (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/12313-apexchart-med-fargekoding-for-strømpriser-og-strømforbruk-nordpool-og-tibber/): ferdig ApexChart-config. Fargen i tittelen og linjen endres basert på prisnivå.
- [Tråd 11352: Stolpediagram for fremtidige strømpriser](https://www.hjemmeautomasjon.no/forums/topic/11352-stolpediagram-for-fremtidige-strømpriser/).
- [Tråd 12344: AI for å generere YAML (apex charts, fargekoding)](https://www.hjemmeautomasjon.no/forums/topic/12344-bruk-av-ai-for-å-generere-yaml-kode-i-ha-eksempel-apex-charts-for-å-fargekode-billigste-og-dyreste-strømpriser/).

Status hos oss: vi gir sensorer, ikke dashboard-eksempler. Mulig: legge til ferdige Lovelace-kort i docs.

### Manuell template-pris-beregning (det vi erstatter)

- [Tråd 11102: Strømpriser (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/11102-strømpriser/): Template som regner ut EUR→NOK med Nordpool/Entso-e + dag/natt-tariff + mva. Manuelt vedlikehold per bruker.
- [Tråd 13251: Nordpool oppsett med nettleie sommer/vinter (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/13251-nordpool-oppsett-med-nettleie-sommer-vinter-mm/): bruker strever med `additional_costs` i Nordpool-YAML.
- [Any good ideas are welcome. Nordpool Energy Price per hour](https://community.home-assistant.io/t/any-good-ideas-are-welcome-nordpool-energy-price-per-hour/34646): 25+ sider, hovedhubben for Nordpool-DIY internasjonalt.

Status hos oss: vi erstatter dette fullstendig. Hovedgrunnen til å bruke Strømkalkulator i stedet for DIY.

### Nettleie-API-tilgang

- [Tråd 9051: API for nettleie-priser hos Elvia](https://www.hjemmeautomasjon.no/forums/topic/9051-api-for-nettleie-priser-hos-elvia/).
- [Tråd 11108: API for nettleie-priser hos Lnett](https://www.hjemmeautomasjon.no/forums/topic/11108-api-for-nettleie-priser-hos-lnett/).

Status hos oss: alle nettselskap innebygd i `dso.py`.

### Andre features fra det internasjonale forumet

- [nordpool_diff (GitHub)](https://github.com/jpulakka/nordpool_diff): omformer spot til termostat-signal. Peker mot derived control-sensorer.
- [Solcast forecast](https://community.home-assistant.io/t/solcast-global-solar-power-forecast-integration/334681): solcelle-forecast som input. Beslutning: vent med VVB til sol kommer.
- [Octopus Go dual-rate Energy Dashboard guide](https://community.home-assistant.io/t/how-to-set-up-octopus-go-or-other-dual-rate-tariff-in-energy-dashboard/484105): mater riktig pris inn i Energy Dashboard per tidsperiode.

### Direkte konkurrent (gammel)

- [Tråd 9415: Lurer du på hva din nye nettleie-kostnad blir? (hjemmeautomasjon)](https://www.hjemmeautomasjon.no/forums/topic/9415-lurer-du-på-hva-din-nye-nettleie-kostnad-blir-bruk-denne-kalkulatoren/): Kalkulator på GitHub (https://github.com/salvesen/Ny-nettleie-kalkulator-elhub-data-). Kun Haugaland Kraft, fra 2021, ikke vedlikeholdt.

### Vår egen tråd

- [Strømkalkulator: True electricity cost for Norway (HA community)](https://community.home-assistant.io/t/stromkalkulator-true-electricity-cost-for-norway-all-grid-companies/1000314): brukerne ber om salgsinntekt for plusskunder + Norgespris-sammenligning, netto-kost (forbruk minus eksport), "forbruk-only"-pris uten kapasitetstrinn, strømstøtte parallelt med Norgespris.

## Hva vi har som andre ikke har

- Norgespris-håndtering (50 øre-tak + 5000 kWh-grense + per-DSO sammenligning)
- Alle norske nettselskap dekket og verifisert
- Faktura-verifisert presisjon (0,01–0,02 kr per linje, 6 BKK-måneder)
- Fritidsbolig/hytte med korrekte kWh-tak
- Solcelle-eksport for plusskunder
- Per-DSO `helligdager_ekstra` (jul/nyttår-lavtariff)
- Restart-resilient akkumulering
- Energy Dashboard-kompatibel akkumulert kostnad

## Anbefalte utvidelser

Innenfor scope (data-integrasjon):

1. **Plusskunde-eksportsensorer + Norgespris-sammenligning på salgssiden**. Etterspurt i vår egen HA-tråd.
2. **Netto-kost-sensor** (forbruk minus eksport). Etterspurt. Bygger på 1.
3. **Forbruk-only pris-sensor** (spot + energiledd + avgifter, uten kapasitetstrinn). Lett.
4. **Eksplisitt 15-min Nordpool-støtte**. Mulig regresjon vi må verifisere.
5. **Dokumentert integrasjon med Dynamic Energy Cost**. Pek på det, ikke bygg det selv.
6. **"Beste N timer"-sensor-attributter** med totalpris (inkl. nettleie dag/natt), ikke bare spot.
7. **ENTSO-e fallback** hvis Nordpool ned. Liten innsats.
8. **Solcelle-forecast som valgfri input** (Solcast/Forecast.Solar) for plusskunde-prediksjon.

Utenfor scope (egne prosjekter):

- Prediktiv kapasitetstrinn-styring. Egen integrasjon (Effektvakt) i `~/dev/hacs-effektvakt/`.
- VVB/varmtvann/billader-styring. HA-automasjoner brukeren skriver selv, eller cheapest-hours-blueprintet.
- Batteri-arbitrage. EMHASS sitt domene.
- ApexCharts-kort som integrasjon. Leveres som dokumentert eksempel.

## Posisjon

Vi er den eneste norske "total kr/kWh"-integrasjonen (spot + nettleie + avgifter + Norgespris + plusskunde + DSO-helligdager + fakturaverifisert). Konkurrentene dekker delmengder. Hold scope der, eksporter rene sensorer som blueprint-økosystemet kan konsumere.
