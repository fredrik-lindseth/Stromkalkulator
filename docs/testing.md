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
commit. `just test-e2e` finnes, men feiler med en melding: Docker-laget er ikke
bygget ennå, se [tests_e2e/README.md](../tests_e2e/README.md).

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

`minimum` er versjonen `hacs.json` lover brukerne. Feiler den, skal
kompatibiliteten rettes eller minimum heves med en begrunnet beslutning, ikke
stille.

`just test-unit` og `just test-ha` tar ekstra argumenter videre til pytest,
f.eks. `just test-unit -k energiledd` eller
`just test-ha target=current -x`.

### Én kommandolinje, tre steder

Pre-push-hooken kjører `just test-unit`, og CI-jobbene kjører `just test-unit`,
`just check` og `just test-ha` for begge mål. Ingen av dem har sin egen
kommandolinje, så ingen av dem kan gå grønn på noe annet enn det du kjørte.
`tests/test_testkommandoer.py` feiler hvis justfile, AGENTS.md, denne filen,
`docs/development.md`, `.pre-commit-config.yaml` og `.github/workflows/ci.yml`
spriker.

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
- **Migrering**: config entry-migrering (v1→v2→v3), lagringsnøkkel-isolasjon mellom entries (se [incident 001](incidents/001-delt-data-mellom-instanser.md)), og lagring/gjenoppretting av persistert data. `test_config_migration.py`, `test_storage_key.py`, `test_persistens.py`.
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

I dag dekker den setup/unload med entitetsregistrering og første
config-flow-steg. Bredden (full config-flow, options og reload, migrering,
repairs, to entries, månedsskifte og DST med kontrollert klokke) kommer med
dcat-issue `stromkalkulator-6b54ywj`, som også eier tidsbudsjettet for dette
avsnittet.

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
