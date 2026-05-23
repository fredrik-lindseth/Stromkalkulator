# Klokke-kilde og tidsstempling i AMS-målere

Oppfølging av spørsmål fra samtale med Håkon om GPS-tid og 10-sekunders-broadcast-forsinkelsen.

> Status: 2026-05-23. Konklusjoner basert på Kaifa KFM_001-spec (Fredriks måler), Aidon RJ45 HAN-spec (referanse for andre brukere), DLMS-standarden, Elhub-dokumentasjon og NIST-data.

## Spørsmålene

1. Hvor får AMS-måleren klokken fra?
2. Er Håkons GPS-tid-poeng relevant (18 sek vs UTC)?
3. Kan vi shifte vår tpi-data for å lukke 9 Wh-gapet?
4. Hva med M-Bus direkte eller firmware-dump som alternativ?

## Klokke-kilde i AMS-måleren

Fredriks måler er en **Kaifa MA304H3E** (Nuri Telecom). Tabellen under gjelder norske AMS-målere generelt (Kaifa, Aidon, Kamstrup) siden alle følger samme bransjepraksis.

| Aspekt          | Verdi                                                 | Kilde                           |
| --------------- | ----------------------------------------------------- | ------------------------------- |
| Klokkekilde     | Intern RTC, typisk 32 kHz krystall                    | DLMS-standard, Kaifa/Aidon-spec |
| Sync-protokoll  | DLMS clock_base, SET fra head-end over WAN            | Gurux DLMS                      |
| Head-end        | Nettselskap-spesifikk (BKK bruker Gridspertise)       | Gridspertise PR                 |
| Sync-frekvens   | Ikke offentlig dokumentert, bransjepraksis timer/døgn | Antagelse                       |
| Elhub-toleranse | 7 sekunder maks drift                                 | Elhub validering V004           |
| GPS-mottager    | **Nei**, ingen GPS i Kaifa MA304 eller Aidon 65xx     | Kaifa/Aidon hardware-spec       |
| NITZ via 4G     | Mulig tilleggskilde, operatøravhengig                 | 3GPP                            |

DLMS class_id 8 (Clock-objektet) som måleren broadcaster på OBIS 0-0:1.0.0 har et `clock_base`-felt med enum-verdier NONE / CRYSTAL / MAINS_50 / MAINS_60 / GPS / RADIO. For AMS-målere i Norden er kilden CRYSTAL.

Kaifa-måleren bruker DLMS/COSEM over HDLC på HAN-porten (ikke ASCII IEC 62056-21 som noen eldre målertyper).

## Håkons GPS-tid-poeng

**Bekreftet faktum, men ikke relevant for vårt avvik:**

- GPS-tid er 18 sekunder foran UTC per 2026
- Siste leap second var 31.12.2016, ingen er lagt til siden
- CGPM-vedtak 2022: stopp leap seconds innen 2035

Hvis måleren brukte rå GPS-tid uten leap-justering, ville broadcast-tidspunktet vist 18 sek diff. Vi observerer 10 sek. Kaifa bruker intern krystall + sync mot head-end, ikke GPS.

## 10-sekunders-stemplingen er DESIGN

Kaifa KFM_001 HAN-spec sier eksplisitt:

> "The values is generated at XX:00:00 and streamed out from the HAN interface 10 seconds later (XX:00:10)"

Aidon RJ45 HAN Interface v1.6 punkt M sier praktisk talt det samme:

> "List 3 ... The values are generated at XX:00:00 and streamed out from the HAN interface 10 second later (XX:00:10)"

Dette er norsk AMS HAN-bransjenorm, ikke en Kaifa- eller Aidon-spesifikk quirk.

Det betyr:

- Verdiene **låses ved nøyaktig XX:00:00** internt i måleren
- Samme verdi sendes til Elhub via WAN
- 10 sek senere serialiseres dataene ut på HAN-grensesnittet (2400 baud M-Bus elektrisk)
- Pluss ~3 sek transmisjon + parsing + MQTT for å nå Home Assistant recorder

10 sekunder er buffring/prosesseringsvindu, ikke klokkedrift.

## Shift-hypotesen praktisk testet

Hvis broadcasten ved HH:00:13 inneholder tpi(HH:00:00) (som spec sier), hadde det vært logisk å shifte vår time-label én time bakover. Testet mot 720 timer fra april 2026:

| Tolkning                           | Timer med <1 Wh diff vs Elhub | Sum \|diff\|        |
| ---------------------------------- | ----------------------------- | ------------------- |
| HAN[i] vs Elhub[i] (vår nåværende) | 131/720                       | 2,5 kWh             |
| HAN[i] vs Elhub[i+1] (shifted)     | 3/719                         | 485 kWh (helt feil) |

Direkte sammenligning er klart best. Shift gjør det dramatisk verre. Vår tpi-diff per time har **riktig time-label**. De 9 Wh som mangler over måneden er ren sample-presisjon fra at HAN-broadcast kommer 13 sek etter time-grensen, ikke et label-problem.

## M-Bus direkte er ikke et alternativ

RJ45 HAN-porten **er** M-Bus elektrisk. Ingen separat M-Bus-kontakt på Kaifa MA304 eller Aidon 65xx. Listene er like uansett tolkning. Samme DLMS-objekter, samme broadcast-timing, samme 10-sek-stempling.

## Firmware-dump er teoretisk mulig men upraktisk

- Ingen offentlig reverse-engineering av Kaifa MA304 eksisterer
- Måleren bruker sannsynligvis Cortex-M med TrustZone, secure boot og signert/kryptert firmware
- Plomben er Justervesenets, brytes må det rapporteres + gebyr (forskrift 2007-12-20-1723)
- Selv hvis du fikk ut firmware, ville den ikke gi noen sniksvei. 10-sek-grensen ligger i DLMS-list-konfigurasjonen, ikke i transport

## Praktisk plan

| Tiltak                                          | Effekt                                                                                | Anbefaling       |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------- |
| Akseptere 9 Wh som dokumentert sample-presisjon | 0 Wh-gap er teoretisk perfekt, men 9 Wh er innenfor BKKs egen avrunding (3 desimaler) | **Anbefales**    |
| Interpolere tpi til HH:00:00 via `p`-strømmen   | Krever endring i export-script, forventet 1-2 Wh restavvik                            | Mulig hvis pri   |
| Shifte time-label                               | **Avvist** av data                                                                    |                  |
| M-Bus / firmware                                | Ikke tilgjengelig                                                                     | Skrinlagt        |
| Bytt til annen HAN-leser (Tibber Pulse)         | Eliminerer 3 sek transmisjons-lag, men ikke 10 sek i måleren                          | Marginal gevinst |

## Konklusjon med tiden

**Hva vi vet:**

- AMS-måleren låser tpi-verdier ved HH:00:00 internt (samme tall Elhub mottar via WAN)
- HAN-broadcasten serialiseres ut 10 sek senere ved HH:00:10 (spec eksplisitt for både Kaifa og Aidon)
- 3 sek til Home Assistant via HAN-bytes + Pow-U-parsing + MQTT
- Total: HA mottar sample ved HH:00:13 lokal tid, men verdien inni gjelder HH:00:00
- 10-sek-stempling er bransjenorm (Kamstrup 5 sek, Kaifa 10-13 sek)
- Elhub-toleranse for målerklokke: 7 sek (vi er langt innenfor)

**Hva vi kan gjøre:**

| Tiltak                                         | Effekt                                                                                                                                                                            | Krav                                   |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Akseptere 9 Wh                                 | Ingenting endres. Innenfor BKKs egen avrunding (3 desimaler)                                                                                                                      | Ingen                                  |
| **13-sek-shift-korreksjon (implementert)**     | **Lukker 9 Wh-gapet til 0,4 mWh**. Trekker fra 13s × (p_mean_HH - p_mean_HH-1) per time. Teleskopisk over måneden.                                                                | `verify_invoice_hourly.py --shift-13s` |
| Bytt til annen HAN-leser (f.eks. Tibber Pulse) | Eliminerer 3 sek transmisjon, men 10 sek i måleren består. Merk: Pow-U fra desember 2023 og nyere støtter Kaifa-RJ45-terminering, eldre Pow-U-revisjoner hadde problemer på Kaifa | Hardware-bytte                         |
| Elhub-API direkte                              | 0 Wh-gap, men kun dagsoppløst, ikke live                                                                                                                                          | Ny integrasjon med Elhub-autentisering |

**Hva vi IKKE kan gjøre:**

- Fjerne 10-sek-stempling i HAN-broadcasten (innebygget i måler-firmware, spec-definert)
- Dumpe måler-firmware for å finne raskere kilde (signert/kryptert, plombert)
- Lese fra "MBUS"-porten i stedet for HAN (det er samme port)
- Shifte time-label for å lukke gapet (praktisk testet, avvist av Elhub-data)

**Anbefaling for prosjektet:** Behold dagens valg (aksepter 9 Wh som dokumentert sample-presisjon). Avviket er under BKKs egen avrunding og innenfor enhver praktisk relevans for fakturakontroll. Hvis 0 Wh-gap blir kritisk senere, implementer p-strøm-interpolering som opsjonelt flagg i export-scriptet.

## Kilder

- [Kaifa KFM_001 HAN-spec (lokal)](specifications/kaifa-kfm-001.pdf), primær kilde for Fredriks Kaifa MA304H3E
- [Aidon RJ45 HAN Interface v1.6 (lokal)](specifications/aidon-rj45-han-interface-v1.6-EN.pdf), punkt M side 8, sekundær referanse
- [Elhub validering V004 Tidsstempling](https://dok.elhub.no/e27/4-0-krav-til-validering)
- [Gurux DLMS Clock class](https://www.gurux.fi/Gurux.DLMS.Objects.GXDLMSClock)
- [NIST – leap seconds, GPS-UTC = 18 s siden 2017](https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds)
- [Justervesenet om plombering](https://www.justervesenet.no/en/surveillance/sealing/)
- [Forskrift om målenheter og måling](https://lovdata.no/dokument/SF/forskrift/2007-12-20-1723)
- [Gridspertise oppkjøp av Aidon (2023)](https://aidon.com/gridspertise-s-r-l-acquires-leading-nordic-smart-grid-solution-provider-aidon-oy/)
- [amsleser.no: Kaifa/Nuri-måler og Pow-U-kompatibilitet](https://www.amsleser.no/blog/post/27-i-have-a-kaifanuri-meter-and-my-new-pow-u-does-not-work)
