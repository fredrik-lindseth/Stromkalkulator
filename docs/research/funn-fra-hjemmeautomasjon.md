# Funn fra hjemmeautomasjon.no

Oversikt over hva andre i HA-miljøet har bygget for å løse deler av det Strømkalkulator dekker. Brukes som referanse for hvor vi kan utvide og hvor vi bevisst lar være.

Tråder gjennomgått mai 2026.

## Features andre har bygget

### Billigste/dyreste X timer

Mest etterspurte feature i forumet. Brukes til elbil-lading, varmtvannsbereder, varmekabler.

- [Tråd 12474 — Howto: Finn laveste strømpris-timer](https://www.hjemmeautomasjon.no/forums/topic/12474-howto-finn-laveste-strømpris-timer/): Node-RED-flow som henter priser fra hvakosterstrommen.no, finner billigste N timer, eksponerer som globale variabler `lavPris` og `lavLavPris` for styring.
- [Tråd 11669 — Integrere strømpriser fra AMS-leser](https://www.hjemmeautomasjon.no/forums/topic/11669-integrere-strømpriser-fra-amsleser-i-home-assistant/): Brukere ønsker «sensorer for billigste/dyreste x antall timer i visse perioder». Diskusjon om at AMS-lesere og Nordpool sletter historiske data, som gjør «hvor mange billigste timer har bilen ladet hittil i natt»-logikk vanskelig.

**Status hos oss**: Ikke implementert.

### Per-time pris-sensorer

24 (eller 96 etter 15-min-overgangen) separate sensorer for å vise prisen hver time.

- [Tråd 13540 — Template sensor for timespriser nordpool](https://www.hjemmeautomasjon.no/forums/topic/13540-template-sensor-for-timespriser-nordpool/): Brukere lager template-sensorer per time fra Nordpool sine `today`/`tomorrow`-attributter. Trådkommentar peker på at logikken bryter sammen etter at Nord Pool gikk over til 15-min-pricing (24×4 elementer).

**Status hos oss**: Ikke implementert. Vi har kun «current price».

### 15-min Nordpool-pricing

Nord Pool gikk over til kvartersbasert dag-ahead-pricing høsten 2025.

- [Tråd 13363 — 15 minutters interval på strømpris](https://www.hjemmeautomasjon.no/forums/topic/13363-15-minutters-interval-på-strømpris/): Diskusjon rundt overgangen.
- [Tråd 13540 — Template sensor for timespriser nordpool](https://www.hjemmeautomasjon.no/forums/topic/13540-template-sensor-for-timespriser-nordpool/): Kommentar om at eksisterende kode brytes.

**Status hos oss**: Coordinator håndterer current price hvert minutt. Ikke verifisert mot 24×4-elementer i `today`/`tomorrow`-attributter. Mulig regresjon vi ikke har oppdaget.

### Predictive kapasitetstrinn-styring

Aktivt regulere forbrukere (panelovner, billader) for å unngå å overskride neste effekttrinn.

- [Tråd 9253 — Prediktiv reduksjon av strømbruk effektariff-nivå](https://www.hjemmeautomasjon.no/forums/topic/9253-prediktiv-reduksjon-av-strømbruk-effektariff-nivå/): PID-regulator basert på Tibber Pulse 2,5s effektmålinger. Integrerer opp forventet forbruk denne timen, styrer 0–100% utgang som slår av/på forbrukere.

**Status hos oss**: Vi har `kapasitet_varsel` (binær varsel), ikke prediktiv styring. Bevisst utenfor scope: styringslogikk hører hjemme i HA-automasjoner eller egne integrasjoner.

### Styring av forbrukere basert på pris

Slå av VVB, varmeovner, varmekabler i pristopper. Slå på når billig.

- [Tråd 12298 — Styring av varmtvannsbereder med Nordpool og rene HA-automasjoner](https://www.hjemmeautomasjon.no/forums/topic/12298-styring-av-varmtvannsbereder-med-nordpool-og-rene-ha-automasjoner/): Komplett løsning med ESPHome + Dallas temperatur-sensor + smart relé + Generic Thermostat helper. Ren HA-automasjon, ikke Node-RED.
- [Tråd 11282 — Styring av forbruk basert på strømpriser (leverandøruavhengig)](https://www.hjemmeautomasjon.no/forums/topic/11282-styring-av-forbuk-basert-på-strømpriser-leverandøruavhengig/): HomeSeer-plugin (PowerControl) som henter priser fra ENTSO-E, beregner når strømmen bør slås av, tar hensyn til VVB-begrensninger, og slår på forbrukere når strømmen er ekstra billig. Senere versjon legger til strømstøtte-beregning.
- [Tråd 10824 — Flow til styring av VVB etter strømpriser](https://www.hjemmeautomasjon.no/forums/topic/10824-flow-til-styring-av-vvb-etter-strømpriser/)
- [Tråd 10738 — SwitchBot/Home Assistant: styre bryter etter strømpriser](https://www.hjemmeautomasjon.no/forums/topic/10738-switchbot-home-assistant-styre-bryter-etter-strømpriser/)

**Status hos oss**: Bevisst utenfor scope. Vi gir data, ikke styringslogikk.

### Tibber-totalpris (inkl. nettleie og avgifter)

Tibber-integrasjonen viser kun råpris fra strømleverandøren, ikke det brukerne ser i Tibber-appen.

- [Tråd 12029 — Får det an å få prisen fra Tibber med avgifter og nettleie som i Tibber-appen](https://www.hjemmeautomasjon.no/forums/topic/12029-går-det-an-å-få-prisen-fra-tibber-med-avgifter-og-nettleie-som-i-tibber-appen/): Trådstarter spør hvorfor Tibber-integrasjonen mangler dette. Anbefaling: HACS-integrasjonen [home_assistant_tibber_data](https://github.com/Danielhiversen/home_assistant_tibber_data).

**Status hos oss**: Vi har «Total strømpris (strømavtale)»-sensor som kombinerer brukerens strømleverandørpris (valgfri input) med vår nettleie-beregning. Direkte konkurrent til `home_assistant_tibber_data`, men dekker også ikke-Tibber-brukere.

### Fargekodet pris-visualisering

Lovelace-kort som fargekoder strømpris dynamisk basert på dagens min/max/mean.

- [Tråd 12313 — ApexChart med fargekoding for strømpriser og strømforbruk (Nordpool og Tibber)](https://www.hjemmeautomasjon.no/forums/topic/12313-apexchart-med-fargekoding-for-strømpriser-og-strømforbruk-nordpool-og-tibber/): Ferdig ApexChart-config delt i tråden. Fargen i tittelen og linjen på grafen endres basert på prisnivå (nå vs. dagens min/max).
- [Tråd 11352 — Stolpediagram for fremtidige strømpriser](https://www.hjemmeautomasjon.no/forums/topic/11352-stolpediagram-for-fremtidige-strømpriser/)
- [Tråd 12344 — Bruk av AI for å generere YAML kode i HA (eksempel: apex charts for å fargekode billigste og dyreste strømpriser)](https://www.hjemmeautomasjon.no/forums/topic/12344-bruk-av-ai-for-å-generere-yaml-kode-i-ha-eksempel-apex-charts-for-å-fargekode-billigste-og-dyreste-strømpriser/)

**Status hos oss**: Vi gir sensorer, ikke dashboard-eksempler. Mulighet: legge til ferdige Lovelace-kort-eksempler i docs.

### Manuell template-pris-beregning

Brukerne lager template-sensorer som regner ut EUR→NOK + dag/natt-nettleie + mva.

- [Tråd 11102 — Strømpriser](https://www.hjemmeautomasjon.no/forums/topic/11102-strømpriser/): Trådstarter deler template som regner ut EUR→NOK med Nordpool/Entso-e + dag/natt-tariff + mva. Manuelt vedlikehold per bruker, per nettselskap.
- [Tråd 13251 — Nordpool oppsett med nettleie sommer/vinter mm](https://www.hjemmeautomasjon.no/forums/topic/13251-nordpool-oppsett-med-nettleie-sommer-vinter-mm/): Bruker strever med `additional_costs` i Nordpool-integrasjonens YAML for å legge på nettleie.

**Status hos oss**: Vi erstatter dette fullstendig. Hovedgrunnen til å bruke Strømkalkulator i stedet for DIY-template.

### Nettleie-API-tilgang

Brukere som ønsker programmatisk tilgang til nettselskapenes priser.

- [Tråd 9051 — API for nettleie-priser hos Elvia](https://www.hjemmeautomasjon.no/forums/topic/9051-api-for-nettleie-priser-hos-elvia/)
- [Tråd 11108 — API for nettleie-priser hos Lnett](https://www.hjemmeautomasjon.no/forums/topic/11108-api-for-nettleie-priser-hos-lnett/)

**Status hos oss**: Vi har alle nettselskap innebygd i `dso.py`. Brukere trenger ikke å hente API-data selv.

### Direkte konkurrent (gammel)

- [Tråd 9415 — Lurer du på hva din nye nettleie-kostnad blir? Bruk denne kalkulatoren](https://www.hjemmeautomasjon.no/forums/topic/9415-lurer-du-på-hva-din-nye-nettleie-kostnad-blir-bruk-denne-kalkulatoren/): Bruker delte en kalkulator for nettleie på GitHub (https://github.com/salvesen/Ny-nettleie-kalkulator-elhub-data-). Kun Haugaland Kraft, fra 2021, ikke vedlikeholdt etter dette.

## Hva vi har som forumet ikke dekker

- Norgespris-håndtering (50 øre-tak + kWh-grense + per-DSO sammenligning)
- Alle norske nettselskap dekket og verifisert
- Faktura-verifisert presisjon (0,01–0,02 kr per linje, 6 BKK-måneder)
- Fritidsbolig/hytte med korrekte kWh-tak
- Solcelle-eksport for plusskunder
- Per-DSO `helligdager_ekstra` (jul/nyttår-lavtariff)
- Restart-resilient akkumulering
- Energy Dashboard-kompatibel akkumulert kostnad-sensor

## Anbefalinger for utvidelse

Innenfor scope (data-integrasjon):

1. **Billigste/dyreste X timer-sensor** — høy etterspørsel i flere tråder. Binær sensor: «er prisen blant N billigste i dag/i natt». Brukes for å trigge automasjoner uten å bygge Node-RED-flow.
2. **15-min-pricing-håndtering** — verifisere at coordinator håndterer 24×4-elementer fra Nordpool. Mulig regresjon.
3. **Per-time pris-attributter** — eksponere dagens 24 (eller 96) priser som attributt på en sensor i stedet for 24 separate template-sensorer.
4. **Dashboard-eksempler i docs/** — ApexChart-kort med fargekoding, eksempel-automatisjoner for VVB og elbil-lading.

Utenfor scope (egne prosjekter):

5. PID-basert prediktiv kapasitetstrinn-styring.
6. VVB/varmtvann/billader-styringslogikk — disse hører hjemme i HA-automasjoner brukeren skriver selv eller en separat «styring»-integrasjon.
