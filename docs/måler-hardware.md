# Måler-hardware og datakjede

Hvordan strøm-data flyter fra måleren i sikringsskapet til BKKs faktura, og til vårt validerings-script. Hva vi vet, hva vi gjetter.

> Status per 2026-05-22: Førsteutkast basert på empiriske observasjoner i eget oppsett (Aidon + Pow-U + HA). Punkter merket «**Antagelse**» må bekreftes mot offisielle manualer eller leverandør.

## Kjeden i ett bilde

```
[Aidon-måler i sikringsskap]
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

## Aidon-måleren

### Konkret hardware i eget sikringsskap

| Felt              | Verdi                                                  |
| ----------------- | ------------------------------------------------------ |
| Måler-merke       | Aidon                                                  |
| Sannsynlig modell | 6534 (3-fase 4-leder, 230/400 V, vanlig i BKK-området) |
| Målernummer       | 6970000000000000                                       |
| Målepunkt-ID      | 707000000000000000                                     |
| Målerkonstant     | 1,00000                                                |
| Adresse           | <adresse>                                              |
| Nettområde        | BKKN1 (NO5)                                            |
| Nettselskap       | BKK AS (fra 27.07.2019)                                |
| Strømleverandør   | Tibber Norge AS (fra 06.09.2019)                       |

Identifikasjon stammer fra Elhub-data og BKK-faktura. Modellbestemmelsen (6534) er basert på at BKK ruller ut nettopp denne typen, men ikke verifisert mot fysisk typeskilt.

### Produsent

Aidon ble grunnlagt i Jyväskylä i Finland i 2004 og har rullet ut rundt 2,5 millioner målepunkter i Norden. Selskapet ble kjøpt opp av italienske Gridspertise 09.11.2023. Gridspertise eies i sin tur av CVC Capital Partners og Enel Group.

Aidon designer og produserer målerne selv. Eneste tredjepartskomponent er Telit-modemmodulen for fjernkommunikasjon. Det er ikke en whitelabel-produsent som de fleste norske AMS-merkene.

### Modellrekken

Alle modellene bruker samme HAN-spek, så broadcast-mønsteret nedenfor gjelder hele rekken.

| Modell          | Type                             | Spenning      | Hvor brukt                               |
| --------------- | -------------------------------- | ------------- | ---------------------------------------- |
| 6515            | 1-fase DC, jordfeil              | 230 V         | Norge, Sverige (eldre Hafslund-rull)     |
| 6520            | 3-fase DC, 3-leder               | 3 x 230 V     | Sverige, IT-nett                         |
| 6525            | 3-fase DC, 3-leder, jordfeil     | 3 x 230 V     | Norge (Hafslund/Elvia Akershus), IT-nett |
| 6530            | 3-fase DC, 4-leder               | 3 x 230/400 V | Sverige                                  |
| 6534            | 3-fase DC, 4-leder, nøytralstrøm | 3 x 230/400 V | **Norge (BKK m.fl.) + Sverige**          |
| 6540            | 3-fase CT, 3-leder               | 3 x 230 V     | Norge/Sverige industri                   |
| 6550            | 3-fase CT, 4-leder               | 3 x 230/400 V | Norge/Sverige industri                   |
| 7-serien (HSDC) | Avansert                         | –             | Nyere installasjoner, oppgraderingsvei   |

### Nettselskap-fordeling i Norge (2023-2024)

| Nettselskap             | Måler-leverandør                |
| ----------------------- | ------------------------------- |
| BKK                     | primært Aidon 6534              |
| Elvia (tidl. Hafslund)  | Aidon 6515/6525                 |
| Glitre                  | Aidon + Kamstrup mikset         |
| Lnett                   | Aidon                           |
| Lyse, Skagerak, Eidsiva | startet med Aidon-kontrakt 2015 |
| Mindre nettselskaper    | ofte Kaifa                      |

### Protokoll og broadcast-mønster

I eget oppsett kjører Aidon **IEC 62056-21 ASCII-protokoll**, ikke DLMS. Verifisert ved at frames parses som ASCII-list-format i Pow-U.

**Aidon-broadcast over HAN** (offisielt dokumentert, [Aidon RJ45 HAN Interface Feature Description v1.6 EN](https://aidon.com/wp-content/uploads/2023/06/AIDONFD_RJ45_HAN_Interface_EN.pdf)):

| Liste | Frekvens                | Innhold                                         |
| ----- | ----------------------- | ----------------------------------------------- |
| list1 | hvert 2,5 sek           | `p` (W), `V_L1-3` (V), `I_L1-3` (A)             |
| list2 | hvert 10 sek            | utvidet sett (spenning, strøm, effekt per fase) |
| list3 | hver time, **HH:00:10** | `tpi`, `tqi`, `tpo`, `peaks0..2`                |

10-sek-offsetten på list3 er nå offisielt dokumentert av Aidon selv. Sitat fra PDF-en: "List 3 is sent 10 seconds after every full hour. Values are generated at XX:00:00 and streamed on HAN interface at XX:00:10." Det er altså et bevisst designvalg fra Aidon, ikke et IEC-krav. IEC 62056-21-spesifikasjonen sier ingenting om timing av kumulative timesverdier.

### Sammenlignet med andre målermerker i Norge

| Merke            | Hourly broadcast etter HH:00 | Kilde                                                                           |
| ---------------- | ---------------------------- | ------------------------------------------------------------------------------- |
| Aidon            | 10 sek                       | [Aidon-spec v1.6](research/specifications/aidon-rj45-han-interface-v1.6-EN.pdf) |
| Kamstrup HAN-NVE | 5 sek                        | [Kamstrup-spec](research/specifications/kamstrup-han-nve-rev3.1.pdf)            |
| Kaifa            | 10-13 sek                    | [Kaifa KFM_001](research/specifications/kaifa-kfm-001.pdf)                      |

10-sek-forsinkelsen er bransje-norm i Norge, ikke en Aidon-bug. Hourly liste sendes etter time-grensen for å unngå kollisjon med 10-sek-listen.

Splittingen er empirisk verifisert i eget oppsett ved sammenligning av målerens egen RTC (`sensor.pow_u_ams_rtc`, fra OBIS 1.0.0 i HAN-framen) mot HA-mottakstid (`last_updated_ts`) over 24 timer:

| Tidspunkt | Hva skjer                                                                        |
| --------- | -------------------------------------------------------------------------------- |
| HH:00:00  | Elhub-snapshot tas internt i Aidon                                               |
| HH:00:10  | Aidon bygger HAN-frame med eget tidsstempel i OBIS 1.0.0 (offisielt dokumentert) |
| HH:00:13  | HA recorder mottar MQTT-publish fra Pow-U                                        |

10 sek inne i måleren mellom snapshot og frame-bygging, 3 sek i transmisjon (HAN-overføring + Pow-U-parsing + MQTT-publish). Forsinkelsen ligger **ikke** mellom Elhub og BKK (bekreftet: Elhub-data matcher faktura med 0 avvik, se [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md)).

## Pow-U / AMSleser.no

ESP32-basert HAN-leser fra [amsleser.no](https://amsleser.no). Bruker AmsToMqtt-firmware (åpen kilde, [amsreader-firmware](https://github.com/UtilitechAS/amsreader-firmware)). Lytter på HAN-port, parser HAN-frames, publiserer over MQTT til HA.

Firmware-koden er gjennomgått direkte. Funn:

- Ingen kunstig forsinkelse mellom parse og MQTT-publish. Tiden fra ferdig parset frame til publisert melding er sub-millisekund.
- `meterTimestamp` (målerens egen RTC i HAN-framen, OBIS 1.0.0) eksponeres som eget MQTT-felt. Det kan brukes for å skille målertid fra mottakstid uten å gjette.

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

`pow_u_ams_houruse` er Pow-U's egen kalkulasjon (tpi-diff per time). I praksis matcher den `tpi_HH+1 - tpi_HH`, men kan avvike marginalt på grenser.

`pow_u_ams_peaks0/1/2` er målerens egen rapporterte topp-3 max-effekt for current month. Dette er **time-snitt-effekt**, ikke momentan-topp.

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

NVE/RME-forskriften krever at AMS-målere rapporterer timesverdier til Elhub. Bekreftet 2026-05-22:

- Elhub-CSV for april 2026 matcher BKK-fakturaen **eksakt** (1381,827 kWh, samme topp 3-verdier)
- Tidssone: lokal CET/CEST med eksplisitt offset i ISO-format (`+02:00` i april)
- Oppløsning: 3 desimaler = 1 Wh
- Kvalitet-flagg: `Målt` for ekte data, `Beregnet` for interpolert ved nedetid
- Lagringsperiode hos Elhub: 10 år
- Format: `KWH 60 Forbruk` = 60-minutters intervall

Elhub-snapshot tas ved presis HH:00:00 lokal tid (måleren har egen RTC for dette). HAN list3-broadcast skjer 13 sek senere.

Det betyr **BKK har de samme verdiene som Elhub**, og **vi har 13-sek-forskjøvet aggregat** i HAN-data. Akkumulert over 720 timer blir det -9 Wh på sum.

Se [research/elhub-vs-han-vs-faktura.md](research/elhub-vs-han-vs-faktura.md) for detaljert analyse.

## Hvor vi har KANTE over BKK

For `p` (momentan effekt) er HAN-strømmen kontinuerlig. Vi kan måle hver 2,5 sekund. BKK ser bare hourly snitt-effekt (kWh-diff per time).

Dette betyr:

- **Vi** kan oppdage en kort spike på 12 kW som bare varte i 5 minutter
- **BKK** ser kun timesnittet, som kan være 6 kW (hvis spiken var halve timen)

For kapasitetsledd er det bekreftet at BKK bruker timesnitt-effekt (= kWh-diff per time, eks. Elhub-snapshot). Vår tpi-baserte beregning matcher dette innenfor 3-8 W per topp. BKK ser ikke korte spikes, vi gjør det (`p`-strømmen 2,5 sek), men det brukes ikke i kapasitetsberegning.

## Empiriske observasjoner (april 2026)

Tallene under gjelder Aidon 6534 i eget oppsett. Andre Aidon-modeller bruker samme HAN-spek, så broadcast-mønsteret skal være likt, men sample-skift og avvik kan variere litt med firmware.

Fra `tests/fixtures/bkk_april_2026_hourly.json` mot BKK-faktura 000000000:

| Måling          | HAN-data                 | Faktura                  | Avvik            |
| --------------- | ------------------------ | ------------------------ | ---------------- |
| Total kWh       | 1381,818                 | 1381,827                 | +9 Wh            |
| Dag kWh         | 620,858                  | 620,829                  | -29 Wh           |
| Natt kWh        | 760,960                  | 760,998                  | +38 Wh           |
| Topp 3 maks     | [5,947, 4,776, 4,266] kW | [5,939, 4,779, 4,262] kW | 3-8 W            |
| Norgespris-komp | -1430,81 kr              | -1427,89 kr              | +2,92 kr (0,2 %) |

Forklaring per linje:

**Total kWh (+9 Wh):** Forklart av 13-sek-lag på siste tpi-sample (01.05 00:00:13 vs 00:00:00). Av disse 13 sekundene ligger 10 sek inne i selve Aidon-måleren (mellom Elhub-snapshot HH:00:00 og bygging av HAN-frame HH:00:10) og 3 sek i transmisjonskjeden (HAN + Pow-U-parsing + MQTT). 13s × snittforbruk 1,92 kW = 6,9 Wh, pluss noen Wh i andre enden.

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
- [Aidon RJ45 HAN Interface Feature Description v1.6 EN](https://aidon.com/wp-content/uploads/2023/06/AIDONFD_RJ45_HAN_Interface_EN.pdf): offisiell Aidon-dokumentasjon på list1/list2/list3-frekvens og 10-sek-offset for list3
- [IEC 62056-21 (gammel offentlig versjon)](https://www.ungelesen.net/protagWork/media/downloads/solar-steuerung/iec62056-21%7Bed1.0%7Den_.pdf): ASCII-protokoll brukt av Aidon i BKK-området. Regulerer ikke timing av kumulative timesverdier.
- [amsleser.no-blogg om HAN-timing](https://www.amsleser.no/module/ets_blog/blog?id_post=36): bekrefter samme funn om 10-sek-offset
- NVE/RME-forskriften om AMS-målere (Antagelse, finn referanse)
