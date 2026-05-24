# Beregninger

Konseptene integrasjonen bruker. Implementasjon i [`coordinator.py`](../custom_components/stromkalkulator/coordinator.py) og [`const.py`](../custom_components/stromkalkulator/const.py). Avgiftsoppslag og sensorer: [domain-rules.md](domain-rules.md), [sensorer.md](sensorer.md).

## Mva-konvensjon

Alle priser i interne formler er inkl. mva, samme enhet som strømstøtte-terskelen og Norgespris.

Spotpris fra HA-core nordpool leveres eks. mva. Coordinator normaliserer ved oppstart av hver beregningssyklus, og bruker så `spot_price` (inkl. mva) i resten av kjeden. Konfig-flagget `spotpris_inkl_mva` lar brukere med spesielle sensorer overstyre.

For eksportinntekt (plusskunder) brukes spotpris eks. mva, siden privatperson ikke har utgående mva. Se [incident 004](incidents/004-spotpris-mva-feilbehandling.md).

## Nettleie

Nettleie = energiledd + kapasitetsledd.

### Kapasitetsledd

Bestemmes av snittet av maks timesforbruk på de tre dagene med høyest forbruk i måneden. Vi sporer høyeste fullførte time per dag (samme metode som Elhub), velger topp-3, snittet bestemmer trinn.

Trinn-tabell og priser ligger per nettselskap i [`dso.py`](../custom_components/stromkalkulator/dso.py).

### Energiledd

Skiller mellom dag og natt/helg:

- **Dag**: hverdager 06:00-22:00, ikke helligdager
- **Natt/helg**: 22:00-06:00, helger og helligdager hele døgnet

Bevegelige helligdager (påske, pinse, Kristi himmelfartsdag) regnes fra påskeformelen.

Noen DSO-er (Glitre Nett, Tensio TN/TS) bruker `helg_som_natt: false`: kun klokkeslett styrer dag/natt. Helger og helligdager er som vanlige hverdager der.

DSO-en lagrer ren energiledd. Coordinator legger på offentlige avgifter og mva basert på avgiftssone.

## Offentlige avgifter (2026)

| Sone         | Forbruksavgift | Enova    | Sum eks. mva | MVA |
| ------------ | -------------- | -------- | ------------ | --- |
| Standard     | 7,13 øre       | 1,00 øre | 8,13 øre     | 25% |
| Nord-Norge   | 7,13 øre       | 1,00 øre | 8,13 øre     | 0%  |
| Tiltakssonen | 0 øre          | 1,00 øre | 1,00 øre     | 0%  |

Fra 2026 er forbruksavgiften flat hele året, lik for Standard og Nord-Norge. Forskjellen er kun mva. Tiltakssonen har fritak for begge.

Kilde: [Skatteetaten](https://www.skatteetaten.no/satser/elektrisk-kraft/).

## Strømstøtte

Når spotpris (inkl. mva) er over terskelen, dekkes 90 % av differansen.

| År   | Terskel       | Eks. mva |
| ---- | ------------- | -------- |
| 2026 | 96,25 øre/kWh | 77 øre   |
| 2025 | 93,75 øre/kWh | 75 øre   |

Beregnes time for time. kWh-tak per måned avhenger av boligtype: bolig og fritidsbolig (fast bosted) har 5000 kWh/mnd, fritidsbolig har ingen rett. Over taket settes støtten til 0 resten av måneden. `stromstotte_gjenstaaende_kwh` viser hvor mye som er igjen.

Næring, fjernvarme og borettslag med fellesmåling støttes ikke.

Kilde: [Forskrift om strømstønad](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791).

## Norgespris

Fast pris fra nettselskapet, alternativ til spotpris.

| Sone                    | Pris inkl. mva | Mva |
| ----------------------- | -------------- | --- |
| Sør-Norge               | 50 øre/kWh     | 25% |
| Nord-Norge/Tiltakssonen | 40 øre/kWh     | 0%  |

Basispris eks. mva er 40 øre/kWh i alle soner. Norgespris-kunder får ikke strømstøtte. Over kWh-taket (5000 for bolig, 1000 for fritidsbolig) betaler du spotpris resten av måneden.

Kilde: [Regjeringens strømtiltak](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/).

## Totalpris

Summen av kraftpris (spot etter strømstøtte eller Norgespris), nettleie og kapasitetsledd-andel.

To Energy Dashboard-strategier:

- **Prissensor (kr/kWh)**: kapasitetsleddet fordeles per forventet kWh, månedstotalen blir [unøyaktig ved avvikende forbruk](../README.md#kapasitetsledd-i-energy-dashboard).
- **Akkumulert kostnad (anbefalt)**: kapasitetsleddet tikker lineært over tid uavhengig av forbruk, månedstotalen treffer fakturaen.

## Norgespris-besparelse

Sammenligner faktisk pris mot alternativet. For Norgespris-kunder: alternativet er spot etter strømstøtte. For spot-kunder: alternativet er Norgespris.

Akkumuleres time for time. Hopper over hvis spotpris-sensor er ugyldig (mer enn 2 timer uten data) for å unngå å akkumulere falsk besparelse.

`monthly_norgespris_compensation` følger BKK sin formel `(norgespris - spot) × kWh` for direkte fakturasammenligning.

## Eksportinntekt (plusskunder)

Når eksport-effektsensor er konfigurert, akkumuleres `spot_price_eks_mva × eksportert_kWh`. Privatperson har ikke utgående mva på salg av kraft, så strømleverandøren betaler eks. mva.

Netto månedskostnad = brutto kostnad minus eksportinntekt.

## Månedlig forbruk

Standard (med energi-sensor konfigurert): delta fra meter-registeret. Forbruk = `energy_sensor.state - forrige_avlesning`. Identisk med Elhub og fakturaen.

Fallback (kun effektsensor): Riemann-sum, forbruk = effekt × tid mellom oppdateringer. Gir 1-5 % avvik over en måned. Se [Nøyaktighet](#nøyaktighet).

Klassifiseres som dag eller natt/helg ved hver oppdatering. Kostnaden akkumuleres parallelt. Estimert månedstotal projiserer fra forbruket hittil og legger til kapasitetsleddet (fast).

## Månedsskifte

Ved månedsskifte arkiveres `monthly_consumption`, topp-3 effekter, kapasitetsledd og kostnader til "forrige måned"-feltene. Nåværende måned nullstilles. Lagres til disk.

Energi akkumulert i selve overgangs-syklusen havner i forrige måned.

## Nøyaktighet

Med energi-sensor konfigurert (anbefalt oppsett): forbruket leses som delta fra meter-registeret og er identisk med Elhub og fakturaen. Nettleie-linjer matcher innenfor 0,01-0,02 kr per linje (verifisert mot 6 BKK-fakturaer fra oktober 2025 til april 2026).

Uten energi-sensor: integrasjonen Riemann-summerer effektsensoren, og du får typisk 1-5 % avvik over en måned. Avviket er størst med mye av/på-utstyr (varmtvannsbereder, induksjonstopp, varmepumpe i defrost). Konfigurer en energi-sensor for å fjerne det.

Nettleie-fakturaen verifiserer kun nettleie-stien (energiledd, kapasitetsledd, avgifter). Spotpris, strømstøtte, Norgespris-besparelse og eksportinntekt fanges ikke der, og må sjekkes mot nettselskapets eller strømleverandørens egne tall. Se [verifiser-din-faktura.md](fakturaer/verifiser-din-faktura.md) for sjekkpunkter utenfor fakturaen. Manglende slik sjekk lot [incident 004](incidents/004-spotpris-mva-feilbehandling.md) gå usett i flere måneder.

Verifiserte fakturaer: [referanse.md](fakturaer/referanse.md).

## Datakilder

- Effektsensor (W) fra AMS-leser via HAN
- Spotpris (NOK/kWh) fra Nord Pool
- Strømleverandør-sensor (valgfri) for sammenligning mot avtalt pris
- Eksport-effektsensor (valgfri) for plusskunder

Oppdateres hvert minutt. Topp-3 effektdager og månedlige aggregater persisteres til disk.
