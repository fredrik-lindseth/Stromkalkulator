# Forward-spread, to-banks-hedging og NOK-likviditet rundt 12:00 CET

Kort markedsresearch på to spørsmål rundt Nord Pools EXR-fixing og hypotesen om at BKKs implisitte EUR/NOK er Nord Pools 12:00 CET-spot.

## To-banks-hedging hos Nord Pool

**Hva det er.** Nord Pool sin tekst: "Once EUR prices are complete, Nord Pool contacts two banks to perform official currency hedging" ([Nord Pool Preliminary prices](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/)). I markedstermer er dette en **bilateral spot-hedge med RFQ** (request-for-quote) mot to motparter, ikke en publisert benchmark. Day-ahead-cashflow har valuteringsdato T+2 (standard FX-spot), så hedgen er en vanlig spot-deal, ikke en 24-timers forward. Ingen offentlig dokumentasjon nevner forward-strip eller opsjoner.

**Hvilke to banker.** Ikke offentliggjort. Nord Pool publiserer en liste over **pre-approved settlement banks** ([PDF](https://www.nordpoolgroup.com/48e896/globalassets/download-center/settlement-collateral-and-fees/settlement-banks_contact-list.pdf)) hvor DNB, Nordea Norge og SEB Oslo er nordiske kandidater, men det er ikke det samme som hedge-motpartene. Mest sannsynlige kandidater for NOK-leg er DNB og Nordea (de to dominerende NOK-market-makerne), men dette er kvalifisert gjetning, ikke dokumentert.

**Er 0,005–0,015 over interbank-mid normal spread?** Ja, innenfor normal RFQ-spread for NOK-spot i 2025–2026. LSEG/WMR-metodikken har bid-ask på spot-NOK på noen tideler av en øre i markedsdyp ([LSEG WMR](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/wmr-fx-methodology.pdf)). En RFQ-quote på 5–15 pip (0,005–0,015 NOK på kurs ~11,5) inkluderer bid-ask + bankens marge for motpartsrisiko og likviditetstilbud.

**Rekonstruksjon fra kjent 12:00 CET-spot.** Beste tilnærming er å starte med ECB-referansekurs (publisert ~16:00 CET, samplet 14:15 CET, [ECB EUR/NOK](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-nok.en.html)) og rulle bakover med tom-next swap points + intraday spot-move til ~12:00. Uten Bloomberg/Reuters tick-data er det ikke gjørbart presist. EXR = preliminær-12:00 + bank-marge er sannsynligvis like nær som du kommer.

**Det vi ikke fant:** identiteten på de to bankene, eksakt RFQ-tidspunkt mellom 12:00 og 13:00, og hvorvidt Nord Pool tar bid eller ask (sannsynligvis ask siden de kjøper NOK for å betale norske selgere, men ikke bekreftet).

## NOK-likviditet rundt 12:00 CET

**Ja, 12:00 CET er et likviditetshull for NOK.** Tokyo stenger ~09:00 CET, Singapore/Hong Kong ~10:00–11:00 CET, og europeisk peak-liquidity starter når New York åpner ~14:30 CET. Vinduet 11:00–13:30 CET kalles ofte "London lunch lull" i FX-litteraturen, og effekten er sterkere for non-USD G10 og spesielt for de mindre G10-valutaene (NOK, SEK, NZD). For NOK forsterkes dette av at primær interbank-aktivitet er Oslo-basert og at Nordic-desks tar lunsj 11:30–12:30. Mest aktive NOK-vindu er 08:00–10:30 CET og igjen 14:00–16:30 CET når London-New York-overlapp gir tightest spreads.

**Mid-skjevhet, ikke bare bredere spread.** Krohn, Mueller & Whelan (2024, Journal of Finance) dokumenterer V-formet return-reversal rundt 14:15 Frankfurt-fixet og 16:00 London-fixet, USD apprecierer 2 bps inn mot fixet og depresierer like mye etterpå ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3521370), [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306)). Implikasjonen for 12:00 CET er at mid-kursen der ikke er en upartisk estimator av "ekte" spot: den ligger i pre-fix-drift-sonen, og bid-ask kan være asymmetrisk fordi market-makere skewer mot forventet hedge-flow.

**Størrelsesorden av effekt.** 12:00 CET-mid vs 14:15 CET-mid kan systematisk avvike med flere bps på G10-cross som NOK, både fra reell prisbevegelse og fra mid-asymmetri når bid-ask brer seg fra ~0,5–1 pip i peak til 2–4 pip i lull (referansenivå fra [BIS Working Paper 836 om FX-spot/swap-likviditet](https://www.bis.org/publ/work836.pdf)). Et systematisk avvik på 0,02–0,05 NOK (~17–43 bps på kurs 11,5) er **for stort til å forklares av bare 12:00-vs-14:15-mid**. Bankmargen i to-banks-hedgen (5–15 pip = ~0,005–0,015 NOK) lukker noe av gapet, men ikke alt. Det resterende gapet på ~0,01–0,03 NOK trenger en annen forklaring.

**Det vi ikke fant:** publiserte NOK-spesifikke spread-målinger på 12:00 CET fra BIS Triennial 2022/2025 (BIS rapporterer turnover, ikke intraday-spread per valuta). Krohn et al. rapporterer aggregert G10-effekt, ikke NOK isolert. Det finnes ikke offentlig data på Nord Pools faktiske hedge-pris vs interbank-mid samme dag, det måtte kommet fra Nord Pool selv eller en av de to bankene.

## Konklusjon for BKK-hypotesen

12:00-vs-14:15-timing forklarer **delvis** 0,02–0,05 NOK-gapet (anslagsvis 0,005–0,015 fra hedge-marge + noen pip fra mid-skjevhet i lull-vinduet), men ikke alt. Verdt å sjekke om BKK faktisk bruker EXR direkte, eller om de legger på en egen valutamarge oppå.
