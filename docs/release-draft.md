# Release-utkast

Utkast til release-notater. Versjonsnummer settes når Fredrik er klar til å publisere. Følger malen i [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Bugfixes

- **Spotpris-mva-håndtering**: HA-core nordpool leverer priser eks. mva, men koden antok inkl. mva. Resultat: 25 % feil i strømstøtte-trigger, totalpris og Norgespris-besparelse for Sør-Norge-brukere på spotprisavtaler. Se [incident 004](docs/incidents/004-spotpris-mva-feilbehandling.md). Migreres automatisk: eksisterende konfig får `spotpris_inkl_mva = True` (bevarer oppførsel). Repair-issue varsler om å slå AV for HA-core nordpool.
- **Avrundingsavvik mot ekte fakturaer**: DSO-energiledd lagres nå som rene eks-mva-priser, inkl-mva-verdien beregnes i kode. BKK-faktura: avvik fra 0,004 til 0,001 øre/kWh.

## Forbedringer

- Konfigurasjons-felt `spotpris_inkl_mva` for spesielle sensor-oppsett
- "Verifiser at integrasjonen regner riktig for ditt nettselskap" som tillit-mekanisme: ny `VERIFISER_DIN_FAKTURA.md` og issue-mal for innsending
- README viser nå "Verifisert mot ekte fakturaer"-tabell øverst
- BKK april 2026-rapport lagt til

## Vedlikehold

- DSO-struktur omskrevet til eks-mva (`energiledd_dag_eks_mva`, `energiledd_natt_eks_mva`)
- Config v1→v3 migrering med automatisk konvertering
- Destillert dokumentasjon, ~5200 linjer netto fjernet
- Slettet 5 redundante testfiler (~1100 linjer), 9 nye tester for spotpris-mva
- 1912 tester passerer, lint rent

## Verifisering

**SHA256:** `<settes av release-workflow>` ([hvordan verifisere](SECURITY.md))

<details>
<summary>Alle commits</summary>

- refactor(dso): eks-mva-priser + fix spotpris mva-håndtering
- docs: destiller dokumentasjon og legg til fakturaverifisering
- docs: fjern em-dashes fra fakturaverifikasjons-filer
- test: fjern 5 redundante testfiler
</details>
