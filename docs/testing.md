# Testing

## Testmiljøer

Fire miljøer, fire virtuelle miljøer, ingen av dem deler `sys.modules` med
hverandre. Det er ikke en pytest-markør som skiller dem, det er hvilke pakker
som er installert: `tests/` stubber `homeassistant.*` i `sys.modules`, og en
ekte `homeassistant` i samme miljø ville kollidert med stubbene.

| Oppskrift                  | Tre        | Gruppe       | Python | Home Assistant |
| -------------------------- | ---------- | ------------ | ------ | -------------- |
| `just test-unit`           | `tests/`   | `unit`       | 3.13   | stubbet        |
| `just check`               | hele repo  | `kvalitet`   | 3.13   | ingen          |
| `just test-ha target=minimum` | `tests_ha/` | `ha-minimum` | 3.13   | 2025.1.0       |
| `just test-ha target=current` | `tests_ha/` | `ha-current` | 3.14   | 2026.9.2       |

`just test` er `test-unit` og `check` i ett, og er det AGENTS.md ber om før
commit. `just test-e2e target=current` kjører en separat Docker-basert HA-server
med livssyklusscenarioer og komprimert juni-avspilling fra timefixturen.
Det laget tester en committet release-ZIP; se [Docker-testlab](#docker-testlab).

Gruppene står i `[dependency-groups]` i `pyproject.toml` og er låst i
`uv.lock`. HA-versjonen står ikke der direkte: den følger av
`pytest-homeassistant-custom-component`, som pinner `homeassistant` eksakt.
`0.13.201` gir HA 2025.1.0, `0.13.365` gir HA 2026.9.2. De to gruppene er
erklært som `conflicts` i `[tool.uv]`, så uv låser dem som atskilte grener
framfor å prøve å få dem inn i samme miljø.

Python-versjonene er ikke fritt valg. HA 2026.9 krever 3.14.2 eller nyere, og
`pytest-homeassistant-custom-component` for 2025.1 krever 3.12 eller nyere.
`uv` henter begge selv, så du trenger ikke installere dem.

HA 2025.1.0 pinner `aiohasupervisor==0.2.2b5`, altså en prerelease. uv nekter
prereleases som default, så den står eksplisitt i `ha-minimum` og
`prerelease = "if-necessary-or-explicit"` i `[tool.uv]` slipper den gjennom.
Uten dette kunne minimum-grenen ikke løses i det hele tatt.

`minimum` er versjonen `hacs.json` lover brukerne, og `hacs.json` er kilden:
`tests/test_testkommandoer.py` leser HA-versjonen `ha-minimum` faktisk løser til
i `uv.lock` og feller den hvis den ikke er den samme. Den feller også hver
HA-versjon skrevet i klartekst i justfile, AGENTS.md, docs eller
`pyproject.toml` som ikke er en av de to låste. Tallet sto i ni kopier uten at
noe holdt dem i synk, og da kunne hacs.json heves uten at minimum-miljøet
testet noe annet enn før. Feiler minimum, skal kompatibiliteten rettes eller
minimum heves med en begrunnet beslutning, ikke stille.

`just test-unit` og `just test-ha` tar ekstra argumenter videre til pytest,
f.eks. `just test-unit -k energiledd` eller
`just test-ha target=current -x`.

### Én kommandolinje, tre steder

Pre-push-hooken kjører `just test-unit`, og CI-jobbene kjører `just test-unit`,
`just check` og `just test-ha` for begge mål. Ingen av dem har sin egen
kommandolinje, så ingen av dem kan gå grønn på noe annet enn det du kjørte.
`tests/test_testkommandoer.py` feiler hvis justfile, AGENTS.md, denne filen,
`docs/development.md`, `.pre-commit-config.yaml` og `.github/workflows/ci.yml`
spriker. Den sjekker ikke bare at oppskriftene heter det samme: `just check` må
faktisk kjøre `ruff check .`, `ruff format --check .`, mypy og vulture, og
`just test-unit` må kjøre hele `tests/`. Ellers kunne mypy falle ut av
oppskriften mens vakten sto grønn.

## Unit-tester

```bash
just test-unit
```

### Hva som dekkes

Testsuiten (`ls tests/test_*.py` for aktuell liste) er organisert i nivåer i stedet for en fil-per-fil-tabell, siden filnavn endres oftere enn testnivåene gjør:

- **Golden faktura**: beregninger verifisert mot ekte fakturafelt og publiserte tall. `test_faktura_bkk.py` (BKK 2025 og 2026), `test_research_reproducibility.py` (research-rapportene skal reproduseres eksakt ved regenerering).
- **Hourly replay**: en hel måneds fixtur-data mates time for time gjennom `NettleieCoordinator`, og de akkumulerte sluttverdiene sjekkes mot fasit. `test_coordinator_replay.py`.
- **Property-baserte tester**: Hypothesis genererer tilfeldige input og sjekker invarianter som ikke-negativitet og monotonisitet. `test_property.py`.
- **Kontrakt**: kjører en reell coordinator-oppdatering og fôrer resultatet inn i sensorklassene, for å fange typemismatch mellom coordinator og sensor før det når produksjon. `test_coordinator_sensor_contract.py`.
- **Migrering**: config entry-migrering (v1→v2→v3→v4→v5), lagringsnøkkel-isolasjon mellom entries (se [incident 001](incidents/001-delt-data-mellom-instanser.md)), og lagring/gjenoppretting av persistert data. `test_config_migration.py`, `test_storage_key.py`, `test_persistens.py`.
- **DST og kalender**: sommertid-overgang, helligdager langt fram i tid, sesongstyrte energiledd-perioder. `test_dst_overgang.py`, `test_edge_cases.py`, `test_energiledd_perioder.py`.
- **Unit**: resten, altså beregningslogikk per komponent (energiledd, kapasitetstrinn, strømstøtte inkl. tak, Norgespris-kompensasjon inkl. tak, spotpris/mva, solcelle-eksport, energisensor-delta), DSO-datavalidering og 2026-tariffer, entity-oppsett (config flow, options flow, setup/unload, diagnostics, button, sensorklasser, månedlige og passthrough-sensorer) og robusthet/coverage-gap-regresjoner.

Nye tester legges i nivået de hører til. Denne listen skal ikke oppdateres for hver ny eller slettet testfil.

### Begrensninger

Unit-testene kjører uten Home Assistant installert (HA stubbes i
`tests/conftest.py`). Options flow med reload, end-to-end setup/unload og
repair-issue-flows er dekket mock-basert (`test_config_flow_options.py`,
`test_init_setup.py`, `test_config_migration.py`), og `test_config_flow.py`
bruker regex mot kildekoden (bevisst skjørt, se filens docstring) fordi den
ikke kjører en reell `ConfigFlow`-instans.

Det som må kjøres mot ekte HA, ligger i `tests_ha/`.

## Ekte Home Assistant

```bash
just test-ha target=minimum
just test-ha target=current
```

`tests_ha/` laster integrasjonen i en ekte `HomeAssistant`-instans via
pytest-homeassistant-custom-component. Egen conftest, eget miljø, egen
asyncio-modus (`-o asyncio_mode=auto`, fordi `hass`-fixturen er en async
generator). Tom collection er rødt: conftest-en avbryter kjøringen hvis
ingen tester ble samlet inn, så en feilstavet sti eller en import som slutter
å samles ikke kan vises som grønn.

Laget dekker katalog-, custom- og sikring-flow, options/reconfigure/reload,
konfigurasjonsmigrering, input- og tariff-repairs, separate entries og
save/load. `test_kalender.py` bruker HAs planlagte timerhendelser med
kontrollert UTC-klokke og Europe/Oslo: forsinket poll over lokal måned,
begge DST-retninger og videre polling etter overgangen.

### Scenarioer og feilklasser

Hvert automatisk integrasjonsscenario i `tests_e2e/driver.py` har et raskt
motsvar. Tabellen viser hvor en feil først skal kunne lokaliseres. Testene i
`test_e2e_regressions.py` ligger i `tests_ha/`; navnene nedenfor er konkrete
tester, ikke bare planlagt dekning.

| Scenario | Rask kontrakt | Hva Docker tilfører |
| --- | --- | --- |
| Onboarding og energiøkning | `test_onboarding_and_energy_increase`: full user/sensors-flow, lastet entry, 0-baseline og +1,25 kWh | HTTP-flow og installasjon fra release-ZIP |
| Restart uten dobbeltbokføring | `test_restart_no_double_booking`: positiv saldo og baseline over entry-reload/Store | Stopp/start av hele HA-prosessen |
| Målerbytte | `test_meter_change`: options/reload, ny kildebinding, bevart saldo og neste normale delta | Samme sekvens gjennom server-API |
| Fjerne valgfri eksportinput | `test_remove_optional`: frisk, aktivert output blir unavailable; entry og forbruk fortsetter | Options og entitetsoppdatering gjennom serveren |
| Manglende input og recovery | `test_missing_input_recovery`: deleted/unavailable/unknown, bevart saldo og normal opptelling etterpå | Inputfeil gjennom server-API |
| Sprang i energiteller | `test_meter_jump`: avvis +1000 kWh, godta neste +1,25 kWh | Sprangvern i installert pakke |
| Ugyldig enhet og recovery | `test_invalid_unit_recovery`: repair opprettes og ryddes i ekte HA-register | Samme synlige repair over server-API |
| Månedsavspilling | `tests/test_coordinator_replay.py` og `tests/test_replay_hendelser.py`: deterministisk energi-/avregningsreplay | Kvitterte avspilte kWh gjennom hele serveren |

Ekte-HA-laget eier også kontrakter som Docker-avspillingen ikke kan bevise:
`test_to_entries.py` vokter separat lagring, identitet og repairs mellom to
anlegg; `test_konfig.py`, `test_custom.py` og `test_input.py` vokter flows,
konfigurasjonsmigrering og inputbinding. `test_kalender.py` og
`test_satsvakt.py` vokter kalendergrenser og årsskiftevakt.
`test_entitetsflate.py` holder hele flaten mot gullfilen
`tests_ha/entitetsflate.json`: entitets-ID, navn, enhet, klasser, ikon og
deaktivert-som-standard for alle 55 entiteter. `test_metadata.py` sjekker
kontraktene per entitet, gullfilen fanger den som forsvant eller byttet navn.
Endrer du flaten med vilje, regenerer med
`SKRIV_ENTITETSFLATE=1 just test-ha target=current tests_ha/test_entitetsflate.py`
og les diffen før du committer den. Unit-laget eier
de detaljerte formlene, prisintervallene og fakturafasit.

`upgrade` og `vakthold` står utenfor den automatiske kjøringen, men de har de
samme raske motsvarene: `tests_ha/test_store_migrering.py` og
`tests/test_persistens.py` for lagringsformatet, `tests/test_config_migration.py`
for entryversjonene, `tests/test_kostnad.py` for fastleddet som periodebeløp,
`tests/test_tariffmodus.py` for satsvarselet, `tests/test_repairs_egendefinert.py`
for fastleddvarselet og `tests/test_vakthold.py` med `tests/test_dst_overgang.py`
for vaktholdet. Docker-kjøringene tilfører ekte varighet, ekte issue-register og
en lagringsfil skrevet av utgaven som faktisk slapp.

Manuelle Docker-handlinger som `outage_han`, `outage_spot` og `recover_inputs`
har varslingsregler i `tests/test_vakthold.py`. Blir en ny varighet eller
repair-sekvens et automatisk E2E-krav, skal den få et tilsvarende deterministisk
bevis. HA-serverens egen bootstrap/tokenutveksling tilhører Docker-harnesset.
Isolasjon, sladding, kildeavstemming og opprydding ved feil testes også
offline i `tests_e2e/test_harness.py`.
Historisk fakturarevalidering eies av `stromkalkulator-443xvtv`; HAN-fixturer
og Elhub/fakturagrunnlag er ulike kilder og skal ha kildeangitte forventninger.

`stromkalkulator-271siks` eier dette scenariokartet.
`stromkalkulator-2uw4t9a` er aktiv etterfølger til `stromkalkulator-6b54ywj`
og eier ekte-HA-kontraktene. Metadata for alle plattformer og bevart identitet
ved reload kontrolleres i `test_metadata.py`; `test_store_migrering.py`
kontrollerer eldre DSO-nøkkel og entry-format v1 gjennom ekte HA Store,
med bevart måned og engangsmigrering.

### Målt kjøretid og arbeidsbudsjett

Målingene fra 13. september 2026 er lokale referanser, ikke garanterte
CI-tider. Pytest-tid utelater miljøinstallasjon og resten av kommandoen.

| Lag | Målt referanse | Praktisk budsjett med varmt miljø |
| --- | --- | --- |
| Unit (`test-unit`) | 3434 bestått, 34 hoppet; 140,75–143,76 s i isolerte trær uten privat grunnlag | Omtrent 3 minutter; `check` kommer i tillegg i `just test` |
| Ekte HA, minimum/current | 63 bestått uten skip i hver, 2,46 / 3,02 s pytest-tid med metadata- og Store-kontraktene | Under 10 s pytest-tid som lokal referanse; nye tester kan øke dette |
| Kun første E2E-speilpakke | 7 tilfeller; 0,93 s minimum / 0,87 s current på `0d465a9` | Rundt ett sekund for en avgrenset regresjon |
| Docker current | 8 scenarioer og 720 juni-timer; ca. 592 s med varmt image-cache | 10–20 minutter lokalt; CI 28 minutter kjøring / 35 minutter jobb |

Disse målingene gjelder de angitte leveransene, ikke en påstand om dagens
testantall. Kald nedlasting av Python, pakker og Docker-image kommer i
tillegg. Docker inngår derfor som separat serverbevis; de korte kontraktene
brukes mens en feil utvikles og rettes.

## Docker-testlab

`just test-e2e target=current` bygger HACS-ZIP fra `HEAD`, starter et eget
Compose-prosjekt med offisielt HA-image låst til tagg og linux/amd64-digest,
oppretter integrasjonen gjennom config-flow og spiller av juni-fixturen.
Ucommittede integrasjonsendringer inngår ikke i denne testen. Python 3.12+ og
Docker med Compose er nok på verten; driveren bruker HAs egne avhengigheter
inne i containeren. Porten er en tilfeldig ledig port på `127.0.0.1`.

Navngitte scenarioer dekker onboarding, energiøkning, restart uten
dobbeltbokføring, målerbytte, fjernet valgfri input, ugyldig enhet, manglende
input med recovery og sprang i energitelleren. Full månedsavspilling venter
på kvitterte kWh i små batcher, fordi HA samler manuelle refresh-kall og
integrasjonen avviser sprang over 100 kWh. Forvent rundt 10–20 minutter på
en varm Docker-cache; CI har 28 minutter for kjøringen og 35 for hele jobben.
Lokalt verifisert 13. september 2026 mot current: alle scenarioer og 720
juni-timer bestod på omtrent 10 minutter med varmt image-cache. En separat
tvunget feil bekreftet at containere og nettverk ryddes også ved feil, og
eksportert evidens inneholdt ingen av testlabens passord eller tokens.
GitHub-jobben må fortsatt bekreftes grønn i CI.

Docker-workflowen `e2e.yml` kjører separat på relevante pull requests og ved
manuell dispatch. Den inngår ikke i `release.yml` sin `needs: ci`, og verken
`upgrade` eller `vakthold` kjøres av den. Grønn release-CI beviser derfor ikke
at disse Docker-løpene er grønne. Før release må resultatene knyttes til
kandidat-SHA-en og scenario-tracen, med alle forventede scenarioer fullført.

Avspillingen endrer ingen klokke. Rapporten skiller HA-integrasjonens
bokførte kWh fra historisk kildeavstemming. HA bruker dagens dato og tariff,
så historisk dag/natt, kroner, månedsskifte, årsskifte og DST skal fortsatt
testes deterministisk i `tests_ha/` og replay-testene. Juni-fixturen har
2 Wh totalavvik og 36/38 Wh dag/natt-avvik mot fakturaen; disse står synlig i
rapporten med toleranser på 10 Wh totalt og 50 Wh per tariffperiode.
HA-energidelta må derimot matche det faktisk avspilte forbruket innen 2 Wh.

For en instans du kan klikke i, og feil du kan la vare i timer:

```bash
python3 tests_e2e/run.py up
# Kommandoen skriver URL, lokal påloggingsfil og lab-mappe.
python3 tests_e2e/run.py replay --run-dir /sti/skrevet/av/up
python3 tests_e2e/run.py scenario --run-dir /sti/skrevet/av/up --name outage_han
python3 tests_e2e/run.py scenario --run-dir /sti/skrevet/av/up --name recover_inputs
python3 tests_e2e/run.py down --run-dir /sti/skrevet/av/up
```

`run` rydder containere/nettverk også ved feil; `up` beholder instansen til
`down`. Den midlertidige config-mappen beholdes lokalt og inneholder testlabens
egen pålogging. CI laster bare opp redigerte logger, scenario-trace og
versjons-/avstemmingsrapport, aldri config, tokens eller full storage.
Ingen produksjonsconfig, privat målearkiv eller supervisor-token brukes.
Les [tests_e2e/README.md](../tests_e2e/README.md) for feilsimulering,
validering av cleanup og presise begrensninger.

### Oppgraderingsveien og vaktholdet

To lengre kjøringer ligger utenfor `just test-e2e`, for begge koster mer tid
enn en port skal koste:

```bash
python3 tests_e2e/run.py upgrade     # rundt 15 minutter
python3 tests_e2e/run.py vakthold    # rundt 40 minutter
```

`upgrade` installerer taggen `v1.16.0`, setter opp to anlegg gjennom dens egen
config-flow, kjører opp akkumulatorene, og bytter så integrasjonen til `--sha`
mens containeren står stille. Da er både lagringsfilen og config-entryene
skrevet av den sluppet utgaven, ikke etterlignet. Kjøringen vokter at
månedsforbruk, døgnmaks og forrige måned overlever, at den kildeløse baselinen
forkastes uten å gi falskt forbruk, og de tre brukersynlige endringene:
fastleddet som periodebeløp, satsvarselet i begge retninger, og Egendefinert
uten trinntabell. `lab.skriv_lagring` nekter å legge inn en nøkkel som ikke
alt sto i filen, så et seedet felt kan ikke bli til et lagringsformat vi har
funnet på.

`vakthold` lar utfallet vare like lenge som et ekte et: 32 minutter for
grace-vinduet på 30. Den prøver også de tilfellene som **ikke** skal varsle,
siden vaktholdet ble avvist tre ganger på falske positiver: omstart med tom
spotcache, et utfall innenfor grace, målerbytte, og delvis friskmelding der
teksten skal skrives om framfor at varselet lukkes. Frossen teller og
strømbrudd seedes gjennom lagringsfilen framfor å ventes ut, for begge handler
om hva `last_energy_increase` og `last_update` sto på da HA startet.

En kjent oppstartsfeil i driveren kan gi falskt rødt etter omstart:
`ready()` venter bare på `/api/`, som kan svare før HA er `RUNNING` og før
entitetene finnes. Da kan `update_entity` bli kalt for tidlig, blant annet i
`test_frossen_teller_varsles` (stromkalkulator-516lois). Dette er ikke rettet i
driveren ennå. En permanent retting må vente på både ferdig HA-oppstart og
nødvendige entiteter, og så bestå hele vaktholdsekvensen inkludert
strømbrudd-motprøven. En grønn enkeltprøve etter ekstra venting er nyttig
feilsøking, men ikke en grønn full suite.

Hold vertsmaskinen våken under de lange testene; dvale avbryter den tilsiktede
sammenhengende kjøringen. Se [labens kjørevilkår](../tests_e2e/README.md#kjør).

`--cache-minutter 95` legger til spotcachen på to timer og tar kjøringen over
to timer. Den står av som default: rangeringen mellom `spot_utfall` og
utfallsraden er alt voktet deterministisk, og en port som tar to timer er en
port ingen kjører. Sommertid hører til `tests/test_dst_overgang.py`; laben kan
ikke flytte klokken, og skal ikke kunne det.

Størrelsen på fallet i `monthly_cost_kr` kan ikke måles her. HA bruker dagens
klokke, så fastleddet blir dagens andel av inneværende måned. De 64 til 145
kronene er målt mot ekte fakturaer i
[docs/research/revalidering-l3b-september-2026.md](research/revalidering-l3b-september-2026.md).
Laben prøver mekanismen: at `monthly_cost_kr` og akkumulert kostnad nå er
samme tall, og at fastleddet ikke rører seg av at forbruket gjør det.

## Live-tester i Home Assistant

`packages/stromkalkulator_test.yaml` gir test-sensorer som kjører i HA. Filen
finnes to steder, her i repoet og installert på HA-instansen, og de har driftet
fra hverandre før uten at noe fanget det. To just-oppskrifter holder dem i takt:

```bash
just deploy-testpakke   # diff mot HA, kopier etter bekreftelse, be om restart
just sjekk-testpakke    # er repo og HA i takt, og står testene grønt?
```

`deploy-testpakke` viser diffen først og gjør ingenting hvis filene er like.
Den restarter ikke HA selv; packages leses bare ved oppstart, så kommandoen for
restart skrives ut til slutt.

`sjekk-testpakke` kjører `scripts/sjekk_testpakke.py`, som leser states over
supervisor-proxyen på `ha-local` og sjekker tre ting: at filen på HA er identisk
med repoets, at hver entitet pakken refererer til finnes i state-maskinen, og at
test-sensorene står i en grei tilstand. Exit 1 hvis noe mangler eller står i
FEIL. Med `--states <fil>` leses states fra en JSON-dump i stedet, nyttig for
feilsøking uten tilgang til boksen.

SSH-en trenger `-o IdentitiesOnly=yes`, ellers faller den på «Too many
authentication failures». Scriptet setter flagget selv.

Uten tilgang til en kjørende HA dekker `tests/test_testpakke.py` det som kan
sjekkes offline: at pakken parser, at unique_id-ene er unike, at test-sensorer
som viser til hverandre finnes i pakken, og at referansene til integrasjonen
svarer til en sensor den faktisk lager (slugger fra `translations/nb.json`).
Instansspesifikke entity-id-er kan bare sjekkes live.

Pass på at packages er aktivert i `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

I Developer Tools > States, filtrer på `test_`. `sensor.test_alle_tester_ok` viser samlet status. Den teller de åtte kjernetestene, mens de tre forrige-måned-testene leses hver for seg. Resultater: `OK`, `FEIL` eller `MANGLER DATA`. Ved FEIL, sjekk attributtene `forventet`, `faktisk`, `differanse`.

| Sensor                                         | Sjekker                           |
| ---------------------------------------------- | --------------------------------- |
| `sensor.test_stromstotte_beregning`            | strømstøtte-formelen              |
| `sensor.test_spotpris_etter_stotte`            | spotpris - strømstøtte            |
| `sensor.test_tariff_korrekt`                   | dag/natt/helg-tariff              |
| `sensor.test_energiledd_korrekt`               | energiledd-valg                   |
| `sensor.test_total_pris_etter_stotte`          | totalpris                         |
| `sensor.test_forbruksavgift`                   | forbruksavgift (7,13 øre)         |
| `sensor.test_enova_avgift`                     | Enova-avgift (1,0 øre)            |
| `sensor.test_norgespris_sammenligning`         | prisforskjell mot Norgespris      |
| `sensor.test_kapasitetstrinn`                  | kapasitetstrinn                   |
| `sensor.test_forrige_maned_data`               | dag + natt = totalt forrige måned |
| `sensor.test_forrige_maned_nettleie_beregning` | forrige måneds nettleie           |
| `sensor.test_forrige_maned_toppforbruk`        | topp-3 og snitt forrige måned     |
| `sensor.test_alle_tester_ok`                   | samlet status (X/8 OK)            |

## Manuell sjekk

Strømstøtte (2026): `max(0, (spotpris - 0.9625) * 0.90)`.

| Spotpris | Strømstøtte |
| -------- | ----------- |
| 0.50 kr  | 0.00 kr     |
| 0.96 kr  | 0.00 kr     |
| 1.00 kr  | 0.03 kr     |
| 1.50 kr  | 0.48 kr     |
| 2.00 kr  | 0.93 kr     |

Tariff:

| Tidspunkt           | Tariff |
| ------------------- | ------ |
| Man-fre 06:00-22:00 | dag    |
| Man-fre 22:00-06:00 | natt   |
| Lør-søn alle timer  | natt   |
| Helligdager         | natt   |

Kapasitetstrinn (BKK):

| Snitt topp-3 | Trinn | Pris       |
| ------------ | ----- | ---------- |
| 0-2 kW       | 1     | 155 kr/mnd |
| 2-5 kW       | 2     | 250 kr/mnd |
| 5-10 kW      | 3     | 415 kr/mnd |
| 10-15 kW     | 4     | 600 kr/mnd |

Avgifter (2026):

| Avgift         | Forventet                           |
| -------------- | ----------------------------------- |
| Forbruksavgift | 0.0891 kr/kWh (7,13 øre × 1.25 mva) |
| Enova-avgift   | 0.0125 kr/kWh (1,0 øre × 1.25 mva)  |

## Feilsøking

Sensor viser FEIL: sjekk attributtene for differansen, sjekk logger, verifiser kilde-sensorer (Nord Pool, strømmåler).

Sensor viser unavailable: verifiser at integrasjonen er lastet (`ssh ha-local "ha core logs" | grep -i "Setting up stromkalkulator"`), sjekk at kilde-sensorer finnes.

Kapasitetstrinn er feil: "Snitt toppforbruk" viser snittet av topp-3. Data lagres per måned, nullstilles ved månedsskifte. Ny installasjon trenger tid på å bygge data.
