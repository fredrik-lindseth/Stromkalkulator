# Hent månedsdata fra Elhub etter innlogging

Logg inn på [Elhub Min side](https://minside.elhub.no/) med BankID. Deretter kan JSON og CSV hentes med direkte lenker i den samme nettleseren, uten å navigere gjennom måler, kalender og eksportdialog.

## JSON-API

Hent forbruk og prissammenligning for en periode:

```text
GET https://minside.elhub.no/api/metering-points/<målepunkt-ID>/metering-values/interval-volume?granularity=INTERVAL&startDate=2026-10-25&endDate=2026-10-26
```

Måleverdiene ligger i `data[0].attributes.priceComparison`. Hvert element inneholder et tidsrom, forbruk i kWh og priser og kostnader for spotpris, Norgespris og strømstøtte:

```json
{
  "startTime": "2026-10-25T00:00:00+02:00",
  "endTime": "2026-10-25T01:00:00+02:00",
  "quantityKwh": 0.781,
  "direction": "Out",
  "resolution": "PT60M",
  "costNorwayPrice": 0.39,
  "costSpotPrice": 0.17,
  "costSupportPrice": 0.17,
  "norwayPrice": 0.5,
  "spotPrice": 0.2115,
  "supportPrice": 0.2115,
  "hasExceededMonthlyNorwayThreshold": false,
  "hasExceededMonthlySupportThreshold": false
}
```

Sluttdatoen må være senere enn startdatoen. Filtrer resultatet til ønsket periode. Bruk `INTERVAL` for måleintervaller; klienten har også `DAILY`, `MONTHLY` og `YEARLY`.

Bruk CSV ved fakturakontroll, siden den inneholder kvalitetsmerking som «Målt» og «Estimert». JSON-prisene er ennå ikke avstemt mot faktura.

`links.self` peker på bakgrunnstjenesten `https://api.elhub.no/meter-data/v1/metering-points/<målepunkt-ID>/price-comparison`. Bruk adressen under `minside.elhub.no` når du henter data med nettleserinnloggingen.

## CSV for fakturakontroll

```bash
python3 scripts/research/elhub_download_url.py --metering-point <målepunkt-ID-fra-fakturaen> --year 2026 --month 10
```

Åpne lenken som skrives ut i den innloggede nettleseren. Nedlastingen heter `interval-volume-<målepunkt-ID>.csv`. Kopier den til `_private/Måleverdier/elhub_oktober.csv`. Innloggingen blir i nettleseren; skriptet leser eller lagrer ingen cookies eller tokens.

### Endepunkt

```text
GET https://minside.elhub.no/api/metering-points/<målepunkt-ID>/metering-values/interval-volume.csv?filter[startDate]=2026-10-01&filter[endDate]=2026-11-01&locale=nb
```

Både CSV og JSON bruker innloggingen på Min side. Ved kall fra nettsiden sendes sesjonscookien med `credentials: include`.

CSV-en er semikolonseparert og bruker desimalkomma. Filtrer på `Fra` i ønsket måned: oktoberforespørselen ga også 24 timer fra 1. november. Kontroller `Kvalitet`, antall timer, total kWh og de tre høyeste døgnmaksene mot fakturaen før dataene brukes som fasit. Oktober 2026 har 745 timer; begge kl. 02-timene 25. oktober må beholdes med hver sin UTC-offset og sorteres etter faktisk tidspunkt.

En nettleserkommando kan vente på sidelasting selv om CSV-nedlastingen allerede er ferdig. Sjekk nedlastingsfilen før du prøver på nytt. Original CSV og reelle identifikatorer oppbevares privat; `lag_replay_fixtures.py` eksporterer tidspunkt og kWh samt kvalitetsavvik til testfixturene.

### Eksempelrespons

Eksemplet viser overgangen til vintertid og en estimert time:

```csv
Fra;Til;Målenavn;Volum;Enhet;Kvalitet;Registreringstidspunkt
2026-10-25T02:00:00+02:00;2026-10-25T02:00:00+01:00;KWH 60 Forbruk;0,489;kWh;Målt;2026-10-27T06:20:22+01:00
2026-10-25T02:00:00+01:00;2026-10-25T03:00:00+01:00;KWH 60 Forbruk;1,452;kWh;Målt;2026-10-27T06:20:22+01:00
2026-10-25T23:00:00+01:00;2026-10-26T00:00:00+01:00;KWH 60 Forbruk;1,370;kWh;Estimert;2026-10-26T06:39:22+01:00
```

De to første radene er ulike timer selv om begge starter kl. 02. Siste rad er nettselskapets estimat og skal ikke merkes som målt. `Registreringstidspunkt` forteller når verdien ble registrert, mens `Fra` og `Til` avgrenser forbruket.

## Hvor lagres dataene?

Alle prosjektstier under er relative til reporoten.

| Innhold | Plassering | I git? |
| --- | --- | --- |
| Nettleserens nedlasting | `~/Downloads/interval-volume-<målepunkt-ID>.csv` | Nei |
| Original CSV for oktober 2026 | `_private/Måleverdier/elhub_oktober.csv` | Nei, gitignorert |
| Anonymisert forbruk og kvalitetsavvik | `tests/fixtures/elhub_oktober_2026.json` | Ja |
| Verifiseringsrapport | `docs/fakturaer/bkk-oktober-2026.md` | Ja |
| Arkivert klientkode med kilde-URL og SHA-256 | `_private/research/elhub/2026-11-06/` | Nei, gitignorert |

Bruk år i navnet på nye originalfiler, for eksempel `_private/Måleverdier/elhub_november_2026.csv`, så samme måned neste år ikke overskriver historikken. Verktøyene leser både dette formatet og de eldre filnavnene uten år; årsspesifikke filer prioriteres.

## Flere endepunkter

| Endepunkt under `/api` | Innhold |
| --- | --- |
| `/session` | Innlogget økt |
| `/metering-points/<id>/metering-values/interval-volume.csv` | Forbruk med kvalitetsmerking |
| `/metering-points/<id>/metering-values/interval-volume` | Forbruk og prissammenligning som JSON |
| `/metering-points/<id>/metering-values/estimated-annual-volume` | Estimert årsforbruk; ikke testet |
| `/metering-points/<id>/metering-values/period-volume` | Periodevolum; ikke testet |

Klientkoden inneholder også `/features`, `/metering-points`, `/metering-points/<id>`, `/time/norway`, `/price-areas/<prisområde>` og rutefamiliene `/contracts/…` og `/consents/authorization-requests`, `/consents/authorization-grants` og `/consents/authorization-documents`. Disse kallene er ikke testet. Kontrakt- og samtykkefunksjonene omfatter også skrivende operasjoner.

## Innlogging og levetid

Innloggingen bruker cookien `user_session`, som ifølge Elhub utløper etter én uke og fornyes ved ny innlogging.[^elhub-cookie] Regn derfor med å logge inn på nytt ved neste månedlige fakturakontroll.

Gjenbruk nettleserøkten så lenge den virker. Når økten utløper, sender nettsiden deg til `/api/login`. Nedlastingsskriptet håndterer ikke innlogging eller fornyelse.

## Automatisk henting med Maskinporten

Min side har ingen synlig funksjon for å opprette en personlig API-nøkkel. «Gi tilgang» deler måledata med en person eller tredjepart. Automatisk henting settes opp gjennom Maskinporten.

Elhub tilbyr bedriftskunder måleverdier gjennom Maskinporten og tilgang tildelt av Elhub. Tilgangen gjelder målere registrert på samme organisasjonsnummer; delt tilgang i Min side er ikke nok. Dette er derfor ikke en direkte erstatning for innlogging til en privat strømkundes måler.[^elhub-bedrift]

### Enkeltpersonforetak og Maskinporten

Et registrert enkeltpersonforetak ser ut til å kunne bruke den ordinære bestillingsløypen. Digdir nevner uttrykkelig «Innehaver» blant rollene som kan delegere tilgang, og Altinn tildeler innehaver Hovedadministrator automatisk.[^maskinporten-selvbetjening][^altinn-fullmakt]

Foretaket må registreres hos Digdir og signere bruksvilkårene.[^maskinporten-konsument][^maskinporten-vilkar] Rettigheten «Selvbetjening av klienter i ID-porten/Maskinporten» gir adgang til å opprette klienter; API-tilbyderen må i tillegg gi tilgang til sitt API. Maskinporten-tilgang alene gir ingen Elhub-måledata.

### Privat måler via foretaket

Elhub beskriver en egen rolle, «Tredjepart API», for å hente måledata med sluttbrukerens godkjenning. Den krever Maskinporten, riktig scope, avtale med sluttbrukeren og sertifikat fra Commfides eller Buypass med samme organisasjonsnummer som aktøren hos Elhub. Tilgang til måleren kan godkjennes i Min side. Det aktuelle datasettet er `METERING_VALUES_HOUR_RESTRICTED`.[^elhub-tredjepart]

Dette er en mulig vei når måleren står på privatpersonen, og må skilles fra bedriftskundens tilgang til egne målere registrert på organisasjonsnummeret. Om Elhub godtar et enkeltpersonforetak som tredjepart for innehaverens egen private måler, er ikke bekreftet. Før bestilling av sertifikat bør Elhub avklare dette brukstilfellet, aktørregistrering, avtaler og eventuelle gebyrer.

### Opprett klienten

Foretaket skal bruke rollen API-konsument for å hente data fra Elhub. Når tilgangen hos Digdir og Elhub er på plass:

1. Logg inn i Samarbeidsportalen og gå til «Virksomhetens tjenester» → «Administrasjon av tjenester» → «Integrasjoner». Velg riktig miljø.
2. Opprett en integrasjon med Maskinporten som tjeneste.
3. Legg til scopet Elhub har tildelt foretaket, og lagre klienten. Bruk scopenavnet fra Elhub; `METERING_VALUES_HOUR_RESTRICTED` er navnet på datasettet.
4. Registrer den offentlige signeringsnøkkelen fra virksomhetssertifikatet i PEM-format. Den private nøkkelen beholdes hos tjenesten som skal hente data.

Digdir støtter også egne offentlige nøkler i JWK-format. Avklar med Elhub om dette kan brukes for deres API; veiledningen deres krever virksomhetssertifikat.

Mangler scopet i listen, må Elhub tildele tilgang til riktig organisasjonsnummer og miljø. Er oppretting av integrasjon deaktivert i produksjon, sjekk innlogging med Ansattporten og klientrettigheten i Altinn. Vises feil virksomhet, må Digdir kontrollere koblingen til e-postdomenet.[^maskinporten-klient]

### Hent nye tokens automatisk

Klienten bruker en signert JWT-forespørsel mot Maskinportens `/token`-endepunkt. Svaret inneholder `access_token` og `expires_in`, som angir levetiden i sekunder. Tokenet sendes til API-et som `Authorization: Bearer <access_token>`. Når det utløper, henter klienten et nytt med en ny signert forespørsel.

Dette gir en vei til automatisk henting uten månedlig BankID-innlogging, så lenge klienten, nøkkelen og Elhub-tilgangen er gyldige. Det som må oppbevares for senere bruk, er klientoppsettet og signeringsnøkkelen.[^maskinporten-token]

## Gjenstående avklaringer

- Elhubs godkjenning og etableringskrav for enkeltpersonforetak med rollen «Tredjepart API» og samtykke fra innehaveren som privat strømkunde.
- Hvilket scope og hvilken autentiseringsmåte Elhub krever for måledata, inkludert om registrert JWK kan brukes etter etablering med virksomhetssertifikat.
- JSON-endepunktets datogrenser, kvalitetsmetadata og prisberegninger mot CSV og faktura.
- Eventuell serverstyrt fornyelse og inaktivitetsgrense for nettleserøkten. Den dokumenterte cookielevetiden er én uke.

## Kilder

[^elhub-cookie]: [Elhub: Informasjonskapsler](https://elhub.no/personvern-og-sikkerhet/informasjonskapsler).
[^elhub-bedrift]: [Elhub: Hente ut måleverdier for bedriftskunder](https://elhub.no/artikler/hente-ut-maleverdier-for-bedriftskunder).
[^maskinporten-selvbetjening]: [Digdir: Selvbetjening av Maskinporten](https://docs.digdir.no/docs/Maskinporten/maskinporten_sjolvbetjening_web.html).
[^altinn-fullmakt]: [Altinn: Tilgang og fullmakt](https://info.altinn.no/hjelp/tilgang-og-fullmakt/).
[^maskinporten-konsument]: [Digdir: Maskinporten for konsumenter](https://samarbeid.digdir.no/maskinporten/konsument/119).
[^maskinporten-vilkar]: [Digdir: Bruksvilkår for private virksomheter](https://samarbeid.digdir.no/maskinporten/bruksvilkar-private-virksomheter/73).
[^elhub-tredjepart]: [Elhub for tredjeparter](https://elhub.no/fagomrader/aktor-og-markedsstruktur/aktorenes-roller?article=elhub-for-tredjeparter).
[^maskinporten-klient]: [Digdir: Selvbetjening som API-konsument](https://docs.digdir.no/docs/Maskinporten/maskinporten_sjolvbetjening_web.html#selvbetjening-som-api-konsument).
[^maskinporten-token]: [Digdir: Maskinportens token-endepunkt](https://docs.digdir.no/docs/Maskinporten/maskinporten_protocol_token.html).
