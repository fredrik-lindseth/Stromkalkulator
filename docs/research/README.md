# Research

Bakgrunn, analyser og åpne spørsmål bak strømkalkulator-integrasjonen.

Filene her dokumenterer hvordan integrasjonen forholder seg til faktiske BKK-fakturaer, hvordan ulike DSO-tariffer er verifisert mot kilder, og åpne spørsmål rundt EUR/NOK-omregning og AMS-måler-timing. Generert tabell-output ligger i `_generated/` og oppdateres av `just verify-all`. PDF-spec for målere ligger i `specifications/`.

## Fakturaverifisering og kodegjennomgang

- [nok-omregning.md](nok-omregning.md), variant-matrise for EUR/NOK-omregning av Norgespris-kompensasjon, med konklusjon om 12:00 CET-hypotesen.
- [elhub-vs-han-vs-faktura.md](elhub-vs-han-vs-faktura.md), sammenligning av Elhub-data, HAN-broadcast og BKK-faktura for å lokalisere 13-sek-forsinkelsen.
- [ikke-validerte-scenarier.md](ikke-validerte-scenarier.md), kodegjennomgang av tre kjente scenarier (DST, negative spotpriser, Norgespris-tak) med identifiserte småfeil.

## EUR/NOK-kurser og valutamarked

- [valutafixinger-12cet.md](valutafixinger-12cet.md), hvilke 12:00 CET-fixinger som faktisk finnes, og hva norske banker og strømleverandører bruker.
- [forward-hedge-og-nok-likviditet.md](forward-hedge-og-nok-likviditet.md), Nord Pools to-banks-hedge og NOK-likviditet i lunsj-vinduet.
- [nok-intraday-volatilitet.md](nok-intraday-volatilitet.md), er observerte 12:00 → 14:15 bevegelser normale, og finnes det systematisk skjevhet.
- [sporsmal-valutaekspert.md](sporsmal-valutaekspert.md), strukturerte spørsmål til en valuta-PhD om EUR/NOK-omregning.
- [bloomberg-verifisering.md](bloomberg-verifisering.md), resultat av Bloomberg 12:00 CET-uttrekket: hypotesen holdt ikke, og veien videre.

## AMS-måler og timing

- [klokke-og-tidsstempling.md](klokke-og-tidsstempling.md), klokke-kilde og 10-sek-broadcast-design i Kaifa/Aidon-målere.

## Nettleietariffer (DSO)

- [dso-trippelverifisering.md](dso-trippelverifisering.md), sjekk av flaggede feil i `dso.py` mot tre uavhengige kilder per nettselskap.
- [andre-nettselskaper.md](andre-nettselskaper.md), verifisering av de største DSO-ene utenom BKK mot publiserte tariffer for 2026.

## Kommunikasjon

- [epost-utkast-bkk.md](epost-utkast-bkk.md), utkast til epost til BKK om Norgespris-snittpris og kursvalg.

## Underkataloger

- [`_generated/`](_generated/), tabellene som regenereres av `just verify-all`. Ikke rediger manuelt.
- [`specifications/`](specifications/), HAN-port-spec for Kaifa, Aidon og Kamstrup AMS-målere.
