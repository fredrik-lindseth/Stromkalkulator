# Revalidering av fakturafasiten etter L3b (september 2026)

Målt mot `7ea60cb` («kostnad: hold døgnmaks i takt også når avlesningen
uteblir»), med `559f799` som før-tilstand, altså der
[L3a-runden](revalidering-l3a-september-2026.md) sluttet. Dette er en
verifiseringsrunde: ingenting i grunnlaget er rettet, og ingen produksjonskode
er rørt.

Serien er `ab4a069` (én pengeakkumulator, fastledd som periodebeløp), `519de08`
(takgrense, trinnskifte, månedsskifte), `74ceb95` og `7ea60cb` (døgnmaks holdes
i takt når avlesningen uteblir). L3a flyttet grunnlaget. L3b flytter kronene, og
det er den som måles her.

## Rå grunnlag er urørt

```
git diff --stat 559f799 7ea60cb -- tests/fixtures/ scripts/research/ \
    tests/replay/fasit.py tests/test_faktura_bkk.py
```

Tom utskrift. `const.py` er også urørt gjennom serien, og BKK-oppføringen i
`dso.py` er identisk ord for ord, selv om `dso.py` ellers fikk 248 linjer
kildejakt i `30e7144` og `9bcf132`. Ingen av de 17 adopterte selskapene eller
Arva er BKK, så referansemånedene kan ikke ha flyttet seg på sats.

Følgen er at attesten som regnes uten coordinatoren er bit-identisk før og
etter:

```
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_<måned>_2026_hourly.json --faktura <måned>_2026
python3 scripts/research/verify_norgespris_eksakt.py
pytest tests/test_faktura_bkk.py -q
```

Alle sju 2026-månedene kjørt i begge utsjekkene gir samme utskrift, linje for
linje, alle «Alt innenfor toleranse». `verify_norgespris_eksakt.py` likeså.
`test_faktura_bkk.py` gir 115 passert begge steder; den importerer bare
`const.py` og dekker oktober, november og desember 2025, som er de eneste
månedene med strømstøtte i stedet for Norgespris. De tre 2025-månedene har
verken Elhub-intervallenergi eller Final-pris i fixturene, så de kan ikke
spilles gjennom coordinatoren, og strømstøtte-komponenten er derfor revalidert
på satsnivå og ikke i replay.

`verify_norgespris_eksakt.py` trenger `_private/Måleverdier/`, som er gitignored
og bare finnes i hovedutsjekken. I et worktree må den lenkes inn
(`ln -s <hovedutsjekk>/_private _private`).

## Det coordinatoren regner

Mai, juni og juli 2026 er spilt gjennom den ekte coordinatoren i begge
utsjekkene, matet fra Elhubs intervallenergi og Nord Pools Final-priser med 10
sekunders målerkadens, lest av rett før månedsskiftet og på `previous_month_*`
etter rulleringen. Metoden og harnesset er de samme som i L3a-notatet, med
kronefeltene lagt til i utskriften.

Februar, mars og april 2026 er i tillegg spilt gjennom med flat pris. De har
Elhub-fixtur men ingen Final-pris, og volum, dag/natt og døgnmaks er uavhengige
av prisen, så de tre kan likevel avstemmes på kapasitetsleddet. Det er
nødvendig her, for det er nettopp kapasitetssiden `7ea60cb` rører.

### Volum og splitt: sto helt stille

| Måned    | Komponent              |                          Før |   Etter | Differanse |                      Faktura |
| -------- | ---------------------- | ---------------------------: | ------: | ---------: | ---------------------------: |
| feb 2026 | dag / natt / total kWh | 893,615 / 780,171 / 1673,769 | uendret |          0 |                              |
| mar 2026 | dag / natt / total kWh | 831,768 / 721,449 / 1553,182 | uendret |          0 |                              |
| apr 2026 | dag / natt / total kWh | 620,829 / 760,998 / 1381,817 | uendret |          0 |                              |
| mai 2026 | dag / natt / total kWh | 518,142 / 661,161 / 1179,288 | uendret |          0 | 518,142 / 661,161 / 1179,303 |
| jun 2026 | dag / natt / total kWh | 590,646 / 442,982 / 1033,617 | uendret |          0 | 590,646 / 442,982 / 1033,628 |
| jul 2026 | dag / natt / total kWh |  514,414 / 424,349 / 938,741 | uendret |          0 |  514,414 / 424,349 / 938,763 |

Dette er kravet L3a-notatet satte: forbruket i kWh og dag/natt-splitten skal
stå stille gjennom L3b. Det gjør de, til siste desimal, i alle seks månedene.
Totalen ligger 0,011 til 0,022 kWh under Elhub som før; det er siste måling i
måneden, som faller etter siste poll i pollplanen, og den differansen er
uendret.

### Kapasitetsleddet: beløpet er det samme, grunnlaget flyttet seg

| Måned    | Komponent         |      Før |    Etter | Differanse | Faktura |
| -------- | ----------------- | -------: | -------: | ---------: | ------: |
| feb 2026 | snitt topp 3 kW   |     5,67 |     5,71 |      +0,04 |   5,706 |
| feb 2026 | fastledd akk. kr  | 404,2968 | 414,9897 |     +10,69 |  415,00 |
| feb 2026 | kapasitetsledd kr |      415 |      415 |          0 |     415 |
| mar 2026 | snitt topp 3 kW   |     4,61 |     4,63 |      +0,02 |   4,630 |
| mar 2026 | fastledd akk. kr  | 249,0501 | 249,9944 |      +0,94 |  250,00 |
| apr 2026 | snitt topp 3 kW   |     4,97 |     4,99 |      +0,02 |   4,993 |
| apr 2026 | fastledd akk. kr  | 249,8645 | 249,9942 |      +0,13 |  250,00 |
| mai 2026 | snitt topp 3 kW   |     4,66 |     4,69 |      +0,03 |   4,692 |
| mai 2026 | fastledd akk. kr  | 248,8473 | 249,9944 |      +1,15 |  250,00 |
| jun 2026 | snitt topp 3 kW   |     4,77 |     4,80 |      +0,03 |   4,796 |
| jun 2026 | fastledd akk. kr  | 247,8853 | 249,9942 |      +2,11 |  250,00 |
| jul 2026 | snitt topp 3 kW   |     4,68 |     4,72 |      +0,04 |   4,715 |
| jul 2026 | fastledd akk. kr  | 248,7196 | 249,9944 |      +1,28 |  250,00 |

Trinnet og månedsbeløpet er uendret i alle seks. Under det flyttet begge tallene
seg, og begge mot fakturaen: etter `7ea60cb` runder snitt topp 3 til fakturaens
verdi i alle seks månedene, mot 0,02 til 0,04 kW for lavt før. Akkumulatoren for
fastleddet lander nå på hele månedsbeløpet minus småøre i stedet for 0,1 til 2,6
kroner under.

Dette er den samme fellen som L3a-runden viste, bare på kapasitetssiden.
`kapasitetsledd`-beløpet er fortsatt 250 kroner i mai, juni og juli, så ser du
bare på beløpet, har ingenting skjedd. April lå på 4,993 kW, sju tusendels
kilowatt under 5,0 kW-grensen mellom 250 og 415 kroner i måneden. Den før-verdien
på 4,97 traff riktig trinn, men det er flaks: en før-verdi som ligger 0,02 lavt
er 0,02 fra å ha bommet med 165 kroner i måneden.

### Kroner: her flyttet det seg, og mye

| Måned    | Komponent                           |           Før |                         Etter | Differanse |                 Faktura |
| -------- | ----------------------------------- | ------------: | ----------------------------: | ---------: | ----------------------: |
| mai 2026 | energiledd akk. kr                  |      392,9573 |                      392,9573 |          0 |                         |
| mai 2026 | energiledd dag kr                   | (fantes ikke) |                      186,3368 |            |                  186,34 |
| mai 2026 | energiledd natt kr                  | (fantes ikke) |                       86,7754 |            |                   86,77 |
| mai 2026 | avgifter kr                         | (fantes ikke) |                      119,8451 |            |                  119,84 |
| mai 2026 | nettleie sum kr                     |        641,80 |                        642,95 |      +1,15 |                  642,95 |
| mai 2026 | strøm akk. kr                       |      589,6438 |                      589,6438 |          0 |                         |
| mai 2026 | `monthly_accumulated_cost_kr`       |     1231,4485 |                     1232,5955 |      +1,15 |                         |
| mai 2026 | `monthly_cost_kr`                   |       1377,27 |                       1232,60 |    -144,67 |                         |
| mai 2026 | `daily_cost_kr` (31.05)             |         35,17 |                         32,16 |      -3,01 |                         |
| mai 2026 | Norgespris kr                       |      -1032,56 |                      -1032,56 |          0 |                -1032,56 |
| mai 2026 | strømstøtte kr                      |             0 |                             0 |          0 |                       0 |
| jun 2026 | energiledd akk. kr                  |      375,5924 |                      375,5924 |          0 |                         |
| jun 2026 | energiledd dag / natt / avgifter kr | (fantes ikke) | 212,4111 / 58,1400 / 105,0413 |            | 212,41 / 58,14 / 105,04 |
| jun 2026 | nettleie sum kr                     |        623,48 |                        625,59 |      +2,11 |                  625,59 |
| jun 2026 | strøm akk. kr                       |      516,8086 |                      516,8086 |          0 |                         |
| jun 2026 | `monthly_accumulated_cost_kr`       |     1140,2862 |                     1142,3951 |      +2,11 |                         |
| jun 2026 | `monthly_cost_kr`                   |       1249,21 |                       1142,40 |    -106,81 |                         |
| jun 2026 | `daily_cost_kr` (30.06)             |         41,35 |                         38,38 |      -2,97 |                         |
| jun 2026 | Norgespris kr                       |       -363,53 |                       -363,53 |          0 |                 -363,54 |
| jul 2026 | energiledd akk. kr                  |      336,0885 |                      336,0885 |          0 |                         |
| jul 2026 | energiledd dag / natt / avgifter kr | (fantes ikke) |  184,9961 / 55,6929 / 95,3995 |            |  185,00 / 55,70 / 95,40 |
| jul 2026 | nettleie sum kr                     |        584,81 |                        586,08 |      +1,27 |                  586,10 |
| jul 2026 | strøm akk. kr                       |      469,3704 |                      469,3704 |          0 |                         |
| jul 2026 | `monthly_accumulated_cost_kr`       |     1054,1786 |                     1055,4533 |      +1,27 |                         |
| jul 2026 | `monthly_cost_kr`                   |       1119,60 |                       1055,45 |     -64,15 |                         |
| jul 2026 | `daily_cost_kr` (31.07)             |         38,25 |                         35,93 |      -2,32 |                         |
| jul 2026 | Norgespris kr                       |       -807,50 |                       -807,50 |          0 |                 -807,50 |

«Nettleie sum» er energiledd akk. pluss fastledd akk., altså den linjen BKK
kaller nettleie subtotal. «Strøm akk.» er kraftdelen, som under Norgespris er
50 øre inkl. mva ganget med forbruket: 0,50 x 1179,288 = 589,644 for mai, som er
tallet på øret.

Strømstøtte er null i alle seks månedene, fordi alle er Norgespris-måneder. De
tre 2025-månedene med strømstøtte er dekket av `test_faktura_bkk.py`, som er
uendret.

## Hvorfor `monthly_cost_kr` falt 64 til 145 kroner

Fordi den var feil før, og det er nøyaktig det `ab4a069` retter.

Før hadde vi to veier til månedskostnaden som ikke svarte likt. Den ene,
`monthly_accumulated_cost_kr`, summerte strøm, energiledd og fastledd hver for
seg og gav 1231,45 for mai. Den andre, `monthly_cost_kr`, akkumulerte
`total_price * energy_kwh` ved hver poll og gav 1377,27. Samme måned, 145,82
kroner fra hverandre.

Differansen er `fastledd_per_kwh`. Den regnes som
`(kapasitetsledd / dager_i_måneden) / 24`, altså kroner per time, og den lå
inne i `total_price`. Ganget med kilowattimer i stedet for timer gav den
0,3360 x 1179,288 = 396,2 kroner fastledd i mai, mot de 250 kronene fakturaen
krever. Trekker du fra de 248,85 som den andre veien alt hadde bokført, sitter
du igjen med de 145,8 kronene som skilte de to. Juni og juli følger samme
regnestykke med sine egne kWh-tall.

Etter `ab4a069` er det én akkumulator, og `total_price` ganges ikke lenger med
kilowattimer noe sted i `coordinator.py` eller `kostnad.py`. Kontrollen er
`grep -n "total_price \* "` i begge filene, som gir tom utskrift.

Den nye verdien stemmer mot fakturaen: 589,64 kraft pluss 642,95 nettleie er
1232,60, og 642,95 er fakturaens nettleie subtotal på øret. Juni lander på
625,59 mot fakturaens 625,59, juli på 586,08 mot 586,10.

`daily_cost_kr` falt av samme grunn og har fått fastleddet lagt til som et
dagsbeløp i stedet. Siste døgn i mai er 32,896 kWh, som til Norgespris pluss
energiledd og avgifter blir 24,11 kroner, pluss 250/31 = 8,06 i fastledd, altså
32,17. Coordinatoren sier 32,16. Juni og juli lander 2 og 3 øre unna på samme
måte. Før-verdiene på 35,17, 41,35 og 38,25 lå rundt tre kroner for høyt, som er
den samme feilenheten.

`fastledd_per_kwh` står fortsatt i attributtet `kapasitetsledd_per_kwh`, der det
er en visningspris og ikke lenger ganges inn i noe beløp. Det er kroner per time
presentert som kroner per kilowattime, og de to er bare like ved nøyaktig 1 kWh/h
forbruk. Det er en visningskuriositet, ikke et avvik i avregningen, men den er
verdt å rette når attributtene skrives om.

## Identiteten L3b flagget selv

`monthly_accumulated_cost_energiledd_kr` beholdt navnet, og `coordinator.py`
lover at den nå summerer nøyaktig
`monthly_energiledd_dag_kr + monthly_energiledd_natt_kr + monthly_avgifter_kr`.
Etterprøvd på alle tre replay-månedene, på fire desimaler:

```
mai  186,3368 + 86,7754 + 119,8451 = 392,9573
juni 212,4111 + 58,1400 + 105,0413 = 375,5924
juli 184,9961 + 55,6929 +  95,3995 = 336,0885
```

Alle tre treffer det utskrevne `monthly_accumulated_cost_energiledd_kr` eksakt.
Splitten stemmer også mot fakturaens egne linjer: 186,34 / 86,77 og 105,10 +
14,74 = 119,84 for mai, med tilsvarende treff i juni og juli.

Identiteten har et fjerde ledd, `_monthly_energiledd_apning`
(`coordinator.py:962-980`). Det er null i en fersk måned og bare ulikt null i
måneden der en lagret fil fra før splitten leses inn: da bæres den gamle summen
som åpningsbalanse, fordi den ikke kan deles i dag, natt og avgifter i ettertid,
og den faller bort ved neste månedsskifte. Oppførselen er dekket av
`tests/test_kostnad.py::TestOppgraderingFraSammenslaattEnergiledd`. Den ene
oppgraderingsmåneden er altså det eneste tilfellet der de tre attributtene ikke
summerer til feltet, og det er dokumentert og bevisst.

## Testporten

`just test` i en ren utsjekk av `7ea60cb`: 3430 passert, 34 hoppet over,
`ruff check` og `ruff format --check` grønne, `mypy` uten funn i 14 filer,
`vulture` uten funn.

## August 2026 er fortsatt ikke avstembar

Uendret fra L3a-runden. 176 av 744 timer mangler HAN-måling, Elhub-CSV-en for
august er ikke lastet ned (`stromkalkulator-r568ale`), og 31.08 kl. 00 står
bevisst ufylt (`stromkalkulator-3u7fttz`). Måneden er merket DELVIS i
`verify_invoice_hourly.py`, og utskriften er bit-identisk før og etter serien.
Den er ikke revalidert utover det.

## Konklusjon

Ingen uforklarte avvik. Alt som flyttet seg, flyttet seg mot fakturaen, og alt
som skulle stå stille sto stille. Denne runden stopper ikke release.

## Slik gjøres den om igjen

To detached worktrees på `559f799` og `7ea60cb`, `_private` lenket inn i begge,
og harnesset fra
[L3a-notatet](revalidering-l3a-september-2026.md), under «Kommandoen som
produserte før/etter-tabellen»,
lagt inn som `tests/test_revalider_maaneder.py`. Til denne runden er utskriften
utvidet med `monthly_energiledd_dag_kr`, `monthly_energiledd_natt_kr`,
`monthly_avgifter_kr`, `monthly_accumulated_cost_strom_kr`,
`monthly_accumulated_cost_kapasitetsledd_kr`, `monthly_net_cost_kr` og
`daily_cost_kr`, alle lest med `.get()` siden de tre første ikke finnes i
før-utsjekken.

Februar, mars og april kjøres med samme harnesse, men med
`p = {start: [1.0] * 4 for start, _ in t}` i stedet for Final-prisene, og med
bare volum- og kapasitetsfeltene lest av.

Fjern begge filene etterpå. De er målinger, ikke porter, og hører ikke hjemme i
suiten. Pollplanen må stoppe på månedsgrensen; ruller du forbi, nullstiller
coordinatoren `monthly_*` og du leser av nuller.

## Neste gang

Denne runden er gyldig for `7ea60cb`. Neste endringsserie som rører
`coordinator.py`, `kostnad.py` eller BKK-satsene i `dso.py` og `const.py` må
kjøre den om igjen, med samme ti måneder: oktober, november og desember 2025
gjennom `tests/test_faktura_bkk.py`, februar til august 2026 gjennom
`verify_invoice_hourly.py`, og februar til juli 2026 i tillegg gjennom
coordinatoren, de tre siste med Final-priser og de tre første med flat pris.
