# Spørsmål til en valuta-PhD om EUR/NOK-omregning hos norske strømleverandører

## Kort kontekst

En Home Assistant-integrasjon for verifisering av norske strømfakturaer mot rådata fra Nord Pool og Norges Bank ([hacs-strømkalkulator](https://github.com/0v-no/hacs-strømkalkulator)). Alle fakturalinjer treffer innenfor noen øre, bortsett fra Norgespris-kompensasjonen, som ligger ~0,5–2 kr unna på en månedsfaktura på ~1500 kr.

Reverse-engineering av kursen BKK ser ut til å bruke gir en implisitt EUR/NOK-kurs (11,0706 for april 2026) som ligger systematisk mellom Norges Banks publiserte 14:15 CET-snapshot (11,0229 aritmetisk, 11,0614 forbruksvektet) og Nord Pools offisielle EXR (11,0815). Hypotesen er at BKK bruker Nord Pools preliminære interbank-kurs ved 12:00 CET (kursen Nord Pool selv dokumenterer at de henter for å konvertere day-ahead-prisene fra EUR til NOK, før auksjonen avholdes ~12:50 CET).

Data: tre måneders verifisering (februar, mars, april 2026). Alle tre månedene gir positivt avvik (vår beregning underestimerer kompensasjonen) på samme variant (NB same-day forward-fill). Kronen styrket seg gjennom 2026, fra 11,21 til 10,91 i april alene.

Vi har allerede gravd i offentlige kilder. De fleste spørsmålene under har vi forsøkt å besvare selv først, det vi ber deg om er **verifikasjon, korrigering eller utdypning**, ikke grunnleggende forklaring.

## Spørsmål, prioritert

### 1. Bloomberg BFIX EURNOK 12:00 CET, er det det vi vil ha?

**Vår forståelse:** Bloomberg BFIX publiserer EUR/NOK-mid hvert 30. minutt, inkludert 12:00 CET. Det er ikke en industri-standard "12:00 fix" som matcher WMR 16:00 London, men det er det enkleste 12:00 CET-snapshotet vi kan hente fra en terminal.

**Spørsmål:**
- Er BFIX 12:00 CET den beste tilgjengelige proxyen for "interbank-mid 12:00 CET" som Nord Pool refererer til? Eller bør vi heller hente tick-data direkte fra EBS/Reuters EUR=?
- Hva er den faktiske ticker-syntaksen i Bloomberg? Vi tipper `EURNOK 12:00 BFIX Curncy`, men er ikke sikre.
- Forskjell mellom BFIX og en "vanlig" EURNOK Curncy med Time-override på 12:00, er det vesentlig?

### 2. Strømleverandørers EUR/NOK-konvertering, Nord Pool EXR eller noe annet?

**Vår forståelse fra offentlige kilder:** "Strømleverandører bruker typisk Nord Pools offisielle daglige EXR for konvertering." Men data tilsier at BKK *ikke* gjør det, hvis BKK brukte Nord Pool EXR direkte, skulle vår variant A truffet på øret. Den gir -3,25 kr avvik for april.

**Spørsmål:**
- Vet du om norske strømleverandører faktisk bruker Nord Pool EXR rett ut, eller om de typisk har en mellomstasjon (egen treasury, en spesifikk bank-fix, en aggregator)?
- Mest sannsynlige forklaring i vårt tilfelle: BKK bruker Nord Pools *preliminære* 12:00 CET-kurs (før to-banks-hedgen som lager EXR), ikke EXR selv. Gir det mening i lys av hvordan kraftbransjen i Norge organiserer fakturering?
- Sidekommentar: Norges Banks egen disclaimer sier deres kurs "kun er ment som referanse, ikke for transaksjoner". Hva bruker DNB/Nordea da i praksis for fakturering? Egen mid-kurs fra eget treasury-desk?

### 3. Intraday-volatilitet 12:00 → 14:15 i 2026

**Vår forståelse:** EUR/NOK ATR ~0,066 i 2026, GARCH-vol 8,2 % annualisert (NYU V-Lab). Et 2t15-vindu skal fange 0,015–0,025 NOK stille / 0,04–0,08 NOK travel. Våre observerte 0,02–0,05 NOK-bevegelser ligger midt i båndet.

**Spørsmål:**
- Bekrefter du at 0,02–0,05 mellom 12:00 og 14:15 er innenfor normal intraday-volatilitet for EUR/NOK, eller virker det høyt/lavt?
- Asymmetri: i feb/mar/apr 2026 har 12:00-kursen vært systematisk *høyere* enn 14:15-kursen (svakere NOK kl. 12). Er det et kjent mønster i en styrkings-trend, eller bare tilfeldig over tre måneder?
- Testbar prediksjon: hvis vi finner en måned med svekkende krone-trend, forventer vi motsatt fortegn på avviket. Anbefaler du mean-difference-test for å bevise mønster, eller noe annet?

### 4. Nord Pools "to-banks-hedging", bilateral spot-RFQ?

**Vår forståelse:** Det er en bilateral spot-RFQ (T+2 FX-spot) mot to motparter. Nord Pool sender RFQ til to banker, tar mid eller dårligste pris, og det blir den offisielle EXR. 0,005–0,015 marge mot interbank-mid er innenfor normal RFQ-spread.

**Spørsmål:**
- Stemmer denne karakteriseringen? Eller er det noe mer komplisert, option-strip, weighted spot, intraday-VWAP?
- Hvilke to banker er det typisk? Nord Pool publiserer det ikke offentlig. DNB og Nordea er antakelig kandidater for NOK-leg, men vi vet ikke sikkert.
- Tar Nord Pool bid eller ask i hedgen (siden de selger NOK-strøm til EUR-priserte forbrukere)?

### 5. NOK-likviditet rundt 12:00 CET, er mid systematisk skjev?

**Vår forståelse:** 12:00 CET er en likviditetslull for NOK, mellom Asia-close (~11:00 CET) og US-open (~14:30 CET), midt i London/Oslo-lunsj. Bid-ask kan være 2–4× bredere enn i peak-tider. BIS Triennial 2022: NOK = 1,7 % av global FX-turnover, så det er en perifer valuta uansett.

**Spørsmål:**
- Hvis spreaden er 2–4× bredere på 12:00 CET, betyr det at "mid" 12:00 CET er en dårligere estimator av "fair value" enn samme mid på 14:15 CET? Eller er bid og ask symmetrisk rundt en stabil mid, bare videre fra hverandre?
- Krohn, Mueller & Whelan (JoF 2024) viser V-formet return-reversal rundt 14:15 Frankfurt-fix, ~2bp run-up + reversal. Det er ~0,002 NOK, to størrelsesordener mindre enn vår observerte 0,02–0,05 gap. Forklarer ikke det vi ser. Stemmer det?

## Det vi kan gjøre noe med

Spørsmål 1 og 2 er mest anvendelige, de gir oss enten en bedre Bloomberg-ticker eller en helt ny hypotese om kursleverandør. 3 er kontekst for hvordan vi tolker dataene vi får tilbake. 4 og 5 er bonus, men 5 kan ha implikasjoner for om vår tilnærming i det hele tatt er meningsfull.

Ikke alle må besvares. Bare det du finner mest interessant eller har umiddelbar kunnskap om.

## Motivasjon

Avviket på 2,92 kr/mnd (eller 0,79 kr ved bytte til rå EUR + NB) er innenfor "treffer på øret"-toleransen for fakturakontroll. Vi *trenger* ikke svar. Men hele prosjektet handler om tillit til beregningene, at vi forstår nøyaktig hvorfor et tall i en sensor er som det er. Hvis vi kan dokumentere kursvalget BKK gjør, kan vi velge å implementere det samme i integrasjonen, og brukere får tall som matcher fakturaen på øret.

## Kilder vi har brukt for vår nåværende forståelse

- [Krohn, Mueller, Whelan: Foreign Exchange Fixings and Returns around the Clock, JoF 2024](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306)
- [Norges Bank WP 12/2013 (King, Osler, Rime): FX microstructure](https://www.norges-bank.no/en/news-events/news-publications/Papers/Working-Papers/2013/WP-201312/)
- [BIS Triennial 2022 OTC FX turnover](https://www.bis.org/statistics/rpfx22_fx.htm)
- [Nord Pool: Preliminary prices and exchange rates](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/)
- [SEB: Navigating the Scandies](https://sebgroup.com/our-offering/markets-and-trading/foreign-exchange/navigating-you-through-the-scandies)
- [NYU V-Lab GARCH NOK](https://vlab.stern.nyu.edu/volatility/VOL.NOK:FOREX-R.GARCH)
