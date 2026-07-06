# Input-sensorer

Hva integrasjonen trenger fra Home Assistant for å beregne strømkostnad.

## TL;DR

For å treffe fakturaen på øret, anbefales:

- **Effektmåler (W)**: instantan effekt (nødvendig)
- **Energimåler (kWh)**: kumulativ måler (sterkt anbefalt)
- **Spotpris-sensor (NOK/kWh)**: fra Nord Pool eller lignende (nødvendig)

Eksport-effektmåler og strømleverandør-sensor er valgfrie og brukes kun hvis du har solceller eller vil sammenligne med faktisk strømavtale.

## Effektmåler (power_sensor)

**Hva**: Sensor som rapporterer hvor mye strøm du bruker nå, i watt (W). Verdien hopper opp og ned i takt med at apparater slår seg på og av.

**Hvor finner du den**: Vanligvis fra AMS-måleren via HAN-porten. Typiske kilder:

- Pow-U / AMSleser.no
- Tibber Pulse
- ESPHome med P1-leser
- Hjemme Pulse

Sensoren heter ofte noe som `sensor.<noe>_power` eller `sensor.<noe>_p` og har enhet `W`.

**Hvorfor brukes den**: For å beregne kapasitetstrinn (toppforbruk per time), spotpris-kostnad i sanntid, og for å estimere månedsforbruk hvis du ikke har en energimåler-sensor.

**Krav**: Bør oppdatere hvert 2-10 sekund. Sensorer som kun oppdateres hvert minutt mister detaljer rundt korte forbruksspisser.

## Energimåler (energy_sensor)

**Hva**: Kumulativ teller som viser totalt antall kWh siden måleren ble installert. Tallet går bare oppover. Dette er den samme verdien som leses av nettselskapet ved fakturering.

**Hvor finner du den**: Fra samme AMS-leser som effektmåleren. Sensoren heter ofte noe som:

- `sensor.<noe>_active_energy_import`
- `sensor.<noe>_total_consumption`
- `sensor.<noe>_last_meter_consumption` (Tibber)
- `sensor.<noe>_tpi` (Pow-U)

Enheten er `kWh` og verdien er stor (typisk over 1000 kWh) og stiger sakte.

**Hvorfor anbefales den**: Gir eksakt forbruk i hver måned, identisk med fakturaen. Forskjellen forklares under «Riemann-summering vs delta-akkumulering» lenger ned.

## OBIS-koder forklart

OBIS = Object Identification System. Det er en standardisert måte å identifisere måleverdier på elektrisitetsmålere over hele Europa.

Du trenger ikke å vite kodene utenat, men det hjelper å gjenkjenne dem:

| OBIS-kode | Hva det er                          | Sensor-type               |
| --------- | ----------------------------------- | ------------------------- |
| 1.7.0     | Aktiv effekt inn nå                 | Effektmåler (W)           |
| 1.8.0     | Aktiv energi inn (kumulativ)        | Energimåler (kWh)         |
| 2.7.0     | Aktiv effekt ut nå (eksport)        | Eksport-effektmåler (W)   |
| 2.8.0     | Aktiv energi ut (kumulativ eksport) | Eksport-energimåler (kWh) |

Når dokumentasjonen sier «OBIS 1.8.0», menes altså bare «kumulativ kWh-teller».

## Spotpris-sensor (spot_price_sensor)

**Hva**: Sensor som viser gjeldende spotpris fra Nord Pool i NOK/kWh.

**Hvor finner du den**: Den offisielle Nord Pool-integrasjonen i Home Assistant gir en `Current price`-sensor. Custom-integrasjonen `custom_components/nordpool` (eldre) gir også en lignende sensor.

**Format**: NOK per kWh, ikke kr/MWh. Hvis sensoren din viser tall som 850 (kr/MWh), må du dele på 1000 for å få NOK/kWh.

**Mva-håndtering**: Se egen seksjon under.

## Strømleverandør-sensor (electricity_provider_price_sensor, valgfri)

**Hva**: Hvis du bruker Tibber eller lignende, har du gjerne en sensor som viser totalprisen du faktisk betaler, inkludert påslag og avgifter.

**Hvor finner du den**: Tibber-integrasjonen gir en `Electricity price`-sensor med totalpris.

**Hvorfor valgfri**: Spotpris-sensoren gir grunnlaget for alle beregninger. Strømleverandør-sensoren brukes bare for å vise «hva du faktisk betaler» i sensoren «Total strømpris (strømavtale)».

## Eksport-effektmåler (export_power_sensor, valgfri)

**Hva**: For plusskunder med solceller. Sensor som viser hvor mye effekt du eksporterer til nettet akkurat nå (W).

**Hvor finner du den**: Samme AMS-leser som effektmåleren, men en annen sensor (OBIS 2.7.0).

**Hvorfor**: Brukes til å beregne inntekt fra salg av strøm til nettet.

## Riemann-summering vs delta-akkumulering (forklart enkelt)

Tenk på effektmåleren (W) som speedometer i bilen. Den viser hvor fort du går nå.

Tenk på energimåleren (kWh) som tripteller. Den viser totalt antall kWh siden den ble nullstilt.

Integrasjonen kan regne ut totalt forbruk på to måter:

**Riemann-summering (når energi-sensor mangler):** Les speedometeret hvert minutt, regn ut «hvor langt har jeg kjørt i dette minuttet» som hastighet × tid. Summer over en hel måned.

Problem: hvis du leser speedometeret midt under en akselerasjon, får du for høyt estimat for forrige minutt. Hvis du leser mens du står stille, men brukte mye effekt for 2 sekunder før, mister du forbruk.

Over en hel måned: summeringen kan avvike fra «ekte» forbruk med flere prosent. Avviket er typisk størst hvis du har mye av/på-utstyr (varmtvannsbereder, induksjonstopp, varmepumpe i defrost).

**Delta-akkumulering (når energi-sensor er konfigurert):** Les triptelleren ved start og slutt av måneden. Differansen er eksakt forbruk. Ingen estimering, ingen avrundingsfeil.

For integrasjonen: konfigurer `energy_sensor`, så bruker den triptelleren (eksakt). Uten `energy_sensor`: integrasjonen leser bare speedometeret (estimat).

## Hvilke sensorer trenger jeg?

### Minimumsoppsett (ikke optimalt, men fungerer)

- Effektmåler (W)
- Spotpris-sensor (NOK/kWh)

Forbruk akkumuleres via Riemann-summering. Kan avvike fra faktura med 1-5 %.

### Anbefalt oppsett (treffer fakturaen)

- Effektmåler (W) for instantan effekt og kapasitetstrinn
- Energimåler (kWh) for eksakt månedsforbruk via delta-akkumulering
- Spotpris-sensor (NOK/kWh)

Kombinerer det beste av begge: instantan effekt for kapasitetstrinn-beregning, eksakt forbruk fra meter-register.

### Plusskunde med solceller

Legg til:

- Eksport-effektmåler (W) for solcelleeksport

### Hvis du bruker Tibber

Legg til:

- Strømleverandør-sensor for å vise hva du faktisk betaler (Tibber-pris kan inkludere påslag og månedsavgift)

## Vanlige AMS-lesere og deres sensorer

### Pow-U / AMSleser.no

| Sensor                 | Bruk                             |
| ---------------------- | -------------------------------- |
| `sensor.pow_u_ams_p`   | Effektmåler (W)                  |
| `sensor.pow_u_ams_tpi` | Energimåler (kWh, OBIS 1.8.0)    |
| `sensor.pow_u_ams_tpo` | Eksport-energi (kWh, OBIS 2.8.0) |

Eksakte navn varierer med konfigurasjon. Sjekk dine sensorer under Innstillinger > Enheter og tjenester.

### Tibber Pulse

| Sensor                                 | Bruk              |
| -------------------------------------- | ----------------- |
| `sensor.<name>_power`                  | Effektmåler (W)   |
| `sensor.<name>_last_meter_consumption` | Energimåler (kWh) |

### ESPHome AMS-leser

Avhenger av firmware. Vanlige prosjekter er `esphome-han-port` og `AMS2MQTT`. Se prosjektets egen dokumentasjon.

### Hjemme Pulse / amsreader

Tilsvarende oppsett. Effekt og energi eksponeres som separate sensorer.

## Hvorfor 'eks. mva' for spotpris-sensor?

Nord Pool publiserer spotpriser eks. mva. HAs offisielle nordpool-integrasjon leverer eks. mva. Integrasjonen forventer dette og legger på mva selv basert på avgiftssone (25 % i Sør-Norge, 0 % i Nord-Norge).

Hvis sensoren din allerede leverer inkl. mva (f.eks. eldre `custom_components/nordpool` med VAT=true, eller manuell template-sensor som legger på 25 %), kryss av «Spotpris-sensor leverer priser inkl. mva» i konfigurasjonen.

Verifiser ved å sammenligne med Nord Pool sin nettside (som viser eks. mva).

## Feilsøking

### Forbruks-totaler matcher ikke fakturaen

1. Sjekk at `energy_sensor` er konfigurert (anbefales)
2. Hvis ikke: forskjell på 1-5 % er forventet pga Riemann-summering
3. Sjekk at HA ikke har vært nede over lengre tid (forbruk i nedetid mistes)
4. Sjekk at `power_sensor` faktisk publiserer hvert 2-3 sekund

### Spotpris virker feil

1. Sjekk at sensoren leverer NOK/kWh, ikke kr/MWh eller annet
2. Sjekk om sensoren har mva inkludert eller ikke
3. Sammenlign med Nord Pool sin nettside

### Kapasitetstrinn-beregning ser rar ut

1. Bruker integrasjonen `power_sensor` (W) til dette, ikke `energy_sensor`
2. Sjekk at effektmåleren oppdaterer ofte nok (helst hvert 2-3 sekund)
3. Sjekk at det er den riktige sensoren som er valgt (HAN-port, ikke f.eks. enkeltapparat)
