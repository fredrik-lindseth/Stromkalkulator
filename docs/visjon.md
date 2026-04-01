# Visjon: Strømkalkulator

## Hva strømmen koster — nå

Strømkalkulator viser hva strømmen koster i det øyeblikket du bruker den. Spotpris, nettleie, avgifter, strømstøtte, kapasitetsledd — summert til en totalpris per kWh, oppdatert hvert minutt.

De fleste norske strømkunder ser ikke hva de betaler før fakturaen kommer. Strømkalkulator viser kostnaden mens den oppstår.

## Prisen, lag for lag

Norsk strømpris er sammensatt: spotpris, energiledd, kapasitetsledd, forbruksavgift, Enova-avgift, mva, og eventuelt strømstøtte. Strømkalkulator viser hvert lag separat og summert.

Brukeren velger detaljeringsnivå. Én sensor for totalpris. Eller drill ned: spotpris, energiledd, kapasitetsledd per kWh, offentlige avgifter, strømstøtte — alt tilgjengelig som egne sensorer.

Strømpris per kWh viser den variable kWh-prisen (spotpris + energiledd) uten estimert kapasitetsledd. Totalpris inkl. avgifter viser den fulle estimerte kostnaden. Begge svarer på forskjellige spørsmål.

## Kapasitetstrinn

Tre dager med høyest effektforbruk bestemmer månedens kapasitetsledd. Strømkalkulator viser hvilke tre dager det er, med dato og effekt. Nåværende trinn, månedskostnad, og hvor mange kW som gjenstår før neste trinn. Varsel når forbruket nærmer seg en trinngrense.

## Dagen og måneden, i kroner

De fleste vil vite «hva har strømmen kostet i dag?» og «hva ligger jeg an til denne måneden?» — ikke øre per kWh.

Dagens kostnad akkumulerer gjennom døgnet. Estimert månedskostnad projiserer basert på forbrukstempo hittil. Vektet snittpris viser hva du faktisk har betalt per kWh denne måneden, basert på når du brukte strøm.

## Fakturasjekk

Ved månedsslutt har Strømkalkulator beregnet nettleien: dag- og nattforbruk splittet og priset, kapasitetsledd fra faktiske topper, avgifter krone for krone. Brukeren kan sammenligne med fakturaen manuelt.

Forrige måneds data bevares med komplett nedbrytning. Typisk avvik fra faktura er 1-5% (avrunding, målefeil).

## Norgespris-sammenligning

Løpende sammenligning mellom spotpris-avtale og Norgespris (40 øre/kWh fast). Akkumulert gjennom måneden, inkludert strømstøtte-terskelen, avgiftssone og volumtak. Viser om du ville spart eller tapt på å bytte.

## Nettselskaper

Alle nettselskaper er støttet med energiledd og kapasitetstrinn. For operatører som ikke er innebygd kan brukeren sette egendefinerte priser. Priser legges inn med referanse til offisielle kilder.

Når nettselskaper fusjonerer, håndteres overgangen automatisk — konfigurasjonen oppdateres og data migreres.

## Avgiftssoner

Tre avgiftssoner gir forskjellig sluttregning for identisk forbruk: standard (25% mva), Nord-Norge (mva-fritak), og tiltakssonen (fritak for både mva og forbruksavgift). Strømkalkulator beregner riktig basert på brukerens sone.

## Elbil og topplast

Elbillading er den vanligste årsaken til høyere kapasitetstrinn. 11 kW lading kan flytte en husholdning fra trinn 3 til trinn 5. Strømkalkulator viser nåværende effekt, dagens topp, og konsekvensen for kapasitetstrinn i sanntid.

## Forbruksmønster

Andel av forbruket på dagtariff versus natt/helg, som enkel prosent. Synliggjør effekten av å flytte forbruk til billigere timer.

## Helligdager

Bevegelige helligdager (påske, pinse, Kristi himmelfartsdag) beregnes algoritmisk fra påskeformelen. Ingen hardkodede datoer som må vedlikeholdes.

## Flere målere

Hver strømmåler konfigureres som egen instans med isolert lagring. Data krysser aldri mellom instanser.

## Robusthet

Prissensorer kan feile midlertidig. Priser som endrer seg maks én gang i timen caches, slik at korte avbrudd ikke gir hull i data. Effektmålinger caches ikke — der reflekterer vi virkeligheten.

## Lokalt først

All beregning skjer lokalt. Strømkalkulator gjør ingen egne API-kall og sender ingen data ut. Kildedata (spotpris fra NordPool, eventuelt Tibber-pris) hentes av andre integrasjoner som er avhengige av internett, men Strømkalkulator legger ingen nye skyavhengigheter oppå.

## Verifiserbarhet

Hver sats og terskelverdi er dokumentert med offisiell kilde (Lovdata, Stortingets avgiftsvedtak, nettselskapenes prislister). En fullstendig testsuite verifiserer formlene, inkludert reelle fakturaer som testdata.

---

_Strømkalkulator gir norske strømkunder en komplett og oppdatert oversikt over hva strømmen koster — synlig mens forbruket skjer, ikke når fakturaen kommer._
