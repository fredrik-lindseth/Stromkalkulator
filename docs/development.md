# Utvikling

## Arkitektur

Home Assistant viser bare spotpris. Norske strømfakturaer har flere komponenter (energiledd, kapasitetsledd, avgifter, strømstøtte). Strømkalkulator beregner faktisk totalpris.

### Filstruktur

```text
custom_components/stromkalkulator/
├── __init__.py      # oppsett, registrer platforms
├── config_flow.py   # UI-konfigurasjon
├── const.py         # konstanter, avgifter, helligdager
├── dso.py           # nettselskap-data
├── coordinator.py   # DataUpdateCoordinator, beregningslogikk
├── inputadapter.py  # validering, enheter og kildebundet energibaseline
├── avregning.py     # energi og pris fordelt på UTC-intervaller
├── kostnad.py       # kroner per intervall og fastledd som periodebeløp
├── sensor.py        # alle sensorer
├── binary_sensor.py # varsler (kapasitet, måledata, aktiv ordning)
├── button.py        # "Lag fakturarapport"-knapp
├── repairs.py       # fix-flows for repair-varslene
├── diagnostics.py   # HAs inngang til diagnostikk
├── diagnostikk.py   # selve diagnostikk-snapshotet
├── strings.json     # oversettbare strenger
├── icons.json       # ikon per entitet, slått opp på translation_key
├── translations/    # nb.json, en.json
└── manifest.json    # HACS-metadata
```

Coordinator oppdateres hvert minutt og leser brukerens sensorer gjennom
`inputadapter.py`. Den binder sammen avregning, kostnadsberegning, vakthold og
lagring per `entry.entry_id`, inkludert energibaseline, akkumulatorer og
effekthistorikk. Sensorer er gruppert i seks devices, arver fra
`CoordinatorEntity` + `SensorEntity` og leser fra `coordinator.data["key"]`.

DSO-data (`dso.py`) er en dict med alle nettselskaper, energiledd dag/natt og kapasitetstrinn. Tidligere kalt `tso.py`. `CONF_DSO` beholder strengverdien `"tso"` for bakoverkompatibilitet.

### Beregningsflyt

```text
Effekt + kumulativ energi (valgfri) + spotpris + valgfrie input
                            │
                            ▼
           inputadapter.py: validering og normalisering
                            │
                            ▼
                coordinator.py: polling hvert minutt
                            │
                            ▼
         avregning.py: energi og pris på UTC-intervaller
                            │
                            ▼
       kostnad.py: energikostnad, støtte og Norgespris
                   + fastledd etter medgått måned
                            │
                            ▼
          coordinator.data → sensorer og fakturarapport
```

Med energisensor brukes differansen mellom kildebundne telleravlesninger.
Uten energisensor estimeres forbruket fra effekt og faktisk medgått tid.
Observasjonstiden styrer bokføringen; polltiden er ikke i seg selv
forbrukstidspunktet. Avregningsboken holder også grunnlaget for timeeffekt og
kapasitetsberegning. Se [inputkontrakten](kontrakter/input-og-konfig.md) og
[avregningskontrakten](kontrakter/avregning.md).

Parallelt med beregningen vurderer coordinatoren om inputene i det hele tatt
leverer: entiteter som har stått `unavailable` over grace-vinduet, en
energiteller som ikke har økt på terskelen, og en spot-cache som er løpt ut.
Resultatet ligger i `data["input_problemer"]`, drives `binary_sensor`-en
`maaledata_problem`, og reiser repair-issues per entry. Se
[input-sensorer.md](input-sensorer.md#når-en-input-dør).

### Hvorfor polling, ikke event-drevet

Coordinator poller hvert minutt i stedet for å abonnere på state-endringer.
Effektbasert akkumulering bruker faktisk medgått tid, begrenset av
`MAX_ELAPSED_HOURS`; tellerbasert avregning bruker observasjonstidene. Ingen
av dem forutsetter nøyaktig ett minutt mellom kallene.

HAN-input kan oppdateres langt oftere enn hvert minutt, og et event-abonnement
ville økt antall beregninger og lagringsforsøk. Sensorenes
`_handle_coordinator_update` dedupliserer allerede uendret tilgjengelighet,
verdi, attributter og `last_reset`, så ett ekstra poll betyr ikke automatisk
én ekstra recorder-rad per sensor. En overgang til event-drift må fortsatt
vurdere Store-skriving, prisprøver, kalendergrenser og vakthold når inputene
ikke sender hendelser. Dagens minuttpoll driver også disse oppgavene.

## Lokalt oppsett

Du trenger `uv` og `just`. Ingenting annet installeres for hånd: gruppene i
`pyproject.toml` er låst i `uv.lock`, og `uv` henter både Python-versjonene og
pakkene selv.

```bash
git clone https://github.com/fredrik-lindseth/Stromkalkulator.git
cd Stromkalkulator
just test
pre-commit install && pre-commit install --hook-type pre-push
```

`just test` er unit-testene og kvalitetssjekkene, uten Home Assistant. Rører du
noe HA faktisk kaller, kjør også `just test-ha target=minimum` og
`just test-ha target=current`. Versjonsmatrisen og hvorfor miljøene er fysisk
atskilt står i [testing.md](testing.md#testmiljøer).

## Deploy til HA (utvikling)

```bash
rsync -av --delete custom_components/stromkalkulator/ ha-local:/config/custom_components/stromkalkulator/
ssh ha-local "ha core restart"
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

`rsync` speiler hele katalogen (inkl. `button.py`, `diagnostics.py`, `strings.json`, `translations/`), så en ny fil i `custom_components/stromkalkulator/` havner automatisk på HA-instansen. En fillistet loop råtner hver gang det legges til en fil. Det er nettopp det som skjedde med `button.py` og `translations/` her.

Etter en rsync kjører HA-en din arbeidstreet, ikke den publiserte releasen, og HACS vet ingenting om det. Usluppet arbeid, som en enhetsendring på en sensor, slår da ut som repairs hos deg alene. Kjør `git log "$(git describe --tags --abbrev=0)..HEAD"` før du konkluderer med at en release er skyld i noe du ser lokalt.

Tilbake til HACS:

```bash
ssh ha-local "rm -rf /config/custom_components/stromkalkulator"
ssh ha-local "ha core restart"
# I HA UI: HACS > Integrations > Stromkalkulator > Download, restart igjen
```

Har dev-builden bumpet `config_flow.VERSION` (f.eks. 3→4), er nedgraderingen enveis: migreringen løftet config-entry-en din til det nye nummeret, og en eldre release med lavere VERSION nekter å laste den (`Config entry ... has version 4 which is higher than the current version 3`, vises som «Migreringsfeil» i UI-et). Deploy da en build med minst like høy VERSION i stedet for å gå tilbake til releasen. Dette treffer bare deg, ingen utgitt versjon kan produsere en entry som er nyere enn seg selv.

## Vanlige oppgaver

- Oppdatere nettleiepriser: sjekkliste i [domain-rules.md](domain-rules.md#oppdatere-satser-årlig-ved-nyttår)
- Legge til sensor: sjekkliste i [domain-rules.md](domain-rules.md#legge-til-ny-sensor)
- Formler: [beregninger.md](beregninger.md)

## Feilsøking

```bash
ssh ha-local "ha core logs --follow"
ssh ha-local "ha core logs" | grep -i stromkalkulator
```

Diagnostikk-nedlasting: Settings > Devices & Services > Strømkalkulator > tre-prikk-menyen > Last ned diagnostikk. JSON-en (`diagnostikk.py`) inneholder releaseversjon, HA-versjon, valgene fra oppsettet, inputrollene med aliaserte entity-id-er og hva hver av dem leverte sist (tilstand, grunn, enhet, alder), energibaselinen med aliasert kildeidentitet, DSO-data, vakthold, beregningsfeltene fra siste oppdatering og repair-varslene som står ute.

Den er bygget for å limes inn i en offentlig issue. Hvert felt står på en allowlist, også feltene på en vaktholdsrad, og hver strengverdi må i tillegg stå i et kjent vokabular (nettselskap, avgiftssone, fastledd-metode) eller treffe et kjent format (ISO-dato, `0-2 kW`, `juni 2026`). Alt annet byttes med `<tekst utelatt>`. Entity-id-er, entry-id og tittel byttes med aliaser. Aliasene er tellere, ikke hasher av navnet: `sensor.alias_1` betyr «den første entiteten denne dumpen nevnte» og ingenting mer. To dumper fra samme oppsett får derfor de samme aliasene, og det er med vilje: det er nettopp sammenligningen av to dumper feilsøkingen trenger, og en teller peker ikke tilbake på noen.

| Feil                                  | Årsak                                                                                      | Løsning                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------- |
| `ImportError`                         | fil på HA er utdatert                                                                      | kopier oppdatert fil                |
| `Entity unavailable`                  | kildesensor mangler                                                                        | sjekk effekt/spotpris-sensor finnes |
| Feil kapasitetstrinn                  | data bygges over tid                                                                       | vent eller opprett testdata         |
| Feil dag/natt                         | helligdag ikke registrert                                                                  | beregnes fra påskeformelen          |
| `has version N higher than current M` | dev-build bumpet `config_flow.VERSION` og migrerte entry-en; du kjører nå en eldre release | deploy build med VERSION ≥ N        |

### Testdata for kapasitetstrinn

Bruk den kastbare Docker-laben for syntetiske effekttopper og lagringsdata.
`upgrade` seeder døgnmaks i Store-filene den eldre utgaven selv har skrevet,
mens containeren står stille, og verifiserer at dataene overlever oppgradering.

```bash
python3 tests_e2e/run.py upgrade
```

For manuell inspeksjon, start `python3 tests_e2e/run.py up` og bruk labens
helpers. Se [Docker-oppsettet](../tests_e2e/README.md). Ikke overskriv
produksjonens Store-fil med et utsnitt: filen inneholder også akkumulatorer,
energibaseline og historikk. Lagringsnøkkelen er alltid `entry_id`.

## Kilder

- [Skatteetaten, forbruksavgift](https://www.skatteetaten.no/satser/elektrisk-kraft/)
- [NVE, nettleiestatistikk](https://www.nve.no/reguleringsmyndigheten/publikasjoner-og-data/statistikk/)
- [Stromstotte.no](https://www.stromstotte.no/)
- [Elhub, Norgespris](https://elhub.no/norgespris/)
