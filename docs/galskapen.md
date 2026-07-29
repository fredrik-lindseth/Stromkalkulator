# Galskapen

Nettleien i Norge er kapasitetsbasert. Fastleddet skal settes ut fra hvor mye
effekt kunden etterspør, men regelverket sier ikke hvordan. RME slår fast at
nettselskapene «har en viss frihet til å bestemme hvordan de vil differensiere»,
og nevner døgnmaks i løpet av en måned, snitt av flere døgnmakser over en periode,
og sikringsstørrelse som eksempler på lovlige innretninger.[^rme]

Sammenligner man prislistene til alle nettselskapene, er det åpenbart at de har
brukt den friheten hver på sin måte. Denne integrasjonen skal regne ut nettleien og
dekker alle nettselskapene, men oppgaven har ingen generell løsning.

## Én husholdning, 69 priser

Ta én husholdning. Snitt av tre døgnmakser på eksakt 5,0 kW, 600 kWh på dagtid og
400 kWh om natten, i juli. Så flytter du den rundt i landet.[^husholdning]

| Nettselskap      | Energiledd | Fastledd | Sum        |
| ---------------- | ---------- | -------- | ---------- |
| Stram            | 182,40 kr  | 330 kr   | 512,40 kr  |
| Noranett         | 89,30 kr   | 530 kr   | 619,30 kr  |
| BKK              | 369,90 kr  | 415 kr   | 784,90 kr  |
| Modalen Kraftlag | 589,10 kr  | 208 kr   | 797,10 kr  |
| Elvia            | 404,00 kr  | 420 kr   | 824,00 kr  |
| Vang Energiverk  | 264,12 kr  | 819 kr   | 1083,12 kr |
| Elmea            | 411,10 kr  | 747 kr   | 1158,10 kr |

Dyreste er 2,26 ganger billigste, og 69 av de 72 selskapene med
kW-trinn gir sin egen unike sum. At prisene varierer er greit nok. Mer interessant er
fordelingen mellom de to leddene: hos Modalen er 74 % av nettleien energiledd,
hos Noranett 14 %.

Det gjør at «flytt forbruket til natten» er verdt fem ganger så mye hos den ene
som hos den andre, mens «hold effekttoppen nede» er verdt fem ganger så mye
motsatt vei.[^andel] Det finnes altså ikke ett spareråd som er riktig for norske
strømkunder.

## Fastleddet måler fem forskjellige ting

Snitt av de tre høyeste døgnmaksene i måneden er den vanligste innretningen, og
70 av 76 oppføringer bruker den.[^antall] De fem andre måler noe annet, og to av dem
måler
ikke effekt i det hele tatt.[^metoder]

Alut og Netera setter fastleddet etter hovedsikringen. Alut har to satser, over og
under 3 x 125 A, og skriver det rett ut i prislisten.[^alut] Netera har fem rader,
fordi satsen også avhenger av systemspenningen. En 63 A hovedsikring koster 333
kr/mnd på 230 V og 667 på 400 V.[^netera] Sikringen ser lik ut i begge tilfeller,
og ingen effektsensor kan skille dem, så brukeren må velge raden selv.

Fjellnett har ingen trinn. De regner grunnbeløp pluss en sats per kW, der kW er
snittet av de fem høyeste ukestoppene over løpende tolv måneder. Hver måned
vektes:[^fjellnett]

| Måned     | Faktor | En 5,0 kW ukestopp teller som |
| --------- | ------ | ----------------------------- |
| januar    | 1,00   | 5,00 kW                       |
| februar   | 1,00   | 5,00 kW                       |
| mars      | 0,85   | 4,25 kW                       |
| april     | 0,50   | 2,50 kW                       |
| mai       | 0,30   | 1,50 kW                       |
| juni      | 0,25   | 1,25 kW                       |
| juli      | 0,25   | 1,25 kW                       |
| august    | 0,25   | 1,25 kW                       |
| september | 0,30   | 1,50 kW                       |
| oktober   | 0,45   | 2,25 kW                       |
| november  | 0,70   | 3,50 kW                       |
| desember  | 0,95   | 4,75 kW                       |

En topp i januar betaler du for i tolv måneder. Samme topp i juli er så godt som
gratis. En Fjellnett-kunde og en BKK-kunde som gjør nøyaktig det samme i samme
sekund, får to helt ulike regninger for det.

Sør Aurdal Energi bruker månedens enkeltstående høyeste time, ikke snittet av
tre.[^soraurdal] Da avgjør én glipp med badstuen og induksjonstoppen hele
måneden.

Ingen av de fem bryter regelverket. Sikringsstørrelse står oppført hos RME som et
gyldig alternativ, på linje med døgnmaks. Problemet er at ingen av selskapene
mener de gjør noe spesielt. Hver av dem har en helt vanlig prisliste med helt vanlige
tall, og ingen skriver at de måler noe annet enn noen andre.

## Hva «natt» betyr

Alle nettselskapene har lavere energiledd om natten. De er ikke enige om når
natten begynner, eller om helgen teller.

Sytti selskap gir nattpris hele helgen. Fem gjør det ikke, så hos dem koster lørdag
klokken 14 like mye som tirsdag klokken 14. Det utgjør 1 792 timer i året, altså
44 % mer tid til dagpris.[^dagtimer]

Hos dem som har helgerabatt teller helligdager som natt, og sju av dem flytter seg
fra år til år. For å vite om 2. pinsedag i 2028 blir dyr eller billig må du først
regne ut påskedagen med heltallsdivisjon og modulo 19, og så legge til femti
dager.[^helligdager] Derfor ligger det en påskeformel i `const.py`.

BKK regner hele julaften og hele nyttårsaften som lavtariff, selv om ingen av dem
er helligdag etter loven.[^bkkjul] Om noen av de andre gjør det samme, er ikke
mulig å slå opp. Ingen av dem skriver det i prislisten, og fri-nettleies skjema har
egne verdier for helligdager og fridager som ikke er i bruk i en eneste fil. Det
viser seg først på fakturaen i desember.

## Forsøket på å standardisere

[fri-nettleie](https://github.com/kraftsystemet/fri-nettleie) på Github gjør
den jobben jeg trodde NVE gjorde, samler alle norske nettleietariffer, delt opp i ledd
og nivå og trinn, i
maskinlesbar format. Samtidig viser
det hvor lite av problemet som lar seg normalisere bort.

Spørsmålet «har dette selskapet helgerabatt?» besvares der på fire måter. Åtte
selskap skriver `dager: [virkedag]`, seks skriver `dager: [ukedag]`, åtte skriver
`dager: [alle]`, og 29 har et dag/natt-skille uten å si hvilke dager det
gjelder.[^dager] Skjemaet sier ikke om «virkedag»
og «ukedag» betyr det samme. Tensio TN skriver `[alle]` og Tensio TS skriver
ingenting, enda de er søsterselskap med samme prisside som kilde. TS hadde
`[alle]` i en tidligere utgave og mistet det underveis.

Den som skal lese datasettet maskinelt må altså gjette, og gjettingen må bygge på
hva unntaket tilfeldigvis heter.

Feltet `grunnpris` er heller ikke en grunnpris. Hos Nettselskapet står den til 1,6
øre, som er sommernattprisen, mens de tre andre satsene ligger over som
unntak.[^grunnpris] I praksis betyr `grunnpris` «den ruten ingen unntak dekker».
En parser som antar at det er den vanligste eller den laveste satsen, får riktig
svar for nesten alle og feil for denne.

Klokkegrensen oppgis av 52 selskap som `6-21` og av fem som `22-5`, altså samme
grense sett fra hver sin ende, uten at noe sier hvilken retning som er riktig. Skal du
lagre dette i ett felt, må du velge én retning og skrive om alle de
andre.[^timer]

## Hva prislistene faktisk oppgir

Et energiledd oppgis i øre/kWh. Spørsmålet er hva som er med i tallet. Her er sju
selskap som alle publiserer «energiledd» og mener fem forskjellige ting med
det:[^konvensjon]

| Nettselskap     | Publiserer                              | Deres tall | Ren nettleie |
| --------------- | --------------------------------------- | ---------- | ------------ |
| Elvia           | Inkl. alt                               | 46,40 øre  | 28,99 øre    |
| Lede            | Inkl. alt                               | 24,42 øre  | 11,41 øre    |
| Mellom          | Inkl. mva, eks. forbruksavgift og Enova | 37,21 øre  | 29,77 øre    |
| Straumnett      | Inkl. mva, eks. forbruksavgift og Enova | 26,20 øre  | 20,96 øre    |
| Vang Energiverk | Eks. mva, inkl. forbruksavgift og Enova | 21,13 øre  | 13,00 øre    |
| Alut            | Inkl. Enova, eks. resten                | 13,10 øre  | 12,10 øre    |
| Føre            | Ren nettleie, avgifter separat          | 19,29 øre  | 19,29 øre    |

Samme ord, ingen merking. Eneste måte å finne ut hvilken variant du har foran deg,
er å regne baklengs og se om resultatet ser fornuftig ut. To av konvensjonene skiller
seg med nøyaktig 8,13 øre, avgiftene, som gjør det lett å trekke dem fra to ganger
uten å merke det.

Så kommer avgiftene, som er fritatt i Nordland og Troms og dobbelt fritatt i
tiltakssonen, etter fylkesgrenser og ikke etter prisområder. Én ren nettleiesats på
29,00 øre blir 30,00 øre i tiltakssonen, 37,13 i Nord-Norge og 46,41 i
Sør-Norge.[^soner] Prisområde NO3 spriker internt, fordi Bindal Kraftnett ligger i
Nordland mens resten av området ligger i Trøndelag og Møre og Romsdal. Fylkesgrensen går
altså tvers gjennom
prisområdet.

Og selv med riktig konvensjon i riktig kilde kan kilden ta feil. I tre uker i juli
oppgav elvia.no 46,60 øre der selskapets eget tariffblad sa 46,40.[^elvia] Norges
største nettselskap hadde en skrivefeil på sin egen prisside, og den eneste måten
å oppdage den på var at et annet datasett var uenig.

## «2026-priser» finnes ikke

Det siste håpet er at man i det minste kan si «dette er prisene for 2026» og
oppdatere en gang i året. De 73 gjeldende husholdningstariffene i fri-nettleie trer
i kraft på 19 forskjellige datoer, fra 1. januar 2024 til 1. juli 2026.[^datoer]
Tretti selskap har ikke rørt satsene siden nyttår, seks endret dem i juli, og tre
har priser som har stått urørt siden 1. januar 2024.

Underveis flytter selskapene på seg. Skiakernett fusjonerte inn i Vevig. Rakkestad
Energi er blitt Elvia. Norgesnett eies av Glitre Nett og har egne, lavere priser.
Noranett er tre separate tariffsett. Area Nett er tre prisområder delt etter kommune,
med 358, 390 og 525 kr/mnd i laveste trinn, så adressen avgjør prisen innenfor
samme selskap.[^identitet] Selv «hvor mange nettselskap finnes det» har ikke et stabilt
svar.

## Regnestykket

Rommet av mulige tariffer lar seg telle. Fastledd-metode: fem observerte verdier.
Trinnsekvenser: 24. Terskelregel ved eksakt grensetreff: to.
Energiledd-form: fem. Helgeregel: to. Ekstra helligdager: to. Avgiftssone:
tre. Ganget sammen blir det 14 400 kombinasjoner, og 41 av dem er
besatt.[^kombinasjoner]

Det er altså ikke et tett problemområde med noen få unntak, men et nesten tomt rom
med 41 punkter spredt utover. Det finnes ingen struktur å generalisere fra, ingen
regel som dekker de resterende 14 359, og ingen garanti mot at et selskap flytter
seg til et av dem i morgen. Koden kan derfor ikke bli generell, den blir en liste.

Fakturaen er det eneste stedet alle leddene står samlet med tall som faktisk er
brukt. Har du en, sier den mer om hva som gjelder hos nettselskapet ditt enn noen
prisliste gjør. Se [bidra med faktura](fakturaer/bidra-med-faktura.md).

[^rme]: [Nettleie for forbruk](https://www.nve.no/reguleringsmyndigheten/regulering/nettvirksomhet/nettleie/nettleie-for-forbruk/),
    Reguleringsmyndigheten for energi (RME), lest 29. juli 2026. Ordrett:
    «Fastleddet skal differensieres, eller settes, på grunnlag av kundens
    etterspørsel etter effekt [...] Nettselskapene har en viss frihet til å
    bestemme hvordan de vil differensiere.» Det finnes altså ingen NVE-anbefalt
    modell å avvike fra. Vi kaller likevel snitt-av-tre-døgnmakser for
    NVE-modellen i kode og dokumentasjon, fordi det er navnet bransjen bruker,
    men navnet er upresist.

[^antall]: `DSO_LIST` i `dso.py` har 76 oppføringer: 75 nettselskap, der Area
    Nett teller som tre siden prisområdene har hver sin tariff, og én
    `Egendefinert` for dem som vil legge inn tall manuelt. Fri-nettleie har 74
    tarifffiler, hvorav 73 har en aktiv husholdningstariff (den fjerde
    Area-filen dekker bare fritidsbolig). Alle tall i dette dokumentet er lest ut
    av `dso.py` eller fri-nettleie 29. juli 2026, eller fra nettselskapets egen
    side der det står i teksten.

[^husholdning]: Regnet med satsene i `dso.py`: `600 × dagsats + 400 × nattsats`
    inkl. forbruksavgift, Enova og mva for selskapets avgiftssone, pluss
    fastleddet for 5,0 kW. Juli er valgt fordi det skiller sesongselskapene fra de
    andre. Tre selskap er utelatt fordi de ikke har en kW-trinntabell i det hele
    tatt (Alut, Netera, Fjellnett), så N = 69. Billigst er Stram med 512,40 kr og
    dyrest Elmea med 1158,10 kr, begge i Nord-Norge uten mva. 67 av de 69 summene
    er unike.

[^andel]: Energileddets andel av nettleien i samme regnestykke: Modalen Kraftlag
    73,9 %, Havnett 59,7 %, Elvia 49,0 %, BKK 47,1 %, Stram 35,6 %, Vang
    Energiverk 24,4 %, Barents Nett 16,6 %, Vestall 14,5 %, Noranett 14,4 %. 73,9
    delt på 14,4 er 5,1.

[^metoder]: Fri-nettleies navn, som vi har tatt inn i `fastledd_metode`:
    `TRE_DØGNMAX_MND` (68 oppføringer, inkludert `Egendefinert`), `OV_TREFASE`
    (Alut, Netera), `FEM_VEKTET_ÅR` (Fjellnett), `MND_MAX` (Sør Aurdal Energi) og
    `UKJENT` (Tinfos, som ikke publiserer metoden sin, og der fri-nettleie har en
    åpen forespørsel til selskapet). Alle fem er implementert. Hva de gjør og
    hvordan, står i
    [beregninger.md](beregninger.md#nettselskap-med-en-annen-metode).

[^alut]: «For husholdning og hytter med etterspurt effekt/- overbelastningsvern
    inntil 3 x 125 A betales 3 500 kr årlig, mens over denne størrelsen betales
    4 500 kr årlig» ([alut.no](https://alut.no/nettleie/)). Alut er i NO4 uten
    mva, så vi lagrer 292 og 375 kr/mnd. Fri-nettleie koder de samme to satsene
    som terskler 0 og 125, uten å oppgi at enheten er ampere.

[^netera]: Prisliste gyldig fra 1. januar 2026
    ([netera.no](https://www.netera.no/nettleie/avtaler/privat/), «Alle priser er
    inkl. mva»): 0-10 A 230 V 2 000 kr/år, 11-63 A 230 V 4 000, 63-125 A 230 V
    8 000, 0-40 A 400 V 4 000, 40-80 A 400 V 8 000. Vi lagrer 167, 333, 667, 333
    og 667 kr/mnd. Fri-nettleie oppgir de tre første som 1 600, 3 200 og 6 400
    kr/år eks. mva, altså de samme tallene med mva-en tatt ut, og bare
    230 V-radene.

[^fjellnett]: Grunnbeløp 2 000 kr/år og 589 kr per kW per år, begge eks. mva
    ([fjellnett.no](https://www.fjellnett.no/nettleie/nettleiepriser/), priser fra
    1. juli 2026). Siden formulerer metoden som «Gjennomsnittet av de fem høyeste
    effektene, løpende siste 12 mnd, forut for fakturatermin, som blir brukt som
    grunnlag for avregning». Fri-nettleie ligger én tariff bak her, med 534 kr/kW
    og energiledd 12,90 øre fra 1. januar, og beskriver Fjellnett med 22 terskler i
    1 kW-steg, altså en trinntabell tegnet opp av en rett linje.

[^soraurdal]: «Fastledd fastsettes på bakgrunn av den timen i måneden du har
    høyest gjennomsnittlig forbruk (månedsmaksimal)», sae.no, kundeinformasjon
    gyldig fra 1. januar 2026. Samme PDF skriver trinnene som «fra [kW] - til og
    med [kW]», og det er hele grunnlaget for at eksakt grensetreff hos dem hører
    til det lavere trinnet. Terskelregelen står i prosa, ikke i et felt. Hos BKK
    går den motsatte vei, og eksakt 5,0 kW koster 415 kr/mnd i stedet for 250.

[^dagtimer]: 2026 har 253 dager som er hverdag og ikke helligdag. Med helgerabatt
    gir det 4 048 timer til dagpris, uten gir det 5 840. De fem uten helgerabatt
    er Glitre Nett, Nettselskapet, Stannum, Tensio TN og Tensio TS
    (`helg_som_natt: false`).

[^helligdager]: `_bevegelige_helligdager` i `const.py` regner skjærtorsdag,
    langfredag, 1. og 2. påskedag, Kristi himmelfartsdag og 1. og 2. pinsedag som
    forskyvninger fra påskedagen, som beregnes med Meeus/Anonymous-algoritmen.
    Påskedag er 5. april 2026, 28. mars 2027 og 16. april 2028. Hvilken ukedag de
    faste helligdagene faller på, avgjør om de er verdt noe: i 2026 faller fire av
    de tolv helligdagene i helgen, og 17. mai er en søndag. I 2027 er 17. mai en
    mandag.

[^bkkjul]: `helligdager_ekstra: ["12-24", "12-31"]`, verifisert mot BKK-fakturaer
    fra oktober 2025 til april 2026. Begge datoene er torsdager i 2026, altså 32
    timer lavtariff som ingen av de andre 74 oppføringene har. Julaften og
    nyttårsaften er ikke helligdager etter helligdagsfredsloven § 2.

[^dager]: Av de 50 selskapene med tidsstyrt energiledd i fri-nettleie oppgir 8
    `dager: [virkedag]` (blant dem BKK, Elvia, Lnett), 6 oppgir `dager: [ukedag]`
    (blant dem Fagne, Jæren Everk), 8 oppgir `dager: [alle]` (blant dem Tensio TN,
    Stannum, Vevig), og 28 oppgir ingen `dager`. Tensio TS hadde `[alle]` i
    tariffen som gjaldt fra januar til juli 2025, og feltet forsvant ved neste
    oppdatering.

[^grunnpris]: Nettselskapet har `grunnpris` 1,6 øre pluss tre unntak: «Høylast
    sommer» 11,6, «Høylast vinter» 12,7 og «Lavlast vinter» 2,7. De Nett har samme
    mønster med `grunnpris` 23,6 og tre unntak. Heuristikken vår i
    `scripts/sjekk_mot_fri_nettleie.py` sorterer unntak uten `timer` først, slik at
    en sesongpris kan sette grunnlinjen før tidsstyrte unntak legges oppå den.

[^timer]: `timer: 6-21` hos 52 selskap, `timer: 22-5` hos fem. Begge betyr dag
    06-22 og natt 22-06. Klokken ligger i `DAY_RATE_START_HOUR` og
    `DAY_RATE_END_HOUR` i `const.py` og gjelder alle. Elvenett-kommentaren om
    natt 22-05 ble fjernet 28. juli 2026: fri-nettleie oppgir høylast 6-21 for
    dem, altså dag fra 06 som hos de andre, så det var ingenting å implementere.

[^konvensjon]: Alle radene er samme størrelse regnet ulikt: ren nettleie pluss
    forbruksavgift 7,13 øre pluss Enova 1,00 øre, ganget med 1,25 der det er mva,
    gir tallet selskapet trykker. De seks oppføringene med en kommentar om
    dobbelttrekk er Arva, Alut, Føre, Romsdalsnett, S-Nett og Straumnett.
    Nettselskapet gjør det motsatte og trykker begge kolonner, 130,00 eks. mva og
    162,50 inkl. mva for laveste trinn. Vi lagrer hele kroner per måned, så det
    blir 163, altså 50 øre for høyt. Fri-nettleie gjør et tredje valg og oppgir alt
    uten avgifter, med fastledd i kr/år, så sammenligningen mot dem er
    `pris / 12 * mva-faktor` med halve kroner rundet opp.

[^soner]: Mva-fritaket følger av merverdiavgiftsloven § 6-6 og gjelder Nordland,
    Troms og Finnmark. Tiltakssonen har i tillegg fritak for forbruksavgift.
    Enova-avgiften på 1,00 øre gjelder overalt, også der alt annet er fritatt. Av
    de 75 selskapene ligger 56 i standardsonen, 11 i Nord-Norge og 8 i
    tiltakssonen. Sonen flytter mer enn nettleien: strømstøtte-terskelen er 96,25
    øre inkl. mva i sør og 77 øre der det ikke er mva, og Norgespris er 50 øre mot
    40. NO3-bommen står i
    [incident 003](incidents/003-no3-mva-feilklassifisering.md).

[^elvia]: elvia.no oppgav 46,60 øre inkl. alt for dagsatsen fra 1. juli 2026,
    mens fri-nettleie hadde 46,40. Fasiten er Elvias eget
    `tariffblad_1_0_standard-tariff_privat_20260701.pdf`, som sier 46,40, altså
    28,99 øre ren nettleie. Prissiden ble rettet i slutten av juli etter at
    avviket ble meldt fri-nettleie. Nattsatsen 16,99 øre (31,40 inkl. alt) stemte
    hele veien.

[^datoer]: Ikrafttredelsesdatoer for de 73 aktive husholdningstariffene: 1. januar
    2024 (Arva, Kystnett, Tinfos), februar, april, august, september, oktober og
    november 2024, januar, mars, april, juli, august, september, oktober og
    november 2025, 1. januar 2026 (30 selskap), mai, juni og 1. juli 2026 (Elvia,
    Glitre, Linja, Nettselskapet, Tensio TN, Tensio TS). Arvas fil er sist
    oppdatert 22. oktober 2024, og der står det også en sesongprising vi aldri har
    fått verifisert sommersatsen på, så Arva-kunder får vintersats i juli.

[^identitet]: `DSO_MIGRATIONS` i `dso.py` mapper `skiakernett` til `vevig`
    (fusjon 1. januar 2025). Rakkestad Energi har identiske satser og trinn som
    Elvia, men står som egen oppføring fordi brukere har valgt den. Norgesnett er
    billigere enn Glitre Nett på hvert enkelt trinn. Noranett, Noranett Andøy og
    Noranett Hadsel har 310, 310 og 270 kr/mnd i laveste trinn. Area Nett har tre
    husholdningsområder med 525, 390 og 358 kr/mnd i laveste trinn (uten mva,
    siden det er tiltakssonen), pluss en fjerde fri-nettleie-fil for fritidsbolig.
    Vi lagret 250 fram til 28. juli 2026, et tall som ikke fantes i noe område. Glitre Nett og Føie har tre
    GLN-numre hver, Arva har to. Midtnett har to gjeldende tariffer, der
    fritidsbolig betaler 20 % mer i fastledd enn husholdning på samme energiledd,
    en dimensjon `DSOEntry` ikke har.

[^kombinasjoner]: Trinnsekvensene er 24 unike rekker av kW-grenser over de 72
    oppføringene som har trinn, der den vanligste (0-2-5-10-15-20-25-50-75-100)
    dekker 27 selskap og 14 av rekkene har ett selskap hver. Antall trinn spenner
    fra fem hos Havnett til 20 hos Noranett. Sygnir har 1 kW-oppløsning opp til
    10, Noranett går 2-4-6-8-10, og Tensio og Linea har trinn helt til 500 kW. De
    fem energiledd-formene er flat, dag/natt, og tre sesongvarianter med ulike
    månedsgrenser: Nettselskapet bytter 1. mai og 1. november, De Nett og Sør
    Aurdal 1. april og 1. oktober, og Area Nett 1. januar og 1. april.
    Terskelregelen har to verdier hos oss, satt eller ikke satt, selv om
    fri-nettleies skjema også tillater `null`. Aksene ganges som uavhengige fordi
    de er det i datamodellen: enhver `DSOEntry` kan sette enhver kombinasjon.
