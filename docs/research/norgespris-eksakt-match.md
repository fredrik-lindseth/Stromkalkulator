# Norgespris: eksakt match mot publiserte Final-priser

Juni 2026-fakturaens Norgespris-linje reproduseres eksakt med Nord Pools
publiserte Final-priser. Dette besvarer spørsmålet [nok-omregning.md](nok-omregning.md)
og [bloomberg-verifisering.md](bloomberg-verifisering.md) har jaktet på siden
april: hvorfor traff vi ikke linjen på øret?

> Status: konklusjon 2026-07-06, komplett samme kveld med Elhub-CSV.
> Både mai- og juni-fakturaens Norgespris-linje reproduseres **eksakt**
> (innenfor 0,005 kr) med Elhub-kWh x Nord Pools publiserte Final-priser.
> Restavviket som tidligere ble dokumentert som et ±0,2 %-bånd var
> prisdata-årgang i HA-recorderen pluss én recorder-aggregatglipp, ikke
> kurskilde eller logikk. Reproduserbar via `just verify-norgespris`.

## Funnet

<!-- BEGIN GENERATED: verify_norgespris_eksakt -->
_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` (krever de private prisarkivene, se `just snapshot-kurs`).

| Måned | Faktura (kr) | HAN x HA-recorder | Avvik | HAN x Final | Avvik | Elhub x Final | Avvik |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mai_2026 | -1032.56 | -1033.11 | -0.55 | -1032.91 | -0.35 | -1032.56 | -0.001 |
| juni_2026 | -363.54 | -363.39 | +0.15 | -363.54 | +0.00 | -363.53 | +0.005 |

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

Elhub-CSV-ene for februar til juni (fakturagrunnlaget BKK leser) gir to
harde tall:

- Dag/natt-regelen vår er bit-identisk med BKKs: klassifiserer vi
  Elhub-timene med vår `er_dagtid`, treffer vi fakturaens dag- og natt-kWh på
  0 Wh i alle fem månedene. Mars-avviket på 1,4 kWh i HAN-dataene var
  HAN-timing-støy, ikke klassifiseringsfeil.
- kWh-kilden (HAN mot Elhub) flytter Norgespris-summen med under 0,07 kr i
  fire av fem måneder. 13-sekundersskiftet koster øre, ikke kroner.
  Unntaket er mai, se neste seksjon.

Bakgrunn for skiftet: [elhub-vs-han-vs-faktura.md](elhub-vs-han-vs-faktura.md).

## Nettleielinjene: BKKs interne avrunding er gulvet

Forbruksavgiftlinjen for juni (92,11 kr) kan ikke reproduseres fra noen
(forbruk x sats)-konvensjon: månedstotal x eksakt sats gir 92,12, per-dag- og
per-time-runding gir andre bom i andre måneder. BKK runder på et mellomnivå
vi ikke kan observere utenfra. Gulvet er ±1-2 øre per avgiftslinje, og det
er hele det gjenværende nettleie-avviket. Energileddene traff eksakt i juni.

## Mai-restavviket på -0,35 kr: løst med Elhub-CSV

Mai traff ikke eksakt med HAN-kWh x Final-priser (-0,35 kr). To hypoteser
sto igjen: kWh-serien vår, eller prisårgang i BKKs fakturakjøring. Elhub-CSV
for mai (lastet ned samme kveld) avgjorde det: **Elhub-kWh x Final treffer
fakturaen på -0,001 kr.** Avviket satt i HAN-kWh-serien.

Og det satt i én dag. Recorder-statistikken for 2. pinsedag 25. mai har
byttet delta mellom nabotimer: time 14/15 med ±0,96 kWh og time 16/17 med
±1,4 kWh. Netto kWh for dagen er nesten uendret (-6 Wh), men prisene i
timeparene var ulike, så Norgespris-summen forskjøv seg -0,34 kr. Resten av
måneden bidro med under 2 øre. Dette er samme klasse feil som
13-sekundersskiftet (delta i feil time), bare større, og den fanges ikke av
teleskop-korreksjonen fordi deltaet ble forskjøvet en hel time i
recorder-aggregatet, ikke 13 sekunder.

Konsekvens: HAN-fixturen duger til kWh-totaler (4 Wh avvik i mai), men for
eksakt Norgespris-verifisering er Elhub-kWh fasiten. RME-sporet
(Power BI-eksport av prissikringsverdier) trengs ikke lenger for dette.

## Konsekvenser i repoet

- `just snapshot-kurs` arkiverer nå også publiserte NOK-kvarterpriser
  (`scripts/research/snapshot_nordpool_nok.py`). Gratis-API-et rekker ~2
  måneder bakover, så arkivering må skje månedlig.
- `scripts/research/verify_invoice_hourly.py` viser eksakt-sjekken automatisk
  når arkivet dekker måneden. `verify_norgespris_eksakt.py` bruker også
  Elhub-CSV som kWh-kilde når `_private/Måleverdier/elhub_<måned>.csv`
  finnes. Forventning: Elhub x Final innenfor ±0,01 kr; HAN x Final kan
  bomme opp mot ~0,4 kr ved recorder-aggregatglipp (som 25. mai).
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

Elhub-radene i tabellen krever `_private/Måleverdier/elhub_<måned>.csv`
(lastes ned fra elhub.no med BankID). kWh-målingene for feb-april ble kjørt
ad-hoc 2026-07-06; mai og juni dekkes av scriptet.
