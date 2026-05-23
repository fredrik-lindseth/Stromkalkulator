# 12:00 CET-fixinger og hva norske banker faktisk bruker

Kilder hentet via offentlige websøk mai 2026. Ingen tilgang til Bloomberg/Refinitiv-terminal, så ticker/RIC kan ikke verifiseres direkte mot live terminaler.

## 12:00 CET-fixing for EUR/NOK

### Konkret svar

Det finnes **ingen enkelt "industri-standard 12:00 CET-fix"** for EUR/NOK analogt med WMR/Refinitiv 16:00 London. Kandidatene:

- **ECB Reference Rate:** concertation ca. 14:10 CET, publiseres ca. 16:00 CET. Disclaimer: *"Using the rates for transaction purposes is strongly discouraged."* Ikke en 12:00-fix.
- **Bloomberg BFIX:** publiseres hver 30. minutt mens markedet er åpent. Det finnes derfor en **BFIX EURNOK 12:00 CET (11:00 GMT)** som datapunkt, TWAP over 306-sek vindu (G10). Ticker-konvensjon `EURNOK BFIX <GO>`, men eksakt streng krever terminal.
- **WMR/LSEG:** hovedfix 16:00 London. Tilbyr også **WMR 2PM CET FX Spot Rate** som egen benchmark, og **WMR Intraday Service** med timesfix 06:00–21:00 UK-tid. EUR/NOK 11:00 GMT er inkludert i intraday-abonnementet, men ikke et eget produkt.
- **Reuters EUR= / EBS snapshot:** råkilde, ikke benchmark.

### Hva Nord Pool faktisk gjør

Nord Pools formulering om "interbank-kurs 12:00 CET" er **deres egen prosess, ikke en publisert benchmark**:

> "Prior to price calculation, Nord Pool gets the currency rates valid at 12:00 CET. (...) Once EUR prices are complete, Nord Pool contacts two banks to perform official currency hedging, and the official exchange rates are set."
> ([Nord Pool: Preliminary prices and exchange rates](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/))

Preliminær interbank-snapshot brukes til auksjonsclearing. Deretter ringer Nord Pool to banker (ikke navngitt offentlig) som hedger og setter den **offisielle EXR-kursen** publisert etter clearing. EXR er altså ikke en markedsfix, det er hedge-prisen.

### Bloomberg-ticker / RIC

- BFIX 12:00 CET: ikke verifisert eksakt ticker. Bloomberg dokumenterer mønsteret `BFIX <currency pair> <time> <GO>`. Pris/produkt-info: [Bloomberg BFIX](https://www.bloomberg.com/professional/products/indices/fx-fixings-reference-rates/).
- WMR Intraday EUR/NOK 11:00 GMT: krever LSEG-abonnement, RIC-mønster `EURNOK=WM11` eller tilsvarende (ikke verifisert).
- ECB: `EXR.D.NOK.EUR.SP00.A` (SDMX-kode, ikke en intraday-fix).

### Andre kraftaktører

- **Nord Pool:** egen EXR via to-banks hedge.
- **EPEX SPOT / Nordic NEMOer (SDAC/SIDC):** day-ahead kjøres i EUR, konvertering håndteres av lokale clearinghus. Metodikk for EUR/NOK på sluttoppgjør er **ikke funnet** offentlig.

### Ikke funnet

- Eksakt Bloomberg-ticker for BFIX EURNOK 12:00 CET (krever terminal).
- Hvilke to banker Nord Pool ringer.
- Kommersiell benchmark som eksplisitt markedsfører "12:00 CET EUR/NOK fix".

## Hva bruker norske banker og bedrifter

### Konkret svar

**Det finnes ingen enkelt bransje-standard.** Praksis varierer per bank, per transaksjonstype og per beløpsstørrelse:

1. **Norges Banks midkurs (`B.EUR.NOK.SP`)** publiseres ca. 16:00 CET basert på ECBs 14:15-concertation. Norges Banks egen disclaimer: *"The exchange rates are only intended to serve as an indication, and are not binding on Norges Bank or other banks."* Den brukes derfor primært til **rapportering, regnskap, statistikk og skatt**, ikke til banktransaksjoner. ([Norges Bank: Exchange rates](https://www.norges-bank.no/en/topics/statistics/exchange_rates/))

2. **Banker (DNB, Nordea) bruker egne treasury-kurser** for kundetransaksjoner. DNB publiserer daglig overførselskursliste (kjøp/salg med spread) og separat midkurs. For ordre < 1 MNOK i likvide kryss veksles løpende på treasury-kurs innenfor 08:00–17:00.

3. **Strømleverandører ved EUR-eksponering:** vanlig praksis er **Nord Pools offisielle daglige EXR**, fordi det er den faktiske clearing-kursen. Eidsiva og lignende standardvilkår viser til Nord Pools dagskurs.

4. **[Forskrift om Norges Banks notering](https://lovdata.no/dokument/LTI/forskrift/1991-08-28-561)** regulerer kun selve noteringen, ikke hvilken kurs bedrifter må bruke. Ingen forskrift pålegger strømleverandører en bestemt kilde.

### Anvendelse på BKK-tallene

BKK 11,0706 ligger mellom NB 11,0229 og Nord Pool EXR 11,0815. En 12:00 CET interbank-snapshot **kan** forklare differansen mot ECBs 14:15-snitt (intradag-bevegelse), men uten BKKs faktiske kilde-feed er dette spekulativt.

### Ikke funnet

- Konkret tekstreferanse i BKK/norske strømleverandørers vilkår på hvilken EUR/NOK-kilde og tidsstempel som brukes.
- Leverandør som publiserer kurs-metodikk på Nord Pool-nivå.
- Om Finanstilsynet eller NVE har ført tilsyn med kurs-praksis.

## Kilder

- [Nord Pool: Preliminary prices and exchange rates](https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/)
- [Bloomberg BFIX Methodology (PDF)](https://assets.bbhub.io/professional/sites/27/BFIX-Methodology.pdf)
- [Bloomberg BFIX product page](https://www.bloomberg.com/professional/products/indices/fx-fixings-reference-rates/)
- [LSEG WMR 2PM CET FX benchmark](https://www.refinitiv.com/en/financial-data/financial-benchmarks/wm-refinitiv-fx-benchmarks/cet-fx-spot-rate)
- [LSEG WMR Methodology (PDF)](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/wmr-fx-methodology.pdf)
- [ECB Euro foreign exchange reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
- [Norges Bank: Exchange rates](https://www.norges-bank.no/en/topics/statistics/exchange_rates/)
- [Norges Bank FAQ valutakurser](https://www.norges-bank.no/en/topics/statistics/exchange_rates/valutakursar-faq/)
- [Norges Bank: Bruk av referansekurser (Aktuell kommentar 8/14)](https://norges-bank.brage.unit.no/norges-bank-xmlui/bitstream/handle/11250/2558045/aktuell_kommentar_08_14.pdf)
- [DNB Markets daglig overførselskursliste](https://www.dnb.no/bedrift/markets/valuta-renter/kursliste/overforsel/daglig)
- [Lovdata: Forskrift om Norges Banks notering (1991-08-28-561)](https://lovdata.no/dokument/LTI/forskrift/1991-08-28-561)
