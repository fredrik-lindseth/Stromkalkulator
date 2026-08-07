# Verifiseringsrapport: BKK-faktura juli 2026

**Fakturanr:** 012345686
**Periode:** 01.07.2026 - 01.08.2026 (31 dager)
**Nettselskap:** BKK (NO5, standard avgiftssone)
**Avtale:** Norgespris (fast 50 øre/kWh inkl. mva)
**Verifisert dato:** 2026-08-07

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
rundt kl. 11 og var nede ut fakturaperioden. HAN-fixturen
(`tests/fixtures/bkk_juli_2026_hourly.json`) har derfor `kwh: null` og
`p_max_w: null` for 61 av 744 timer, fra 29.07 kl. 11 til og med 31.07 kl. 23.
Spotprisen er komplett for alle 744 timene.

Hullet er **ikke fylt**. Elhub er kWh-fasiten, men Elhub-eksporten som ligger
lokalt (`_private/Måleverdier/elhub_juli.csv`) dekker bare 01.07-05.07 (120
timer), altså ingenting av hullet. Alternativet, å fordele fakturaens
restforbruk utover de 61 timene, ville gjort verifiseringen sirkulær: vi
hadde da bekreftet fakturaen med tall hentet fra fakturaen. Timene står som
`null`, og `scripts/research/verify_invoice_hourly.py` holder dem utenfor
summene og merker volumlinjene `DELVIS`. Bakgrunnen ligger i fixturens
`metadata.datahull`.

**Gjenstår:** ny eksport av hele juli fra minside.elhub.no til
`_private/Måleverdier/elhub_juli.csv`, deretter fylle `kwh` for de 61 timene
derfra (`p_max_w` forblir `null`, Elhub har ikke effekt). Da kan
time-for-time-verifiseringen og Elhub x Final-sjekken kjøres fullt ut, og
juli kan legges til i `FAKTURA_MAP` i `tests/test_coordinator_replay.py`.

### Restanalyse: er fakturaen konsistent i hullet?

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
`scripts/research/verify_invoice_hourly.py`. Volumlinjene dekker bare de 683
målte timene og kan derfor ikke sammenlignes med fakturaen:

| Linje                  | Beregnet (683 timer) | Faktura (744 timer) | Status |
| ---------------------- | -------------------- | ------------------- | ------ |
| Total kWh              | 858.250              | 938.763             | DELVIS |
| Forbruk dag kWh        | 449.454              | 514.414             | DELVIS |
| Forbruk natt kWh       | 408.796              | 424.349             | DELVIS |
| Nettleie sum           | 552.52               | 586.10              | DELVIS |
| Norgespris-komp        | -719.30              | -807.50             | DELVIS |
| Total inkl. Norgespris | -166.79              | -221.40             | DELVIS |
| Kapasitet              | 250.00               | 250.00              | OK     |

Kapasitetslinjen er den eneste volum-avhengige linjen som lar seg verifisere
fullt ut, fordi alle tre topp-effektene ligger før utfallet. Se under.

Norgespris-kompensasjonen over de 683 målte timene blir -719.30 kr med
HA-recorderens priser og -719.10 kr med Nord Pools publiserte Final-priser.
Differansen på 0.20 kr er den kjente prisårgang-effekten: fire søndager
(05.07, 12.07, 19.07, 26.07) har konstant kursavvik mellom recorder og
publisert, se [research/norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).
Juli hadde 18 timer med spot under 50 øre inkl. mva der kunden betaler
mellomlegg. Måneden har ingen helligdager, så dag/natt-klassifiseringen er ren
ukedag/helg.

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
under fakturaen og snitt 4,703 kW. Avviket på 11.07 er større enn det
dokumenterte spennet på 3-8 W per topp, men langt fra trinngrensen på 5,0 kW,
så trinnvalget står trygt. Verdt å følge med på om spennet skal utvides i
[begrensninger.md](../begrensninger.md) når flere måneder er målt.

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

## Status og gjenstående

Linje-for-linje-attesten er komplett: integrasjonens satser og formler
reproduserer fakturaen innenfor avrundingsfeil, verifisert via
`tests/test_faktura_bkk.py` (fixture `FAKTURA_JULI_2026`).

Time-for-time-verifiseringen er **delvis**. HAN-utfallet 29.-31. juli gjør at
volumlinjene ikke lar seg reprodusere fra egne måledata, og Elhub-CSV-en som
ligger lokalt dekker ikke perioden. Restanalysen over viser at fakturaen er
konsistent med modellen i hullet, men det er en plausibilitetssjekk, ikke en
reproduksjon. Juli er derfor ikke lagt til i
`tests/test_coordinator_replay.py` og ikke tatt med i
`docs/research/_generated/verify_norgespris_eksakt.md`-tabellen.

For å lukke dette trengs en ny Elhub-eksport for hele juli. Se HAN-utfall-
seksjonen over.

## Konklusjon

Integrasjonen beregner nettleie korrekt for juli 2026. Alle fakturaposter
matcher på øret (maks 0.01 kr på totalen, som skyldes fakturaens
fem-desimalers Norgespris-sats), kapasitetstrinnet treffer, og satsene i
dso.py og const.py er
uendret fra juni og konsistente med det BKK fakturerer. Den fulle
time-for-time-reproduksjonen står igjen til Elhub-dataene for hele måneden er
hentet ned.
