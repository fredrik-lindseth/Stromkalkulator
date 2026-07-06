# EUR/NOK intraday-volatilitet: 12:00 vs 14:15 CET

Vurderer om observerte 12:00 → 14:15 CET-bevegelser på 0,02–0,05 NOK/EUR i Q1+Q2 2026 er normale, og om det finnes systematisk skjevhet å justere for.

## 1. Er 0,02–0,05 NOK/EUR normalt?

**Ja, godt innenfor normalen. Trolig i nedre halvdel av forventet bånd.**

Referansepunkter:

- Daglig EUR/NOK-ATR i januar 2026: **0,0662** (Traders Union, 13. jan 2026).
- Daglig vol siste 30 dager (myfxbook): **~1,15%**, ca. 0,12–0,14 NOK ved kurs ~11,5.
- NYU V-Lab GARCH for NOK 22. mai 2026: **~8,2% annualisert** = ca. 0,52% daglig (~0,06 NOK).
- Krohn/Mueller/Whelan (2024): G9-valutaer har ~**2bp pre-fix run-up** i USD og like stor reversal post-fix. 2bp på EUR/NOK = ~0,002 NOK. Den _systematiske_ fix-komponenten er mye mindre enn støyen rundt.

Et 2t15-vindu fanger typisk **20–30% av daglig variasjon**. På ATR ~0,07 betyr det forventet absoluttbevegelse **0,015–0,025 NOK** stille dag, **0,04–0,08 NOK** travel dag. 0,02–0,05 ligger midt i båndet.

Konklusjon: normal intraday-støy, ikke målefeil eller strukturell anomali.

## 2. Intraday-mønstre i NOK rundt 12:00 CET

Ingen publisert studie dokumenterer en "12:00 CET dip" spesifikt for EUR/NOK, men flere kilder peker samme vei:

- BIS Triennial 2022: NOK er 1,7% av global FX-turnover, en **mindre-likvid G10**. Spreads i EUR/NOK bredere enn EUR/SEK og langt bredere enn EUR/USD.
- Norges Bank WP 2013/12 (King, Osler, Rime): mindre-likvide valutaer har **større prisimpact per ordre** og tydeligere intraday-mønstre.
- Desk-observasjoner (SEB, Nordea): NOK-likviditet konsentrert **08:00–16:00 CET**, peak under London-overlapp ~09:00–11:00 og 13:30–16:00. Vinduet **11:30–13:30 CET** er "European lunch lull", Nordic-desker redusert, US ennå ikke åpne.
- Nord Pools 12:00-snapshot faller midt i denne tynne perioden. En enkelt stor ordre kan flytte mid-prisen mer enn senere.

Rimelig å forvente at **12:00-kursen har høyere varians enn 14:15-kursen**, men ingen systematisk bias.

## 3. ECB-fix 14:15 CET, kjent vol-mønster

Krohn, Mueller & Whelan (JoF 2024, "Foreign Exchange Fixings and Returns around the Clock"):

- USD apprecierer mot G9 i opptrekket til både London-fix (16:00 CET) og **ECB-fix (14:15 CET)**, deretter reversal. W-formet over døgnet.
- Pre-fix appreciation ~**2bp**, statistisk signifikant over 21 år.
- Long-USD pre-fix / short post-fix: 11–14% annualisert mot EUR, GBP, JPY.
- Forfatterne tolker det som dealer-intermediasjon av USD-etterspørsel rundt benchmarks. NOK er ikke i G9-utvalget, men paperet generaliserer til G10.

Bias-størrelsen (2bp) er to størrelsesordener mindre enn 12:00→14:15-spreaden (0,02–0,05 NOK = ~20–45bp på kurs 11). Fix-effekten forklarer ikke observasjonen vår, den drukner i intraday-støy.

ECB publiserer ingen offisiell volatilitets- eller bias-analyse av 14:15-snapshot. Norges Bank arvet tidspunktet fra ECB i 2015–2016 av synkroniseringsgrunner og har ikke publisert egen sammenligning.

## 4. Systematisk 12:00 høyere enn 14:15 i styrkings-perioder?

Ingen publisert evidens. Hypoteser som er forenlige:

- I en trend-styrking gjennom dagen vil ethvert tidlig snapshot ligge svakere enn et senere. Ikke et NOK-fenomen, triviell konsekvens av drift.
- 12:00 CET ligger i lunch lull. Hvis Nord Pools deltakere systematisk gjør EUR-salg (NOK-inntekt-hedge) før day-ahead-auksjonen ~12:50, kan EUR/NOK presses ned mot 14:15. Spekulativt, ingen kilde dokumenterer dette.

Med ~100 handelsdager i Q1+Q2 og systematisk bias < 0,01 NOK ville en t-test sannsynligvis ikke skilt fra støy. Hvis vi ser stabilt fortegn over 100+ observasjoner, kjør en mean-difference-test før vi kaller det mønster.

## 5. Det vi ikke fant offentlig svar på

- Eksplisitt intraday-volatilitetsstudie av EUR/NOK med minutter-granularitet. Slike finnes hos Refinitiv/Bloomberg, men ikke i åpne kilder.
- ECB- eller Norges Bank-publisert bias-analyse av 14:15-snapshot vs alternative tidspunkter. Ingen av sentralbankene har offentliggjort dette.
- Kvantitativ kobling mellom Nord Pool 12:00-snapshot og EUR/NOK-mid. Ingen akademisk litteratur på krysset kraftmarked × FX-mikrostruktur for Norden.

## Kilder

- Krohn, Mueller, Whelan (2024). "Foreign Exchange Fixings and Returns around the Clock." Journal of Finance 79(1), 541–578. https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306
- Bank of Canada Staff WP 2021-48 (working-paper-versjon av samme). https://www.bankofcanada.ca/2021/10/staff-working-paper-2021-48/
- BIS Triennial Central Bank Survey 2022, OTC FX turnover. https://www.bis.org/statistics/rpfx22_fx.htm
- King, Osler, Rime (2013). "The market microstructure approach to foreign exchange." Norges Bank WP 12/2013. https://www.norges-bank.no/en/news-events/news-publications/Papers/Working-Papers/2013/WP-201312/
- ECB Framework for euro foreign exchange reference rates. https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- Norges Bank, exchange rates FAQ (14:15 CET snapshot, synkronisert med ECB). https://www.norges-bank.no/en/topics/statistics/exchange_rates/valutakursar-faq/
- NYU V-Lab, NOK GARCH volatility. https://vlab.stern.nyu.edu/volatility/VOL.NOK:FOREX-R.GARCH
- Traders Union, EUR/NOK ATR & forecast. https://tradersunion.com/currencies/forecast/eur-nok/long-term-forecast/
- myfxbook EUR/NOK volatility. https://www.myfxbook.com/forex-market/volatility/EURNOK
- SEB, "Navigating you through the Scandies". https://sebgroup.com/our-offering/markets-and-trading/foreign-exchange/navigating-you-through-the-scandies
