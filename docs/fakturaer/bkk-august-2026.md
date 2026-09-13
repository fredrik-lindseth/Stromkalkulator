# Verifiseringsrapport: BKK-faktura august 2026

**Fakturanr:** 012345687
**Periode:** 01.08.2026 - 01.09.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-09-11 (linje for linje), 2026-09-13 (time for time).

## Fakturadata

| Priselement           | Forbruk     | Pris            | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ----------- | --------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 475.519 kWh | 35.963 øre/kWh  | 171.01       | 171.01             | 0.00     |
| Energiledd natt/helg  | 489.448 kWh | 13.125 øre/kWh  | 64.24        | 64.24              | 0.00     |
| Kapasitet 2-5 kW      | 31 dager    | 250 kr/mnd      | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 964.967 kWh | 8.913 øre/kWh   | 86.00        | 86.01              | 0.01     |
| Enovaavgift           | 964.967 kWh | 1.25 øre/kWh    | 12.06        | 12.06              | 0.00     |
| **Nettleie subtotal** |             |                 | **583.31**   | **583.32**         | **0.01** |
| Norgespris            | 964.967 kWh | -1.0222 kr/kWh  | -986.38      | -986.39            | 0.01     |
| **Total**             |             |                 | **-403.07**  | **-403.07**        | **0.00** |
| Herav MVA             |             |                 | 116.66       | 116.66             | 0.00     |

**Resultat:** Alle linjer matcher fakturaen når fakturaens eget forbrukstall
brukes. De to ettøringene er avrunding: forbruksavgiften lander på 86.0075 der
BKK har rundet til 86.00, og Norgespris-satsen er oppgitt med fire desimaler
(-1.0222 kr/kWh), så vår replay av linjen gir -986.3893. De går hver sin vei og
totalen treffer eksakt. Satsene er uendret fra juli.

August er tredje måned på rad med lavt forbruk, men spotprisen fortsatte opp:
implisitt snittspot 50 + 102.22 = 152.22 øre/kWh inkl. mva, mot 136.017 i juli
og 85.171 i juni. Kompensasjonen vokser derfor raskere enn forbruket, og
fakturaen er til gode med 403 kr.

## HAN-utfall 01.-08. august

`sensor.pow_u_ams_tpi` og `sensor.pow_u_ams_p` lå nede fra 29.07.2026 kl. 11 til
08.08.2026 kl. 08. Det er det samme utfallet som ga juli-hullet, og det strekker
seg altså over månedsskiftet og inn i hele første uken av august. HAN-fixturen
(`tests/fixtures/bkk_august_2026_hourly.json`) mangler `kwh` og `p_max_w` for 176
av 744 timer, fra 01.08 kl. 00 til og med 08.08 kl. 07. Det er 24 % av måneden,
mot 8 % i juli.

Hullet er fylt. Elhub-eksporten for august kom 13.09.2026, 744 timer der alle
er merket «Målt», og timene er skrevet inn med

```bash
python3 scripts/research/fyll_datahull_fra_elhub.py \
    --fixture tests/fixtures/bkk_august_2026_hourly.json \
    --elhub "_private/Måleverdier/elhub_august.csv"
```

177 timer har nå `"kwh_kilde": "elhub"`. De 176 fra utfallet, pluss 31.08 kl. 23,
som er overstyrt for hånd: HAN målte 0,0 kWh der med p_max 3293 W i samme time,
altså tpi som frøs i månedens siste time. Elhub har 1,378 kWh, og totalsummen
treffer fakturaen først med den verdien. Samme feil som 29.07 kl. 10 i
juli-fixturen, og begrunnelsen er arkivert i fixturens metadata. `p_max_w` står
fortsatt null i alle 177; Elhub har ikke effektdata.

`metadata.tpi_start_kwh` er satt til 134220,946. Tpi ved 08.08 kl. 08 er
`tpi_end` 135184,533 minus HAN-deltaene derfra og ut måneden (734,957), altså
134449,576. Trekk fra Elhub-forbruket 01.08 kl. 00 til 08.08 kl. 07 (228,630),
og du får 134220,946. Kontrollen er juli: tpi_start 133282,180 pluss
juli-forbruket 938,773 gir 134220,953, sju wattimer unna. `tpi_end_kwh` er en
avlest verdi og ligger de samme 1,378 kWh under den ekte tellerstanden som den
frosne timen, men ingen test leser feltet; summen av timene er fasiten.

### HAN mot Elhub time for time

De 567 timene som har både HAN-måling og Elhub-verdi, avviker i tre timer. Den
ene er 31.08 kl. 23 over. De to andre er 23.08 kl. 09 og 10, der HAN har 0,0 og
3,818 kWh mot Elhubs 1,092 og 2,720. Det er recorder-aggregatet som har flyttet
deltaet mellom to nabotimer, samme mønster som 2. pinsedag 2026. Summen av paret
stemmer på 6 Wh, og 23.08 er en søndag, så begge timene er natt/helg og
dag/natt-splitten rører seg ikke. De står som målt.

### Restanalysen holdt

Før Elhub-dataen kom, ble hullet anslått ved å trekke det målte fra fakturaen.
Anslaget kan nå måles mot fasit:

| Størrelse                 |     Anslått |       Elhub | Avvik       |
| ------------------------- | ----------: | ----------: | ----------- |
| Forbruk i hullet          | 230.005 kWh | 230.008 kWh | 3 Wh        |
| Herav dag                 | 125.697 kWh | 125.694 kWh | 3 Wh        |
| Herav natt/helg           | 104.308 kWh | 104.314 kWh | 6 Wh        |
| Implisitt Norgespris-sats |    -100.189 |    -100.158 | 0.031 øre/kWh |

Tallene gjelder alle 177 Elhub-fylte timene, altså 80 dag-timer og 97
natt/helg-timer. Anslaget bommet med tre wattimer på en måned. Det var en
plausibilitetssjekk og ikke en attest, men det var en god en.

## Spotpris-utfall 17., 23. og 31. august

Nytt denne måneden: `sensor.nord_pool_no5_current_price` har hull i
HA-recorderen. 48 timer manglet helt, fordelt på tre døgn som alle begynner ved
døgnskiftet: 17.08 kl. 01-16, 23.08 kl. 01-09 og 31.08 kl. 01-23. Dette er
første gang spotserien har hull siden januar 2026.

Time 00 de tre døgnene hører til hullet selv om recorderen har en verdi der.
Sensoren går `unknown` presis kl. 00:00:00 og `unavailable` åtte sekunder
senere, og HAs statistikk-kompilator regner timesnittet bare over numeriske
states. Da blir den siste numeriske staten før midnatt, altså 23:45-kvarteret
kvelden før, båret gjennom hele time 00. Verdien er ikke en måling av timen,
den er kvelden før om igjen.

Beviset ligger i tallene. Utfallet 04.09, som er utenfor denne fakturaen, har
mean = min = max = 1.33741 for time 00, identisk med staten fra 03.09 kl. 23:45.
For august:

| Døgn  | Recorder time 00 | Forrige døgn 23:45 | Avvik (rå) | Publisert time 00 | Utfall              |
| ----- | ---------------- | ------------------ | ---------- | ----------------- | ------------------- |
| 17.08 | 1.26647          | 1.26293            | 0.354 øre  | 1.30852           | fylt som randtime   |
| 23.08 | 1.36097          | 1.36097            | 0          | 1.438275          | fylt som randtime   |
| 31.08 | 1.35957          | 1.35947            | 0.01 øre   | 1.364737          | fylt for hånd       |

Avviks-kolonnen er den rå avstanden, altså recorder-verdien mot arkivprisen slik
den står. 23.08 er identisk til siste desimal. De to andre avviker med noen
tideler av en øre, som er kurs-årgangen mellom recorderens publiseringskurs og
arkivets, og scriptet regner den inn: 16.08 har årgang 1,00281, og med den blir
avstanden for 17.08 0,00 øre, ikke 0,354. Tabellen ser altså ut som om regelen
bommer på 17.08, men det gjør den ikke.

Dette forklarer også hvorfor recorder-verdien lå *under* alle fire
kvarterprisene i timen: den kom aldri fra timen.

51 timer er fylt fra Nord Pools publiserte Final-kvarterpriser med
`scripts/research/fyll_spothull_fra_nordpool.py`, merket
`"spot_kilde": "nordpool_publisert"` i fixturen: de 48 tomme timene og alle tre
randtimene. To av randtimene kjenner scriptet igjen selv, og regelen har to krav som begge må være oppfylt: verdien ligger
innenfor 0,5 øre/kWh av forrige døgns 23:45-kvarter, og den ligger minst
0,2 øre/kWh lenger unna sin egen publiserte time enn den ligger fra kvarteret.
Begge avstandene måles mot kurs-årgangsjustert pris, ikke mot arkivprisen rå:
23:45-kvarteret justeres med årgangen kvelden før, siden det er derfra verdien
er båret, og timens egen pris med årgangen på sitt eget døgn. Uten det bommer en
ekte måling på sin egen publiserte time på en årgangsdag av en grunn som ikke
har noe med hull å gjøre, og krav 2 slår til på en gyldig verdi. Kolonnen
«Publisert time 00» i tabellen over er det andre kravet: de to fylte randtimene
bommer 4,2 og 7,7 øre på sin egen time, og 31.08 bommer 0,52. Nærheten til
23:45-kvarteret alene ville ikke holdt. På en natt med flat pris ligger en ekte
måling i time 00 også innenfor 0,5 øre av kvarteret kvelden før, og da ville
scriptet overskrevet en gyldig måling og merket den med en årsak som ikke er
sann. Er verdien nær begge, gjetter ikke scriptet: timen blir stående som målt
og skrevet ut, så den kan avgjøres for hånd med `--overstyr`.

Årgangen måles av døgnets egne ekte timer, så et helt hullet døgn, et døgn med
under seks ekte timer, eller et døgn der faktoren ikke er konstant, gir ingen
målt årgang. Da er ikke krav 2 etterprøvbart, og timen blir stående. 31.08 kl. 00
er akkurat det tilfellet: hele døgnet er hullet, så det er ingen ekte timer å
måle årgangen på, og de 0,52 øre timen bommer på sin egen publiserte time ligger
innenfor det en årgang kunne forklart. Scriptet lot den derfor stå og skrev den
ut i stedet for å merke den `randtime_forrige_kvarter`; den påstanden holder
ikke når forutsetningen for regelen ikke lar seg måle, og en fixture som påstår
noe usant om seg selv er verre enn et åpent hull.

Timen er avgjort for hånd 13.09.2026 og fylt med den publiserte prisen 1.364737.
Begrunnelsen: 0,52 øre fra sin egen time mot 0,01 øre fra 23:45-kvarteret
kvelden før er femti ganger nærmere gårsdagen enn sin egen time. De to andre
randtimene i august viser samme mønster, 4,2 og 7,7 øre fra egen time mot 0 og
0,35 fra kvarteret, og 31.08 er den tetteste av de tre mot kvelden før. De rå
avstandene er entydige selv om krav 2 ikke kan prøves, og kostnaden ved å ta
feil er under ett øre på fakturaen. Kommandoen var:

```
python3 scripts/research/fyll_spothull_fra_nordpool.py \
    --fixture tests/fixtures/bkk_august_2026_hourly.json \
    --overstyr "2026-08-31T00:00:00+02:00=<begrunnelse>"
```

Timen står under `overstyrte_timer`, ikke under `randtimer`, nettopp fordi
regelen aldri kjente den igjen. Går det andre veien, altså at årgangen dytter en
ekte randtime ut av krav 1, blir timen også stående og skrevet ut.

Begrunnelsen for de to automatisk fylte randtimene arkiveres i fixturens
metadata under `spothull.fylt_fra_nordpool.randtimer`, den håndavgjorte under
`overstyrte_timer`. Begge deler står gjennom senere kjøringer av scriptet.
`verify_norgespris_eksakt.py` holder alle 51 utenfor
prisfidelitets-sammenligningen, ellers ville den målt arkivet mot seg selv.

Hvorfor den offisielle Nord Pool-integrasjonen faller ut presis ved døgnskiftet
vet vi ikke. HA-loggen dekker bare siste boot, så nettene det gjelder er borte.

## Time-for-time-verifisering

Kjørt med `scripts/research/verify_invoice_hourly.py` over alle 744 timene,
altså 567 HAN-målte og 177 fra Elhub:

| Linje            |  Beregnet |   Faktura |    Avvik | Status |
| ---------------- | --------: | --------: | -------: | ------ |
| Total kWh        |   964.964 |   964.967 |   -3 Wh  | OK     |
| Forbruk dag kWh  |   475.502 |   475.519 |  -17 Wh  | OK     |
| Forbruk natt kWh |   489.462 |   489.448 |  +14 Wh  | OK     |
| Energiledd dag   |    171.00 |    171.01 |   -0.01  | OK     |
| Energiledd natt  |     64.24 |     64.24 |    0.00  | OK     |
| Forbruksavgift   |     86.01 |     86.00 |   +0.01  | OK     |
| Enovaavgift      |     12.06 |     12.06 |    0.00  | OK     |
| Kapasitet        |    250.00 |    250.00 |    0.00  | OK     |
| Nettleie sum     |    583.32 |    583.31 |   +0.01  | OK     |
| Norgespris-komp  |   -986.31 |   -986.38 |   +0.07  | OK     |
| Total            |   -402.99 |   -403.07 |   +0.08  | OK     |

Alle linjer er innenfor toleransen i
[prosedyren](neste-maaned-prosedyre.md#6-sjekk-avvik-mot-april): total innenfor
50 Wh, dag og natt innenfor 100 Wh hver, avgiftslinjene innenfor 2 øre.

Måneden er også spilt gjennom den ekte coordinatoren
(`tests/test_coordinator_replay.py`, `FAKTURA_MAP["august_2026"]`). Den lander på
964.965 kWh totalt, 475.56 dag, 489.41 natt, snitt topp 3 på 4,40 kW og
Norgespris-kompensasjon -986,31 kr. Alle innenfor testens toleranser.
`tests/test_replay_hendelser.py` avstemmer august mot Elhub-intervallenergi og
Final-priser med poll-jitter og månedsskifte; august flyttet fra `UFULLSTENDIGE`
til `AVSTEMBARE` i samme slengen.

## Kapasitetstrinn-verifisering

| Faktura                 | Vår beregning               | Match? |
| ----------------------- | --------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2) | `kapasitetstrinn_nummer: 2` | Match  |
| Pris: 250 kr/mnd        | `kapasitetsledd: 250`       | Match  |

Maks effekt fra fakturaen (timesnitt-kW, topp 3 dager):

- 4,790 kW, målt 23.08.2026 kl. 12:00
- 4,299 kW, målt 02.08.2026 kl. 16:00
- 4,111 kW, målt 05.08.2026 kl. 17:00

Snitt topp 3 = 4,400 kW, innenfor 2-5 kW-trinnet.

To av de tre toppene, 02.08 og 05.08, ligger inne i HAN-hullet, så `p_max_w` er
null der. De lar seg likevel etterprøve, for BKK regner kapasitetsleddet av
timesnitt-kW, og en times energi i kWh *er* timesnittet i kW. Elhub gir dermed
alle tre:

| Dag og time    | Faktura  |      Vår | Avvik   |
| -------------- | -------: | -------: | ------- |
| 23.08 kl. 12   | 4,790 kW | 4,799 kW | +8,7 W  |
| 02.08 kl. 16   | 4,299 kW | 4,286 kW | -12,8 W |
| 05.08 kl. 17   | 4,111 kW | 4,105 kW | -5,7 W  |
| Snitt topp 3   | 4,400 kW | 4,397 kW | -3,3 W  |

Samme dag og samme time i alle tre, og alle tre innenfor det dokumenterte
3-20 W-spennet. De to som lå i hullet treffer altså like godt som den målte.
Fjerdeplassen er 4,006 kW (22.08), godt under fakturaens tredjeplass, så ingen
dag motsier fakturaens topp 3.

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -102,22 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Eksakt-sjekken, Elhub-kWh ganget med publiserte Final-priser over hele måneden:
**-986,38 kr mot fakturaens -986,38 kr, avvik +0,000**. Alle 744 timene har
publisert Final-pris i kvarterarkivet, så sjekken er dekkende. Det er det beste
treffet av de fire månedene som har den (mai -0,001, juni +0,005, juli +0,003).

Prisfidelitet mot publisert, målt over de 517 timene som både har HAN-måling og
ekte recorder-pris: 218 bit-like, 418 innenfor 0,01 øre/kWh. Én dag med
kurs-årgang, 16.08 (søndag), HA/publisert = 1.00281 konstant over alle 24 timer.
Det er det vanlige søndagsmønsteret. Regnet med recorder-prisene lander
Norgespris-summen for de HAN-målte timene 0,18 kr fra Final-summen, og 16.08 står
for 0,12 av dem.

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

Satsene er uendret fra juli. August er fortsatt sommersats for forbruksavgift
(8,913 øre/kWh inkl. mva). Måneden har ingen helligdager, så
dag/natt-klassifiseringen er ren ukedag/helg.

## Sammenligning med juli 2026

| Parameter               | Juli            | August          | Endring             |
| ----------------------- | --------------- | --------------- | ------------------- |
| Antall dager            | 31              | 31              | uendret             |
| Totalt forbruk          | 938.76 kWh      | 964.97 kWh      | +26.21 kWh (+3 %)   |
| Dag-forbruk             | 514.41 kWh      | 475.52 kWh      | -38.89 kWh          |
| Natt-forbruk            | 424.35 kWh      | 489.45 kWh      | +65.10 kWh          |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret             |
| Nettleie                | 586.10 kr       | 583.31 kr       | -2.79 kr            |
| Norgespris-kompensasjon | -807.50 kr      | -986.38 kr      | -178.88 kr          |
| Total                   | -221.40 kr      | -403.07 kr      | -181.67 kr          |

Forbruket tar seg litt opp igjen, men hele økningen ligger på natt/helg mens
dagforbruket faller. Nettleien er derfor så godt som uendret, siden
natt-tariffen er under halvparten av dag-tariffen. At fakturaen likevel svinger
181 kr er ren spotpris: kompensasjonen steg 22 %.

## Status

Komplett. Linje for linje mot `tests/test_faktura_bkk.py`
(`FAKTURA_AUGUST_2026`), time for time mot `verify_invoice_hourly.py` og
`verify_norgespris_eksakt.py`, og gjennom coordinatoren i
`tests/test_coordinator_replay.py` og `tests/test_replay_hendelser.py`.

Forbeholdet som står igjen er proveniensen, ikke regnestykket: 177 av 744 timer
har kWh fra Elhub og ikke fra HAN, og alle 177 mangler `p_max_w`. Månedens topp 3
er likevel etterprøvd, siden timesenergien er timesnitt-effekten.

## Konklusjon

Integrasjonen beregner nettleie korrekt for august 2026. Alle fakturaposter
matcher, alle tre effekttoppene treffer innenfor 13 W, Norgespris-linjen treffer
på null øre mot publiserte Final-priser, og satsene i `dso.py` og `const.py` er
uendret fra juli og konsistente med det BKK fakturerer.
