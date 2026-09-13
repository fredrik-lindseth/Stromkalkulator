# Avregningskontrakt

Denne kontrakten binder avregningskjernen (`avregning.py`, L1), replay-fasiten
(L2), coordinatoren (L3a), kostnadskjernen (L3b) og sensorene (L3c). Endres noe
her, endres alle fem. Den er skrevet fordi coordinatoren i dag priser hvert
poll-delta med øyeblikkspris i en åpen klokketime-bøtte, mens regelverket og
fakturaen er timebasert.

Invarianten alt hviler på:

> Samme observerte målehistorikk skal gi samme avregning uavhengig av når
> integrasjonen pollet. Energi bokføres etter avlesningens observasjonstid,
> ikke etter pollens.

Tall i dokumentet er målt, ikke antatt. Kildene står ved hvert tall.

## A. Beslutningsport: priskilde, avrunding, gyldighet, måletyper

### A1 Avregningsintervallet er klokketimen, uttrykt i UTC

Et avregningsintervall er halvåpent, `[start, slutt)`, og lagres i UTC.
Standard lengde er 60 minutter, og intervallgrensene faller sammen med
klokketimen i Europe/Oslo (som alltid er en hel UTC-time, også over
sommertidsskiftene).

Europe/Oslo brukes kun til to ting: å avgjøre dag- eller natt-tariff, og å
avgjøre hvilken fakturamåned intervallet hører til. Begge avgjøres av
intervallets **start**, ikke slutt. Alt annet regnes i UTC.

Poll-tidspunktet er behandlingstid. Det har ingen plass i avregningen utover å
være anledningen til at en avlesning ble hentet.

### A2 Timeprisen er det uvektede snittet av prisrutene

Prisen for et avregningsintervall er Nord Pools publiserte day-ahead-pris for
budområdet, i NOK/kWh eks. mva. Leveres prisen i kvartersoppløsning, er
timeprisen det **uvektede aritmetiske snittet av de fire kvarterprisene, regnet
ved full presisjon uten mellomavrunding**.

Belegget er fakturaen: Norgespris-linjen reproduseres innenfor 0,005 kr for mai,
juni og juli 2026 med Elhub-kWh ganger snittet av Nord Pools publiserte
Final-kvarterpriser. Tallene per måned står i
[verify_norgespris_eksakt.md](../research/_generated/verify_norgespris_eksakt.md),
bakgrunnen i [norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).

Alternativet var å bruke Nord Pools publiserte timespris slik den står, altså
avrundet til to desimaler NOK/MWh. Forskjellen er målt på kvarterarkivet for
NO5 (`_private/Måleverdier/nordpool_nok_kvarter_no5.json`, 3120 hele timer,
5. mai til 11. september 2026): snittet av de fire kvarterne er selv et
tosifret desimaltall i bare 810 av 3120 timer, og avstanden mellom rått snitt
og tosifret avrunding er maks 0,005 og typisk 0,0025 NOK/MWh. For en måned på
2000 kWh er det maks 1 øre, typisk et halvt. Valget er altså ikke materielt,
og da velger vi den varianten som ikke kaster informasjon.

### A2.1 Prisruten, og hva det vil si at en prisprøve er observert

I drift leser integrasjonen prisen fra brukerens prissensor, ikke fra et API
med ferdige intervaller. Da må det stå presist hva en prisprøve er, for de to
nærliggende svarene er begge målt og begge gale:

- Leser man prisprøvens observasjonstid av `last_updated`, slik B1 gjør for
  energi, får to like priser på rad aldri prøve nummer to. HA oppdaterer ikke
  `last_updated` når verdien er uendret, prøven kan ikke bæres inn (punkt 4
  under), og intervallet blir permanent `uten_pris`. Ingen strømstøtte og ingen
  Norgespris den timen.
- Lar man prisen være en tidsvektet trinnfunksjon av polltiden, blir prisen
  polltidsavhengig. Et etterslep på ti sekunder ved hver rutegrense gir en feil
  i størrelsesorden 0,2 % av prishoppet, altså 1 til 2 kr i måneden ved store
  hopp, og det bryter C2.6.

Den tredje veien er å ta på alvor at **en pris gjelder for et intervall, ikke
for et øyeblikk**. Nord Pool publiserer én pris per **prisrute**: et halvåpent
UTC-vindu på `opplosning_minutter`, forankret i hele klokketimer. I v1 er ruten
15 minutter uansett prissensor, se «Hvilken rutelengde?» under, så et
avregningsintervall på en time består av fire ruter.

En prisprøve er derfor et par, `(rutestart, verdi)`, og ikke en state-avlesning
med et klokkeslett. **B1s regel om `observed_at` fra `last_updated` gjelder
energi, ikke pris.** Observasjonstiden til en prisprøve er rutestarten, snappet
til gridet:

1. **Rute.** Prøven tilordnes ruten som inneholder **polltiden**, altså
   `avlest_kl` fra adapteren ([input-og-konfig.md
   §1](input-og-konfig.md#1-typede-inputresultater)). Prissensoren
   er en trinnfunksjon som per definisjon viser prisen for ruten som gjelder nå,
   og det er den egenskapen vi leser, ikke når staten sist ble skrevet.
2. **Settlevindu.** En prøve godtas bare når polltiden ligger minst
   `PRIS_SETTLE_SEKUNDER` (60) etter rutestart. Prissensoren oppdateres noen
   sekunder etter rutegrensen, og uten dette vinduet ville den første pollen i
   ruten hatt forrige rutes pris. Vinduet er grensen for hvor sen en priskilde
   kan være før den får feil rute, og 60 sekunder er seks ganger etterslepet som
   er målt på en Nord Pool-sensor i drift (ti sekunder).
3. **Siste godkjente prøve i ruten gjelder.** Flere polls treffer samme rute.
   Kommer de med ulik verdi, har kilden publisert på nytt inne i ruten, og
   verdien vi står igjen med er den kilden står ved.
4. **Ingen bæring.** En prøve gjelder bare sin egen rute. Verken forrige eller
   neste rutes verdi fyller et hull (C2.5).

Prisen for avregningsintervallet er det **uvektede snittet av verdiene i de
rutene som har en godkjent prøve**. Ingen tidsvekting: en rute teller likt
uansett hvor i ruten prøven ble tatt og hvor mange polls som traff den. Det er
nøyaktig samme regning som `scripts/research/verify_norgespris_eksakt.py` og
`scripts/research/maal_fordelingsregel.py` gjør mot kvarterarkivet
(`sum(kvarter) / len(kvarter) / 1000`), så drift og etterkontroll regner likt.

`pris_prover` er antall ruter med godkjent prøve og `pris_prover_ventet` er
`60 / opplosning_minutter`. Er de like, er intervallet `komplett`. Er
`pris_prover` lavere og over null, er prisen snittet av rutene som kom, og
intervallet er `delvis_pris`. Er den null, er intervallet `uten_pris` (C4).

**Hvilken rutelengde?** Prisruten er 15 minutter, alltid, og integrasjonen
spør ikke brukeren og gjetter ikke på sensoren. En kvartersnativ sensor gir da
fire ulike verdier som snittes, altså A2 eksakt. En timesoppløst sensor holder
samme verdi gjennom alle fire rutene, og det uvektede snittet av fire like tall
er timesprisen selv. Den samme regelen gir altså rett svar for begge uten å
vite hvilken sensor brukeren har, og det er grunnen til at den er valgt framfor
et felt i oppsettet. `opplosning_minutter` på prisintervallet (B2) er derfor 15
i v1. Den er ikke det samme tallet som avregningsintervallets lengde, som er 60
(A1 og A5). Radene i C8 med 60 minutters rute viser at regelen er
oppløsningsuavhengig; v1 kjører ikke i den modusen.

**Hva dette koster på invarianten.** C2.6 holder uavkortet så lenge hver rute
har minst én poll i settlevinduet sitt, altså så lenge pollintervallet er
kortere enn ruten minus 60 sekunder. Ved dagens poll hvert minutt
(`UPDATE_INTERVAL_MINUTES`) mot en rute på et kvarter er marginen stor. Skulle det ikke holde, er tapet en rute
som mangler og som merker seg selv som `delvis_pris`, ikke en pris som glir med
polltiden: verdien i en rute er den samme uansett når i ruten den ble lest.
Fasit for regelen er prøvetabellen i C8, som `tests/test_avregningskontrakt.py`
kjører.

### A3 Avrunding

Ingen mellomavrunding. Energi (kWh), pris (NOK/kWh) og kroner akkumuleres ved
full flyttallspresisjon gjennom hele kjeden. Avrunding skjer kun ved
presentasjon, i data-dicten: kWh til tre desimaler, kroner til to, priser til
fire. Det er samme presisjon som i dag.

Merverdiavgift legges på per intervall, etter avgiftssonen, på samme måte som
i dag. Priskontrakten er eks. mva hele veien inn.

### A4 Gyldighetsdato og prisårgang

Prisen hører til leveringsdøgnet, ikke til publiseringsdøgnet. På dager der
valutamarkedet var stengt på auksjonsdagen publiserer Nord Pool en foreløpig
NOK-kurs som senere korrigeres til Final. Integrasjonen ser bare den årgangen
som fantes i leveringstimen.

Kontrakten: **en avregning rettes aldri bakover.** Et lukket intervall beholder
prisen det ble avregnet med, og revisjonsstatusen (`foreløpig` eller `final`)
lagres som felt slik at diagnostikken kan vise den. Målt effekt av årgangen er
0,04 til 0,05 % av Norgespris-kompensasjonen, altså 0,1 til 0,6 kr per måned.
Etterkontroll mot faktura bruker prisarkivet og Final-priser, ikke sensoren.

### A5 Støttede måle- og avtaletyper

Versjon 1 dekker **timesavregnede forbruksmålepunkt for husholdning** i NO1 til
NO5, med spotavtale eller Norgespris.

Er noen husholdninger kvartersavregnet hos Elhub i dag? Nei. Referansepunktet i
`_private/Måleverdier/README.md` står som `Avregningsmetode: Timesavregnet` med
måleserien `KWH 60 Forbruk`. Statnetts beskrivelse av overgangen til
kvartersoppløsning sier det samme generelt: 15-minutterskravet gjelder
produksjon (utenom plusskunder), utveksling mellom nettområder og stort
forbruk, mens øvrige målere fortsetter med timesoppløsning, og Elhub
transformerer timesverdiene til kvarter før rapportering til eSett
([Statnett: Quarterly resolution and the energy markets][statnett], lest
12.09.2026). Husholdningen avregnes altså på time, selv om engrosmarkedet
kjører kvarter.

Bryteren for den dagen dette endrer seg er lengden på **avregningsintervallet**,
60 minutter i v1. Å sette den til 15 krever at målepunktet faktisk er
kvartersavregnet hos Elhub, og at prissensoren er kvartersnativ; da avregnes
hver prisrute for seg i stedet for å snittes inn i timen. Prisrutene er 15
minutter allerede i v1 (A2.1), så bryteren er ett tall og et nytt sett
fasittall, ikke en ny regel.

Ikke dekket i v1: kvartersavregnede målepunkt, næringskunder, plusskunder på
egne avregningsregler for produksjon.

## B. Datakontrakt

### B1 Energiavlesning

Det integrasjonen leser fra energisensoren. En avlesning er en observasjon av
en kumulativ teller, ikke et forbruk.

| Felt | Type | Betydning |
| --- | --- | --- |
| `source_identity` | str | Registry `unique_id` for entiteten. Identiteten til den fysiske kilden, ikke `entity_id`. |
| `entity_id` | str | Kun for visning og diagnostikk. Kan endres av brukeren uten at kilden er en annen. |
| `value_kwh` | float | Kumulativ teller, normalisert til kWh av inputadapteren (K1). |
| `observed_at` | datetime (UTC, aware) | Entitetens `last_updated`. Dette er tiden energien gjelder for, ikke polltiden. |
| `kvalitet` | enum | `malt`, `estimert`, `avvist`. |
| `schema_version` | int | Skjemaversjon for avlesningen. |

`observed_at` er alltid tidssoneklar. En naiv datetime er en programmeringsfeil
og skal kaste, ikke tolkes som lokal tid.

**Bruker uten energisensor.** Energisensoren er valgfri
([input-og-konfig.md §6](input-og-konfig.md#6-tariffmodus)), og en bruker med
effekt- og prissensor uten akkumulerende teller er et vanlig oppsett, ikke et
hjørnetilfelle. Uten teller finnes ingen avlesning i tabellen over, og brukeren
skal likevel inn i den samme boken. Coordinatoren lager da én **syntetisk
avlesning** per poll, med disse feltene:

| Felt | Verdi for en syntetisk avlesning |
| --- | --- |
| `source_identity` | Effektsensorens `unique_id`. |
| `entity_id` | Effektsensorens. |
| `value_kwh` | Ikke en tellerstand: energien i vinduet, effekten ved pollen ganget med vinduets lengde i timer. |
| `observed_at` | Polltiden, ikke effektsensorens `last_updated`. |
| `kvalitet` | `estimert`. |

Vinduet er `(forrige polltid, polltid]`, og fordelingen over
avregningsintervallene følger C1 som ellers. Fire ting følger av det, og de må
stå her, for uten dem lander to utførere ulikt:

- **`observed_at` er polltiden.** For en teller er `last_updated` tiden energien
  ble observert. For en effektprøve er energien ikke observert i det hele tatt,
  den er estimert over et vindu, og vinduets ende er pollen. Bruker man
  effektsensorens `last_updated` som vindusende, blir halen mellom siste rapport
  og pollen liggende ubokført, og en effektsensor som holder samme verdi en
  stund bokfører null mens forbruket går.
- **C2.6 gjelder ikke for denne stien.** En Riemann-sum av punktprøver avhenger
  av når prøvene ble tatt, og det er ikke til å reparere uten en teller. Det er
  `kvalitet = estimert` som sier fra om det. Vil brukeren ha polltidsuavhengig
  avregning, er svaret en energisensor.
- **Vindu lengre enn `MAX_ELAPSED_HOURS` bokføres ikke.** Er pollen forsinket
  eller HA nede, holder ikke antakelsen om konstant effekt gjennom vinduet, og
  energien forkastes framfor å gjettes. Intervallene i gapet får ingen energi:
  de er «uten data» etter C4, ikke null forbruk. Et døgn nede koster en
  effektbruker døgnet. Det er prisen for ikke å ha en teller, og den skal stå
  her framfor å oppdages i en faktura.

  Dette er ikke det coordinatoren gjorde før L3a, og setningen som sto her sa
  at det var. Den gamle koden kappet `elapsed_hours` til `MAX_ELAPSED_HOURS`
  (seks minutter) og bokførte seks minutters forbruk uansett hvor langt gapet
  var. Regelen over er strengere, og den er den som gjelder. Merk hva den
  koster: med seks minutters grense mot et pollintervall på ett minutt taper en
  effektbruker hvert vindu der pollen har glidd mer enn fem minutter. En
  teller merker ikke gapet i det hele tatt, for deltaet dekker det.
- **Er energisensoren konfigurert, gjelder telleren.** Den syntetiske stien er
  ikke en reserve som slår inn når telleren er `Utilgjengelig` en stund: når
  telleren kommer tilbake, dekker deltaet hele fraværet, og en syntetisk
  sti ved siden av ville bokført de samme kilowattimene to ganger. Stien velges
  av konfigurasjonen, ikke av tilstanden.

Energibaselinen i [input-og-konfig.md §5](input-og-konfig.md#5-energibaseline)
gjelder ikke for den syntetiske stien; det finnes ingen tellerstand å måle
delta fra. `avregning_kilde` står som effektsensorens identitet.

### B2 Prisintervall

| Felt | Type | Betydning |
| --- | --- | --- |
| `start_utc` | datetime (UTC) | Inklusiv. |
| `slutt_utc` | datetime (UTC) | Eksklusiv. |
| `nok_per_kwh_eks_mva` | float \| None | `None` betyr ingen pris. Aldri 0 som erstatning. |
| `omrade` | str | NO1 til NO5. |
| `opplosning_minutter` | int | Lengden på en prisrute (A2.1). 15 i v1. |
| `kilde` | enum | `sensor`, `arkiv`, `manuell`. |
| `revisjon` | enum | `forelopig`, `final`, `ukjent`. |
| `pris_prover` | int | Antall prisruter i intervallet med godkjent prøve (A2.1). |
| `pris_prover_ventet` | int | `60 / opplosning_minutter`, altså 1 ved timesoppløsning og 4 ved kvarter. |

Negative priser er gyldige og klippes ikke. `urimelig_verdi`-grensen i
[input-og-konfig.md](input-og-konfig.md#1-typede-inputresultater) gjelder
tallets absoluttverdi, så en negativ pris passerer den.

### B3 Avregnet intervall

| Felt | Type | Betydning |
| --- | --- | --- |
| `start_utc` | datetime (UTC) | Inklusiv. |
| `slutt_utc` | datetime (UTC) | Eksklusiv. |
| `kwh` | float | Fordelt energi, se C1. |
| `lokal_maned` | str | `YYYY-MM` i Europe/Oslo, avgjort av `start_utc`. |
| `lokal_time` | int | 0 til 23 i Europe/Oslo, avgjort av `start_utc`. |
| `tariff` | enum | `dag` eller `natt`, avgjort av `start_utc` i Europe/Oslo. |
| `pris` | prisintervall \| None | Se B2. |
| `regelkilde` | str | `{tariffmodus}:{dso_id}:{avgiftsaar}`, for eksempel `catalog:bkk:2027`. Alle tre leddene avgjøres av `start_utc`, og avgiftsåret er året i Europe/Oslo (C3). |
| `kvalitet` | enum | `komplett`, `delvis_pris`, `uten_pris`, `ufullstendig`. Priskvaliteten, med `ufullstendig` som overstyring. Se under. |
| `energikvalitet` | enum | `malt` eller `estimert`. Hvor energien i intervallet kom fra, samme enum som B1. Se under. |
| `apen` | bool | `True` så lenge `slutt_utc` ligger fram i tid. Se C6. |

**Når `kvalitet` er `ufullstendig`.** De tre første verdiene er priskvaliteten
etter A2.1 og C4, og de utelukker hverandre. `ufullstendig` er ikke en fjerde
priskvalitet, den er en overstyring: **et intervall skal ha `ufullstendig` når,
og bare når, boken står i måneden som krysset migreringen** (`ufullstendig`-
flagget i D), uansett hvor mange prisprøver intervallet fikk. Flagget fjernes
ved første månedsskifte, og intervaller bokført etter det får priskvaliteten
sin som ellers. Overstyringen gjelder også et intervall som får ny pris i en
replay: `ufullstendig` blir stående, for det som mangler er historikk, ikke
pris.

Grunnen til at den vinner over priskvaliteten, er at `kvalitet` er
overskriften brukeren og diagnostikken leser. Står måneden som `ufullstendig`
(`avregning_ufullstendig` i data-dicten), er ikke summen sammenlignbar med en
faktura, og det er den viktigste opplysningen om intervallet. Priskvaliteten
går aldri tapt: den finnes alltid på `pris.kvalitet`, og den som vil ha begge,
leser begge.

**Målt mot estimert energi.** `energikvalitet` er B1s enum, båret videre til
intervallet, og den er eget felt fordi `kvalitet` alt er opptatt av prisen.
Uten den finnes ingen måte å se at et intervall er fylt fra den syntetiske
stien, og det er nettopp den som ikke er polltidsuavhengig (C2.6).

- `malt` er standard: energien kommer fra deltaet mellom to tellerstander.
- `estimert` betyr at energi i intervallet kom fra effektstien i B1.
- `estimert` smitter og vaskes aldri bort: lander det estimert energi i et
  intervall som alt har målt energi, blir intervallet `estimert`. Blandingen
  skjer ikke i drift, siden stien velges av konfigurasjonen og ikke av
  tilstanden, men den kan oppstå ved et bytte av oppsett midt i en time, og da
  er den svakeste kilden den som gjelder for hele intervallet.
- B1s tredje verdi, `avvist`, kan aldri stå på et intervall. En avvist
  avlesning bokføres ikke, så den har ikke noe intervall å stå på; den telles i
  `avregning_avvist_kwh`.

Fastledd (kapasitetsledd) er ikke energi og hører ikke hjemme i et avregnet
intervall. Det akkumuleres over tid mot en egen NOK-per-periode-flate og
avstemmes i sak 33f81xu.

## C. Invarianter og fordelingsregel

### C1 Fordelingsregel: jevnt over tid

Et godkjent målerdelta mellom to avlesninger fordeles **jevnt over tid** på de
avregningsintervallene vinduet `(forrige observed_at, ny observed_at]` dekker,
prorata på sekunder i hvert intervall.

Valget er tatt med Elhub som dommer, og det koster noe å ta det. Målingen ligger
i `scripts/research/maal_fordelingsregel.py` (juni 2026: 720 timer Elhub-kWh som
fasit, timepriser fra kvarterarkivet, fasitsum 704,28 kr eks. mva). Telleren
simuleres med jitter på pollintervallet, 20 kjøringer per rad:

| Poll | Jevnt over tid | Snap til sluttintervall | Snap til startintervall |
| --- | --- | --- | --- |
| 5 min | -0,07 .. -0,03 kr (spenn 0,04) | -0,19 .. +0,14 kr (spenn 0,34) | -0,27 .. -0,01 kr (spenn 0,26) |
| 30 min | -0,46 .. -0,05 kr (spenn 0,41) | -0,96 .. +1,32 kr (spenn 2,28) | -1,61 .. +0,59 kr (spenn 2,19) |
| 3 t (gap) | -3,17 .. -0,95 kr (spenn 2,21) | -3,37 .. +7,06 kr (spenn 10,43) | -14,35 .. -0,43 kr (spenn 13,92) |

Kolonnen som avgjør er spennet, for det er prisen på invarianten: hvor mye
avregningen flytter seg når bare polltiden endrer seg. Jevn fordeling er
kontinuerlig i polltid og har et spenn som er en tiendedel av snapping ved lange
gap. Snapping er diskontinuerlig: ett sekunds forskyvning av en poll kan flytte
et helt delta over en intervallgrense.

Jevn fordeling er ikke eksakt heller, og det skal stå: den antar konstant
effekt gjennom hele pollvinduet, mens den ekte effekten skifter ved
timegrensen. Restfeilen er systematisk liten (under 0,07 kr per måned ved
5-minutters poll) og skrumper mot null når pollintervallet er kort. Ved vanlig
drift (poll hvert minutt) er den ikke målbar.

Randtilfeller:

- To avlesninger med samme `observed_at` og ulik teller: vinduet har lengde
  null og kan ikke fordeles. Avlesningen er `avvist`, ikke bokført.
- Negativt delta (målerreset eller kildebytte): ikke bokført, deltaet settes
  til 0 og baseline flyttes. Kilde og hendelse føres i diagnostikken.
- Delta over `MAX_ENERGY_DELTA_KWH`: avvist, ført som
  `avregning_avvist_kwh`, og **baselinen flyttes til den nye tellerstanden**,
  akkurat som ved negativt delta. Uten den flyttingen ville hver senere
  avlesning også ligget over grensen, og boken ville stått stille for godt etter
  ett sprang. En hytte som har stått tom i tre uker og kommer tilbake med 150
  kWh på telleren, får altså de 150 avvist og synlige, og regner videre fra den
  nye standen. Det som går tapt er forbruket i vinduet, og det er tallet som
  står i `avregning_avvist_kwh`.

  «Over» er strengt: et delta på nøyaktig `MAX_ENERGY_DELTA_KWH` bokføres. Den
  gamle koden hadde `0 < delta < MAX` og avviste grensen selv. Forskjellen er
  ett enkelt delta på nøyaktig 100,000 kWh og har ingen praktisk betydning,
  men den skal stå her framfor å være en stille uenighet mellom kontrakt og
  kode.

### C2 Invariantene

1. **Bevaring.** Summen av fordelte kWh over intervallene er nøyaktig lik det
   godkjente målerdeltaet (innenfor flyttallsslakk, 1e-9 kWh).
2. **Ingen dobbeltbokføring.** En avlesning identifisert ved
   (`source_identity`, `observed_at`, `value_kwh`) bokføres én gang. Kommer den
   igjen, er den en duplikat og forkastes.
3. **Monotoni i observasjonstid.** En avlesning med `observed_at` eldre enn
   siste behandlede observasjon bokføres ikke på nytt. Den logges som forsinket.
4. **Pris følger energien.** Strømstøtte, Norgespris og energiledd regnes med
   satsene og prisen som gjaldt i energiens eget intervall, aldri med prisen
   som gjelder når pollen skjer.
5. **Aldri null, aldri naboens pris.** Et intervall uten pris får ikke prisen
   0, og ikke prisen fra et annet intervall. Se C4.
6. **Polltidsuavhengighet.** To avspillinger av samme observerte historikk med
   ulike polltidspunkt gir samme avregning når avlesningene er de samme.
   Endres avlesningenes `observed_at`, er historikken en annen. For energi
   gjelder dette uten forbehold så lenge energien kommer fra en teller. For
   pris gjelder det så lenge hver prisrute har minst én poll i settlevinduet
   sitt (A2.1); en rute uten poll er en merket mangel (`delvis_pris`), ikke en
   pris som flytter seg. For en bruker uten energisensor gjelder invarianten
   ikke for energien heller, se B1.
7. **Restartlikhet.** Samme hendelsesrekke, med eller uten omstart midt i, gir
   samme avregning. Se C5.
8. **Fastledd er utenfor.** Kapasitetsleddet akkumuleres tidsbasert og summerer
   ikke over energiintervaller.

### C3 Sommertid og årsskifte

Fordi intervallene er UTC og halvåpne, er sommertidsskiftene ikke et
spesialtilfelle i fordelingen: UTC-tidslinjen er sammenhengende gjennom begge.
Det som er et spesialtilfelle er merkelappene, og de avgjøres alltid av
`start_utc` omregnet til Europe/Oslo:

| Sak | UTC-intervall | Lokal merkelapp | Fakturamåned | Avgiftsår i `regelkilde` |
| --- | --- | --- | --- | --- |
| D1 | 2026-03-29T00:00Z | 2026-03-29 01:00 CET | 2026-03 | 2026 |
| D2 | 2026-03-29T01:00Z | 2026-03-29 03:00 CEST | 2026-03 | 2026 |
| D3 | 2026-10-25T00:00Z | 2026-10-25 02:00 CEST | 2026-10 | 2026 |
| D4 | 2026-10-25T01:00Z | 2026-10-25 02:00 CET | 2026-10 | 2026 |
| D5 | 2026-03-31T22:00Z | 2026-04-01 00:00 CEST | 2026-04 | 2026 |
| D6 | 2026-12-31T23:00Z | 2027-01-01 00:00 CET | 2027-01 | 2027 |

D1 og D2 er vårskiftet: lokal time 02 finnes ikke, og det skal ikke finnes noe
intervall med den merkelappen. D3 og D4 er høstskiftet: to ulike intervaller
har samme lokale merkelapp `02:00`, og de skal holdes fra hverandre av
`start_utc`, aldri av veggklokken. D5 viser at fakturamåneden skifter ved lokal
midnatt, ikke ved UTC-midnatt.

D6 er årsskiftet, og det er samme regel en gang til: intervallet som starter
kl. 23 UTC 31. desember er allerede januar lokalt, og det er de nye
avgiftssatsene som gjelder for det. `regelkilde` følger `start_utc` på alle tre
leddene sine, så et intervall som ligger igjen i gammelt år beholder gammelt
avgiftsår selv om det bokføres etter nyttår.

Veggklokke-aritmetikk (`hour`-sammenligning, `utcoffset`-sjekker,
`replace(hour=...)`) hører ikke hjemme i avregningskjernen. Den skal regne i
UTC og be `zoneinfo` om merkelappene.

### C4 Intervaller uten data eller uten pris

Tre ulike ting, som ikke skal blandes:

- **Uten pris**: intervallet har energi, men ingen prisprøve. kWh bokføres i
  intervallet, prisen står `None`, kvaliteten er `uten_pris`, og energien
  summeres synlig i `kwh_uten_pris`. Ingen kroner regnes for den energien, og
  den fylles ikke inn senere. Norgespris-kunder får fortsatt strømdelen sin,
  siden den er fastpris og ikke avhenger av spot; det er spotavhengige beløp
  som står stille.
- **Delvis pris**: intervallet har færre prisruter med prøve enn ventet
  (`pris_prover < pris_prover_ventet`). Prisen er det uvektede snittet av de
  rutene som kom (A2.1), kvaliteten er `delvis_pris`, og energien summeres i
  `kwh_delvis_pris`. Dette er ikke en feil, bare en merket usikkerhet: prisen
  er rett for de rutene vi så, og vi later ikke som vi så de andre.
- **Uten data**: intervallet har ingen energi bokført. Det finnes da ikke i
  boken. Et hull i boken er ikke null forbruk, og skal ikke vises som det. Er
  hullet forårsaket av at integrasjonen var nede, er det synlig gjennom at
  `avregning_sist_observert` er eldre enn intervallet.

**Bruker uten spotpris.** Er spotsensoren slettet, utilgjengelig eller aldri
konfigurert, kommer det ingen prisprøve, og intervallene er `uten_pris` så
lenge det varer. Det er hele følgen: energien bokføres som ellers, og
integrasjonen kaster ikke `UpdateFailed`
([input-og-konfig.md §1](input-og-konfig.md#1-typede-inputresultater)).
Leverandørprisen er ikke en erstatning for spot og settes aldri inn i stedet:
den er avtaleprisen kunden betaler, ikke markedsprisen strømstøtten og
Norgespris regnes mot. Prissensorens visningscache er heller ingen kilde til
avregningen, se samme paragraf.

### C5 Omstart

Ved omstart gjenopptas avregningen fra den persisterte boken, ikke fra null:

- Siste behandlede observasjon (`source_identity`, `observed_at`, `value_kwh`)
  leses fra Store og er baseline for neste delta. Er kilden en annen enn den
  lagrede, er deltaet 0 og baseline flyttes (K1).
- Åpne intervaller leses tilbake med sin bokførte kWh og lukkes når tiden
  passerer `slutt_utc`, ikke ved første poll. Det er de åpne og de nærmeste
  timene bak dem som lagres, ikke hele måneden: lagringen skjer ved hver poll,
  og en måned med prisruter er et par hundre kilobyte å skrive hvert minutt.
  Vinduet er tre timer (`LAGRINGSVINDU`). Det som faller utenfor er ferdig
  avregnet, og summen av det ligger i månedsfeltene coordinatoren bærer.
- Prisrutene som alt er godkjent i et åpent intervall ligger i boken og leses
  tilbake med det. Uten det ville en omstart midt i timen gjort et `komplett`
  intervall til `delvis_pris`, og C2.7 ville brutt.
- Første poll etter omstart er en helt vanlig avlesning. Den utløser ingen
  varsling i seg selv, og deltaet den bærer fordeles over intervallene det
  faktisk tilhører, ikke inn i timen HA kom opp igjen.
- Den lagrede observasjonen har ingen aldersgrense. Er kilden den samme,
  gjenopptas avregningen fra den uansett hvor lenge det er siden, og vernet mot
  det gigantiske spranget er `MAX_ENERGY_DELTA_KWH`. Regelen eies av
  [input-og-konfig.md §5](input-og-konfig.md#5-energibaseline) og står bare der.
- Et strømbrudd er ikke et eget tilfelle. Det er en omstart med et gap foran
  seg, og den første avlesningen etter bruddet bærer et delta som fordeles jevnt
  over intervallene i gapet (C1). De fleste av dem har ingen prisprøve og blir
  `uten_pris`, som er synlig i `kwh_uten_pris`. Er deltaet større enn
  `MAX_ENERGY_DELTA_KWH`, avvises det og føres i `avregning_avvist_kwh` (C1).
- Kort omstart og omstart etter et døgn er samme regel. Forskjellen er bare hvor
  mange intervaller vinduet dekker og hvor mange av dem som mangler pris.

### C6 Åpent, lukket og uforanderlig

Et intervall er **åpent** til klokken i UTC har passert `slutt_utc`, og
**lukket** etterpå. Lukkingen skjer av tiden alene, ikke av en poll.

Et lukket intervall kan fortsatt få bokført kWh. Bokføring styres av
avlesningens observasjonsvindu, aldri av om intervallet er åpent: en vanlig
avlesning kl. 11:00:03 bokfører inn i 10:00-intervallet som nettopp lukket, og
etter en omstart bokføres det inn i intervaller som er timer gamle. Alt annet
ville brutt C2.6 og C2.7.

Prisen står fast ved lukking, ikke ved arkivering. En prisprøve lander alltid i
ruten polltiden faller i (A2.1), så et lukket intervall får aldri en ny prøve,
og et `uten_pris`-intervall fylles ikke senere (C4). Energi og pris skiller lag
her med vilje: energien kommer etterskuddsvis fra en teller og må kunne bokføres
bakover, prisen leses i sanntid og kan ikke det.

Et intervall blir **uforanderlig** når fakturamåneden det hører til arkiveres
ved månedsrulleringen. Etter det tar det ikke imot mer energi heller, og
`regelkilde` står som den var (A4).

Månedsrulleringen skjer inne i bokføringen av den første avlesningen med
`observed_at` i den nye måneden, ikke ved et klokkeslett: vinduet deles ved
månedsgrensen, delen før grensen bokføres i den gamle måneden, måneden
arkiveres, og resten bokføres i den nye. Fordi vinduene er sammenhengende,
`(forrige observed_at, ny observed_at]`, kan ingen senere avlesning nå bakenfor
et arkivert månedsskifte. En avlesning med `observed_at` eldre enn siste
behandlede observasjon er forsinket og bokføres ikke (C2.3). Hvilken måned
sensorene *viser* følger klokken som før; det er boken som rulleres ved
bokføring.

### C7 Prøvetabell for fordelingen (normativ)

Radene er fasit for fordelingsregelen. `tests/test_avregningskontrakt.py`
kjører dem, og L1 og L2 skal kjøre dem mot sin egen implementasjon.

| Sak | Fra (UTC) | Til (UTC) | Delta kWh | Fordeling (UTC-start=kWh) |
| --- | --- | --- | --- | --- |
| F1 | 2026-06-15T10:30:00Z | 2026-06-15T10:45:00Z | 0.400 | 2026-06-15T10:00:00Z=0.400 |
| F2 | 2026-06-15T10:45:00Z | 2026-06-15T11:15:00Z | 1.200 | 2026-06-15T10:00:00Z=0.600; 2026-06-15T11:00:00Z=0.600 |
| F3 | 2026-06-15T09:20:00Z | 2026-06-15T12:10:00Z | 8.500 | 2026-06-15T09:00:00Z=2.000; 2026-06-15T10:00:00Z=3.000; 2026-06-15T11:00:00Z=3.000; 2026-06-15T12:00:00Z=0.500 |
| F4 | 2026-06-15T10:00:00Z | 2026-06-15T11:00:00Z | 2.000 | 2026-06-15T10:00:00Z=2.000 |
| F5 | 2026-03-29T00:30:00Z | 2026-03-29T01:30:00Z | 4.000 | 2026-03-29T00:00:00Z=2.000; 2026-03-29T01:00:00Z=2.000 |
| F6 | 2026-10-25T00:30:00Z | 2026-10-25T01:30:00Z | 4.000 | 2026-10-25T00:00:00Z=2.000; 2026-10-25T01:00:00Z=2.000 |

F5 og F6 er de to sommertidsskiftene. At de ser trivielle ut er hele poenget:
i UTC er de vanlige timer, og fordelingen skal ikke merke skiftet.

### C8 Prøvetabell for prisruter (normativ)

Radene er fasit for A2.1 og kjøres av samme testfil. Intervallet er
`2026-06-15T10:00:00Z` til `11:00:00Z`, og polltidene er `mm:ss` etter
intervallstart. `PRIS_SETTLE_SEKUNDER` er 60.

| Sak | Oppløsning | Polls (mm:ss=NOK/kWh) | Ruter med prøve | Intervallpris | Kvalitet |
| --- | --- | --- | --- | --- | --- |
| P1 | 15 | 00:30=1.00; 02:00=1.00; 17:00=1.10; 32:00=1.20; 47:00=1.30 | 4 | 1.15 | komplett |
| P2 | 15 | 02:00=1.00; 17:00=1.00; 32:00=1.00; 47:00=1.00 | 4 | 1.00 | komplett |
| P3 | 15 | 00:10=0.90; 01:30=1.00; 16:00=1.00; 31:00=1.00; 46:00=1.00 | 4 | 1.00 | komplett |
| P4 | 60 | 05:00=1.23 | 1 | 1.23 | komplett |
| P5 | 15 | 02:00=1.00; 33:00=1.40 | 2 | 1.20 | delvis_pris |
| P6 | 15 | 00:20=1.00; 15:30=1.10 | 0 | - | uten_pris |
| P7 | 60 | 02:00=1.00; 10:00=1.40 | 1 | 1.40 | komplett |

P2 er feilen som gjorde denne seksjonen nødvendig: fire like priser på rad er
fire prøver, ikke én. P3 viser settlevinduet, der prøven ti sekunder etter
rutestart fortsatt bærer forrige rutes pris og ikke teller. P6 er en sensor som
bare ble lest inne i settlevinduene, og den gir ingen pris i det hele tatt,
ikke en halv. P7 er en kilde som publiserte på nytt inne i ruten.

## D. Persistens og migrering

Lagringsnøkkelen er `entry.entry_id`, som før ([incident
001](../incidents/001-delt-data-mellom-instanser.md)).

Store-versjonene:

| Versjon | Hvem | Innhold |
| --- | --- | --- |
| 1 | dagens utgave | Månedssummer, døgnmakser, akkumulerte kroner. Ingen kildeidentitet, ingen observasjonstid. |
| 2 | K1 | Som v1, pluss `source_identity` og normalisert kWh på baseline. |
| 3 | denne serien | Som v2, pluss `skjema_versjon`, siste behandlede observasjon og åpne intervaller med bokførte kWh og godkjente prisruter. |

Migrering v2 til v3 er enveis og gjør dette:

- Gamle månedssummer beholdes som **åpningsbalanse** for inneværende måned. De
  får ikke intervallhistorikk, for den finnes ikke og kan ikke rekonstrueres.
- Måneden migreringen skjer i merkes `avregning_ufullstendig: true`. Flagget
  ligger i data-dicten, vises i diagnostikken, og fjernes ved første
  månedsskifte etter migreringen. Så lenge flagget står, skal hvert intervall
  boken leverer ha `kvalitet = ufullstendig` (B3). Det er den eneste kilden til
  den verdien: et intervall blir aldri `ufullstendig` av noe som gjelder
  intervallet alene.
- Første avlesning etter migrering blir baseline. Ingen intervaller bokføres
  bakover.
- v2-feltene skrives videre uendret i v3-filen så lenge 1.17-serien lever, slik
  at en nedgradering ikke mister månedsdata. Nedgradering er ellers ikke støttet.

Skjemaversjonen står også i data-dicten (`avregning_skjema`), så en bruker som
rapporterer en feil kan si hvilken bok tallene kom fra.

**Versjonen er et felt i dataene, ikke `Store`-konstruktørens major version.**
Tallene i tabellen over skal ligge i nøkkelen `skjema_versjon` på toppnivå i
Store-filen, mens `Store(hass, 1, ...)` blir stående. Se
[input-og-konfig.md §5](input-og-konfig.md#5-energibaseline) for hvorfor; regelen
eies der, og gjelder hele filen, ikke bare baselinen. Det er én teller for hele
filen: K1 setter den til 2, og boken her løfter den til 3.

Migreringen leser hele Store-filen, ikke bare bokens egne nøkler. Felt boken
ikke kjenner igjen, altså alt v1 og v2 la der, følger med uendret under
`ovrige`, slik at den som eier filen kan skrive dem tilbake. Det er slik
løftet over om at v2-feltene overlever i v3-filen blir innfridd.

## Felttabell for data-dicten

Grensesnittet L1, L2, L3a, L3b og L3c bygger mot. Nye felt:

| Felt | Type | Betydning |
| --- | --- | --- |
| `avregning_skjema` | int | Store-skjemaversjon boken ble lest fra (3). |
| `avregning_ufullstendig` | bool | Måneden mangler intervallhistorikk fordi den krysset migreringen. |
| `avregning_sist_observert` | str \| None | ISO UTC for siste behandlede avlesnings `observed_at`. |
| `avregning_kilde` | str \| None | `source_identity` for energikilden boken er ført mot. |
| `avregning_siste_intervall` | str \| None | ISO UTC-start for siste lukkede intervall. |
| `avregning_apne_intervaller` | int | Antall intervaller i boken som ennå ikke er lukket. |
| `avregning_avvist_kwh` | float | kWh forkastet denne måneden (sprang, målerreset, duplikat). |
| `kwh_uten_pris` | float | kWh bokført denne måneden i intervaller uten pris. |
| `kwh_delvis_pris` | float | kWh bokført denne måneden i intervaller med færre prisprøver enn ventet. |

Felt som beholdes med samme navn, men får rettet betydning:

| Felt | Betydning etter denne kontrakten |
| --- | --- |
| `monthly_consumption_dag_kwh` | Sum kWh over avregnede intervaller med `tariff = dag` i måneden, ikke sum av poll-bøtter. |
| `monthly_consumption_natt_kwh` | Tilsvarende for `natt`. |
| `monthly_consumption_total_kwh` | Sum over alle avregnede intervaller i måneden. |
| `current_hour_energy` | kWh bokført i det åpne intervallet, ikke i en veggklokke-bøtte. |
| `daily_cost_kr` | Kroner fra intervaller med lokal dato lik i dag (L3b). |
| `monthly_accumulated_cost_strom_kr` | Kroner fra intervallenes egen pris, ikke fra prisen ved polltid (L3b). |
| `monthly_accumulated_cost_energiledd_kr` | Som over, med satsen som gjaldt i intervallet (L3b). |
| `monthly_accumulated_cost_kapasitetsledd_kr` | Uendret. Fastledd akkumuleres tidsbasert, ikke over energiintervaller. |
| `is_day_rate` | Uendret: tariffen akkurat nå, for visning. Avregningen bruker intervallets egen `tariff`. Begge leser samme `Tariffregel`; kopien i coordinatoren er borte. |

Felt som forsvinner: ingen i denne omgang. L3b og L3c avgjør hva som kan
pensjoneres når kronene flyttes inn i boken.

`current_hour_energy` står fortsatt i veggklokke-bøtta si etter L3a, mot det
tabellen over sier. Den mater `_daily_max_power` og dermed fastleddet, og å
flytte den til boken er en egen endring med egne fasittall. Den hører til L3b,
sammen med resten av fastleddet.

## Status

L3a er inne (coordinatoren bokfører gjennom `avregning.py`). A, B, C og D
gjelder for energi, tariff, pris, kvalitet og Norgespris-linjen.
`monthly_cost_kr`, `daily_cost_kr` og `monthly_accumulated_cost_strom_kr`
regnes fortsatt med prisen som sto ved polltid; de er L3bs.

## Hva denne kontrakten pensjonerer

Punkt 7 og 8 i [begrensninger.md](../begrensninger.md) (gap-bøtte og
øyeblikksprising av gap-forbruk) er beskrivelser av dagens adferd, og begge
brytes av C1 og C2. De skal fjernes derfra når L3a er inne, ikke før.

[statnett]: https://www.statnett.no/en/for-stakeholders-in-the-power-industry/system-operation/the-power-market/quarterly-resolution-and-the-energy-markets/
