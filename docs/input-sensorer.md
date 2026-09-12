# Input-sensorer

Hva integrasjonen trenger fra Home Assistant for å beregne strømkostnad.

## Kort fortalt

Integrasjonen trenger en effektmåler (W) for instantan effekt og en spotpris-sensor (NOK/kWh) fra Nord Pool eller lignende. En energimåler (kWh) er ikke påkrevd, men uten den estimeres forbruket, så skal du treffe fakturaen på øret bør du ha den.

Eksport-effektmåler og strømleverandør-sensor er valgfrie og brukes kun hvis du har solceller eller vil sammenligne med faktisk strømavtale.

## Effektmåler (power_sensor)

Sensoren rapporterer hvor mye strøm du bruker nå, i watt (W). Verdien hopper opp og ned i takt med at apparater slår seg på og av.

Den kommer vanligvis fra AMS-måleren via HAN-porten. Typiske kilder:

- Pow-U / AMSleser.no
- Tibber Pulse
- ESPHome med P1-leser
- Hjemme Pulse

Sensoren heter ofte noe som `sensor.<noe>_power` eller `sensor.<noe>_p` og har enhet `W`.

Integrasjonen bruker den til kapasitetstrinn (toppforbruk per time), til spotpris-kostnad i sanntid, og til å estimere månedsforbruk hvis du ikke har en energimåler-sensor.

Den bør oppdatere hvert 2-10 sekund. Sensorer som kun oppdateres hvert minutt mister detaljer rundt korte forbruksspisser.

## Energimåler (energy_sensor)

Dette er en kumulativ teller som viser totalt antall kWh siden måleren ble installert. Tallet går bare oppover, og det er den samme verdien nettselskapet leser av ved fakturering.

Den kommer fra samme AMS-leser som effektmåleren. Sensoren heter ofte noe som:

- `sensor.<noe>_active_energy_import`
- `sensor.<noe>_total_consumption`
- `sensor.<noe>_last_meter_consumption` (Tibber)
- `sensor.<noe>_tpi` (Pow-U)

Enheten er `kWh` og verdien er stor (typisk over 1000 kWh) og stiger sakte.

Den gir eksakt forbruk i hver måned, identisk med fakturaen. Forskjellen forklares under «Riemann-summering vs delta-akkumulering» lenger ned.

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

Sensoren viser gjeldende spotpris fra Nord Pool i NOK/kWh. Den offisielle Nord Pool-integrasjonen i Home Assistant gir en `Current price`-sensor, og den eldre custom-integrasjonen `custom_components/nordpool` gir en lignende.

Formatet skal være NOK per kWh, ikke kr/MWh. Viser sensoren din tall som 850 (kr/MWh), må du dele på 1000.

Mva er en sak for seg, se egen seksjon under.

## Strømleverandør-sensor (electricity_provider_price_sensor, valgfri)

Bruker du Tibber eller lignende, har du gjerne en sensor som viser totalprisen du faktisk betaler, inkludert påslag og avgifter. Tibber-integrasjonen gir en `Electricity price`-sensor med totalpris.

Den er valgfri fordi spotpris-sensoren gir grunnlaget for alle beregninger. Strømleverandør-sensoren brukes bare for å vise «hva du faktisk betaler» i sensoren «Total strømpris (strømavtale)».

## Eksport-effektmåler (export_power_sensor, valgfri)

For plusskunder med solceller. Sensoren viser hvor mye effekt du eksporterer til nettet akkurat nå (W), og kommer fra samme AMS-leser som effektmåleren, men som en annen sensor (OBIS 2.7.0). Integrasjonen bruker den til å beregne inntekt fra salg av strøm til nettet.

## Riemann-summering vs delta-akkumulering

Tenk på effektmåleren (W) som speedometeret i bilen. Den viser hvor fort du går nå.

Tenk på energimåleren (kWh) som triptelleren. Den viser totalt antall kWh siden den ble nullstilt.

Integrasjonen kan regne ut totalt forbruk på to måter:

Riemann-summering brukes når energi-sensoren mangler: les speedometeret hvert minutt, regn ut «hvor langt har jeg kjørt i dette minuttet» som hastighet × tid. Summer over en hel måned.

Problem: hvis du leser speedometeret midt under en akselerasjon, får du for høyt estimat for forrige minutt. Hvis du leser mens du står stille, men brukte mye effekt for 2 sekunder siden, mister du forbruk.

Over en hel måned: summeringen kan avvike fra «ekte» forbruk med flere prosent. Avviket er typisk størst hvis du har mye av/på-utstyr (varmtvannsbereder, induksjonstopp, varmepumpe i defrost).

Delta-akkumulering brukes når energi-sensoren er konfigurert: les triptelleren ved start og slutt av måneden. Differansen er eksakt forbruk. Ingen estimering, ingen avrundingsfeil.

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

Effektmåleren gir kapasitetstrinn-beregningen, energimåleren gir eksakt forbruk fra meter-registeret.

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

## Hvorfor «eks. mva» for spotpris-sensor?

Nord Pool publiserer spotpriser eks. mva. HAs offisielle nordpool-integrasjon leverer eks. mva. Integrasjonen forventer dette og legger på mva selv basert på avgiftssone (25 % i Sør-Norge, 0 % i Nord-Norge).

Hvis sensoren din allerede leverer inkl. mva (f.eks. eldre `custom_components/nordpool` med VAT=true, eller manuell template-sensor som legger på 25 %), kryss av «Spotpris-sensor leverer priser inkl. mva» i konfigurasjonen.

Verifiser ved å sammenligne med Nord Pool sin nettside (som viser eks. mva).

## Når en input dør

Integrasjonen regner bare på det sensorene forteller. Dør en av dem, stopper
tallene uten å se feil ut, og det er verre enn en åpenbar feilmelding. Sommeren
2026 lå HAN-leseren nede i 237 timer i strekk, og det ble oppdaget ti dager for
sent, da fakturaen skulle verifiseres. Derfor står det nå et vakthold på
inputene.

Vaktholdet ser etter tre ting:

| Situasjon                                               | Hva som skjer                                            |
| ------------------------------------------------------- | -------------------------------------------------------- |
| Entiteten er `unavailable` eller `unknown` over 30 min  | Måledata-problem slår på, og du får et reparasjonsvarsel |
| Energitelleren rapporterer, men øker ikke på tre timer  | Samme, med typen «frossen»                               |
| Spotprisen har vært borte lenger enn cachen på to timer | Samme, med typen «spot_utlopt»                           |

Du ser det på `binary_sensor`-en «Måledata-problem» og under Innstillinger >
Reparasjoner. Varslene forsvinner av seg selv når inputen er tilbake.
Integrasjonen sender ikke varsler selv; bygg en automasjon på binary_sensoren
hvis du vil ha push.

Tretimersgrensen for frossen teller er justerbar under Configure (1 til 48
timer). Hev den på en hytte eller et anlegg som står uten forbruk i perioder,
ellers varsler den hver gang hovedbryteren er av.

Hva som skjer med tallene mens en input er nede:

- Effektmåler nede: døgnmaks og dermed kapasitetstrinnet blir for lavt.
  Timene i hullet finnes ikke.
- Energimåler nede: månedsforbruket blir for lavt. Når måleren kommer
  tilbake, kan hele hullet komme som ett sprang. Er spranget over 100 kWh,
  forkastes det, og du får et eget varsel med tallet, siden et sprang like
  gjerne kan være et målerbytte som ekte forbruk.
- Spotpris nede: kWh telles videre, men kostnad, strømstøtte og
  Norgespris-sammenligning fryser når cachen på to timer er tom.
- Strømleverandør-sensor nede: bare sammenligningssensoren «Total strømpris
  (strømavtale)» blir borte. Ingen alarm, bare et attributt.

## Feilsøking

### Forbruks-totaler matcher ikke fakturaen

1. Sjekk at `energy_sensor` er konfigurert (anbefales)
2. Hvis ikke: forskjell på 1-5 % er forventet på grunn av Riemann-summering
3. Sjekk at HA ikke har vært nede over lengre tid (forbruk i nedetid mistes)
4. Sjekk at `power_sensor` faktisk publiserer hvert 2-3 sekund

### Spotpris virker feil

1. Sjekk at sensoren leverer NOK/kWh, ikke kr/MWh eller annet
2. Sjekk om sensoren har mva inkludert eller ikke
3. Sammenlign med Nord Pool sin nettside

### Kapasitetstrinn-beregning ser rar ut

1. Integrasjonen bruker `power_sensor` (W) til dette, ikke `energy_sensor`
2. Sjekk at effektmåleren oppdaterer ofte nok (helst hvert 2-3 sekund)
3. Sjekk at det er den riktige sensoren som er valgt (HAN-port, ikke f.eks. enkeltapparat)
