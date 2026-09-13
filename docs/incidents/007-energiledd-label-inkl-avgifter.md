# Incident 007: Energiledd-feltet ba om «inkl. avgifter», koden ville ha eks.

**Dato:** 12. september 2026
**Status:** teksten rettet i `4f1dae2`, varsel til de berørte i denne fiksen
**Berørte versjoner:** 1.12.0 til og med 1.16.0, kun oppsett med egendefinert
nettselskap

## Symptomer

Ingen bruker meldte fra. Feilen ble funnet under en synk av `translations/nb.json`
mot `strings.json`: steget for egendefinerte priser ba om energiledd
«(inkl. avgifter)» på norsk og «(incl. taxes)» på engelsk, mens malen i
`strings.json` og koden under hadde bedt om eks. mva og avgifter siden 1.12.0.

Det er nettopp derfor den er alvorlig. En bruker som taster inn en for høy sats
får tall som ser plausible ut: nettleien er høyere enn naboens, men den er også
det hos noen. Ingenting i integrasjonen sier fra, og fakturaen fra nettselskapet
kommer med et annet beløp uten at det er opplagt hvorfor.

## Rotårsak

Koden regner energiledd som ren nettleie og legger avgiftene på selv:

```python
def compute_energiledd_inkl_mva(energiledd_eks_mva: float, avgiftssone: str) -> float:
    return (energiledd_eks_mva + forbruksavgift + ENOVA_AVGIFT) * (1 + mva_sats)
```

Slik har det vært siden `6080f93`, DSO-refactoren som la om fra lagrede
inkl-mva-priser til eks-mva-priser. Den commiten gjorde tre ting riktig og én
feil: koden ble lagt om, `strings.json` ble rettet fra «(inkl. avgifter)» til
«eks. mva og eks. forbruksavgift/Enova», og en v1-til-v2-migrering konverterte
satsene som allerede lå lagret. Men `translations/nb.json` og `translations/en.json`
ble ikke rørt, og det er de to filene Home Assistant faktisk serverer. Malen er
bare kilde for oversettelsesverktøyet.

Før `6080f93` var teksten riktig: alle tre filene sa «inkl. avgifter», og koden
forventet nettopp det. Feilen oppsto altså ikke fordi noen skrev feil tekst, men
fordi en commit rettet malen og koden uten å ta med oversettelsene.

Slik så det ut i vinduet:

| Fil                    | Til og med 1.11.x | 1.12.0 til 1.16.0 | Fra 1.17.0 |
| ---------------------- | ----------------- | ----------------- | ---------- |
| `const.py` (koden)     | inkl. avgifter    | eks. avgifter     | eks.       |
| `strings.json` (malen) | inkl. avgifter    | eks. avgifter     | eks.       |
| `nb.json`              | inkl. avgifter    | inkl. avgifter    | eks.       |
| `en.json`              | inkl. avgifter    | inkl. avgifter    | eks.       |

Integrasjonen har bare nb og en, og engelsk er fallbacken for alle andre språk,
så det fantes ikke en språkkombinasjon som viste den riktige teksten i vinduet.

Teksten sto i beskrivelsen over `pricing`-steget, altså førstegangsoppsettet.
Fra 1.14.0 fikk `options`- og `reconfigure`-stegene en `data_description` under
selve feltet som sa «Ren nettleie eks. mva og avgifter», også i nb og en. Den som
gikk inn og redigerte satsen etter 1.14.0 fikk altså riktig veiledning, mens den
som satte opp for første gang fortsatt ble bedt om å ta med avgiftene.

At feilen fikk stå i to språkfiler i fem versjoner, skyldes at paritetstestene i
`test_config_flow.py` bare sammenlignet nøkkelsett på ett nivå. Tekstinnholdet
var det ingen som så på.

## Hvor mye det utgjør

Avgiftene er 7,13 øre/kWh forbruksavgift pluss 1,0 øre/kWh Enova, altså 8,13
øre/kWh eks. mva. Hvor galt det blir, avhenger av hva brukeren leste «inkl.
avgifter» som:

| Tolkning                                   | Feil per kWh (Sør-Norge) | 1500 kWh/mnd | Per år  |
| ------------------------------------------ | ------------------------ | ------------ | ------- |
| Energiledd + forbruksavgift + Enova        | 10,16 øre                | 152 kr       | 1829 kr |
| Hele linjen fra fakturaen, altså inkl. mva | 21,69 øre                | 325 kr       | 3905 kr |

Regnestykket for den første raden, med BKK-satsen som står som default i
skjemaet (28,77 øre/kWh eks. mva):

- Riktig: `(0,2877 + 0,0813) x 1,25 = 0,46125 kr/kWh`
- Tastet 0,369 etter teksten: `(0,369 + 0,0813) x 1,25 = 0,56288 kr/kWh`
- Differanse: `0,10163 kr/kWh`, som er avgiftene med mva på.

I Nord-Norge og tiltakssonen er det mindre: uten mva blir første rad 8,13
øre/kWh, og i tiltakssonen, der forbruksavgiften er fritatt, 1,00 øre/kWh.

Feilen treffer alt som bygger på energileddet: energiledd-sensorene, månedlig
nettleie, månedlig total, estimert månedskostnad og fakturaestimatet.
Strømstøtte, Norgespris og spotpris er ikke berørt.

## Reproduksjon

1. Sett opp integrasjonen på nytt og velg «Egendefinert» som nettselskap.
2. På 1.16.0 leste feltet «Energiledd dag (NOK/kWh)» med beskrivelsen
   «angi energiledd-priser i NOK/kWh (inkl. avgifter)».
3. Tast inn 0,369, altså BKKs energiledd med forbruksavgift og Enova lagt til,
   slik teksten ber om.
4. `sensor.energiledd_dag` viser 0,5629 NOK/kWh der den skulle vist 0,4613.

## Fiksen

Teksten er rettet i `4f1dae2`, i både `strings.json`, `nb.json` og `en.json`, og
`tests/test_oversettelser.py` vokter nå at de tre holder seg i synk ordrett.

De som alt har tastet feil har fortsatt tallet sitt. Denne fiksen legger til et
repair-varsel for config entries med egendefinert nettselskap:
`_check_egendefinerte_satser` i `__init__.py` reiser
`egendefinert_energiledd_<entry_id>` ved oppstart, med brukerens egne satser og
avgiftsbeløpet for sonen som plassholdere i teksten. Varselet påstår ikke at
brukeren har tastet feil, for det kan vi ikke vite, bare at teksten var
villedende og at satsen bør sjekkes mot prislisten.

Varselet er fiksbart. `ConfirmRepairFlow` alene holdt ikke: varselet reises på
nytt ved hver oppstart så lenge entryet bruker egendefinerte satser, så en ren
bekreftelse ville kommet tilbake neste gang HA startet.
`EgendefinertSatserRepairFlow` i `repairs.py` skriver derfor
`egendefinert_satser_bekreftet` på config entryet, og det er flagget sjekken
leser før den reiser varselet igjen. Oppsett som gjøres etter rettingen får
flagget satt i config-flowen med en gang, og ser aldri varselet.

## Tester

`tests/test_repairs_egendefinert.py` dekker begge sidene: at varselet reises for
et egendefinert oppsett og ikke for et kjent nettselskap eller et som alt er
bekreftet, at satsene og avgiftsbeløpet havner i teksten, at fix-flowen skriver
bekreftelsen og at den tåler et entry som er slettet i mellomtiden.

`tests/test_config_flow.py` har fått en innholdsvakt: ingen tekst som hører til
energiledd-feltene får si «inkl. avgifter» eller «incl. taxes», i noen av de tre
filene. Tekstdriften mellom filene vokter `test_oversettelser.py`; denne vokter
at innholdet stemmer med koden selv om alle tre filene er enige.

## Gjennomgang av de andre feltene

Feilen sto i to språk uten at noen merket den, så resten av skjemaet ble lest
mot koden. Ett funn: `export_power_sensor` var merket «Eksport-effektmåler
(valgfri)» uten enhet, mens coordinatoren deler avlesningen på 1000
(`coordinator.py:889`) og altså krever watt. En kW-sensor blir dermed delt på
1000 en gang for mye, og eksportinntekten blir tusen ganger for lav.
Effektmåleren for import står allerede merket «(W)», og har samme regnestykke på
linje 859. Labelen og beskrivelsen på eksport er rettet i alle tre filene.

Det funnet er mindre alvorlig enn energiledd-feilen, ikke mer. En månedlig
eksportinntekt nær null er synlig gal for den som har solceller, så feilen
melder seg selv. En nettleie som er 10 øre/kWh for høy ser derimot ut som et
plausibelt tall, og ingenting avslører den før fakturaen kommer.

Enheten er likevel en regel uten håndhevelse. `EntitySelector` filtrerer bare på
`device_class="power"` for både import og eksport, og ingen leser
`unit_of_measurement`, så en kW-sensor slipper gjennom oppsettet uten et pip.
Riktig løsning er å konvertere etter enheten sensoren faktisk oppgir, eventuelt
avvise kW ved oppsett. Ikke gjort her, ført som eget punkt.

De øvrige feltene stemmer: spotpris-sensoren er merket NOK/kWh og valideres mot
øre/kWh og kr-totaler ved oppsett, energimåleren er merket kWh, Norgespris-
teksten oppgir riktige satser og kWh-grenser for begge soner, og
avgiftssone-forklaringen er den som ble rettet etter incident 003.

## Lærdom

En label er en del av regnestykket. Står det noe annet over feltet enn koden
venter, er tallet feil selv om all koden under er riktig, og ingen test av
beregningene vil noen gang oppdage det.

Malen er ikke det brukeren ser. `strings.json` ble rettet sammen med koden, så
for den som leser malen så alt riktig ut i fem versjoner. Home Assistant serverer
`translations/`, og det var de filene som løy. Retter du en tekst som hører til
en regneregel, må alle språkfilene med i samme commit, og vakten må stå på
oversettelsene, ikke på malen.

Et varsel som kommer tilbake ved hver omstart er verre enn ingen varsel, fordi
det trener brukeren i å overse Repairs. Er varselet reist fra en tilstand som
ikke endrer seg av seg selv, må bekreftelsen lagres et sted som overlever en
restart.

## Kilder

- `6080f93`, DSO-refactoren som la om koden og malen uten oversettelsene (v1.12.0)
- `4f1dae2`, synken som avdekket avviket
- `custom_components/stromkalkulator/const.py:compute_energiledd_inkl_mva`
- Skatteetatens satser for elektrisk kraft 2026 (7,13 øre/kWh forbruksavgift,
  1,0 øre/kWh Enova), som ligger til grunn for tallene over
