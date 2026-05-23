# Klokke-kilde og tidsstempling i AMS-målere

Oppfølging av spørsmål fra samtale med Håkon om GPS-tid og 10-sekunders-broadcast-forsinkelsen.

> Status: 2026-05-23. Konklusjoner basert på Aidons egen spec, DLMS-standarden, Elhub-dokumentasjon og NIST-data.

## Spørsmålene

1. Hvor får Aidon-måleren klokken fra?
2. Er Håkons GPS-tid-poeng relevant (18 sek vs UTC)?
3. Kan vi shifte vår tpi-data for å lukke 9 Wh-gapet?
4. Hva med M-Bus direkte eller firmware-dump som alternativ?

## Klokke-kilde i Aidon-måleren

| Aspekt          | Verdi                                                 | Kilde                     |
| --------------- | ----------------------------------------------------- | ------------------------- |
| Klokkekilde     | Intern RTC, typisk 32 kHz krystall                    | DLMS standard, Aidon-spec |
| Sync-protokoll  | DLMS clock_base, SET fra head-end over WAN            | Gurux DLMS                |
| Head-end        | Gridspertise Gateware (tidligere Aidon NIS)           | Gridspertise PR           |
| Sync-frekvens   | Ikke offentlig dokumentert, bransjepraksis timer/døgn | Antagelse                 |
| Elhub-toleranse | 7 sekunder maks drift                                 | Elhub validering V004     |
| GPS-mottager    | **Nei**, ingen GPS i Aidon 6534                       | Aidon hardware-spec       |
| NITZ via 4G     | Mulig tilleggskilde, operatøravhengig                 | 3GPP                      |

DLMS class_id 8 (Clock-objektet) som måleren broadcaster på OBIS 0-0:1.0.0 har et `clock_base`-felt med enum-verdier NONE / CRYSTAL / MAINS_50 / MAINS_60 / GPS / RADIO. For AMS-målere i Norden er kilden CRYSTAL.

## Håkons GPS-tid-poeng

**Bekreftet faktum, men ikke relevant for vårt avvik:**

- GPS-tid er 18 sekunder foran UTC per 2026
- Siste leap second var 31.12.2016, ingen er lagt til siden
- CGPM-vedtak 2022: stopp leap seconds innen 2035

Hvis Aidon brukte rå GPS-tid uten leap-justering, ville broadcast-tidspunktet vist 18 sek diff. Vi observerer 10 sek. Aidon bruker intern krystall + sync mot Gridspertise, ikke GPS.

## 10-sekunders-stemplingen er DESIGN

Aidon RJ45 HAN Interface v1.6 punkt M:

> "List 3 ... The values are generated at XX:00:00 and streamed out from the HAN interface 10 second later (XX:00:10)"

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

RJ45 HAN-porten **er** M-Bus elektrisk. Ingen separat M-Bus-kontakt på Aidon 65xx. Listene er like uansett tolkning. Samme DLMS-objekter, samme broadcast-timing, samme 10-sek-stempling.

## Firmware-dump er teoretisk mulig men upraktisk

- Ingen offentlig reverse-engineering av Aidon 65xx eksisterer
- Aidon bruker sannsynligvis Cortex-M med TrustZone, secure boot og signert/kryptert firmware
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

## Konklusjon

9 Wh-gapet over en hel måned er ren sample-presisjon fra at HAN-broadcasten kommer 10 sek etter måleverdien låses. Vi har bekreftet eksplisitt at:

- Aidon låser verdier ved HH:00:00 og sender HAN-broadcast 10 sek senere (innebygget design)
- Klokken er intern krystall, ikke GPS
- Elhub-toleransen er 7 sek (vi er innenfor)
- Det finnes ingen sniksvei via M-Bus eller firmware-dump

For praktiske formål (fakturakontroll) er 9 Wh ubetydelig. Hvis 0 Wh-gap er ønsket, krever det interpolering via `p`-strømmen mellom HH:00:00 og HH:00:13.

## Kilder

- [Aidon RJ45 HAN Interface v1.6 (lokal)](specifications/aidon-rj45-han-interface-v1.6-EN.pdf) — punkt M, side 8
- [Elhub validering V004 Tidsstempling](https://dok.elhub.no/e27/4-0-krav-til-validering)
- [Gurux DLMS Clock class](https://www.gurux.fi/Gurux.DLMS.Objects.GXDLMSClock)
- [NIST – leap seconds, GPS-UTC = 18 s siden 2017](https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds)
- [Justervesenet om plombering](https://www.justervesenet.no/en/surveillance/sealing/)
- [Forskrift om målenheter og måling](https://lovdata.no/dokument/SF/forskrift/2007-12-20-1723)
- [Gridspertise oppkjøp av Aidon (2023)](https://aidon.com/gridspertise-s-r-l-acquires-leading-nordic-smart-grid-solution-provider-aidon-oy/)
