# Norgespris: eksakt match mot publiserte Final-priser

Juni 2026-fakturaens Norgespris-linje reproduseres eksakt med Nord Pools
publiserte Final-priser. Dette besvarer spørsmålet [nok-omregning.md](nok-omregning.md)
og [bloomberg-verifisering.md](bloomberg-verifisering.md) har jaktet på siden
april: hvorfor traff vi ikke linjen på øret?

> Status: konklusjon 2026-07-06. Juni 2026-fakturaens Norgespris-linje
> reproduseres **eksakt** (0,00 kr avvik) med Nord Pools publiserte
> Final-kvarterpriser og våre HAN-kWh. Restavviket som tidligere ble
> dokumentert som et ±0,2 %-bånd var prisdata-årgang i HA-recorderen, ikke
> kurskilde eller logikk. Reproduserbar via `just verify-norgespris`.

## Funnet

<!-- BEGIN GENERATED: verify_norgespris_eksakt -->
_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` (krever de private prisarkivene, se `just snapshot-kurs`).

| Måned | Faktura (kr) | HA-recorder (kr) | Avvik | Publisert Final (kr) | Avvik |
| --- | ---: | ---: | ---: | ---: | ---: |
| mai_2026 | -1032.56 | -1033.11 | -0.55 | -1032.91 | -0.35 |
| juni_2026 | -363.54 | -363.39 | +0.15 | -363.54 | +0.00 |

Prisårgang-dager (HA-recorderen har foreløpig kurs, publisert er Final):

| Dag | Ukedag | HA/publisert | Timer |
| --- | --- | ---: | ---: |
| 2026-05-02 | lør | 0.99892 | 24 |
| 2026-05-03 | søn | 1.00055 | 24 |
| 2026-05-10 | søn | 1.00444 | 24 |
| 2026-05-17 | søn | 1.00164 | 24 |
| 2026-05-24 | søn | 0.99696 | 21 |
| 2026-05-25 | man | 0.99673 (varierende) | 23 |
| 2026-05-31 | søn | 0.99769 | 24 |
| 2026-06-14 | søn | 0.99558 | 24 |
| 2026-06-21 | søn | 1.00304 | 24 |

Symmetri: mai_2026 har 35 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -20.61 kr); juni_2026 har 83 timer med spot under 50 øre inkl. mva (å klippe dem ville flyttet summen -27.61 kr). BKK fakturerer symmetrisk.
<!-- END GENERATED -->

Beregningen er den samme som integrasjonen gjør: `(0,50 - spot inkl. mva) x
kWh`, summert time for time, med 13-sekunders-korreksjonen på kWh. Det eneste
som byttes er priskilden: HA-recorderens lagrede timesnitt mot Nord Pools
publiserte Final-kvarterpriser (snitt av 4 kvarter per time, som er
avregningsprisen for timesavregnede kunder etter MTU15).

## Prisårgang: derfor avviker recorder-prisene

HA-integrasjonen henter NOK-prisene når de publiseres, dagen før levering.
På dager der valutamarkedet er stengt på auksjonsdagen (søndager og enkelte
helligdager, auksjonen kjøres lørdag/helligdag) er kursen i publiseringen
foreløpig. Nord Pool korrigerer senere til Final, men integrasjonen henter
ikke gamle dager på nytt, så recorderen beholder den foreløpige årgangen.
Det er dette vi kaller prisårgang: samme time, samme EUR-pris, to utgaver
av NOK-prisen.

Beviset er at avvikene ligger som konstant faktor over hele leveringsdøgn,
kun på slike dager (tabellen over). 10. mai impliserer HA-prisene kurs
10,8513, mens Final er 10,80338. Samme EUR-priser, annen kurs.

At juni treffer 0,00 med Final-priser beviser samtidig at BKK fakturerer
Final-årgangen, ikke den foreløpige.

## Symmetrien er bevist

Juni hadde 83 timer med spot under 50 øre inkl. mva. I de timene betaler
Norgespris-kunden mellomlegg til BKK, og de inngår i fakturaens sum: uten dem
ville linjen vært 27,61 kr mer i kundens favør. Integrasjonens symmetriske
formel er altså riktig, og det er ikke lenger en antakelse.

## kWh-siden: målt mot Elhub

Elhub-CSV-ene for februar, mars og april (fakturagrunnlaget BKK leser) gir to
harde tall:

- Dag/natt-regelen vår er bit-identisk med BKKs: klassifiserer vi
  Elhub-timene med vår `er_dagtid`, treffer vi fakturaens dag- og natt-kWh på
  0 Wh i alle tre månedene. Mars-avviket på 1,4 kWh i HAN-dataene var
  HAN-timing-støy, ikke klassifiseringsfeil.
- kWh-kilden (HAN mot Elhub) flytter Norgespris-summen med -0,02, -0,07 og
  +0,00 kr. 13-sekundersskiftet koster altså øre, ikke kroner.

Bakgrunn for skiftet: [elhub-vs-han-vs-faktura.md](elhub-vs-han-vs-faktura.md).

## Nettleielinjene: BKKs interne avrunding er gulvet

Forbruksavgiftlinjen for juni (92,11 kr) kan ikke reproduseres fra noen
(forbruk x sats)-konvensjon: månedstotal x eksakt sats gir 92,12, per-dag- og
per-time-runding gir andre bom i andre måneder. BKK runder på et mellomnivå
vi ikke kan observere utenfra. Gulvet er ±1-2 øre per avgiftslinje, og det
er hele det gjenværende nettleie-avviket. Energileddene traff eksakt i juni.

## Mai-restavviket på -0,35 kr

Mai treffer ikke eksakt med Final-priser. Det som er utelukket: kWh-kilden
(±0,07 kr målt), fallback-prisene for 1.-4. mai (EUR-fixture x
exchangeRate-arkivet, validert mot 432 overlapp-timer med median 0,003
øre/kWh avvik, kan maks flytte ~0,01 kr) og BKK-avrunding (juni traff eksakt
uten avrundingsledd). Gjenstående kandidater:

1. Mai-kWh-serien vår mot Elhubs (mai-CSV er ikke lastet ned, krever BankID).
2. Prisårgang i selve fakturakjøringen: mai hadde 7 årgang-dager mot junis 2,
   og en Final-korreksjon etter BKKs fakturakjøring ville gitt akkurat et
   slikt avvik.

Dommerne er Elhub-CSV for mai og RMEs publiserte prissikringsverdier
(Power BI-eksport, se [bloomberg-verifisering.md](bloomberg-verifisering.md)).
0,35 kr på 1032,56 er 0,034 %, godt innenfor praktisk fakturakontroll.

## Konsekvenser i repoet

- `just snapshot-kurs` arkiverer nå også publiserte NOK-kvarterpriser
  (`scripts/research/snapshot_nordpool_nok.py`). Gratis-API-et rekker ~2
  måneder bakover, så arkivering må skje månedlig.
- `scripts/research/verify_invoice_hourly.py` viser eksakt-sjekken automatisk
  når arkivet dekker måneden. Forventning: |avvik| <= 0,05 kr.
- [neste-maaned-prosedyre.md](../fakturaer/neste-maaned-prosedyre.md) og
  [begrensninger.md](../begrensninger.md) er oppdatert: recorder-avviket på
  0,04-0,05 % er prisårgang og gjelder bare den løpende sensoren, ikke
  verifiseringen.

Live-sensoren i HA kan ikke bli mer presis her: den akkumulerer med prisen
slik den ser ut i leveringstimen, og på søndager kan det være foreløpig
kurs. Korreksjonen kommer etterpå, og en akkumulert sum kan ikke rettes
bakover. Feilen er 0,1-0,6 kr per måned og vasker seg delvis ut.

## Reprodusering

```bash
# Arkiver priser (krever internett, kjør månedlig før vinduet lukker)
just snapshot-kurs

# Eksakt-verifisering av alle måneder med prisdekning (uten nett)
just verify-norgespris

# Oppdater den genererte tabellen i denne filen
python3 scripts/research/verify_norgespris_eksakt.py --emit-markdown
python3 scripts/research/inject_generated.py
```

kWh-målingene mot Elhub (feb-april) ble kjørt ad-hoc 2026-07-06 med
Elhub-CSV-ene i `_private/Måleverdier/` og fixturene i `tests/fixtures/`;
tallene står i teksten over og lar seg reprodusere med samme filer.
