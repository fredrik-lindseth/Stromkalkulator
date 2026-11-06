# Dokumentasjon

Start med [oppsett i README](../README.md) for å installere Strømkalkulator. Her finner du forklaringer på beregningene, veiledning for fakturakontroll og dokumentasjon for utviklere.

## Bruk og beregninger

- [Input-sensorer](input-sensorer.md): effekt, energi og spotpris.
- [Sensorer](sensorer.md) · [English](sensors.en.md): verdier, attributter og bruk i Home Assistant.
- [Beregninger](beregninger.md): nettleie, avgifter, strømstøtte og Norgespris.
- [Begrensninger](begrensninger.md): hvor datagrunnlag og beregninger ikke gir en full fasit.
- [Satsendringer](satsendringer.md): hvordan tariffendringer håndteres.
- [Hvorfor nettleie er komplisert](galskapen.md): forskjellene mellom nettselskapenes modeller.

## Fakturakontroll og datakilder

- [Kontroller din faktura](fakturaer/verifiser-din-faktura.md) og [bidra med en faktura](fakturaer/bidra-med-faktura.md).
- [Verifiserte fakturaer](fakturaer/referanse.md): rapporter og målegrunnlag per måned.
- [Legg til en fakturamåned](fakturaer/neste-maaned-prosedyre.md) og [kontroller beregningsendringer](fakturaer/utviklerkontroll.md).
- [Måledata og prisgrunnlag](research/README.md): Elhub, HAN-målinger og publiserte spotpriser.

## Utvikling

- [Arkitektur](development.md), [tester](testing.md) og [bidrag](contributing.md).
- [Domeneregler](domain-rules.md): kilder og krav ved endring av satser og sensorer.
- [Avregningskontrakt](kontrakter/avregning.md) og [input og konfigurasjon](kontrakter/input-og-konfig.md).
- [Endringslogg og release](release-notes.md).
- [Hendelser](incidents/): feilårsaker og regler som hindrer gjentakelse.

Brukerveiledninger ligger direkte i `docs/`. Fakturarapporter, beregningskontrakter, hendelser og datakilder har egne mapper. Beskriv gjeldende oppførsel i veiledningene; oppgaver hører hjemme i oppgavesporingen, og gamle implementasjonsforløp finnes i git.
