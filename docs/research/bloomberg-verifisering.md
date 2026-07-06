# Bloomberg-verifisering: 12:00 CET-hypotesen

Resultatet av Bloomberg-uttrekket som ble bestilt for å teste om BKK bruker
Nord Pools preliminære 12:00 CET-interbankkurs til NOK-omregning av
Norgespris-kompensasjonen. Bakgrunnen og hele variant-matrisen ligger i
[nok-omregning.md](nok-omregning.md); dette er den korte rapporten på selve
Bloomberg-dataene.

**Konklusjon først:** Hypotesen holdt ikke. 12:00-kursen forbedrer ikke avviket
systematisk, og restavviket forblir i samme ±0,2 %-bånd som med Norges
Bank-kursen.

## Hvilke data vi hadde

Hentet fra Bloomberg-terminal via BDH-formler, ticker `EURNOK Curncy`:

| Felt                       | Beskrivelse                                  |
| -------------------------- | -------------------------------------------- |
| PX_LAST (12:00)            | siste tick ved snapshot 12:00 Europe/Berlin  |
| PX_BID / PX_ASK (12:00)    | bid og ask ved samme snapshot                |
| PX_MID (12:00)             | mid-pris ved samme snapshot (brukt som kurs) |
| PX_LAST (daglig)           | vanlig daglig close, uten tid-override       |

- **Periode:** 02.01.2026 – 30.04.2026, daglig, 85 bankdager (jan 21, feb 20, mar 22, apr 22).
- **Snapshot:** 12:00 Europe/Berlin (= 12:00 CET/CEST = 12:00 Oslo).
- **Kurs brukt i analysen:** PX_MID @ 12:00, same-day forward-fill for helg/helligdag.
- **Dekning:** treffer de Norgespris-verifiserte månedene februar, mars og april. Dekker **ikke** mai (mai-fakturaen kom først nå, og Bloomberg-serien stopper 30.04).

Råfila (`fredrik_xr_data.xlsx`) og den genererte fixturen
(`bloomberg_eur_nok_1200cet_2026.json`) ligger under `_private/Måleverdier/`
og er gitignorert. Bloomberg-data er lisensiert og kan ikke redistribueres,
så de holdes utenfor repoet med vilje. Bare avledede aggregater (kurssnitt,
avvik) er gjengitt her.

## Metode

Samme forbruksvektede beregning som NB-variantene i `nok-omregning.md`, men med
12:00-kursen som kurskilde:

```
snitt_eks_mva = sum(eur_mwh/1000 * kurs_dag * kwh) / sum(kwh)
komp          = (0,50 - snitt_eks_mva * 1,25) * forbruk
avvik         = komp - fakturaens Norgespris-linje
```

Logikken er gjenbrukt fra `match_norgespris_alle_maaneder.py` via
`match_norgespris_bloomberg.py`. NB-tallene reproduserer den eksisterende
variant-matrisen eksakt (feb +2,07, mar +0,70, apr +0,78), som bekrefter at
sammenligningsgrunnlaget er riktig.

## Resultat

| Måned   | NB 14:15 avvik | BBG 12:00 avvik | NB vektet | BBG vektet | implisitt match |
| ------- | -------------: | --------------: | --------: | ---------: | --------------: |
| 2026-02 |        +2,07 kr |        +3,15 kr |   11,3303 |    11,3251 |         11,3426 |
| 2026-03 |        +0,70 kr |        +0,46 kr |   11,1605 |    11,1613 |         11,1616 |
| 2026-04 |        +0,78 kr |        −1,97 kr |   11,0614 |    11,0748 |         11,0705 |

Prediksjonen var at alle tre avvikene skulle krympe mot null med den ekte
12:00-kursen. I stedet vokste februar (+2,07 → +3,15), mars krympet litt
(+0,70 → +0,46), og april bommet over til andre siden (+0,78 → −1,97).

## Hvorfor det ikke løste seg

Den daglige forskjellen mellom 12:00-kursen og NB 14:15 er reell (stdev 0,029,
spenn ±0,08, blandet fortegn), men vasker seg stort sett ut under
forbruksvekting. Netto månedseffekt er liten og ikke konsistent i fortegn:
BBG-kursen ligger over NB i april, men under NB i februar. Fakturaens
implisitte kurs ligger derimot over NB i alle tre månedene. For april havner
implisitt match (11,0705) pent mellom NB (11,0614) og BBG (11,0748), men
februar bryter mønsteret: implisitt (11,3426) ligger over både NB og BBG. En
ren tid-på-dagen-forklaring holder ikke.

## Forbehold om dataene

I dette uttrekket er PX_MID @ 12:00 og daglig PX_LAST (close) numerisk så godt
som identiske (innenfor 5·10⁻⁵). Vi kan derfor ikke fullt ut skille et ekte
12:00-snapshot fra dagsluttkursen. Bid/ask-spreaden er til stede (ekte
interbank-quote, og kursen avviker fra NB dag for dag), så dataene er
meningsfulle, men vi har trolig ikke fått en *ren* 12:00-fixing isolert fra
close. Et BFIX-12:00-uttrekk (se appendiks) ville vært skarpere.

## Reproduksjon

Krever den private Bloomberg-fixturen:

```bash
# Lag fixturen fra råfila (xlsx -> json under _private/)
uv run --with openpyxl python scripts/research/snapshot_bloomberg_eur_nok.py

# Kjør 12:00-kursen mot fakturaene, side om side med NB
python3 scripts/research/match_norgespris_bloomberg.py
```

## Veien videre

Bloomberg 12:00 er utelukket som kilde. Neste spørsmål er hva BKK faktisk
fakturerer fra. En research-runde 2026-06-20 (seks vinkler + verifisering),
fulgt opp med egne live-kall, ga to ting verdt å ta med videre.

### Verifisert live 2026-06-20

Nord Pool publiserer sin **egen** daglige EUR/NOK i feltet `exchangeRate` på
NOK-svaret fra `dataportal-api.nordpoolgroup.com/api/DayAheadPrices` (NO5,
currency=NOK). Det er denne kursen som ganges på EUR-prisen for hele
leveringsdøgnet, og svaret er merket `state: Final` (altså etter
to-banks-hedge, ikke den preliminære 12:00-kursen). Dette er kursen forskrift
om kraftomsetning forankrer som fasit, ikke Norges Bank eller Bloomberg.

To ting jeg bekreftet med egne kall (51 leveringsdøgn, 30.04–19.06.2026):

1. **Nord Pool-kursen sporer Norges Bank dagen FØR (D-1), ikke same-day.**
   Snittavvik mot NB D-1: abs 0,0166 (stdev 0,024). Mot NB same-day: abs 0,0275
   (stdev 0,037). D-1 er klart nærmere. Det gir mening: valutasnapshotet tas på
   auksjonsdagen (D-1, ~12:00 CET rett før day-ahead-auksjonen ~12:50), ikke på
   leveringsdagen. Eksempel: NP-levering 12.05 = 10,83484, NB 11.05 (D-1) =
   10,8275, NB 12.05 = 10,771.
2. **Nord Pool-kursen ligger i snitt litt OVER NB D-1** (+0,0051), som er
   hedge-påslaget. Det forklarer hvorfor fakturaens implisitte kurs har ligget
   konsistent litt over NB i alle månedene.

Konsekvens for variantmatrisen i [nok-omregning.md](nok-omregning.md):
hovedvarianten vår (B: NB same-day) bruker feil FX-dag. Den mekanisk korrekte
gratis-proxyen er **variant C (NB previous-bankday / D-1)**, som allerede ga
den beste februar-matchen (+0,08 kr). Restavviket er da gapet mellom NB D-1 og
Nord Pools faktiske hedge-kurs (~0,02 i kurs, ~0,2 % i sum).

### Haken, og hva vi faktisk kan gjøre

Det gratis anonyme API-et serverer om lag de siste to månedene (tilgjengelig tilbake
til ~19.04 da jeg sjekket 20.06); eldre datoer gir 401. Fixturemånedene jan–mars
og første halvdel av april er altså ikke gratis tilgjengelige lenger. Men **mai (den
nye fakturaen) ligger innenfor vinduet akkurat nå** og faller ut utover sommeren.
Det betyr at vi for første gang kan teste med Nord Pools EKTE kurs, mot
mai-fakturaen, hvis vi henter dataene snart. For å verifisere bakover lenger enn
vinduet trengs enten en gratis Data Portal-konto (innlogget eksport tilbake til
1992) eller NB D-1 som proxy.

### RME-sporet, verifisert mot lovdata 2026-06-20

Dette er det mest lovende sporet, og nå sjekket mot primærkilden. Forskrift om
Norgespris ([FOR-2025-09-08-1790](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1790)):

- **§ 11:** nettselskapet (BKK) skal beregne prissikringsverdi *time for time* =
  elspotpris i budområde − referansepris (40 øre/kWh eks. mva, § 10), og
  beregningen skal ta hensyn til mva.
- **§ 23 fjerde ledd:** prissikringsverdier time for time *offentliggjøres av
  Reguleringsmyndigheten for energi (RME)*.
- Forskriften sier **ingenting** om valutakurs, kurskilde eller avrunding. Den
  delen er altså uregulert, akkurat som vi mistenkte.

Hva «elspotpris i budområde i NOK» betyr forankres i
[forskrift om kraftomsetning § 7-6](https://lovdata.no/dokument/LTI/forskrift/2025-08-24-1714):
spotfakturering skal skje på «Nord Pool sin publiserte timespris per budområde
oppgitt i NOK». Det er nettopp Nord Pools NOK-pris (med `exchangeRate`-en over),
ikke en BKK-egen omregning.

**Viktig korreksjon:** research-runden hevdet RME bruker «Epex Spot + Norges
Bank». Det stemmer for **strømstøtte/fjernvarme**, som regnes på *månedssnitt*
spotpris (NVEs strømstøttesats-side sier eksplisitt Epex Spot + NB-kurs). Det er
en *annen* mekanisme enn den *timesbaserte* Norgespris-prissikringsverdien for
vanlige strømkunder. Ikke bland dem.

**Konsekvensen for verifisering bakover:** RME publiserer den offisielle
prissikringsverdien per time per budområde, i NOK, med den offisielle
omregningen allerede bakt inn. Norgespris gjelder fra 01.10.2025 (strømstøtte-
grunnlaget enda lenger tilbake), så denne serien dekker **alle** fixturemånedene
og mai. Henter vi RMEs timesverdier for NO5, trenger vi ingen FX-rekonstruksjon
og ingen Nord Pool-vindu, og kan sjekke hvilken som helst måned til øret.
**Verifisert 2026-06-20:** RME publiserer verdiene kun som en innebygd Power
BI-rapport på [nve.no/…/prissikringsverdier-time-for-time](https://www.nve.no/reguleringsmyndigheten/kunde/stroem/dette-er-norgespris/prissikringsverdier-time-for-time/)
: ingen åpen fil-nedlasting og intet API (`api.nve.no` har ingen pris-endepunkter).
Eneste vei til rådata er Power BI sin «Eksporter data»: åpne rapporten, filtrer
NO5 + måned, eksporter CSV/XLSX. Siden er åpen, ingen innlogging. For NO5 er
verdiene oppgitt **inkl. mva**. Maskinporten gjelder bare nettselskapenes
innrapportering *til* RME, ikke nedlasting. Det som gjenstår å bekrefte er om
eksporten faktisk gir time-rader (ikke aggregert) og rekker tilbake til
01.10.2025; klarer den ikke det, er fallback en innsynsforespørsel til RME
(`underlag_stromstotte@nve.no`), som etter § 23 plikter å offentliggjøre verdiene.
Selve uttrekket krever en nettleser-økt; Power BI-eksporten lar seg ikke skripte rent.

Den ene gjenværende usikkerheten: § 11 sier nettselskapet *beregner* verdien,
mens § 23 sier RME *offentliggjør* den. Om BKKs fakturerte verdi er bit-identisk
med RMEs publiserte (eller marginalt avrundet/kildet annerledes) er nettopp det
et BKK-spørsmål kan avklare.

Vær ærlig om gulvet: faktura rundes til øre (prisopplysningsforskriften, 2
desimaler). Et restavvik på under 3 kr / 0,05–0,2 % per måned er sannsynligvis
avrundings- og kildepresisjonsstøy, ikke en feil i integrasjonen. Det kan vise
seg umulig å lukke til null utenfra.

> **Motbevist 2026-07-06:** Det lot seg lukke. Med Nord Pools publiserte
> Final-kvarterpriser traff vi juni-fakturaens Norgespris-linje på øret.
> Se [norgespris-eksakt-match.md](norgespris-eksakt-match.md).

### Rangert

1. **Hent RMEs publiserte timesverdier (prissikringsverdi) for NO5.** Den
   offisielle fasiten i NOK, med omregningen allerede bakt inn, dekker alle
   måneder fra 01.10.2025. Lar oss verifisere bakover til øret uten
   FX-rekonstruksjon og uten Nord Pool-vinduet. Haken (verifisert 2026-06-20):
   verdiene finnes kun som Power BI-dashboard, ikke som fil/API, så uttrekket
   må gjøres manuelt via «Eksporter data» i en nettleser (detaljer over).
   Høyest sjanse for å faktisk lukke gapet.
2. ~~**Kjør Nord Pools faktiske `exchangeRate` mot den nye mai-fakturaen.**~~
   Gjort 2026-07-06, med de publiserte NOK-kvarterprisene i stedet for
   rekonstruksjon: juni traff eksakt (0,00 kr), mai har -0,35 kr igjen.
   Arkivet utvidet med `scripts/research/snapshot_nordpool_nok.py`.
   Se [norgespris-eksakt-match.md](norgespris-eksakt-match.md).
3. **Bytt primær gratis-proxy fra NB same-day (B) til NB D-1 (C)** i
   variantanalysen. Mekanisk korrekt, gratis, og best-matchende. Lav innsats.
4. **Spør BKK direkte** om de fakturerer bit-identisk med RMEs publiserte
   verdier, og hvilken kurskilde/avrunding de bruker. Utkast i
   [epost-utkast-bkk.md](epost-utkast-bkk.md).
5. ~~**Godta ±0,2 % / under 3 kr som gulv**~~ Avlivet 2026-07-06: gulvet på
   Norgespris-linjen er ~0 med riktig priskilde. Det som gjenstår er
   mai-restavviket på 0,35 kr (punkt 1 og Elhub-CSV avgjør).

**Anbefalt neste steg:** finn og hent RMEs timesverdier for NO5 (1). Det er den
direkte fasiten og svarer på bakover-verifiseringen uten FX i det hele tatt.
Reproduksjon av NP-kurs-uthentingen som kryssjekk:

```bash
curl -s -H "User-Agent: Mozilla/5.0" \
  "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices?date=2026-05-12&market=DayAhead&deliveryArea=NO5&currency=NOK" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['exchangeRate'], d['areaStates'])"
```

## Appendiks: hvis du vil bestille på nytt (BFIX 12:00)

Uttrekket vi fikk var fallback-varianten (vanlig spot med tid-override), som
ga PX_MID ≈ daglig close. For en ren 12:00-fixing er Bloomberg BFIX det riktige
produktet (mid-snapshot hvert 30. minutt, inkludert 12:00 CET).

```
# BFIX, bekreft ticker i terminalen først (BFIX <GO>)
=BDH("EURNOK 12:00 BFIX Curncy","PX_LAST","2026-01-02","2026-05-31","Per","D")
```

Velg EUR/NOK, 12:00 CET, periode etter behov. «Save As → CSV» og kjør samme
analyse. Merk DST: april–oktober er CEST (UTC+2), november–mars er CET (UTC+1);
12:00 Oslo håndteres av terminalen hvis du oppgir Europe/Oslo eller Europe/Berlin.

Men vurder om det er verdt det: analysen over viser at selv en perfekt
12:00-kurs ikke ville lukket februar, der fakturaens implisitte kurs ligger
over både NB og 12:00-interbank. Et nytt Bloomberg-snapshot er trolig bortkastet.
Den bedre veien er Nord Pools egen `exchangeRate` (som sporer NB D-1, ikke
12:00-interbank), ikke mer FX-data fra terminalen. Se [Veien videre](#veien-videre).
