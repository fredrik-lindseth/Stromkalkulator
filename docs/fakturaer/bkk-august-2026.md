# Verifiseringsrapport: BKK-faktura august 2026

**Fakturanr:** 012345687
**Periode:** 01.08.2026 - 01.09.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-09-11 (linje for linje). Time-for-time er delvis, se under.

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

Hullet er **ikke fylt ennå**: Elhub-eksporten for august er ikke lastet ned.
Når `_private/Måleverdier/elhub_august.csv` ligger på plass, fylles timene med

```bash
python3 scripts/research/fyll_datahull_fra_elhub.py \
    --fixture tests/fixtures/bkk_august_2026_hourly.json \
    --elhub "_private/Måleverdier/elhub_august.csv"
```

`metadata.tpi_start_kwh` er også `null` fordi måleren ikke rapporterte ved
periodestart. Den utledes som tpi(08.08 kl. 08) minus Elhub-forbruket
01.08-08.08, og må settes før august kan legges til i
`tests/test_coordinator_replay.py`.

### Restanalyse: er fakturaen konsistent i hullet?

Samme plausibilitetssjekk som for juli. Fakturaen minus det vi faktisk har målt
gir et restforbruk og en implisitt Norgespris-sats; ligger den innenfor spennet
av faktiske timepriser i hullet, henger fakturaen sammen med modellen vår.

| Størrelse                    | Verdi                                 |
| ---------------------------- | ------------------------------------- |
| Restforbruk                  | 230.005 kWh (125.697 dag, 104.308 natt) |
| Fordelt på                   | 80 dag-timer, 96 natt/helg-timer      |
| Snitt dag                    | 1.571 kWh/h                           |
| Snitt natt/helg              | 1.087 kWh/h                           |
| Implisitt Norgespris-sats    | -100.186 øre/kWh                      |
| Faktiske timesatser i hullet | -138.780 til 38.256 øre/kWh           |
| Uvektet snitt av timesatsene | -101.037 øre/kWh                      |

Den implisitte satsen ligger innenfor spennet og tett på det uvektede snittet.
Døgnprofilen (1.57 kWh/h dag mot 1.09 natt) er den normale for husstanden.
Fakturaen er konsistent med modellen også der vi mangler måling. Dette er en
plausibilitetssjekk, ikke en attest.

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

| Døgn  | Recorder time 00 | Forrige døgn 23:45 | Avvik (rå) | Publisert time 00 |
| ----- | ---------------- | ------------------ | ---------- | ----------------- |
| 17.08 | 1.26647          | 1.26293            | 0.354 øre  | 1.30852           |
| 23.08 | 1.36097          | 1.36097            | 0          | 1.438275          |
| 31.08 | 1.35957          | 1.35947            | 0.01 øre   | 1.364737          |

Avviks-kolonnen er den rå avstanden, altså recorder-verdien mot arkivprisen slik
den står. 23.08 er identisk til siste desimal. De to andre avviker med noen
tideler av en øre, som er kurs-årgangen mellom recorderens publiseringskurs og
arkivets, og scriptet regner den inn: 16.08 har årgang 1,00281, og med den blir
avstanden for 17.08 0,00 øre, ikke 0,354. Tabellen ser altså ut som om regelen
bommer på 17.08, men det gjør den ikke.

Dette forklarer også hvorfor recorder-verdien lå *under* alle fire
kvarterprisene i timen: den kom aldri fra timen.

Alle 51 timene er fylt fra Nord Pools publiserte Final-kvarterpriser med
`scripts/research/fyll_spothull_fra_nordpool.py`, merket
`"spot_kilde": "nordpool_publisert"` i fixturen. Randtimene kjenner scriptet
igjen selv, og regelen har to krav som begge må være oppfylt: verdien ligger
innenfor 0,5 øre/kWh av forrige døgns 23:45-kvarter, og den ligger minst
0,2 øre/kWh lenger unna sin egen publiserte time enn den ligger fra kvarteret.
Begge avstandene måles mot kurs-årgangsjustert pris, ikke mot arkivprisen rå:
23:45-kvarteret justeres med årgangen kvelden før, siden det er derfra verdien
er båret, og timens egen pris med årgangen på sitt eget døgn. Uten det bommer en
ekte måling på sin egen publiserte time på en årgangsdag av en grunn som ikke
har noe med hull å gjøre, og krav 2 slår til på en gyldig verdi. Kolonnen
«Publisert time 00» i tabellen over er det andre kravet: de tre randtimene
bommer 4,2, 7,7 og 0,52 øre på sin egen time. Nærheten til
23:45-kvarteret alene ville ikke holdt. På en natt med flat pris ligger en ekte
måling i time 00 også innenfor 0,5 øre av kvarteret kvelden før, og da ville
scriptet overskrevet en gyldig måling og merket den med en årsak som ikke er
sann. Er verdien nær begge, gjetter ikke scriptet: timen blir stående som målt
og skrevet ut, så den kan avgjøres for hånd med `--overstyr`.

Regelen er ikke uttømmende. Årgangen måles av døgnets egne ekte timer, så et
helt hullet døgn, et døgn med under seks ekte timer, eller et døgn der faktoren
ikke er konstant, gir ingen målt årgang. Da faller scriptet tilbake til rå
publisert pris som før, og utskriften sier «kurs-årgang umålt». 31.08 er
akkurat det tilfellet: den fylles med umålt årgang, og de 0,52 øre den bommer på
egen time ligger innenfor det en årgang kunne forklart. Beviset for at den er
båret er likevel sterkt, siden 0,01 øre fra 23:45-kvarteret er tilfeldig for en
måling. Går det andre veien, altså at årgangen dytter en ekte randtime ut av
krav 1, blir timen stående og skrevet ut.

Begrunnelsen for de fylte randtimene arkiveres i fixturens metadata under
`spothull.fylt_fra_nordpool.randtimer`.
`verify_norgespris_eksakt.py` holder alle 51 utenfor
prisfidelitets-sammenligningen, ellers ville den målt arkivet mot seg selv.

Hvorfor den offisielle Nord Pool-integrasjonen faller ut presis ved døgnskiftet
vet vi ikke. HA-loggen dekker bare siste boot, så nettene det gjelder er borte.

## Time-for-time-verifisering (delvis)

Kjørt med `scripts/research/verify_invoice_hourly.py` over de 568 timene som har
måling. Volumlinjene kan ikke sammenlignes med fakturaen før hullet er fylt, og
er merket DELVIS:

| Linje                  | Beregnet (568 t) | Faktura | Status |
| ---------------------- | ---------------- | ------- | ------ |
| Total kWh              | 734.962          | 964.967 | DELVIS |
| Forbruk dag kWh        | 349.822          | 475.519 | DELVIS |
| Forbruk natt kWh       | 385.140          | 489.448 | DELVIS |
| Kapasitet              | 250.00           | 250.00  | OK     |
| Norgespris-komp        | -755.95          | -986.38 | DELVIS |

Kapasitetslinjen er den eneste som er sammenlignbar, og den treffer.

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

To av de tre toppene (02.08 og 05.08) ligger inne i HAN-hullet og kan ikke
etterprøves. Den tredje kan: replay gir 4,802 kW på 23.08 kl. 12:00, altså
12 W over fakturaens 4,790 og innenfor det dokumenterte 3-20 W-spennet. Vår
høyeste målte dag utenom den er 4,011 kW (22.08), godt under fakturaens
andreplass, så ingen målt dag motsier fakturaens topp 3.

Trinnvalget står uansett trygt: snittet av våre tre høyeste *målte* dager er
4,224 kW, og både det og fakturaens 4,400 ligger klart innenfor 2-5 kW.

## Norgespris-verifisering

| Parameter           | Faktura                | Vår kode                                 | Match? |
| ------------------- | ---------------------- | ---------------------------------------- | ------ |
| Norgespris fastpris | (implisitt 50 øre/kWh) | `NORGESPRIS_INKL_MVA_STANDARD = 0.50`    | Ja     |
| Strømstøtte         | 0 (Norgespris-kunde)   | `stromstotte = 0.0` når `har_norgespris` | Ja     |
| Kompensasjon        | -102,22 øre/kWh snitt  | Beregnes time-for-time av BKK            | N/A    |

Eksakt-sjekken (Elhub-kWh x publiserte Final-priser) kan ikke kjøres før
Elhub-CSV-en finnes. Prisdekningen er på plass: alle 744 timene har publisert
Final-pris i kvarterarkivet.

Prisfidelitet mot publisert, målt over de 517 timene som både har HAN-måling og
ekte recorder-pris: 218 bit-like, 418 innenfor 0,01 øre/kWh. Én dag med
kurs-årgang, 16.08 (søndag), HA/publisert = 1.00281 konstant over alle 24 timer.
Det er det vanlige søndagsmønsteret. Regnet med recorder-prisene lander
Norgespris-summen for de målte timene 0,18 kr fra Final-summen, og 16.08 står
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

Linje-for-linje-attesten er komplett: integrasjonens satser og formler
reproduserer fakturaen innenfor avrundingsfeil, verifisert via
`tests/test_faktura_bkk.py` (fixture `FAKTURA_AUGUST_2026`).

Time-for-time-verifiseringen er **delvis** og venter på Elhub-eksporten for
august. Det som gjenstår når CSV-en er på plass:

1. Fyll de 176 timene med `fyll_datahull_fra_elhub.py`
2. Sett `metadata.tpi_start_kwh`
3. Kjør `verify_invoice_hourly.py` og `just verify-norgespris` på nytt
4. Legg august inn i `FAKTURA_MAP` i `tests/test_coordinator_replay.py`
5. Oppdater volumtabellen og statusen i denne rapporten

## Konklusjon

Integrasjonen beregner nettleie korrekt for august 2026. Alle fakturaposter
matcher, kapasitetstrinnet treffer, og satsene i `dso.py` og `const.py` er
uendret fra juli og konsistente med det BKK fakturerer. Verifiseringen av
volumlinjene mot egne målinger står igjen, og er blokkert på data vi ikke har
fordi HAN-leseren var nede den første uken av måneden.
