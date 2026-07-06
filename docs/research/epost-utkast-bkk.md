# Utkast: epost til BKK om Norgespris-snittpris

Til din kontakt i BKK. Mål: hvilken EUR/NOK-kurs og snittberegning brukes for Norgespris-snittpris på fakturaen.

## Bakgrunn

Vi har bygd et open source-verktøy som verifiserer BKK-fakturaer linje-for-linje. Alle linjer treffer på øret unntatt Norgespris-snittpris, der vi ligger 0,14 % over. Avviket er marginalt, men vi vil dokumentere hvorfor.

## Epost-utkast

Emne: Hvilken EUR/NOK-kurs brukes for Norgespris-snittpris?

```
Hei,

Jeg har laget en Home Assistant-integrasjon som
verifiserer BKK-fakturaer mot egen AMS-måler-data.

Alle linjer matcher på øret unntatt Norgespris-snittpris, der vi
ligger 0,14 % over deres beregning.

For april 2026 (faktura 000000000):

- Vår vektede snittspot inkl. mva: 1,5355 kr/kWh
- Fakturas implisitte snitt (fra -1,0333 kr/kWh på Norgespris-linjen): 1,5333 kr/kWh
- Diff: 2,92 kr av 1427,89 kr

To spørsmål:

1. Hvilken EUR/NOK-kurs bruker dere? Nord Pools egne NOK-priser, Norges Banks daglige fixing, eller noe annet?

2. Snittes kursen aritmetisk over måneden, eller forbruksvektes den per time?

Jeg vil bare kunne dokumentere "BKK bruker X" i verktøyet, så brukere forstår hvorfor vi har 0,14 % rest-avvik, og eventuelt kan vi bruke samme kurs. Fakturaen er riktig.

Mvh
<kunde>
Kunde nr. 00000000
```

## Hva du gjør med svaret

Oppdater [research/nok-omregning.md](nok-omregning.md) med svaret. Hvis BKK bruker en kurs vi enkelt kan replikere, vurder å bygge inn samme logikk for å lukke gapet. Hvis ikke, behold som dokumentert kjent avvik.
