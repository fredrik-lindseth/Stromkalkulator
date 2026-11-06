# Kontroller beregningene mot faktura

Bruk denne kontrollen når du endrer avregning, kostnadsberegning, tariffer, fakturafixturer eller grunnlaget for replay-testene. For en ny fakturamåned følger du [månedsprosedyren](neste-maaned-prosedyre.md). Rapportene og dekningen per måned står i [fakturaoversikten](referanse.md).

## Tre kontroller av samme grunnlag

| Kontroll | Hva den viser | Hvor den kjøres |
| --- | --- | --- |
| Fakturalinjer | Formler og satser gir riktige beløp fra fakturaens oppgitte forbruk og kapasitetstrinn | `tests/test_faktura_bkk.py` |
| Måledata og priser | HAN- og Elhub-forbruk stemmer med faktura; endelige spotpriser gir riktig Norgespris-beløp | `scripts/research/verify_invoice_hourly.py` og `verify_norgespris_eksakt.py` |
| Hele beregningskjeden | Coordinatoren bokfører avlesninger, priser og månedsskifter riktig | `tests/test_coordinator_replay.py` og `tests/test_replay_hendelser.py` |

Skriptkontrollen kjører egne beregninger. Den erstatter derfor ikke replay gjennom coordinatoren. Testenes avviksgrenser gjelder hver sin datakilde og sammenligning; de skal ikke gjøres romsligere for å få en endring til å passere.

## Kjør kontrollene

```bash
just test

python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_oktober_2026_hourly.json \
    --faktura oktober_2026

just verify-norgespris
```

Gjenta skriptkontrollen for de fakturamånedene endringen berører. `just test` kjører hele faktura- og replay-suiten, inkludert månedsløpene som er utelatt fra `just test-fast`. Du trenger ikke kjøre hurtigtesten i tillegg. CI kjører full suite for kandidatens SHA før publisering. Endrer du setup, config-flow, entiteter, migrering eller repairs, kjører du også begge [HA-testmiljøene](../testing.md#ekte-home-assistant).

Bruk `just test-evidence` når du trenger en lagret rapport fra fulltesten. Tall, testresultater og kildegrunnlag havner i `dist/domain-evidence/`; CI publiserer de samme rapportene som `domain-evidence-<SHA>`. Fulltesten avviser manglende eller hoppede obligatoriske fakturatester. Se [testbevisene](../testing.md#testbevis-fra-fakturaavstemmingen) for innhold og avgrensning.

Eksakt Norgespris-kontroll trenger de private Elhub-filene og prisarkivene. Manglende data gir ikke en godkjent avstemming. Et recorder-avvik kan samtidig stå rødt selv om Elhub med endelige priser treffer fakturaen; rapporten må vise hvilken kontroll som avviker.

## Sammenlign komponentene

Kontroller totalforbruk, dag- og nattforbruk, døgnmaksene, snittet som bestemmer kapasitetstrinnet, energiledd, avgifter, fastledd, støtte og totalsum hver for seg. Uendret totalsum kan skjule at energi eller kroner har flyttet seg mellom tariffperioder.

Fastleddet er et beløp for en periode. Det skal ikke ganges med kWh. Kontroller både bokført andel underveis i måneden og hele beløpet ved månedsskiftet. Månedssensorene skal lese bokføringen, og avgifter skal være skilt fra nettleiens energiledd. Feltene og reglene står i [avregningskontrakten](../kontrakter/avregning.md).

Les inneværende måneds verdier før rullering og `previous_month_*` etter rullering. Bruk replayets tidsstempler med tidssone: begge kl. 02-timene ved vintertid må beholdes. Test også prishull, målerutfall, sene avlesninger og forbrukstak når endringen berører dem. Dekningen og kjente begrensninger står i [testguiden](../testing.md) og [begrensningene](../begrensninger.md).

## Bevar datagrunnlaget

Behold faktura, originale måledata og prisarkiv uendret når du sammenligner to kodeversjoner. Sammenlign samme intervaller med samme inngangsverdier. Må en fixture korrigeres, dokumenter kilde og kvalitet separat fra kodeendringen. En Elhub-verdi merket «Estimert» er fortsatt et estimat etter eksport til en testfixture.

[Elhub-veiledningen](../research/maaling/elhub-api.md) beskriver nedlasting og lagring. [Prisgrunnlaget](../research/priser/norgespris-eksakt-match.md) forklarer forskjellen mellom recorder-priser og endelige priser, og [HAN-veiledningen](../research/maaling/han-maling.md) beskriver tidsforskyvningen i måledata.
