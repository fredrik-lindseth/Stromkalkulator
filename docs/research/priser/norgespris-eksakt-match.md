# Prisgrunnlag for Norgespris og fakturakontroll

Bruk Elhubs intervallforbruk og Nord Pools publiserte, endelige NOK-priser når du kontrollerer Norgespris mot faktura. Recorder-priser viser hva Home Assistant hadde tilgjengelig underveis, og kan avvike fra det endelige prisgrunnlaget.

## Beregning

For de timesavregnede BKK-fixturene brukes et uvektet snitt av kvarterprisene i hver time. Norgespris-linjen er summen av `(Norgespris − spotpris) × kWh` innenfor forbrukstaket, med lik avgiftsbehandling på begge priser. En time med spotpris under Norgespris gir et tillegg; den skal ikke klippes bort.

Bruk sats og forbrukstak for riktig periode, avgiftssone og boligtype. De fullstendige reglene står i [avregningskontrakten](../../kontrakter/avregning.md) og [beregningene](../../beregninger.md).

## Recorder-priser og endelige priser

En lagret pris i Home Assistant kan være fra en annen publisering enn prisen som inngår i fakturaen. Ved uendret EUR-pris kan ulik valutakurs gi en konstant faktor mellom NOK-prisene gjennom et døgn. Varierer faktoren innenfor døgnet, er ikke én valutakurs alene en tilstrekkelig forklaring.

Bruk de publiserte NOK-prisene direkte ved avstemming. Rekonstruksjon fra EUR-pris og en kurs fra Norges Bank eller en annen valutakilde gir ikke nødvendigvis samme pris. Den løpende integrasjonen bokfører prisen den får fra sin input-sensor; fakturakontrollen sammenligner også mot det endelige arkivet.

## Måledata, hull og avrunding

Elhub-forbruk kan avvike fra HAN-data fordi en måling mangler, er estimert eller er fordelt på en annen time i recorderen. Behold kildemerking og kvalitet. [HAN-veiledningen](../maaling/han-maling.md) forklarer tidsstemplene, og [Elhub-veiledningen](../maaling/elhub-api.md) beskriver nedlasting.

Et hull ved midnatt kan etterlate en tilsynelatende gyldig recorder-pris for time 00 som egentlig er siste pris fra foregående døgn. `fyll_spothull_fra_nordpool.py` kontrollerer slike randtimer mot publiserte priser og døgnets kursforhold. Når grunnlaget er utilstrekkelig, kreves en begrunnet manuell overstyring. Kriteriene står i skriptets dokumentasjon; kilde og begrunnelse lagres i fixturen.

Avstem fakturalinjene hver for seg. Små avvik kan komme av avrunding på et mellomnivå som ikke er oppgitt på fakturaen. Bruk avviksgrensene i verifiseringsverktøyene og oppgi det faktiske avviket i månedsrapporten.

## Arkivering og kontroll

Arkiver prisene månedlig, mens de fortsatt er tilgjengelige i Nord Pools gratis-API. Arkivet ligger i `_private/Måleverdier/`.

```bash
just snapshot-kurs
just verify-norgespris

python3 scripts/research/verify_norgespris_eksakt.py --emit-markdown
python3 scripts/research/inject_generated.py
```

`verify_invoice_hourly.py` viser også kontrollen mot endelige priser når arkivet dekker måneden. Elhub-filene bør hete `elhub_<måned>_<år>.csv`; eldre navn uten år støttes også. Se [månedsprosedyren](../../fakturaer/neste-maaned-prosedyre.md).

## Sammenligning med faktura

Tabellen viser forskjellen mellom datakildene. En delvis HAN-serie gir ingen full månedsavstemming, selv om Elhub-kolonnen dekker hele måneden. Faktorene mellom recorder-pris og publisert pris er observerte avvik; ved varierende faktor er årsaken ikke fastslått av denne kontrollen.

<!-- BEGIN GENERATED: verify_norgespris_eksakt -->
_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` (krever de private prisarkivene, se `just snapshot-kurs`).

| Måned | Faktura (kr) | HAN x HA-recorder | Avvik | HAN x Final | Avvik | Elhub x Final | Avvik |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mai_2026 | -1032.56 | -1033.11 | -0.55 | -1032.91 | -0.35 | -1032.56 | -0.001 |
| juni_2026 | -363.54 | -363.39 | +0.15 | -363.54 | +0.00 | -363.53 | +0.005 |
| juli_2026 | -807.50 | (delvis) |  | (delvis) |  | -807.50 | +0.003 |
| august_2026 | -986.38 | (delvis) |  | (delvis) |  | -986.38 | +0.000 |
| september_2026 | -1140.51 | (delvis) |  | (delvis) |  | -1140.51 | -0.004 |
| oktober_2026 | -1422.10 | (delvis) |  | (delvis) |  | -1422.10 | -0.002 |

HAN-fixturen mangler timer i: juli_2026 (62 timer); august_2026 (177 timer); september_2026 (1 timer); oktober_2026 (1 timer). Måneder med full Elhub-CSV står likevel i tabellen; HAN-kolonnene deres er merket (delvis) og Elhub-kolonnen dekker hele måneden.

Prisårgang-dager (HA-recorderen har foreløpig kurs, publisert er Final):

| Dag | Ukedag | HA/publisert | Timer |
| --- | --- | ---: | ---: |
| 2026-05-02 | lør | 0.99892 | 24 |
| 2026-05-03 | søn | 1.00055 | 24 |
| 2026-05-10 | søn | 1.00444 | 24 |
| 2026-05-17 | søn | 1.00164 | 24 |
| 2026-05-24 | søn | 0.99696 | 21 |
| 2026-05-25 | man | 0.99673 (varierende) | 23 |
| 2026-05-31 | søn | 0.99769 | 24 |
| 2026-06-14 | søn | 0.99558 | 24 |
| 2026-06-21 | søn | 1.00304 | 24 |
| 2026-07-05 | søn | 1.00174 | 24 |
| 2026-07-12 | søn | 1.00243 | 24 |
| 2026-07-19 | søn | 1.00274 | 24 |
| 2026-07-26 | søn | 0.99394 | 20 |
| 2026-08-16 | søn | 1.00281 | 24 |
| 2026-09-06 | søn | 1.00242 | 24 |
| 2026-09-07 | man | 1.00242 | 24 |
| 2026-09-13 | søn | 1.00059 | 24 |
| 2026-09-14 | man | 1.00059 | 24 |
| 2026-09-15 | tir | 0.99974 | 24 |
| 2026-09-16 | ons | 0.99930 | 24 |
| 2026-09-17 | tor | 1.00061 | 24 |
| 2026-09-20 | søn | 0.99865 | 20 |
| 2026-09-23 | ons | 1.00098 | 24 |
| 2026-09-24 | tor | 0.99969 | 24 |
| 2026-09-25 | fre | 0.99769 | 24 |
| 2026-09-26 | lør | 1.00044 | 24 |
| 2026-09-27 | søn | 1.00090 | 24 |
| 2026-09-28 | man | 1.00088 | 20 |
| 2026-10-01 | tor | 1.00060 | 24 |
| 2026-10-04 | søn | 1.00158 | 24 |
| 2026-10-05 | man | 1.00158 | 24 |
| 2026-10-11 | søn | 1.00672 | 24 |
| 2026-10-18 | søn | 1.00527 | 24 |
| 2026-10-19 | man | 1.00527 | 24 |
| 2026-10-25 | søn | 0.99783 (varierende) | 24 |
| 2026-10-26 | man | 0.99830 | 24 |
| 2026-10-31 | lør | 0.99855 | 24 |

Symmetri: mai_2026 har 35 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -20.61 kr); juni_2026 har 83 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -27.61 kr). BKK fakturerer symmetrisk.
<!-- END GENERATED -->
