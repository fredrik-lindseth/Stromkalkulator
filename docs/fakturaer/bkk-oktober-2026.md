# Verifiseringsrapport: BKK-faktura oktober 2026

Periode: 01.10.2026–01.11.2026, 31 dager og 745 timer. BKK, NO5, standard avgiftssone og Norgespris. Anonymisert fakturareferanse: 012345689. Kontrollert 6. november 2026.

## Resultat

Nettleien og Norgespris-fradraget matcher fakturaen til øret når beregningen bruker Elhubs fakturagrunnlag og Nord Pools endelige priser. Satsene i integrasjonen er uendret. Én time er estimert av nettselskapet, og HA-recorderens lagrede priser gir et større avvik enn tidligere måneder. Begge forskjellene er beskrevet nedenfor.

| Linje | Faktura | Beregnet fra fakturagrunnlaget | Avvik |
| --- | ---: | ---: | ---: |
| Energiledd dag, 641,262 kWh | 230,61 kr | 230,61 kr | 0,00 kr |
| Energiledd natt/helg, 518,956 kWh | 68,11 kr | 68,11 kr | 0,00 kr |
| Kapasitet 2–5 kW | 250,00 kr | 250,00 kr | 0,00 kr |
| Forbruksavgift, 1 160,218 kWh | 103,40 kr | 103,40 kr | 0,00 kr |
| Enovaavgift | 14,51 kr | 14,50 kr | −0,01 kr |
| Nettleie | 666,63 kr | 666,63 kr | 0,00 kr |
| Norgespris | −1 422,10 kr | −1 422,10 kr | 0,00 kr |
| Total | −755,47 kr | −755,47 kr | 0,00 kr |
| Herav mva på nettleien | 133,33 kr | 133,33 kr | 0,00 kr |

Tabellen bruker integrasjonens satser uten mellomavrunding: 0,359625 kr/kWh dag, 0,13125 natt, 0,089125 forbruksavgift og 0,0125 Enova. Summen beregnes før avrunding, så summen av de viste, avrundede linjene kan avvike med ett øre. Enova-linjen ligger innenfor det kjente avrundingsavviket hos BKK.

Elhub-kWh × Final-priser gir Norgespris −1 422,102465 kr, altså −0,002465 kr mot fakturaen. Den trykte gjennomsnittssatsen −1,2257 kr/kWh har færre desimaler og gir −1 422,08 kr; den kan ikke brukes som eksakt fasit.

## Forbruk og kapasitet

Elhub dekker alle 745 timer og summerer til 1 160,218 kWh, identisk med fakturaen. 744 timer har kvalitet «Målt», én har «Estimert». Begge kl. 02-timene ved overgangen til vintertid 25. oktober er med, med hver sin UTC-offset.

| Topp | Faktura og Elhub | HAN |
| --- | ---: | ---: |
| 15.10 kl. 12 | 5,253 kW | 5,260 kW |
| 29.10 kl. 21 | 4,515 kW | 4,499 kW |
| 12.10 kl. 19 | 4,421 kW | 4,428 kW |
| Snitt | 4,730 kW | 4,729 kW |

Snittet gir kapasitetstrinn 2–5 kW og 250 kr. HAN-kolonnen bruker rå timesdelta; verifiseringsskriptets korreksjon for 13 sekunders forsinkelse gir 4,719 kW, fortsatt samme trinn.

## Den estimerte timen

25.10 kl. 23:00 viser HA-recorderen 0,557 kWh, mens Elhub bruker 1,370 kWh med kvalitet «Estimert». Forskjellen er 0,813 kWh. Hele den rå HAN-måneden er 1 159,401 kWh, 0,817 kWh under fakturaen. Nesten hele avviket er derfor forklart av at fakturaen bruker et estimat i denne timen. Hvorfor nettselskapet estimerte timen, er ikke fastslått.

I replay-fixturen er denne ene timen erstattet med fakturagrunnlaget og merket med `kwh_kilde: elhub` og `elhub_kvalitet: Estimert`. Opprinnelig HAN-verdi og begrunnelse ligger i metadata; originaleksporten er bevart privat. Dette er en tilpasning av testgrunnlaget for å gjenskape fakturaen, ikke en retting av brukerens historikk eller et bevis på faktisk forbruk. Elhub-fixturen bevarer også kvalitetsavviket.

Med denne erstatningen og skriptets 13-sekunderskorreksjon blir totalen 1 160,217 kWh, dagforbruket 641,218 og nattforbruket 518,998. Avvikene er henholdsvis −1, −44 og +42 Wh; nettleien blir 666,63 kr.

## Lagrede og endelige spotpriser

Med det justerte forbruksgrunnlaget gir HA-recorderens priser Norgespris −1 423,68 kr, mens endelige priser gir −1 422,10 kr. Prisforskjellen utgjør omtrent 1,58 kr. Rå HAN-data uten erstatning av den estimerte timen gir −1 423,96 kr med recorder-prisene.

Flere døgn har en nesten konstant faktor mellom recorder-pris og endelig pris, i tråd med tidligere funn om foreløpig valutakurs. Vintertidsdøgnet har også variasjon innenfor døgnet, så hele avviket tilskrives ikke valutakurs alene. [Prisanalysen](../research/norgespris-eksakt-match.md) viser døgnene. Den eksakte fakturakontrollen bruker Elhub og Final; recorder-avviket forblir synlig og skal ikke godkjennes ved å øke toleransen.

## Regresjonsdekning og rettinger

Oktober inngår i de parametriserte fakturatestene og i `test_replay_hendelser.py`, som mater hele måneden gjennom coordinatoren med måleravlesninger, prisprøver, poll-jitter og månedsskifte. Testene kontrollerer også begge vintertidstimene mot uavhengig avregning. Den eldre replayen med naiv lokaltid brukes ikke som vintertidsbevis.

Fakturakontrollen avdekket tre feil i utviklerverktøyene: én prosent toleranse skjulte reelle avvik; tekstsortering byttet rekkefølgen på vintertidstimene; og Elhub-eksporten merket alle timer som målt uten å lese kvaliteten. De er rettet og dekket av regresjonstester. Den komplette Elhub × Final-kontrollen vises nå også når HAN-serien har hull eller erstattede timer, og avvik over ett øre gir feilstatus.

```bash
python3 scripts/research/verify_invoice_hourly.py --hourly tests/fixtures/bkk_oktober_2026_hourly.json --faktura oktober_2026
just test-unit -k '"oktober_2026 or invoice_verification"'
```

Den første kommandoen gir med hensikt exit 1: recorderens Norgespris-avvik overskrider grensen på 0,60 kr, selv om Elhub × Final-kontrollen er grønn. Replay-testene bruker de endelige prisene og skal være grønne.
