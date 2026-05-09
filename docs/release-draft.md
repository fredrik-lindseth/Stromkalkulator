# Release-utkast v1.12.0

Følger malen i [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Bugfixes

- **Spotpris-mva-håndtering**: HA-core nordpool leverer priser eks. mva, men koden antok inkl. mva. Resultat: 25 % feil i strømstøtte-trigger, totalpris og Norgespris-besparelse for Sør-Norge-brukere på spotprisavtaler. Se [incident 004](docs/incidents/004-spotpris-mva-feilbehandling.md). Migreres automatisk: eksisterende konfig får `spotpris_inkl_mva = True` (bevarer oppførsel). Repair-issue varsler om å slå AV for HA-core nordpool.
- **Eksportinntekt for plusskunder** brukte spotpris inkl. mva. Plusskunder får betalt eks. mva, så Sør-Norge-eksport ble overrapportert med 25 %.
- **Falsk Norgespris-besparelse** ble akkumulert når spotpris-sensor var nede over 2 timer. Hopper nå over akkumulering ved ugyldig spot.
- **Avrundingsavvik mot ekte fakturaer**: DSO-energiledd lagres nå som rene eks-mva-priser, inkl-mva-verdien beregnes i kode.

## Forbedringer

- Konfigurasjons-felt `spotpris_inkl_mva` for spesielle sensor-oppsett
- "Verifiser at integrasjonen regner riktig for ditt nettselskap" som tillit-mekanisme: ny `VERIFISER_DIN_FAKTURA.md` og issue-mal for innsending
- README viser nå "Verifisert mot ekte fakturaer"-tabell øverst
- BKK april 2026-rapport lagt til

## Vedlikehold

- DSO-struktur omskrevet til eks-mva
- Config v1→v3 migrering med automatisk konvertering
- Destillert dokumentasjon
- Konsolidert tester (faktura, valideringer, helpers)

## Verifisering

**SHA256:** `<settes av release-workflow>` ([hvordan verifisere](SECURITY.md))

<details>
<summary>Alle commits</summary>

- refactor(dso): eks-mva-priser + fix spotpris mva-håndtering
- docs: destiller dokumentasjon og legg til fakturaverifisering
- refactor: kode-destillering
- test: konsolidér faktura-tester, valideringer og conftest
</details>
