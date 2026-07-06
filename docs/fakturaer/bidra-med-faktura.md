# Bidra med faktura for verifisering

Integrasjonen er per i dag kun verifisert mot BKK (NO5). For å sikre at beregningene er korrekte i hele Norge trenger vi ekte fakturaer fra brukere i andre prisområder og hos andre nettselskaper.

**Du trenger ikke Home Assistant eller integrasjonen for å bidra.**

## Hva vi trenger

1. **Fakturaen din** (PDF eller skannet kopi) hvor priselementene er synlige
2. **Elhub-eksport** av timesforbruket for samme periode

Begge må være fra samme måned for at vi skal kunne sammenligne.

## Slik henter du Elhub-eksport

1. Gå til [elhub.no](https://elhub.no) og logg inn med BankID
2. Velg "Mine målepunkter"
3. Velg perioden som matcher fakturaen
4. Eksporter som CSV

Tar 30 sekunder. CSV-en inneholder kun forbruksverdier per time, ingen personlig informasjon utover MålepunktID.

## Hva fakturaen må vise

For at vi skal kunne verifisere må disse postene være synlige:

- Energiledd dag (kWh × øre/kWh)
- Energiledd natt/helg (kWh × øre/kWh)
- Kapasitetstrinn eller fastledd (kr/mnd)
- Forbruksavgift (kWh × øre/kWh)
- Enova-avgift (hvis aktuelt)
- Eventuelle støtteordninger (strømstøtte, Norgespris-kompensasjon)
- Total nettleie

De fleste norske nettleie-fakturaer har dette som standard. BKK, Elvia, Tensio, Lnett og Lede formaterer det i en tabell.

## Områder vi er mest interessert i

Listet etter hvor mye verdi det gir oss:

1. **Nord-Norge (NO4)** med nettselskap som Nordlandsnett, Lofotkraft, Troms Kraft, Hålogaland Kraft. Avgiftssone Nord-Norge har ingen mva på strøm og redusert forbruksavgift. Vi har kode for det, men null faktura-verifisering ennå.

2. **Tiltakssonen (Finnmark + Nord-Troms)** har ingen mva i det hele tatt, og er en egen kategori.

3. **NO2 (Sør-Vest)** med Lnett eller Lede. Vi fikset nettopp tariff-bugs i begge basert på offisielle prislister, men har ikke verifisert at fikset treffer ekte fakturaer.

4. **NO3 (Midt-Norge)** med Tensio TN eller Tensio TS. Største nettselskap i regionen.

5. **NO1 (Sør-Norge/Østlandet)** med Elvia. Norges største nettselskap.

NO5 (Bergens-området) med BKK er allerede dekket, og NO1 med andre nettselskaper enn Elvia (f.eks. Glitre Nett, Norgesnett, Asker Nett) er fint å ha, men ikke prioritert.

## Norgespris eller strømstøtte

Begge ordninger er interessante. Norgespris-kunder (de fleste fra 1. oktober 2025) har en "Norgespris-kompensasjon"-linje på fakturaen. Ikke-Norgespris-kunder har "strømstøtte". Vi verifiserer begge formler.

Hvis du har **både** Norgespris og strømstøtte på samme faktura (overgangsmåned), enda bedre.

## Personvern

- Send gjerne anonymisert: stryk over navn, adresse og målepunkt-ID
- Vi trenger ikke kundenummer eller fakturanummer
- Elhub-CSV-en kan beholde MålepunktID (det er ikke personnummer-koblet i klartekst)
- Faktura-data legges inn i åpent repo, så hvis du er usikker, anonymiser før du sender

## Hvor sender du?

Lag et issue på [GitHub: hacs-strømkalkulator/issues](https://github.com/fredrik-lindseth/Stromkalkulator/issues) eller send direkte. Vedlegg trenger ikke ligge på GitHub, kan sendes på e-post eller Signal etter avtale.

## Hva skjer etterpå

For hver faktura:

1. Vi legger inn forventede tall i `tests/test_faktura_bkk.py` (eller en ny fil hvis det blir mange)
2. Timesdataene legges i `tests/fixtures/<nettselskap>_<måned>_hourly.json`
3. En replay-test verifiserer at coordinator-output matcher fakturaen på øret
4. Hvis avviket er > 1 kr graver vi i hva som er forskjellig, og enten oppdaterer integrasjonen eller dokumenterer kjent begrensning

Tar ~30 minutter per faktura å integrere.

## Takk

Hver faktura som blir lagt inn dekker tusenvis av brukere i samme nettselskap. Det er noe av det mest verdifulle du kan bidra med.
