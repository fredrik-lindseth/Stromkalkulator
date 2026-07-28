# Incident 006: Kapasitetstrinn uten kilde for 44 nettselskap

**Dato:** 28. juli 2026
**Status:** løst
**Berørte versjoner:** alle fra og med `e369e48` (1. april 2026) til denne fiksen

## Symptomer

To brukere meldte feil priser etter at nettselskapene hevet nettleien 1. juli
2026: [#11](https://github.com/fredrik-lindseth/Stromkalkulator/issues/11) om
Nettselskapet AS og [#12](https://github.com/fredrik-lindseth/Stromkalkulator/issues/12)
om Elvia. Begge meldingene handlet om kapasitetsleddet.

En full gjennomgang mot fri-nettleie viste at problemet var langt større enn de
to. Av de 72 nettselskapene i `DSO_LIST` hadde 44 feil kapasitetstrinn. Energileddene var derimot
nesten helt riktige: bare Elvia (og Rakkestad, som følger Elvia) måtte rettes,
og etter det matcher alle fri-nettleie innenfor 0,1 øre/kWh.

## Rotårsak

To uavhengige årsaker som forsterket hverandre.

### Kapasitetstrinn ble aldri sjekket

`scripts/sjekk_mot_fri_nettleie.py` sammenlignet kun dag/natt-energiledd. Den
ukentlige CI-jobben som skulle fange pris-drift var derfor blind for
kapasitetsleddet, som er halve nettleien for en vanlig husholdning. Elvias
fastledd lå på priser fra før 1. juli og ga grønn CI hele veien.

### En mal ble kopiert inn i stedet for priser

I `e369e48` (1. april 2026, "refactor: rename TSO→DSO overalt") ble en bunke
nettselskap flippet fra `supported: False` med tomme trinn til `supported: True`.
Energileddene ble hentet per nettselskap og er riktige. Kapasitetstrinnene ble
fylt med samme mal for alle: 200/300/450/600/750/900/1200 kr/mnd.

Fjorten nettselskap fikk malens seks første trinn: Bindal, Bømlo, Haringnett,
Jæren Everk, KE Nett, Klive, Lysna, Meløy, Norefjell, R-Nett, S-Nett, Stannum,
Stram og Straumnett. Ni av dem hadde helt identisk liste hele veien opp (Bindal,
Haringnett, Lysna, Meløy, Norefjell, S-Nett, Stannum, Stram, Straumnett), og to
par til delte liste ved uhell: Everket/Midtnett og Jæren Everk/KE Nett. Alle fire
er separate selskap med egne prislister.

Ingen test fanget det. `test_dso_data_validation.py` sjekket at trinn er sortert,
positive og ikke-avtagende, altså strukturen, aldri verdiene mot en kilde. En mal
med pene, stigende tall passerer alle de sjekkene.

## Konsekvenser

Kapasitetsleddet er et fast månedsbeløp, så feilen slo direkte inn i
månedskostnad og faktura-estimat med hele avviket. Ytterpunktene:

| Nettselskap | Vårt trinn 1 | Riktig | Avvik |
| ----------- | ------------ | ------ | ----- |
| Klive       | 200 kr/mnd   | 481    | -281  |
| Vestall     | 150 kr/mnd   | 306    | -156  |
| Straumnett  | 200 kr/mnd   | 438    | -238  |
| Stram       | 200 kr/mnd   | 110    | +90   |
| Elvia       | 125 kr/mnd   | 150    | -25   |

Feilen gikk i begge retninger, så den var ikke synlig som et konsistent for
høyt eller for lavt estimat.

Tre nettselskap hadde i tillegg et topptrinn som gjentok prisen fra trinnet
under i stedet for å fortsette oppover (Havnett, Sygnir, Vevig). Det traff bare
husstander over det høyeste publiserte trinnet.

## Løsning

1. `scripts/sjekk_mot_fri_nettleie.py` sammenligner nå fastledd i tillegg til
   energiledd. Fri-nettleie oppgir kr/år eks. mva, vi lagrer kr/mnd inkl. mva,
   så sammenligningen deler på 12 og ganger med mva-faktoren for nettselskapets
   avgiftssone. Avvik teller i exit-koden på lik linje med energiledd.
2. Kapasitetstrinn for 40 av de 44 hentet fra fri-nettleie, med kilde-kommentar
   og tariffdato per oppføring. De fire siste står i punktet under.
3. Elvia, Nettselskapet og Glitre verifisert direkte mot nettselskapenes egne
   prislister, ikke bare fri-nettleie. BKK står uendret på faktura-verifiserte
   tall. Alle fire stemmer med fri-nettleie, som er en uavhengig bekreftelse på
   at konverteringen er riktig.
4. Regresjonstest: to nettselskap kan ikke ha identiske kapasitetstrinn uten at
   delingen er ført opp med begrunnelse.

Etter fiksen er det null fastledd-avvik og null energiledd-avvik mot
fri-nettleie.

### Oppfølging: de fem avvikende metodene

Fem nettselskap brukte en annen fastledd-metode enn vår modell med snitt av tre
døgnmakser, og for dem var det ikke tallene men beregningsmodellen som var feil:
Alut og Netera (`OV_TREFASE`, sikringsbasert), Fjellnett (`FEM_VEKTET_ÅR`),
Sør-Aurdal (`MND_MAX`) og Tinfos (`UKJENT`). Alle fire modellene er nå
implementert, med `fastledd_metode` per nettselskap og fri-nettleies egne
metodenavn som verdi. Drift-vakten sammenligner både metoden og satsene, hver på
sin akse, så ingen av de fem står lenger uten vakt. Se
[beregninger.md](../beregninger.md#nettselskap-med-en-annen-metode) og
[begrensninger.md](../begrensninger.md).

Tinfos publiserer ikke tariffen sin, og fri-nettleie har en åpen forespørsel til
dem. Vi regner med NVE-modellen og merker beløpet som uverifisert i stedet for å
gjette på en annen modell.

Area Nett finnes ikke i fri-nettleie som ett selskap, det er delt i fire
regioner med ulik pris, og må verifiseres manuelt.

## Tester

- `tests/test_dso_tariffer_2026.py`: Elvia og Nettselskapet per 01.07.2026, med
  kr/mnd per trinn.
- `tests/test_dso_data_validation.py::test_ingen_utilsiktet_delte_kapasitetstrinn`:
  fanger mal-symptomet direkte. Verifisert mot tilstanden før fiksen, der den
  ville avdekket tre grupper.

## Lærdom

1. **En drift-detektor som dekker halve datasettet gir falsk trygghet.** Den
   ukentlige jobben var grønn i fire måneder mens 44 nettselskap hadde feil
   fastledd. Grønn CI ble lest som "prisene stemmer", ikke som "energileddene
   stemmer". Når en sjekk innføres, hør etter hva den *ikke* dekker.
2. **Strukturvalidering er ikke verdivalidering.** Trinnene besto alle tester
   fordi de var sortert, positive og stigende. Tester som bare beskriver formen
   på data, sier ingenting om at data er riktig.
3. **Identiske verdier på tvers av uavhengige enheter er et varsel.** Fjorten
   nettselskap med samme prisliste er statistisk umulig. Den invarianten er
   billig å teste og ville fanget dette 1. april.
4. **Skill mellom hva som er researchet og hva som er fylt ut.** Samme commit ga
   riktige energiledd og oppdiktede kapasitetstrinn for de samme selskapene. At
   en del av en oppføring har kilde, gjør ikke resten troverdig. Kilde-kommentar
   per felt, ikke per nettselskap.
5. **Bruker-issues er stikkprøver, ikke sakens omfang.** To meldinger om to
   nettselskap avdekket en feil i 44. Når en bruker melder feil pris, sjekk hele
   klassen.

## Kilder

- [kraftsystemet/fri-nettleie](https://github.com/kraftsystemet/fri-nettleie) (CC-BY-4.0)
- [Elvia tariffblad 01.07.2026](https://www.elvia.no/siteassets/dokumenter/priser/2026/1-juli-2026/tariffblad_1_0_standard-tariff_privat_20260701.pdf)
- [nettselskapet.as/strompris](https://nettselskapet.as/strompris)
- [glitrenett.no nettleiepriser privatkunde](https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde)
- `e369e48` (1. april 2026): commiten som innførte malen
