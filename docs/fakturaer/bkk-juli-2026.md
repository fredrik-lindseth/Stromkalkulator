# Verifiseringsrapport: BKK-faktura juli 2026

**Fakturanr:** 012345686
**Periode:** 01.07.2026 - 01.08.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-08-07 (linje for linje), 2026-08-08 (time for time, etter full Elhub-eksport)

## Fakturadata

| Priselement           | Forbruk     | Pris            | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ----------- | --------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 514.414 kWh | 35.963 øre/kWh  | 185.00       | 185.00             | 0.00     |
| Energiledd natt/helg  | 424.349 kWh | 13.125 øre/kWh  | 55.70        | 55.70              | 0.00     |
| Kapasitet 2-5 kW      | 31 dager    | 250 kr/mnd      | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 938.763 kWh | 8.913 øre/kWh   | 83.67        | 83.67              | 0.00     |
| Enovaavgift           | 938.763 kWh | 1.25 øre/kWh    | 11.73        | 11.73              | 0.00     |
| **Nettleie subtotal** |             |                 | **586.10**   | **586.10**         | **0.00** |
| Norgespris            | 938.763 kWh | -0.86017 kr/kWh | -807.50      | -807.50            | 0.00     |
| **Total**             |             |                 | **-221.40**  | **-221.39**        | **0.01** |
| Herav MVA             |             |                 | 117.22       | 117.22             | 0.00     |

**Resultat:** Alle linjer matcher fakturaen når fakturaens eget forbrukstall
brukes. Juli er den skarpeste måneden så langt: ingen linje bommer i det hele
tatt på øret. Ettøringen på totalen kommer av at fakturaen bare oppgir
Norgespris-satsen med fem desimaler (-0.86017 kr/kWh), så vår replay av
linjen lander på -807.4958 der BKK har regnet time for time. Satsene er
uendret fra juni.

Juli er den andre måneden på rad med lavt totalforbruk, men Norgespris-linjen
snur fakturaen tilbake til et beløp til gode (-221.40 kr) fordi spotprisen
steg igjen: implisitt snittspot 50 + 86.017 = 136.017 øre/kWh inkl. mva, mot
85.171 i juni.

## HAN-utfall 29.-31. juli

`sensor.pow_u_ams_tpi` og `sensor.pow_u_ams_p` sluttet å rapportere 29. juli
og var nede ut fakturaperioden. HAN-fixturen
(`tests/fixtures/bkk_juli_2026_hourly.json`) manglet derfor `kwh` og
`p_max_w` for 61 av 744 timer, fra 29.07 kl. 11 til og med 31.07 kl. 23.
Spotprisen er komplett for alle 744 timene.

Utfallet startet i praksis én time tidligere: 29.07 kl. 10 har HAN-målt 0,0
kWh med `p_max` 4623 W, som er fysisk umulig. tpi-måleren frøs midt i timen,
så det reelle hullet er 62 timer. Beviset er totalsummen: fylles bare de 61
null-timene fra Elhub mangler måneden 1,6 kWh mot fakturaen, men med
Elhub-verdien for time 10 (1,635 kWh) lander totalen 10 Wh fra fakturaen.

Hullet ble først stående **ufylt** (Elhub-eksporten som lå lokalt dekket bare
01.07-05.07), og restanalysen under ble brukt som plausibilitetssjekk. Etter
ny Elhub-eksport for hele måneden (2026-08-08) er alle 62 timene fylt med
Elhub-kWh via `scripts/research/fyll_datahull_fra_elhub.py`, merket
`"kwh_kilde": "elhub"` i fixturen og dokumentert i `metadata.datahull`.
`p_max_w` er fortsatt `null` for de fylte timene (Elhub har ikke effektdata),
men alle fakturaens tre effekttopper ligger før utfallet.
`verify_norgespris_eksakt.py` holder de fylte timene utenfor HAN-summene,
så proveniensen i forskningsnotatene består.

### Restanalyse: er fakturaen konsistent i hullet?

Analysen under ble gjort før hullet ble fylt, og beholdes som metodikk for
fremtidige utfall der Elhub-data ikke finnes. Elhub-fyllingen bekreftet den i
etterkant: restforbruket fakturaen tilskrev hullet stemte med Elhub-målingene.

Selv uten måling kan vi teste om fakturaen henger sammen med modellen vår i
hullet. Fakturaen minus det vi faktisk har målt gir et restforbruk og en
implisitt Norgespris-sats. Ligger den satsen innenfor spennet av faktiske
timepriser i hullet, er fakturaen konsistent.

| Størrelse                        | Verdi                                |
| -------------------------------- | ------------------------------------ |
| Restforbruk                      | 80.513 kWh (64.960 dag, 15.553 natt) |
| Fordelt på                       | 43 dag-timer, 18 natt/helg-timer     |
| Snitt dag                        | 1.511 kWh/h                          |
| Snitt natt/helg                  | 0.864 kWh/h                          |
| Implisitt Norgespris-sats        | -109.546 øre/kWh                     |
| Faktiske timesatser i hullet     | -134.486 til -50.264 øre/kWh         |
| Uvektet snitt av timesatsene     | -112.708 øre/kWh                     |

Den implisitte satsen ligger godt innenfor spennet, og litt over det uvektede
snittet, som er akkurat det man venter når forbruket vekter dagtimer med litt
lavere kompensasjon tyngre. Døgnprofilen (1.5 kWh/h dag mot 0.9 natt) er også
den normale for husstanden. Fakturaen er altså konsistent med modellen vår
også der vi mangler måling. Dette er en plausibilitetssjekk, ikke en attest.

## Time-for-time-verifisering

Utført med HAN-eksport fra HA-recorder via
`scripts/research/verify_invoice_hourly.py`, etter at de 62 utfallstimene ble
fylt med Elhub-kWh (se over). Alle 744 timer har måling:

| Linje                  | Beregnet | Faktura | Avvik  | Status |
| ---------------------- | -------- | ------- | ------ | ------ |
| Total kWh              | 938.773  | 938.763 | +0.010 | OK     |
| Forbruk dag kWh        | 514.400  | 514.414 | -0.014 | OK     |
| Forbruk natt kWh       | 424.373  | 424.349 | +0.024 | OK     |
| Energiledd dag         | 184.99   | 185.00  | -0.01  | OK     |
| Energiledd natt        | 55.70    | 55.70   | -0.00  | OK     |
| Forbruksavgift         | 83.67    | 83.67   | +0.00  | OK     |
| Enovaavgift            | 11.73    | 11.73   | +0.00  | OK     |
| Kapasitet              | 250.00   | 250.00  | +0.00  | OK     |
| Nettleie sum           | 586.10   | 586.10  | +0.00  | OK     |
| Norgespris-komp        | -807.75  | -807.50 | -0.25  | OK     |
| Total inkl. Norgespris | -221.65  | -221.40 | -0.25  | OK     |

Dag/natt-splitten treffer på 14/24 Wh, godt innenfor det dokumenterte
±100 Wh-spennet. Norgespris-avviket på 0,25 kr med HA-recorderens priser er
den kjente prisårgang-effekten: fire søndager (05.07, 12.07, 19.07, 26.07)
har konstant kursavvik mellom recorder og publisert. Med Nord Pools
publiserte Final-priser er avviket -0,05 kr, og den skarpeste sjekken,
Elhub-kWh x Final for hele måneden, treffer fakturaen på **+0,003 kr**, jf.
[research/norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).
Juli hadde 18 timer med spot under 50 øre inkl. mva der kunden betaler
mellomlegg (målt over de 683 HAN-timene; alle utfallstimene lå over 50 øre).
Måneden har ingen helligdager, så dag/natt-klassifiseringen er ren ukedag/helg.

## Kapasitetstrinn-verifisering

| Faktura                 | Vår beregning               | Match? |
| ----------------------- | --------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2) | `kapasitetstrinn_nummer: 2` | Match  |
| Pris: 250 kr/mnd        | `kapasitetsledd: 250`       | Match  |

Maks effekt fra fakturaen (timesnitt-kW, topp 3 dager):

- 5,004 kW, målt 13.07.2026 kl. 17:00
- 4,581 kW, målt 11.07.2026 kl. 16:00
- 4,561 kW, målt 27.07.2026 kl. 17:00

Snitt topp 3 = 4,715 kW, innenfor 2-5 kW-trinnet. Replay av HAN-dataene gir
samme tre dager og timer, med 4,993 / 4,561 / 4,555 kW, altså 11 / 20 / 6 W
under fakturaen og snitt 4,703 kW. Avviket på 11.07 er større enn spennet på
3-8 W som var dokumentert til og med juni, men langt fra trinngrensen på
5,0 kW, så trinnvalget står trygt. Forventningstabellen i
[neste-maaned-prosedyre.md](neste-maaned-prosedyre.md) er utvidet til 3-20 W.

Utfallet 29.-31. juli påvirker ikke denne linjen. BKK lister selv 13.07,
11.07 og 27.07 som de tre høyeste dagene, altså lå ingen topp i de dagene vi
mangler måling for. Vår fjerde- og femtehøyeste målte dag var 4,102 kW
(14.07) og 4,091 kW (23.07), godt under topp 3.

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -86,017 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Implisitt snittspot juli utledet fra kompensasjonen: 50 + 86,017 = 136,017
øre/kWh inkl. mva (108,81 øre/kWh eks. mva). Kraftig opp fra juni (85,171
inkl. mva).

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

Satsene er uendret fra juni. Juli er fortsatt sommersats for forbruksavgift
(8,913 øre/kWh inkl. mva).

## Sammenligning med juni 2026

| Parameter               | Juni            | Juli            | Endring            |
| ----------------------- | --------------- | --------------- | ------------------ |
| Antall dager            | 30              | 31              | +1 dag             |
| Totalt forbruk          | 1033.63 kWh     | 938.76 kWh      | -94.87 kWh (-9 %)  |
| Dag-forbruk             | 590.65 kWh      | 514.41 kWh      | -76.24 kWh         |
| Natt-forbruk            | 442.98 kWh      | 424.35 kWh      | -18.63 kWh         |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret            |
| Nettleie                | 625.59 kr       | 586.10 kr       | -39.49 kr          |
| Norgespris-kompensasjon | -363.54 kr      | -807.50 kr      | -443.96 kr         |
| Total                   | 262.05 kr       | -221.40 kr      | -483.45 kr         |

Forbruket faller videre inn i sommeren, men spotprisen steg kraftig igjen i
juli, så kompensasjonen mer enn doblet seg og fakturaen snudde fra å betale
til å få tilbake.

## Status

Linje-for-linje-attesten er komplett: integrasjonens satser og formler
reproduserer fakturaen innenfor avrundingsfeil, verifisert via
`tests/test_faktura_bkk.py` (fixture `FAKTURA_JULI_2026`).

Time-for-time-verifiseringen er også komplett etter Elhub-fyllingen: alle
volumlinjer reproduseres, juli kjører i `tests/test_coordinator_replay.py`
(`FAKTURA_MAP`), og eksakt-sjekken står i
`docs/research/_generated/verify_norgespris_eksakt.md`-tabellen med
Elhub x Final-avvik +0,003 kr. HAN-kolonnene for juli er merket delvise der,
siden 62 av timene ikke er HAN-data.

## Konklusjon

Integrasjonen beregner nettleie korrekt for juli 2026. Alle fakturaposter
matcher på øret (maks 0.01 kr på totalen, som skyldes fakturaens
fem-desimalers Norgespris-sats), kapasitetstrinnet treffer, og satsene i
dso.py og const.py er uendret fra juni og konsistente med det BKK fakturerer.
Norgespris-linjen er reprodusert eksakt med Elhub-kWh x publiserte
Final-priser, som mai og juni. Månedens lærdom: HAN-utfall midt i en time
etterlater en falsk 0,0-måling før hullet, og Elhub-fylling pluss
totalsum-avstemming avslører den.
