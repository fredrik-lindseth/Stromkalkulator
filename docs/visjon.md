# Visjon: Strømkalkulator

*Sist oppdatert: mars 2026*

---

## Sannheten om strømregningen — i sanntid

Strømkalkulator er den definitive kilden til hva strømmen faktisk koster, i det øyeblikket du bruker den. Ikke en tilnærming. Ikke et estimat basert på gårsdagens priser. Den eksakte kronebeløpet — spotpris, nettleie, avgifter, strømstøtte, kapasitetsledd — alt inkludert, oppdatert hvert minutt.

Norske strømkunder har tradisjonelt måttet vente til fakturaen kommer for å vite hva de betalte. Strømkalkulator snur dette på hodet. Kostnaden er synlig *mens den oppstår*, og brukeren kan handle på den informasjonen i sanntid.

## Kapasitetstrinn du faktisk forstår

Kapasitetsmodellen er det mest forvirrende elementet i den norske nettleien. Tre dager med høyest forbruk bestemmer hele månedens fastledd — men de færreste vet hvilke dager det er, eller hvor nærme de er neste trinn.

Strømkalkulator viser de tre toppene visuelt, med dato, klokkeslett og effekt. Brukeren ser sitt nåværende trinn, hva det koster per måned, og hvor mange kilowatt som gjenstår før neste trinn slår inn. Når forbruket nærmer seg en trinngrense, varsles brukeren — tidsnok til å reagere. Skru av varmtvannsberederen. Utsett elbil-ladingen. Et konkret valg med et konkret beløp knyttet til det.

Historikken over kapasitetstrinn vises måned for måned. Brukeren ser trenden: «I januar var jeg på trinn 4, i februar trinn 3, nå i mars er jeg på vei mot trinn 2.» Denne oversikten gjør det mulig å forstå effekten av endringer i vaner, og gir motivasjon til å holde forbruket jevnt.

## Fakturaen — før den kommer

Ved månedsslutt har Strømkalkulator allerede regnet ut hva nettleiefakturaen kommer til å vise. Dag- og nattforbruk er splittet og priset etter riktige satser. Kapasitetsleddet er beregnet fra de faktiske toppene. Avgiftene er lagt på krone for krone.

Brukeren sammenligner dette med den faktiske fakturaen. Avvik markeres tydelig: «Forventet 847 kr, fakturert 863 kr — differanse 16 kr.» Dette gir brukeren et verktøy for å oppdage feil i faktureringen, noe som faktisk forekommer.

Forrige måneds data lever videre som referansepunkt helt til neste måned er over, slik at man alltid har to måneder å sammenligne med.

## Norgespris — et informert valg

Norgespris-ordningen gir forbrukere et reelt valg: fast pris eller spotpris med støtte. Men valget er blindt uten data. Strømkalkulator eliminerer gjettingen.

En løpende sammenligning viser hva brukeren betaler med sin nåværende avtale versus hva de *ville* betalt med alternativet. Ikke bare akkurat nå, men akkumulert gjennom hele måneden. «Du har spart 127 kr denne måneden ved å velge spotpris» — eller «Du ville spart 84 kr med Norgespris.»

Denne sammenligningen tar hensyn til alt: spotpris, strømstøtte-terskelen, avgiftssone, og volumtak. Den gir et ærlig svar på et spørsmål de fleste bare kan spekulere i.

## Alle nettselskaper, oppdatert

Strømkalkulator kjenner prissatsene til hvert nettselskap i Norge. Ikke bare de store — alle. Energileddet, kapasitetstrinnene, og eventuelle særordninger er lagt inn med referanse til offisielle kilder.

Når nettselskaper fusjonerer, håndteres overgangen automatisk. Brukeren trenger ikke gjøre noe — konfigurasjonen oppdateres, lagringen migreres, og beregningene fortsetter uten avbrudd.

Nye priser for kommende år er tilgjengelige så fort nettselskapene publiserer dem, gjerne før årsskiftet. Fellesskapet bidrar med oppdateringer, og hver endring er sporbar tilbake til en offisiell kilde.

## Regionalt korrekt, ned til kommunenivå

Norge er ikke ett strømmarked. Avgiftssonene — standard, Nord-Norge, og tiltakssonen — gir dramatisk forskjellig sluttregning for identisk forbruk. Strømkalkulator beregner riktig forbruksavgift, Enova-avgift og merverdiavgift basert på brukerens sone.

En bruker i Hammerfest og en bruker i Oslo med samme spotpris og samme nettselskap får forskjellig totalpris. Strømkalkulator viser begge riktig, uten at brukeren trenger å forstå avgiftsreglene selv.

## Elbil og topplast

Elbillading er den vanligste årsaken til at husholdninger havner på et høyere kapasitetstrinn. En enkel ladeøkt på 11 kW kan flytte en husholdning fra trinn 3 til trinn 5 — en forskjell på flere hundre kroner i måneden.

Strømkalkulator viser konsekvensen av lading i sanntid. «Nåværende effekt: 9.2 kW. Topp i dag: 11.4 kW. Ditt kapasitetstrinn er allerede satt av denne toppen.» Brukeren ser at videre lading i dag ikke gjør vondt verre — men at en ny toppdag i morgen kan bli dyr.

Denne innsikten gjør det mulig å ta bevisste valg om *når* man lader, uten å måtte forstå den underliggende modellen.

## Helligdager og tariffperioder

Dag- og nattariff styres av klokken, ukedagen og kalenderen. Helligdager betyr nattariff hele døgnet — inkludert bevegelige helligdager som påske, pinse og Kristi himmelfartsdag.

Strømkalkulator beregner alle bevegelige helligdager algoritmisk fra påskeformelen. Ingen hardkodede datoer som må oppdateres. Ingen feil andre påskedag 2028 fordi noen glemte å legge den inn. Formelen dekker alle år, automatisk.

## Flere målere, isolert

En husholdning med flere strømmålere — garasje, anneks, utleiebolig — konfigurerer hver måler som en egen instans. Hver instans har sin egen lagring, sine egne topper, sitt eget kapasitetstrinn. Data krysser aldri mellom instanser, selv når de tilhører samme nettselskap.

Hver måler vises som en egen enhet i Home Assistant, med et fullt sett av sensorer. Oversikten er tydelig: «Hovedhus: trinn 3, 415 kr/mnd. Garasje: trinn 1, 155 kr/mnd.»

## Ingen sky, ingen API, ingen avhengigheter

Strømkalkulator gjør ingen API-kall. Den sender ingen data ut av hjemmet. Alt beregnes lokalt fra to sensorverdier som allerede finnes i Home Assistant: effektmålingen fra HAN-porten og spotprisen fra Nord Pool.

Det finnes ingen ekstern tjeneste som kan gå ned og ta med seg beregningene. Ingen persondata som sendes til en tredjepart. Ingen API-nøkler som utløper. Integrasjonen er selvforsynt — den trenger bare Home Assistant og en strømmåler.

## Tillit gjennom transparens

Hver formel, hver sats, og hver terskelverdi i Strømkalkulator er dokumentert med referanse til offisielle kilder. Forbruksavgiften refererer til Stortingets avgiftsvedtak. Strømstøtte-terskelen refererer til Lovdata. Kapasitetstrinnene refererer til nettselskapets egen prisliste.

Brukeren trenger ikke stole på at beregningen er riktig — de kan verifisere det selv. Og det gjør de. Brukere som sammenligner med sine faktiske fakturaer er den beste kvalitetssikringen integrasjonen har.

---

*Strømkalkulator er det verktøyet norske strømkunder burde fått fra nettselskapet sitt: en ærlig, fullstendig og oppdatert oversikt over hva strømmen faktisk koster. Ikke en forenklet graf. Ikke en faktura som kommer for sent. En levende beregning som gir deg kontroll over ditt eget forbruk — fordi du endelig ser hva det betyr i kroner og øre.*
