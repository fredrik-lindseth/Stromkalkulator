# Visjon: Strømkalkulator

## Hva strømmen koster — nå

Strømkalkulator viser hva strømmen koster i det øyeblikket du bruker den. Spotpris, nettleie, avgifter, strømstøtte, kapasitetsledd — summert til en totalpris per kWh, oppdatert hvert minutt.

De fleste norske strømkunder ser ikke hva de betaler før fakturaen kommer. Strømkalkulator viser kostnaden mens den oppstår.

## Prisen, lag for lag

Norsk strømpris er sammensatt: spotpris, energiledd, kapasitetsledd, forbruksavgift, Enova-avgift, mva, og eventuelt strømstøtte. Strømkalkulator viser hvert lag separat og summert.

Brukeren velger detaljeringsnivå. Én sensor for totalpris. Eller drill ned: spotpris, energiledd, kapasitetsledd per kWh, offentlige avgifter, strømstøtte — alt tilgjengelig som egne sensorer.

Strømpris per kWh viser den variable kWh-prisen (spotpris + energiledd) uten estimert kapasitetsledd. Totalpris inkl. avgifter viser den fulle estimerte kostnaden. Begge svarer på forskjellige spørsmål.

## Kapasitetstrinn

Tre dager med høyest effektforbruk bestemmer månedens kapasitetsledd. Strømkalkulator viser hvilke tre dager det er, med dato, klokkeslett og effekt. Nåværende trinn, månedskostnad, og hvor mange kW som gjenstår før neste trinn. Varsel når forbruket nærmer seg en trinngrense.

## Dagen og måneden, i kroner

De fleste vil vite «hva har strømmen kostet i dag?» og «hva ligger jeg an til denne måneden?» — ikke øre per kWh.

Dagens kostnad akkumulerer gjennom døgnet. Estimert månedskostnad projiserer basert på forbrukstempo hittil. Vektet snittpris viser hva du faktisk har betalt per kWh denne måneden, basert på når du brukte strøm.

## Fakturasjekk

Når nettleiefakturaen kommer, reproduserer Strømkalkulator hver linje: energiledd dag og natt, kapasitetsledd med riktig trinn, forbruksavgift, Enova-avgift, mva — alt separat og summert. Norgespris-kompensasjonen akkumuleres time for time gjennom måneden, slik at brukeren kan sammenligne direkte med BKKs (eller et annet nettselskaps) beregning.

Forrige måneds data bevares komplett: forbruk splittet på dag/natt, topp 3 effektdager med klokkeslett, kapasitetstrinn og -pris, og Norgespris-kompensasjon i kroner. Typisk avvik er noen få kroner, fordi integrasjonen bruker Riemann-sum fra effektsensoren mens måleren teller kWh direkte.

## To sannheter om pris

Strømkalkulator skiller tydelig mellom to ting:

**Marginalkostnad** — hva koster én ekstra kWh akkurat nå? Totalpris-sensoren svarer på dette, inkludert en andel av kapasitetsleddet fordelt per kWh. Nyttig for sanntidsbeslutninger og Energy Dashboard, men summen over en måned treffer ikke fakturaen fordi kapasitetsledd er et fast beløp som ikke skalerer med forbruk.

**Faktisk månedskostnad** — hva kommer fakturaen til å vise? Månedlig total-sensoren svarer på dette, med kapasitetsledd som flat sum. Treffer fakturaen innenfor noen få kroner.

Begge er riktige svar på forskjellige spørsmål. Strømkalkulator kommuniserer tydelig hvilken sensor som svarer på hva.

## Norgespris-sammenligning

Løpende sammenligning mellom spotpris-avtale og Norgespris (40 øre/kWh fast). Akkumulert gjennom måneden, inkludert strømstøtte-terskelen, avgiftssone og volumtak. Viser om du ville spart eller tapt på å bytte.

Norgespris-kompensasjonen — det faktiske kronebeløpet nettselskapet krediterer time for time — spores separat. Når fakturaen kommer, kan brukeren sammenligne direkte med Norgespris-linjen.

## Solceller og eksport

Plusskunder selger overskuddsstrøm til spotpris. Strømkalkulator sporer eksportert energi og beregner inntekten. Nettokostnad — kjøp minus salg — gir et komplett bilde av strømregningen.

For kunder som valgte bort Norgespris for å selge til høyere sommerpris, viser sammenligningssensoren om regnestykket faktisk går opp: Norgespris gir billigere kjøp men påvirker ikke salgsinntekten. Strømkalkulator holder tellingen.

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

Hver sats og terskelverdi er dokumentert med offisiell kilde (Lovdata, Stortingets avgiftsvedtak, nettselskapenes prislister). En fullstendig testsuite verifiserer formlene, inkludert reelle fakturaer som testdata. Når noe ikke stemmer perfekt — som kapasitetsledd i Energy Dashboard — dokumenteres begrensningen åpent.

---

_Strømkalkulator gir norske strømkunder en komplett og oppdatert oversikt over hva strømmen koster — synlig mens forbruket skjer, verifiserbart når fakturaen kommer._
