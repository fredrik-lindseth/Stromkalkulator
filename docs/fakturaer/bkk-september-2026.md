# Verifiseringsrapport: BKK-faktura september 2026

**Fakturanr:** 012345688
**Periode:** 01.09.2026 - 01.10.2026 (30 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-10-04 (linje for linje og time for time).

## Fakturadata

| Priselement           | Forbruk     | Pris            | Faktura (kr) | Vår beregning (kr) | Avvik    |
| --------------------- | ----------- | --------------- | ------------ | ------------------ | -------- |
| Energiledd dag        | 557.794 kWh | 35.963 øre/kWh  | 200.60       | 200.60             | 0.00     |
| Energiledd natt/helg  | 426.997 kWh | 13.125 øre/kWh  | 56.04        | 56.04              | 0.00     |
| Kapasitet 2-5 kW      | 30 dager    | 250 kr/mnd      | 250.00       | 250.00             | 0.00     |
| Forbruksavgift        | 984.791 kWh | 8.913 øre/kWh   | 87.76        | 87.77              | 0.01     |
| Enovaavgift           | 984.791 kWh | 1.25 øre/kWh    | 12.31        | 12.31              | 0.00     |
| **Nettleie subtotal** |             |                 | **606.71**   | **606.72**         | **0.01** |
| Norgespris            | 984.791 kWh | -1.1581 kr/kWh  | -1140.51     | -1140.49           | 0.02     |
| **Total**             |             |                 | **-533.80**  | **-533.77**        | **0.03** |
| Herav MVA             |             |                 | 121.34       | 121.34             | 0.00     |

**Resultat:** Alle linjer matcher fakturaen når fakturaens eget forbrukstall
brukes. Ettøringen på forbruksavgiften er det vanlige avrundingsgulvet: 984,791 ×
8,913 øre er 87,774 kr, og BKK skriver 87,76. Norgespris-satsen er oppgitt med
fire desimaler, så linjen kan ikke replayes eksakt fra satsen. Den er etterprøvd
time for time under. Satsene er uendret fra august.

Spotprisen fortsatte opp for fjerde måned på rad: implisitt snittspot 50 + 115,81
= 165,81 øre/kWh inkl. mva, mot 152,22 i august og 136,02 i juli. Fakturaen er
til gode med 533,80 kr.

## Datagrunnlag

HAN-leseren hadde ingen utfall i september. Fixturen
(`tests/fixtures/bkk_september_2026_hourly.json`) har `kwh` og `p_max_w` for alle
720 timene. Elhub-eksporten er tatt 04.10.2026, og alle 720 timene er merket
«Målt». Summen er 984,791 kWh, akkurat fakturaens tall.

### 01.09 kl. 00 bar med seg augusts siste time

HAN og Elhub er enige til siste wattime i alle timer unntatt én. 01.09 kl. 00 har
HAN 2,027 kWh, mens Elhub har 0,651. Det er etterslepet fra august: tpi frøs
31.08 kl. 23 (HAN 0,0 kWh, Elhub 1,378, se
[august-rapporten](bkk-august-2026.md#han-utfall-01-08-august)), og da den
begynte å telle igjen, kom energien med i første time i september. 1,378 + 0,651
er 2,029, to wattimer fra HAN-deltaet.

Timen er overstyrt med Elhub-verdien og har `"kwh_kilde": "elhub"`. Begrunnelsen
er arkivert i fixturens metadata. `metadata.tpi_start_kwh` er flyttet tilsvarende,
fra avlest 135184,533 til 135185,909, så replayen ikke teller augusts energi inn i
september. Kontroll: august-fixturens tpi_end pluss Elhubs 1,378 kWh for 31.08
kl. 23 gir 135185,911, to wattimer unna.

### Spotpris-utfall 01.-02. og 04. september

`sensor.nord_pool_no5_current_price` mistet statistikk to ganger: 01.09 kl. 00
til 02.09 kl. 12, og 04.09 kl. 01-19, til sammen 56 timer. Hullene er fylt fra
publiserte Final-kvarterpriser med `fyll_spothull_fra_nordpool.py`, samme som i
august.

To grensetimer rundt hullet 04.09 er avgjort for hånd, og begge står under
`spothull.fylt_fra_nordpool.overstyrte_timer`:

| Time        | Recorder | Publisert time | Hva recorder-verdien er                       |
| ----------- | -------: | -------------: | --------------------------------------------- |
| 04.09 kl. 00 |  1.33741 |        1.28348 | 23:45-kvarteret 03.09, 0,00 øre unna           |
| 04.09 kl. 20 |  1.35628 |        1.37138 | 20:45-kvarteret 04.09, 0,00 øre unna           |

Time 00 er det kjente mønsteret fra august: staten fra kvelden før er båret
gjennom timen. Den ble ikke fanget automatisk fordi 04.09 bare har fire ekte timer
etter hullet, og regelen trenger seks for å måle kurs-årgangen. Den trengs ikke
her, for timene 22 og 23 kvelden før og 21 til 23 samme kveld treffer publisert
pris på 0,00 øre. Årgangen er altså 1 begge døgn, og avstanden på 5,39 øre til
sin egen time kan ikke forklares med kurs.

Time 20 er nytt. Sensoren kom tilbake rundt 20:45, og HAs statistikk snittet bare
over det siste kvarteret. Verdien er en ekte pris, men for et kvarter og ikke for
timen, og den bommer 1,51 øre på timesnittet. Med 58 fylte timer i alt er det
bare 662 timer igjen der recorder-prisen kan måles mot publisert pris.

Hvorfor sensoren faller ut vet vi fortsatt ikke. States-historikken for 04.09 er
purget fra HA, så nettene kan ikke etterforskes i ettertid.

## Time-for-time-verifisering

Kjørt med `scripts/research/verify_invoice_hourly.py` over alle 720 timene:

| Linje            |  Beregnet |   Faktura |    Avvik | Status |
| ---------------- | --------: | --------: | -------: | ------ |
| Total kWh        |   984.791 |   984.791 |    0 Wh  | OK     |
| Forbruk dag kWh  |   557.779 |   557.794 |  -15 Wh  | OK     |
| Forbruk natt kWh |   427.012 |   426.997 |  +15 Wh  | OK     |
| Energiledd dag   |    200.59 |    200.60 |   -0.01  | OK     |
| Energiledd natt  |     56.05 |     56.04 |   +0.01  | OK     |
| Forbruksavgift   |     87.77 |     87.76 |   +0.01  | OK     |
| Enovaavgift      |     12.31 |     12.31 |    0.00  | OK     |
| Kapasitet        |    250.00 |    250.00 |    0.00  | OK     |
| Nettleie sum     |    606.72 |    606.71 |   +0.01  | OK     |
| Norgespris-komp  |  -1140.75 |  -1140.51 |   -0.24  | OK     |
| Total            |   -534.03 |   -533.80 |   -0.23  | OK     |

Alle linjer er innenfor toleransen i
[prosedyren](neste-maaned-prosedyre.md#6-sjekk-avvik-mot-april). Norgespris-avviket
på 0,24 kr er HA-recorderens priser, se under.

Måneden er også spilt gjennom den ekte coordinatoren
(`tests/test_coordinator_replay.py`, `FAKTURA_MAP["september_2026"]`), og
`tests/test_replay_hendelser.py` avstemmer den mot Elhub-intervallenergi og
Final-priser med poll-jitter og månedsskifte. Begge er grønne.

## Kapasitetstrinn-verifisering

| Faktura                 | Vår beregning               | Match? |
| ----------------------- | --------------------------- | ------ |
| Trinn: 2-5 kW (trinn 2) | `kapasitetstrinn_nummer: 2` | Match  |
| Pris: 250 kr/mnd        | `kapasitetsledd: 250`       | Match  |

| Dag og time  | Faktura  | Elhub    | HAN      | HAN-avvik |
| ------------ | -------: | -------: | -------: | --------- |
| 16.09 kl. 16 | 5,126 kW | 5,126 kW | 5,126 kW | 0 W       |
| 27.09 kl. 17 | 4,355 kW | 4,355 kW | 4,359 kW | +4 W      |
| 05.09 kl. 16 | 4,275 kW | 4,275 kW | 4,283 kW | +8 W      |
| Snitt topp 3 | 4,585 kW | 4,585 kW | 4,589 kW | +4 W      |

Samme dag og time i alle tre. 16.09 er første enkeltdag over 5 kW siden juli,
men snittet holder seg i 2-5 kW-trinnet. Fjerdeplassen er 4,082 kW (26.09).

## Norgespris-verifisering

Eksakt-sjekken, Elhub-kWh ganget med publiserte Final-priser over hele måneden:
**-1140,51 kr mot fakturaens -1140,51 kr, avvik -0,004**. Alle 720 timene har
Final-pris i kvarterarkivet.

Prisfidelitet mot publisert, målt over de 662 timene med ekte recorder-pris: 153
bit-like og 295 innenfor 0,01 øre/kWh. Det er en klart lavere andel enn før, og
grunnen er kurs-årgang. 14 døgn i september har HA-prisen forskjøvet med en
konstant faktor mot Final, mellom 0,99769 og 1,00242. Til nå har det nesten bare
skjedd på søndager. I september gjelder det også hverdager, med en sammenhengende
rekke fra 13. til 17. og fra 23. til 28. Det rammer bare recorder-sammenligningen.
Fakturaen og eksakt-sjekken bruker Final-prisene, og der er treffet uendret.
Tabellen står i [norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).

## Avgiftsverifisering

| Avgift         | Faktura (øre/kWh) | Vår const (eks. mva) | Vår const \* 1.25 | Match? |
| -------------- | ----------------- | -------------------- | ----------------- | ------ |
| Forbruksavgift | 8.913             | 7.13                 | 8.9125            | Ja     |
| Enovaavgift    | 1.25              | 1.00                 | 1.25              | Ja     |
| MVA-sats       | 25%               | 0.25                 |                   | Ja     |

Ingen helligdager i september, så dag/natt-klassifiseringen er ren ukedag/helg.

## Sammenligning med august 2026

| Parameter               | August          | September       | Endring             |
| ----------------------- | --------------- | --------------- | ------------------- |
| Antall dager            | 31              | 30              | -1                  |
| Totalt forbruk          | 964.97 kWh      | 984.79 kWh      | +19.82 kWh (+2 %)   |
| Dag-forbruk             | 475.52 kWh      | 557.79 kWh      | +82.28 kWh          |
| Natt-forbruk            | 489.45 kWh      | 427.00 kWh      | -62.45 kWh          |
| Kapasitetstrinn         | 2-5 kW (250 kr) | 2-5 kW (250 kr) | uendret             |
| Nettleie                | 583.31 kr       | 606.71 kr       | +23.40 kr           |
| Norgespris-kompensasjon | -986.38 kr      | -1140.51 kr     | -154.13 kr          |
| Total                   | -403.07 kr      | -533.80 kr      | -130.73 kr          |

Forbruket går litt opp, men hovedsakelig flytter det seg fra natt og helg til
dagtid. Det er derfor nettleien øker med 23 kr selv om total-kWh nesten står
stille. Kompensasjonen øker 16 % på grunn av høyere spot.

## Konklusjon

Integrasjonen beregner nettleie korrekt for september 2026. Alle fakturaposter
matcher, effekttoppene treffer innenfor 8 W, Norgespris-linjen treffer på under
ett øre mot publiserte Final-priser, og satsene i `dso.py` og `const.py` er
uendret og konsistente med det BKK fakturerer.
