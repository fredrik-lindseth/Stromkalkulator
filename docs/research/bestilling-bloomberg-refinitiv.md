# Bestilling: EUR/NOK 12:00 CET interbank-spot via Bloomberg eller Refinitiv

For å lukke siste 0,79 kr i Norgespris-verifiseringen ([nok-omregning.md](nok-omregning.md)) trenger vi historiske EUR/NOK-kurser fra det tidspunktet Nord Pool selv bruker som preliminær kurs.

## Hva vi vil ha

**EUR/NOK spot mid-price (interbank), daglig snapshot kl. 12:00 Europe/Oslo lokal tid, for hver bankdag i januar–april 2026.**

Ca. 80 datapunkter. CSV-format:

```
date,bid,ask
2026-01-02,11.7980,11.7990
2026-01-05,11.7790,11.7800
...
```

Hvis kun én verdi (mid eller last) er tilgjengelig fra terminalen, holder det. Vi regner ut mid selv hvis vi får bid+ask.

## Hvorfor 12:00 Europe/Oslo

Nord Pool dokumenterer eksplisitt at de henter interbankkurs 12:00 CET som preliminær kurs for NOK-konvertering av day-ahead-priser. Kilde: <https://www.nordpoolgroup.com/en/trading/Day-ahead-trading/Preliminary-prices-and-exchange-rates/>.

Norges Banks publiserte kurs (B.EUR.NOK.SP) er 14:15 CET-snapshot — to timer senere. Vår analyse av BKK-fakturaen viser implisitt kurs 11,0706 NOK/EUR for april 2026, som ligger mellom NB 14:15 CET (11,06) og Nord Pools EXR etter to-banks-hedge (11,08). Dette stemmer med 12:00 CET-snapshot før hedge.

**Merk DST:** april–oktober er CEST (UTC+2), november–mars er CET (UTC+1). 12:00 Oslo = 10:00 UTC i april, 11:00 UTC i januar–februar. Lettest å spørre på lokal Oslo-tid og la terminalen håndtere DST.

## Bloomberg-spørring

**Ticker:** `EURNOK Curncy`
**Felt:** `PX_MID` (eller `PX_BID` + `PX_ASK`)
**Periode:** 2026-01-02 til 2026-04-30, daglig
**Snapshot:** 12:00 Europe/Berlin (= Europe/Oslo)

### Terminal

```
EURNOK Curncy HP <GO>
```

Sett:
- Period = Daily
- Time = 12:00
- Time Zone = Europe/Berlin (TZ-kode 20)

### Excel (BDH-formel)

```
=BDH("EURNOK Curncy","PX_MID","01/02/2026","04/30/2026",
     "Per","D","Time","12:00","TimeZone","20")
```

For bid og ask:
```
=BDH("EURNOK Curncy","PX_BID,PX_ASK","01/02/2026","04/30/2026",
     "Per","D","Time","12:00","TimeZone","20")
```

## Refinitiv (Eikon/Workspace)

**RIC:** `EURNOK=` (interbank spot — ikke `EURNOK=R`, som er Reuters internal)
**Felt:** `BID`, `ASK` eller `MID_PRICE`
**Periode:** 2026-01-02 til 2026-04-30
**Snapshot:** 12:00 Europe/Oslo

### Eikon Excel

```
=TR("EURNOK=","TR.BIDPRICE;TR.ASKPRICE",
    "SDate=2026-01-02 SEdate=2026-04-30 Frq=D Time=12:00 TZ=Europe/Oslo")
```

### Tick History (om tilgjengelig)

```
RIC=EURNOK=
Date Range: 2026-01-02 to 2026-04-30
Tick interval: Daily at 10:00 UTC (april) / 11:00 UTC (jan–mars)
```

## Hva vi gjør med dataene

1. Kjører `scripts/research/match_norgespris_variants.py` med 12:00 CET-kursen som ny variant
2. Sammenligner mot fakturaens implisitte snittspot for hver av de fire månedene
3. Hvis avviket går mot 0 har vi bekreftet at BKK bruker Nord Pool preliminary-kurs, og vi kan oppdatere [nok-omregning.md](nok-omregning.md) med endelig konklusjon

## Backup-bestilling (hvis 12:00 ikke er tilgjengelig)

Hvis terminalen bare har closing-priser eller bestemte fastsette tidspunkter:

- 11:00 GMT (= 12:00 CET / 13:00 CEST) — interbank london-fix-tidspunkt
- 14:15 CET — ECB/NB-snapshot (forventet å matche våre eksisterende NB-data)
- 16:00 CET — london-close

Da kan vi sammenligne flere kandidater i samme analyse.

## Kontakt

Spørsmål om hva vi trenger eller hvordan dataene skal formateres: Fredrik (eier av hacs-strømkalkulator).
