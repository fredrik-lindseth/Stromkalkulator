# Måler-hardware og datakjede

Hvordan strøm-data flyter fra måleren i sikringsskapet til BKKs faktura, og til vårt validerings-script. Hva vi vet, hva vi gjetter.

> Status per 2026-05-23: Førsteutkast basert på empiriske observasjoner i eget oppsett (Kaifa MA304H3E + Pow-U + HA). Punkter merket «**Antagelse**» må bekreftes mot offisielle manualer eller leverandør.

## Kjeden i ett bilde

```
[AMS-måler i sikringsskap]
  (Kaifa / Aidon / Kamstrup)
        │
        ├── HAN-port (kontinuerlig) ────────► [Pow-U lest av AMSleser.no]
        │   list1 hvert ~2,5 s: p, V, I              │
        │   list3 hver time:    tpi, peaks         MQTT
        │                                            │
        │                                            ▼
        │                                  [Home Assistant recorder]
        │                                            │
        │                                  hourly statistics
        │                                            │
        │                                            ▼
        │                                  [vårt validerings-script]
        │
        └── DLMS over PLC/GPRS (per time) ──► [Elhub]
                                                     │
                                                     ▼
                                                  [BKK]
                                                     │
                                                     ▼
                                                [Faktura]
```

## TPI: Total Power In

TPI = **Total Power In**, akronym fra M-Bus/IEC 62056. OBIS-kode `1-0:1.8.0` = "Sum Active Energy Imported".

- Kumulativ kWh-teller i selve måleren
- Monoton voksende (nullstilles kun ved meterbytte)
- Oppløsning: 0,001 kWh = 1 Wh i HAN-output (Antagelse: høyere internt)
- **Samme register som BKK avleser for fakturering**

Forbruk per time = `tpi[HH+1] - tpi[HH]`.

## AMS-måler-merker i Norge

Norge har tre dominerende AMS-måler-merker. Alle bruker samme NEK HAN-spec, men med forskjellig fysisk port-layout og protokoll på HAN.

| Merke    | Modeller                                      | Protokoll på HAN     | HAN-port                     | M-Bus slave-port | DSO-er                                                            |
| -------- | --------------------------------------------- | -------------------- | ---------------------------- | ---------------- | ----------------------------------------------------------------- |
| Aidon    | 6515, 6525, 6534, 6540, 6550, 7-serien        | IEC 62056-21 ASCII   | RJ45, dobbeltmerket HAN/MBUS | Nei              | Aidon-deler av BKK, Elvia, Glitre, Lnett, Lyse, Skagerak, Eidsiva |
| Kaifa    | MA105H2E, MA304H3E, MA304H4, MA304T3, MA304T4 | DLMS/COSEM over HDLC | RJ12 (eller RJ45)            | Ja, egen port    | Kaifa-deler av BKK (SORIA), Glitre, mindre nettselskaper          |
| Kamstrup | Omnipower                                     | DLMS/COSEM           | RJ45 (HAN-NVE)               | Modellavhengig   | Glitre, deler av Aidon-DSO-er                                     |

**SORIA-alliansen:** 27 nettselskaper fra Haugaland til Varanger gjorde felles innkjøp av 700 000 målere fra Nuri Telecom (Kaifa). BKK var program-manager. Det betyr at BKK NO5 har både Aidon og Kaifa i feltet, ofte i samme nettområde.

### HAN-broadcast-timing

Alle tre merker sender list1/list2 raskt og list3 (timesverdier) like etter time-grensen. Sitatene i spec-ene er nesten ordrette. Tallene her er kun selve målerens broadcast-tid på HAN-port, ikke ende-til-ende-forsinkelse til HA recorder.

| Merke            | List 3 broadcast | Kilde                                                                                                  |
| ---------------- | ---------------- | ------------------------------------------------------------------------------------------------------ |
| Aidon            | HH:00:10         | [`aidon-rj45-han-interface-v1.6-EN.pdf`](research/specifications/aidon-rj45-han-interface-v1.6-EN.pdf) |
| Kaifa            | HH:00:10         | [`kaifa-kfm-001.pdf`](research/specifications/kaifa-kfm-001.pdf)                                       |
| Kamstrup HAN-NVE | HH:00:05         | [`kamstrup-han-nve-rev3.1.pdf`](research/specifications/kamstrup-han-nve-rev3.1.pdf)                   |

Aidon og Kaifa har identisk timing. Begge spec-ene formulerer det som "values generated at XX:00:00 and streamed out from HAN interface 10 seconds later (XX:00:10)". Det er et bevisst designvalg, ikke et IEC-krav. IEC 62056-21-spesifikasjonen sier ingenting om timing av kumulative timesverdier.

### Ende-til-ende-forsinkelse til HA recorder

HA-mottakstid = meter-broadcast + transmisjons-tid gjennom HAN-leseren. Transmisjon dekker fysisk HAN-overføring, parsing i leseren og MQTT-publish (eller annen kanal) inn til HA recorder.

| Måler-merke + HAN-leser     | Total forsinkelse (forventet) | Komponenter                        |
| --------------------------- | ----------------------------- | ---------------------------------- |
| Kaifa MA304 + Pow-U         | 10-13 sek                     | 10 sek måler + 3 sek transmisjon   |
| Aidon 65xx + Pow-U          | 10-15 sek                     | 10 sek måler + 3-5 sek transmisjon |
| Kamstrup Omnipower + Pow-U  | 5-10 sek                      | 5 sek måler + 3-5 sek transmisjon  |
| Kaifa/Aidon + Tibber Pulse  | Ukjent                        | Annet nettverkslag (Tibber Cloud)  |
| Kaifa/Aidon + Tibber Bridge | Ukjent                        | RJ45 direkte HAN, lokal kobling    |
| Kaifa/Aidon + ESPHome AMS   | 3-10 sek                      | Avhengig av firmware               |

Mitt Kaifa + Pow-U-oppsett er målt til nøyaktig 13 sek (10 sek inne i måleren, 3 sek i transmisjon). Det er kun denne verifiserings-pipelinen i [scripts/research/verify_invoice_hourly.py](../scripts/research/verify_invoice_hourly.py) som påvirkes. Selve HA-integrasjonen leser `p`-strømmen kontinuerlig og er upåvirket av forsinkelsen.

Andre kombinasjoner må verifiseres empirisk hos brukeren. Se [verifiser-din-faktura.md, seksjon 5c](fakturaer/verifiser-din-faktura.md#5c-velg-riktig---shift-seconds) for hvordan dette håndteres i scriptet og hva `--shift-seconds` skal settes til.

## Eget oppsett

| Felt                   | Verdi                                                  |
| ---------------------- | ------------------------------------------------------ |
| Måler-merke            | Kaifa                                                  |
| Modell                 | MA304H3E (3-fase 4-leder, 3x230 V)                     |
| Importør               | NURI Telecom Co., Ltd., Fjøsangerveien 65, 5054 Bergen |
| Produsent              | Shenzhen Kaifa Technology (Chengdu), Kina              |
| Målernummer            | 6970000000000000 (anonymisert)                         |
| Målepunkt-ID           | 707000000000000000 (anonymisert)                       |
| Målerkonstant          | 1,00000                                                |
| Adresse                | <adresse>                                              |
| Nettområde             | BKKN1 (NO5)                                            |
| Nettselskap            | BKK AS (fra 27.07.2019)                                |
| Strømleverandør        | Tibber Norge AS (fra 06.09.2019)                       |
| Standarder             | EN 50470, IEC 62052/62053, DLMS 2017                   |
| Protokoll på HAN       | DLMS/COSEM (HDLC), ikke ASCII                          |
| Frontpanel-indikatorer | F1 F2 F3 HAN MB L1 L2 L3 F4 PDI EF OC                  |

Måler-merket er verifisert fysisk: frontpanelet viser "nuri" + "KAIFA MA304H3E" og DLMS 2017-logo. Identifikasjon ellers stammer fra Elhub-data og BKK-faktura.

### Porter på frontpanelet (Kaifa MA304H3E)

Kaifa MA304H3E har to separate porter under hvert sitt deksel:

- **HAN-port** (høyre): kunde-tilgjengelig RJ12-kontakt (RJ45 på enkelte varianter). M-Bus elektrisk på 2400 8N1 med DLMS/COSEM-rammer over HDLC.
- **M-Bus slave-port** (venstre, separat deksel): for daisychain til vann- og gass-målere. Ikke samme som HAN, hverken elektrisk eller logisk.

Indikatorene "HAN" og "MB" på selve displayet styres uavhengig, basert på hvilken port som er aktivert. Justervesenets plombe sitter på klemmedekselet nederst.

### Porter på frontpanelet (Aidon 6534, til sammenligning)

Aidon 6534 har én lokal port for kunden: en RJ45-kontakt med dobbeltmerking "HAN" og "MBUS" på dekselet. Samme port elektrisk og logisk. Aidon dokumenterer den som "M-Bus Mini-Master per EN 13757-2" (24V/12V, 21 mA max, RJ45-pinout). Det finnes ingen separat M-Bus slave-port på 6534, ingen optisk P0-port og ingen WAN-port på fronten. Modem og antenne sitter inne i systemmodulen.

Kilder: [Aidon 6534 bruksanvisning (Lidköping)](https://lidkoping.se/download/18.36ac91af17c781f2c53151a0/1635773765116/Aidon%206534%20manual.pdf), [Aidon RF2 ESD installasjonsveiledning (L-Nett)](https://www.l-nett.no/getfile.php/13162796-1623075080/Dokumenter/Dokumenter%20for%20elinstallat%C3%B8rer/Aidon%20RF2_ESD%20installasjonsveiledning_NO.pdf).

### Protokoll og broadcast-mønster på Kaifa

Kaifa MA304H3E kjører **DLMS/COSEM over HDLC** på HAN-porten, ikke ASCII. Pow-U-firmwaren auto-detekterer dette og bytter parser ut fra rammeformatet.

| Liste | Frekvens                | Innhold                                         |
| ----- | ----------------------- | ----------------------------------------------- |
| list1 | hvert 2,5 sek           | `p` (W), `V_L1-3` (V), `I_L1-3` (A)             |
| list2 | hvert 10 sek            | utvidet sett (spenning, strøm, effekt per fase) |
| list3 | hver time, **HH:00:10** | `tpi`, `tqi`, `tpo`, `peaks0..2`                |

Sample-skiftet i eget oppsett er empirisk verifisert ved å sammenligne målerens egen RTC (`sensor.pow_u_ams_rtc`, fra OBIS 1.0.0) mot HA-mottakstid (`last_updated_ts`) over 24 timer:

| Tidspunkt | Hva skjer                                                                          |
| --------- | ---------------------------------------------------------------------------------- |
| HH:00:00  | Elhub-snapshot tas internt i måleren                                               |
| HH:00:10  | Måleren bygger HAN-frame med eget tidsstempel i OBIS 1.0.0 (offisielt dokumentert) |
| HH:00:13  | HA recorder mottar MQTT-publish fra Pow-U                                          |

10 sek inne i måleren mellom snapshot og frame-bygging, 3 sek i transmisjon (HAN-overføring + Pow-U-parsing + MQTT-publish). Forsinkelsen ligger **ikke** mellom Elhub og BKK. Bekreftet: Elhub-data matcher faktura med 0 avvik, se [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md).

## Pow-U / AMSleser.no

ESP32-basert HAN-leser fra [amsleser.no](https://amsleser.no). Bruker AmsToMqtt-firmware (åpen kilde, [amsreader-firmware](https://github.com/UtilitechAS/amsreader-firmware)). Lytter på HAN-port, parser HAN-frames (både ASCII og DLMS/HDLC), publiserer over MQTT til HA.

Firmware-koden er gjennomgått direkte. Funn:

- Ingen kunstig forsinkelse mellom parse og MQTT-publish. Tiden fra ferdig parset frame til publisert melding er sub-millisekund.
- `meterTimestamp` (målerens egen RTC i HAN-framen, OBIS 1.0.0) eksponeres som eget MQTT-felt. Det kan brukes for å skille målertid fra mottakstid uten å gjette.

### Kaifa-spesifikk merknad

Pow-U fra AMSleser.no har historisk hatt problemer med RJ45-terminering mot Kaifa-målere. Versjoner levert fra desember 2023 og senere har fikset dette. Har du en Pow-U eldre enn des 2023 på en Kaifa-måler, oppgrader hardwaren.

Referanse: [amsleser.no blogpost om Kaifa/Nuri](https://www.amsleser.no/blog/post/27-i-have-a-kaifanuri-meter-and-my-new-pow-u-does-not-work).

### Sensorer i HA

Sensorer som havner i HA (auto-oppdaget):

| Entity                        | Kilde             | Frekvens              |
| ----------------------------- | ----------------- | --------------------- |
| `sensor.pow_u_ams_p`          | list1             | ~2,5 sek              |
| `sensor.pow_u_ams_u1/2/3`     | list1             | ~2,5 sek              |
| `sensor.pow_u_ams_i1/2/3`     | list1             | ~2,5 sek              |
| `sensor.pow_u_ams_tpi`        | list3             | 1x per time, HH:00:13 |
| `sensor.pow_u_ams_houruse`    | beregnet av Pow-U | 1x per time           |
| `sensor.pow_u_ams_peaks0/1/2` | list3             | 1x per time           |
| `sensor.pow_u_ams_max`        | beregnet av Pow-U | løpende               |

`pow_u_ams_houruse` er Pow-U sin egen kalkulasjon (tpi-diff per time). I praksis matcher den `tpi_HH+1 - tpi_HH`, men kan avvike marginalt på grenser.

`pow_u_ams_peaks0/1/2` er målerens egen rapporterte topp-3 maks-effekt for inneværende måned. Dette er **time-snitt-effekt**, ikke momentan-topp.

## HA recorder og long-term statistics

HA recorder lagrer to ting:

- `states`-tabellen: hver sample, kort retensjon (default 10 dager)
- `statistics`-tabellen: hourly aggregat, full historikk

For monotone tellere som tpi filtrerer recorder aggressivt. Vi observerer kun 1 tpi-sample per time i states-tabellen. Det tilsvarer broadcastfrekvensen, ikke en recorder-filtrering.

For `p` (effekt) får vi alle ~2,5-sek-samples ned i states.

Long-term statistics aggregeres slik:

- `state` = siste sample i tidsvinduet
- `mean`, `min`, `max` = aggregat over samples i vinduet
- For tpi: `state` ≈ tpi-verdi ved HH+1:00:13 (siste sample), brukt for diff-beregning

## Elhub-rapportering

NVE/RME-forskriften krever at AMS-målere rapporterer timesverdier til Elhub. Bekreftet 2026-05-23:

- Elhub-CSV for april 2026 matcher BKK-fakturaen **eksakt** (1381,827 kWh, samme topp 3-verdier)
- Tidssone: lokal CET/CEST med eksplisitt offset i ISO-format (`+02:00` i april)
- Oppløsning: 3 desimaler = 1 Wh
- Kvalitet-flagg: `Målt` for ekte data, `Beregnet` for interpolert ved nedetid
- Lagringsperiode hos Elhub: 10 år
- Format: `KWH 60 Forbruk` = 60-minutters intervall

Elhub-snapshot tas ved presis HH:00:00 lokal tid (måleren har egen RTC for dette). HAN list3-broadcast skjer 13 sek senere.

Det betyr at BKK har de samme verdiene som Elhub, og at vi har 13-sek-forskjøvet aggregat i HAN-data. Akkumulert over 720 timer blir det -9 Wh på sum.

Se [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for detaljert analyse.

## Der vi ser mer enn BKK

For `p` (momentan effekt) er HAN-strømmen kontinuerlig. Vi kan måle hvert 2,5 sekund. BKK ser bare times-snitt av effekten (kWh-diff per time).

Dette betyr:

- **Vi** kan oppdage en kort spike på 12 kW som bare varte i 5 minutter
- **BKK** ser kun timesnittet, som kan være 6 kW (hvis spiken var halve timen)

For kapasitetsledd er det bekreftet at BKK bruker timesnitt-effekt (= kWh-diff per time, eks. Elhub-snapshot). Vår tpi-baserte beregning matcher dette innenfor 3-8 W per topp. BKK ser ikke korte spikes, vi gjør det (`p`-strømmen 2,5 sek), men det brukes ikke i kapasitetsberegning.

## Empiriske observasjoner (april 2026)

Tallene under gjelder Kaifa MA304H3E i eget oppsett. Aidon- og Kamstrup-målere bruker samme NEK HAN-spek og skal gi tilsvarende sample-skift, men firmware-detaljer kan flytte avviket noen Wh.

Fra `tests/fixtures/bkk_april_2026_hourly.json` mot BKK-faktura 000000000:

| Måling          | HAN-data                 | Faktura                  | Avvik            |
| --------------- | ------------------------ | ------------------------ | ---------------- |
| Total kWh       | 1381,818                 | 1381,827                 | +9 Wh            |
| Dag kWh         | 620,858                  | 620,829                  | -29 Wh           |
| Natt kWh        | 760,960                  | 760,998                  | +38 Wh           |
| Topp 3 maks     | [5,947, 4,776, 4,266] kW | [5,939, 4,779, 4,262] kW | 3-8 W            |
| Norgespris-komp | -1430,81 kr              | -1427,89 kr              | +2,92 kr (0,2 %) |

Forklaring per linje:

**Total kWh (+9 Wh):** Forklart av 13-sek-lag på siste tpi-sample (01.05 00:00:13 vs 00:00:00). Av disse 13 sekundene ligger 10 sek inne i selve Kaifa-måleren (mellom Elhub-snapshot HH:00:00 og bygging av HAN-frame HH:00:10) og 3 sek i transmisjonskjeden (HAN + Pow-U-parsing + MQTT). 13s × snittforbruk 1,92 kW = 6,9 Wh, pluss noen Wh i andre enden.

**Topp 3 (3-8 W):** Samme sample-skifte i hourly aggregat. Vår "13:00-time" er teknisk 13:00:13 til 14:00:13. Time-snittet inneholder altså 13 sek av "neste" time og mangler 13 sek av "denne" time, som gir det observerte avviket på topp-3.

**Norgespris-komp (+2,92 kr):** Bekreftet at Nord Pool-integrasjonen returnerer **eks. mva** (vektet snitt 1,2284 × 1,25 = 1,5355, matcher fakturas implisitte 1,5333). Restavvik ~2 øre/kWh skyldes trolig EUR/NOK-vekslingskurs eller MVA-håndteringsforskjell mellom HA-cache og BKKs prisberegning.

## Hva vi kan gjøre bedre

1. **Interpolere tpi til presis HH:00:00** ved å bruke `p`-strømmen mellom HH:00:00 og HH:00:13. Forventet effekt: lukker 9 Wh-gapet.
2. **Hente rå Nord Pool EUR-priser + NB-kurser** for å reprodusere spot-snitt eksakt. Forventet effekt: lukker 2,92 kr-gapet, men avhenger av om BKK bruker samme kurser.
3. ~~Snapshot-automation i HA på HH:00:00~~. Virker ikke. Av de 13 sekundene ligger 10 inne i selve måleren (mellom Elhub-snapshot og bygging av HAN-frame), så HA mottar aldri en HH:00:00-tpi uansett trigger-tidspunkt.

Se [fakturaverifisering-prosjekt.md](fakturaverifisering-prosjekt.md) for plan.

## Referanser

- [AMSleser.no](https://amsleser.no): Pow-U-leverandør
- [AmsToMqtt firmware](https://github.com/UtilitechAS/amsreader-firmware): Pow-U firmware (kildekode gjennomgått, ingen kunstig forsinkelse, `meterTimestamp` eksponert via MQTT)
- [Aidon RJ45 HAN Interface Feature Description v1.6 EN](https://aidon.com/wp-content/uploads/2023/06/AIDONFD_RJ45_HAN_Interface_EN.pdf): list1/list2/list3-frekvens og 10-sek-offset for list3 (Aidon)
- [Kaifa KFM_001 HAN Interface Description](research/specifications/kaifa-kfm-001.pdf): DLMS/COSEM-rammer på HAN, list3 ved HH:00:10
- [Kamstrup HAN-NVE Interface Description rev 3.1](research/specifications/kamstrup-han-nve-rev3.1.pdf): DLMS/COSEM, list3 ved HH:00:05
- [NURI Telecom Co., Ltd.](https://www.nuritelecom.com/): koreansk importør, leverte 700 000 Kaifa-målere til SORIA-alliansen via felles innkjøp under BKK
- [SORIA-alliansen, BKK pressemelding](https://www.bkk.no/): 27 nettselskaper fra Haugaland til Varanger, Kaifa MA304-utrulling
- [amsleser.no blogpost om Kaifa/Nuri](https://www.amsleser.no/blog/post/27-i-have-a-kaifanuri-meter-and-my-new-pow-u-does-not-work): Pow-U pre-des-2023 RJ45-problem på Kaifa
- [IEC 62056-21 (gammel offentlig versjon)](https://www.ungelesen.net/protagWork/media/downloads/solar-steuerung/iec62056-21%7Bed1.0%7Den_.pdf): ASCII-protokoll brukt av Aidon i BKK-området. Regulerer ikke timing av kumulative timesverdier.
- [amsleser.no-blogg om HAN-timing](https://www.amsleser.no/module/ets_blog/blog?id_post=36): bekrefter samme funn om 10-sek-offset
- NVE/RME-forskriften om AMS-målere (Antagelse, finn referanse)
