# Måledata og prisgrunnlag

Her beskrives datakildene som brukes til å kontrollere Strømkalkulator mot faktura. Selve beregningsreglene står i [avregningskontrakten](../kontrakter/avregning.md), og fakturakontrollen er beskrevet i [utviklerveiledningen](../fakturaer/utviklerkontroll.md).

| Tema | Dokumentasjon |
| --- | --- |
| Hente forbruk fra Elhub | [JSON, CSV og Maskinporten](maaling/elhub-api.md) |
| Måling og tidsstempler | [HAN-data og sammenligning med Elhub](maaling/han-maling.md) |
| Målernes HAN-grensesnitt | [Spesifikasjoner for Kaifa, Aidon og Kamstrup](maaling/specifications/README.md) |
| Priser til fakturakontroll | [Nord Pool-priser og Norgespris](priser/norgespris-eksakt-match.md) |
| Beregnede sammenligninger | [Genererte tabeller](_generated/) |

Originale måledata og prisarkiver ligger i gitignorert `_private/Måleverdier/`. Testene bruker anonymiserte [fixturer](../../tests/fixtures/README.md). Genererte tabeller oppdateres av skriptene; veiledningene forklarer hvordan resultatene skal brukes.

Nettselskapenes satser og kildekrav er samlet i [domenereglene](../domain-rules.md). Fakturarapportene ligger under [fakturaer](../fakturaer/referanse.md).
