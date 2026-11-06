# Hent månedsdata fra Elhub etter innlogging

Logg inn på [Elhub Min side](https://minside.elhub.no/) med BankID. Deretter kan CSV-filen lastes ned med en direkte lenke i den samme nettleseren, uten å navigere gjennom måler, kalender og eksportdialog.

```bash
python3 scripts/research/elhub_download_url.py --metering-point <målepunkt-ID-fra-fakturaen> --year 2026 --month 10
```

Åpne lenken som skrives ut i den innloggede nettleseren. Nedlastingen heter `interval-volume-<målepunkt-ID>.csv`. Kopier den til `_private/Måleverdier/elhub_oktober.csv`. Innloggingen blir i nettleseren; skriptet leser eller lagrer ingen cookies eller tokens.

## Endepunktet

```text
GET https://minside.elhub.no/api/metering-points/<målepunkt-ID>/metering-values/interval-volume.csv?filter[startDate]=2026-10-01&filter[endDate]=2026-11-01&locale=nb
```

Dette er nettsidens eget API, identifisert i de offentlige JavaScript-filene `assets/index.js`, `assets/desktop-header.module.js` og `assets/env.js`. Nettsiden bruker `credentials: include` mot `/api`. Direkte nedlasting i en innlogget Firefox-økt er verifisert 6. november 2026. Endepunktet er ikke en lovnad om et stabilt integrasjons-API; ved endringer undersøkes nettsidens eksportfunksjon igjen.

CSV-en er semikolonseparert og bruker desimalkomma. Filtrer på `Fra` i ønsket måned: oktoberforespørselen ga også 24 timer fra 1. november. Kontroller `Kvalitet`, antall timer, total kWh og de tre høyeste døgnmaksene mot fakturaen før dataene brukes som fasit. Oktober 2026 har 745 timer; begge kl. 02-timene 25. oktober må beholdes med hver sin UTC-offset og sorteres etter faktisk tidspunkt.

En nettleserkommando kan vente på sidelasting selv om CSV-nedlastingen allerede er ferdig. Sjekk nedlastingsfilen før du prøver på nytt. Original CSV og reelle identifikatorer oppbevares privat; `lag_replay_fixtures.py` eksporterer bare tidspunkt og kWh til testfixturene.
