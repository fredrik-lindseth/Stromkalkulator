# AMS-måler-spesifikasjoner og standarder

Lokal kopi av offisielle dokumenter brukt i fakturaverifiserings-prosjektet. Lagret 2026-05-22 så vi slipper å lete igjen og er beskyttet mot at originalt-URLer flyttes eller forsvinner.

## Aidon (BKK-området, vanligst i Norge)

| Fil                                                                          | Versjon | Språk | Kilde                                                                                                                 |
| ---------------------------------------------------------------------------- | ------- | ----- | --------------------------------------------------------------------------------------------------------------------- |
| [aidon-rj45-han-interface-v1.6-EN.pdf](aidon-rj45-han-interface-v1.6-EN.pdf) | 1.6     | EN    | [aidon.com](https://aidon.com/wp-content/uploads/2023/06/AIDONFD_RJ45_HAN_Interface_EN.pdf)                           |
| [aidon-rj45-han-interface-v1.5-SV.pdf](aidon-rj45-han-interface-v1.5-SV.pdf) | 1.5     | SV    | [skekraft.se](https://www.skekraft.se/wp-content/uploads/2022/10/SKEKRAFT1-886958-v3-Aidon_HAN_Interface_RJ45.pdf)    |
| [aidon-rj45-han-interface-v1.4-EN.pdf](aidon-rj45-han-interface-v1.4-EN.pdf) | 1.4     | EN    | [skekraft.se](https://www.skekraft.se/wp-content/uploads/2021/03/Aidon_Feature_description_RJ45_HAN_Interface_EN.pdf) |
| [aidon-han-interface-v1.0A-NEK.pdf](aidon-han-interface-v1.0A-NEK.pdf)       | 1.0A    | EN    | [nek.no](https://www.nek.no/wp-content/uploads/2018/11/Aidon-HAN-Interface-Description-v10A-ID-34331.pdf)             |

**Nøkkelfunn:** List 3 (kumulative tellere) sendes "10 seconds after every full hour. Values are generated at XX:00:00 and streamed on HAN interface at XX:00:10". Gjelder hele 6000- og 7000-serien.

Modeller dokumentert: 6515 (1-fase), 6520, 6525 (3-fase Hafslund), 6530, **6534 (3-fase BKK)**, 6540, 6550 (CT industri), 7000-serien (HSDC nyere).

## Kamstrup

| Fil                                                                        | Beskrivelse               | Kilde                                                                                                                      |
| -------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [kamstrup-han-nve-rev3.1.pdf](kamstrup-han-nve-rev3.1.pdf)                 | HAN-NVE Interface rev 3.1 | [nek.no](https://www.nek.no/wp-content/uploads/2018/10/Kamstrup-HAN-NVE-interface-description_rev_3_1.pdf)                 |
| [kamstrup-han-nve-5512-2441-2021.pdf](kamstrup-han-nve-5512-2441-2021.pdf) | 5512-2441 EN D1 (2021)    | [nek.no](https://www.nek.no/wp-content/uploads/2022/07/5512-2441_EN_D1_12-2021-HAN-NVE-module-interface-specification.pdf) |

**Nøkkelfunn:** HAN-NVE-modul sender hourly liste XX:00:05 (5 sek etter time-grensen, ifølge spec-en).

## Kaifa

| Fil                                    | Beskrivelse            | Kilde                                                                     |
| -------------------------------------- | ---------------------- | ------------------------------------------------------------------------- |
| [kaifa-kfm-001.pdf](kaifa-kfm-001.pdf) | Kaifa KFM_001 HAN-spek | [nek.no](https://www.nek.no/wp-content/uploads/2018/11/Kaifa-KFM_001.pdf) |

**Nøkkelfunn:** Hourly broadcast ved ca. XX:00:10 til XX:00:13.

## Internasjonal standard

| Fil                                                      | Beskrivelse                                      | Kilde                                                                                                               |
| -------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| [iec62056-21-ed1.0-1996.pdf](iec62056-21-ed1.0-1996.pdf) | IEC 62056-21 ed 1.0 (1996) ASCII serial protocol | [ungelesen.net](https://www.ungelesen.net/protagWork/media/downloads/solar-steuerung/iec62056-21%7Bed1.0%7Den_.pdf) |

**Nøkkelfunn:** Standarden regulerer framing, baudrate og data-encoding, men sier ingenting om når kumulative timesverdier skal sendes. Hver målerprodusent velger eget timing. Den nyeste utgaven er bak IEC-paywall (~CHF 200), men vi har ikke behov for den.

## Konklusjon på tvers av merker

| Merke            | Hourly broadcast etter HH:00 | Kilde           |
| ---------------- | ---------------------------- | --------------- |
| Aidon            | 10 sek                       | Aidon-spec v1.6 |
| Kamstrup HAN-NVE | 5 sek                        | Kamstrup-spec   |
| Kaifa            | 10-13 sek                    | Kaifa KFM_001   |

10-sek-forsinkelsen er ikke en Aidon-bug. Det er bransje-norm at hourly liste sendes etter time-grensen for å unngå kollisjon med 10-sek-listen som sendes presis HH:00:00. BKKs Elhub-snapshot tas presis HH:00:00 internt i måleren, så det BKK fakturerer er presis time-grense, ikke broadcast-tidspunkt.

## Eierskap (Aidon, per 2023-11-09)

Aidon er kjøpt av **Gridspertise** (eid av CVC Capital Partners og Enel Group). Ingen tegn til OEM eller whitelabel-rebranding. Aidon designer og produserer selv. Telit-modemmodul er den eneste eksterne komponenten dokumentert.

## Andre kilder (lenker, ikke arkivert lokalt)

- [amsleser.no blog post om Aidon hourly broadcast](https://www.amsleser.no/module/ets_blog/blog?id_post=36)
- [ArnieO/SmartMeterDocumentation](https://github.com/ArnieO/SmartMeterDocumentation) (samler nasjonale spec-dokumenter)
- [amshan-homeassistant discussion #6 (modell-oversikt)](https://github.com/toreamun/amshan-homeassistant/discussions/6)
- [amsreader-firmware issue #630 (Kamstrup-bruker med samme problem)](https://github.com/UtilitechAS/amsreader-firmware/issues/630)
- [amshan issue #51](https://github.com/toreamun/amshan-homeassistant/issues/51)
- [HA frontend issue #13151 (hourly i feil time)](https://github.com/home-assistant/frontend/issues/13151)
- [Wikipedia: Aidon](https://en.wikipedia.org/wiki/Aidon)
- [Gridspertise oppkjøpsannonsering](https://www.gridspertise.com/search-news/news/2023/11/gridspertise-completes-acquisition-aidon)

## Lisens og bruk

Disse PDFene er publisert offentlig av målerprodusenter og NEK. Lagret her som lokal kopi for research-formål. Sjekk originalkilde for ev. oppdaterte versjoner før du siterer i offentlig dokumentasjon.
