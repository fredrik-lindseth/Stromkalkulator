# Satsendringer

Hva som faktisk ble endret i `dso.py` i en gitt runde, med tall og kilde per
nettselskap. CHANGELOG sier at satsene er oppdatert. Her står hvilke.

Reglene for hvordan en sats endres, altså kildekrav, mva-kolonner og
drift-vakten, står i [domain-rules.md](domain-rules.md#endre-satser).

## Oktober 2026

Kontrollert 27. oktober 2026 mot nettselskapenes egne prislister. Energiledd er øre/kWh uten mva og offentlige avgifter. Fastledd er kr/mnd med eventuell mva. Satsendringene gjelder fra 1. oktober.

| Nettselskap | Energiledd dag/natt, før → nå | Fastledd | Kilde |
| --- | --- | --- | --- |
| Asker Nett | 23,87/15,87 → 29,87/19,87 | Første trinn 215 → 225; alle trinn oppdatert | [Prisliste](https://askernett.no/prisliste-for-privatkunder-okt-2026/) |
| Barents Nett | 11,32 → 10,75 | Første trinn 517 → 491; alle trinn oppdatert | [Tariffbrosjyre](https://www.barents-nett.no/getfile.php/1315602-1790233965/Bilder/Nett/Nettleiebrosjyre%2001.10.2026.pdf) |
| Etna Nett | 25,55/18,59 → 27,55/20,59 | Eksisterende trinn beholdt | [Prisliste](https://etna.no/uploads/Etna-Nett-NETTLEIEPRISER-GJELDENE-FRA-1-OKTOBER-2026.pdf) |
| Glitre Nett og tidligere Norgesnett | 25,60/13,60 → 27,87/15,87 | 165, 270, 455, 765, 1025, 1275, 2062,50, 3075, 4105 og 7190 | [Privatkundetariff](https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde) |
| Kystnett | 18,00 → 17,00 | Første trinn 493 → 508; alle trinn oppdatert | [Prisliste](https://kystnett.no/Nettleie/?Article=68) |
| Midtnett | 23,862/18,862 → 31,00/26,00 | Husholdning uendret; egen FB22-tabell for fritidsbolig | [Prisliste HN22/FB22](https://midtnett.no/wp-content/uploads/2026/09/Pris-fra-1.okt-2026.pdf) |

Asker, Midtnett og tidligere Norgesnett bruker klokkegrensene 06–22/22–06 også i helger og på helligdager. Midtnetts publiserte månedskolonne inklusive mva brukes direkte; avrundingsforskjeller mot fri-nettleies årsbeløp er under én krone og dokumenterer ikke alene en feil oppstrøms.

Tidligere Norgesnett-kunder ble [overført til Glitres kundeløsning i oktober](https://www.glitrenett.no/informasjon/fra-norgesnett-til-glitre-nett-slik-pavirker-endringen-deg). Norgesnetts gamle nettsider er avviklet, og satsvakten følger nå den felles Glitre-tariffen. De tre gamle RK Nett-unntakene er fjernet fordi prisene nå samsvarer.

## Runden i september 2026

Ti nettselskap fikk nye satser. Alle er verifisert mot nettselskapets egen
prisliste i tillegg til fri-nettleie. Energiledd i øre/kWh eks. mva og
offentlige avgifter, kapasitetstrinn i kr/mnd inkl. mva.

| Nettselskap              | Gjelder fra | Energiledd                                                                     | Kapasitetstrinn                                  | Kilde                                                          |
| ------------------------ | ----------- | ------------------------------------------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------- |
| Elinett                  | 01.08.2026  | dag 22,64 → 25,50, natt 14,64 → 17,50                                          | alle ti hevet, trinn 1 251 → 281                 | [elinett.no](https://www.elinett.no/kunde/nettleie-2/nettleie) |
| Elvenett                 | 01.09.2026  | natt 11,00 → 5,00                                                              | tre laveste var for høye, trinn 1 194 → 160      | [elvenett.no](https://www.elvenett.no/priser-og-avtaler/)      |
| Høland og Setskog Elverk | 01.08.2026  | dag 22,50 → 27,50, natt 17,50 → 23,50                                          | alle ti hevet, trinn 1 200 → 265                 | [hsev.no](https://hsev.no/nettleie)                            |
| Lysna                    | 01.08.2026  | natt 24,03 → 26,03                                                             | nytt trinn 25-50 kW, trinn 1 388 → 375           | [lysna.no](https://lysna.no/prisar-for-private-kundar)         |
| Mellom                   | 20.08.2026  | uendret                                                                        | åtte → tolv trinn, alle hevet, trinn 1 254 → 281 | [mellom.no](https://mellom.no/nettleie/nettleiepriser/)        |
| Nordvest Nett            | 01.07.2026  | dag 26,03 → 31,23, natt 20,03 → 25,23                                          | alle ti hevet, trinn 1 158 → 190                 | [nvn.no](https://www.nvn.no/nettleige/nettleie-privatkunder)   |
| Norefjell Nett           | 01.08.2026  | dag 22,53 → 23,53, natt 15,08 → 18,58                                          | alle ti hevet, trinn 1 243 → 266                 | [norefjell-nett.no](https://norefjell-nett.no/strompris)       |
| RK Nett                  | 01.08.2026  | 20,14 → 23,02                                                                  | hele tabellen hevet, trinn 1 266 → 305           | [rauland-nett.no](https://www.rauland-nett.no/nettleige)       |
| Sør Aurdal Energi        | 01.09.2026  | vinter (okt-mar) 25,52 → 29,52, sommer (apr-sep) 21,52 → 25,52, begge eks. mva | uendret                                          | [sae.no](https://sae.no/tariffer)                              |
| Telemark Nett            | 01.09.2026  | 25,00 → 28,00                                                                  | hele tabellen hevet, trinn 1 355 → 398           | [tnett.no](https://www.tnett.no/prisar/nettleige-1/)           |

Sør Aurdal-økningen er 5,00 øre/kWh inkl. mva i alle tariffgrupper. Telemark
Nett heter nå TNett.

RK Nett og Telemark Nett ble funnet ved å gå til primærkildene for 16
oppføringer som hadde fått kapasitetstrinn fra fri-nettleie under opprydningen
i juli. Elleve var tallmessig uendret, to fikk nye tariffer og tre hadde
avrundingsrettinger. Noranett Andøy og Hadsel telles som to oppføringer.
Omfanget er diffen i `30e7144` i `dso.py`; committittelens «17» var feil.

### Seks satser var rundet feil vei

Tre kapasitetstrinn og tre energisatser hos Romsdalsnett, Vestmar Nett og
Enida er rettet mot selskapenes publiserte tall. Vi hadde blant annet regnet
bakover fra inkl.-mva-priser framfor å bruke prislistenes egne kolonner.
De tre kapasitetstrinnene i koden gikk ned nøyaktig 1 kr/mnd hver;
energileddene ble justert med 0,002 øre/kWh eks. mva. Virkningen i kroner av
energisatsene avhenger av forbruket.

| Nettselskap  | Sats            | Var    | Er            | Kilde                                                                                         |
| ------------ | --------------- | ------ | ------------- | --------------------------------------------------------------------------------------------- |
| Romsdalsnett | 2-5 kW          | 363    | 362 kr/mnd    | [romsdalsnettas.no](https://www.romsdalsnettas.no/nettleie/)                                  |
| Romsdalsnett | 20-25 kW        | 1160   | 1159 kr/mnd   | [romsdalsnettas.no](https://www.romsdalsnettas.no/nettleie/)                                  |
| Vestmar Nett | 20-25 kW        | 1495   | 1494 kr/mnd   | [vestmar-nett.no](https://vestmar-nett.no/wp-content/uploads/2026/01/Tariffer-01.01.2026.pdf) |
| Vestmar Nett | energiledd      | 17,102 | 17,10 øre/kWh | [vestmar-nett.no](https://vestmar-nett.no/wp-content/uploads/2026/01/Tariffer-01.01.2026.pdf) |
| Enida        | energiledd dag  | 26,998 | 27,00 øre/kWh | [enida.no](https://enida.no/strompris)                                                        |
| Enida        | energiledd natt | 20,998 | 21,00 øre/kWh | [enida.no](https://enida.no/strompris)                                                        |
