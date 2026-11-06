# AGENTS.md

Home Assistant-integrasjon for nettleie, strømstøtte og Norgespris-sammenligning i Norge.

## Ansvarsområde

Strømkalkulator er en Home Assistant-integrasjon som beregner nettleien fra målt forbruk og nettselskapets tariffer. Den håndterer energiledd, kapasitetstrinn, offentlige avgifter, strømstøtte og Norgespris, slik at du kan følge kostnadene og kontrollere dem mot nettleiefakturaen.

Strømpris og måledata hentes fra andre integrasjoner, for eksempel Nord Pool og en AMS/HAN-leser. Strømkalkulator bruker disse som grunnlag for nettleieberegningen og de offentlige støtteordningene.

Strømleverandørens avtalevilkår, påslag, abonnement og avtalehistorikk ligger utenfor integrasjonens ansvarsområde. Eksisterende totalpris- og kostnadsvisninger gir ikke full avregning av strømavtalen. Valg av kjøretidspunkt, prisoptimalisering og laststyring hører til [Effektvakt](https://github.com/fredrik-lindseth/hacs-effektvakt) eller brukerens automasjoner.

Eventuelle beregninger av kommende priser følger samme ansvarsområde: kostnadsgrunnlag og synliggjøring av forutsetninger. Ikke bygg en laststyrings- eller planleggingsmotor her.

Private arbeidsnotater og intern oppgavesporing skal ikke inn i offentlige filer, tester eller commit-meldinger.

## Hovedfiler

- `custom_components/stromkalkulator/`: integrasjonskode
- `dso.py`: nettselskap-data
- `const.py`: avgifter, satser, helligdager
- `coordinator.py`: beregningslogikk
- `sensor.py`: sensor-definisjoner
- `config_flow.py`: oppsett og options-flow, sensor-validering

## Før commit

```bash
just test
```

`just test` er `just test-unit` (hele `tests/`) og `just check` (ruff check,
ruff format --check, mypy og vulture) i ett. Begge kjører gjennom `uv` mot
låste dependency-grupper i `uv.lock`, så du trenger `uv` og `just`, men ikke å
installere noe for hånd. Home Assistant er ikke med: `tests/` stubber HA bort,
og en ekte `homeassistant` i samme miljø ville kollidert med stubbene.

Rører du noe Home Assistant faktisk kaller, altså setup, config-flow,
entiteter, migrering eller repairs, kjør også ekte HA:

```bash
just test-ha target=minimum
just test-ha target=current
```

`minimum` er versjonen `hacs.json` lover brukerne, og `current` er
nyeste versjon vi har prøvd. Begge må være grønne. Feiler `minimum`, er det
kompatibiliteten som skal rettes, eller minimum som skal heves med en begrunnet
beslutning i CHANGELOG og `hacs.json`. Ikke hev det stille.

De samme oppskriftene kjøres av pre-push-hooken og av CI, så det finnes ikke en
annen kommandolinje som kan gå grønn på noe annet. `tests/test_testkommandoer.py`
feiler hvis justfile, denne seksjonen, `docs/testing.md`, `docs/development.md`,
`.pre-commit-config.yaml` og `.github/workflows/ci.yml` spriker.

Hookene kjøres bare når de er installert: sjekk `git config core.hooksPath`
(skal være tom) og kjør `pre-commit install` og
`pre-commit install --hook-type pre-push` i en fersk klone.

`mypy` er blokkerende i CI, men sto lenge ikke i denne seksjonen. Da gikk en
`bool(dso)` som ikke smalner typen rett gjennom lokal grønn testsuite og feilet
i CI etter push, så releasen ble hoppet over.

Full oversikt over de fire miljøene, versjonsmatrisen og hvorfor de er atskilt:
[docs/testing.md](docs/testing.md#testmiljøer).

## Viktige regler

### Lagring

Bruk `entry.entry_id` som lagringsnøkkel, aldri DSO-id eller brukervalgt
konfigurasjon. Se [incident 001](docs/incidents/001-delt-data-mellom-instanser.md).

### Sensor-enheter

`MONETARY` krever ISO 4217 (`NOK`), satser skal ikke ha `device_class` og
beholder `NOK/kWh` eller `kr/mnd`. Å bytte enhet på en sensor med `state_class`
gir én repair hos hver bruker, så gjør det bare når gevinsten er reell. Se
[domain-rules.md](docs/domain-rules.md#sensor-enheter-og-device_class).

### Satser

Endringer i `const.py` (avgifter, terskel) eller `dso.py` (energiledd,
kapasitetstrinn) krever offisiell kilde og bestått testsuite. Kjør
`uv run --with pyyaml python scripts/sjekk_mot_fri_nettleie.py --bare-avvik` for
å fange pris-drift mot fri-nettleie før du endrer eller committer satser. Den
sjekker både energiledd og fastledd; avvik i begge feller exit-koden.

### Endringslogg og release

Før du skriver eller endrer CHANGELOG/release-noter, endrer versjon eller releaseflyt, eller pusher til main: les og følg [docs/release-notes.md](docs/release-notes.md). Der står skrivereglene, kontrollkommandoene og publiseringsporten. Slupne seksjoner er historikk; push til main kan publisere en release.

### Kapasitetstrinn

Aldri mal, gjetning eller gjenbruk fra et annet nettselskap. Mangler kilde, la
`supported` stå `False`. Se
[incident 006](docs/incidents/006-kapasitetstrinn-uten-kilde.md) og
[domain-rules.md](docs/domain-rules.md#kapasitetstrinn-krever-kilde-per-nettselskap).

### DSO-helligdager

`helligdager_ekstra` i `dso.py` (f.eks. `["12-24", "12-31"]` for BKK) skal kun
legges til når en ekte faktura fra DSO-en bekrefter at hele dagen behandles som
natt-tariff. Default er kun offisielle norske helligdager.

### Månedsskifte

Ikke nullstill `_daily_max_power`, `_monthly_consumption` eller
`_previous_month_*` manuelt. Skjer automatisk.

### Kursarkiv (kjør månedlig)

`just snapshot-kurs` arkiverer Nord Pools daglige `exchangeRate` og de
publiserte NOK-kvarterprisene i `_private/Måleverdier/`. Gratis-API-et rekker
bare ~2 måneder bakover, så kjør den hver gang du er i repoet (minst månedlig)
før fakturamånedene faller ut. Kvarterprisene er fasiten BKK fakturerer fra; med
dem reproduseres Norgespris-linjen eksakt (verifisert juni 2026). HA-recorderen
lagrer prisene slik de så ut ved publisering og kan ha foreløpig valutakurs på
søndager, så den duger ikke som fasit. Bakgrunn:
[docs/research/priser/norgespris-eksakt-match.md](docs/research/priser/norgespris-eksakt-match.md).

## Dokumentasjon

[docs/README.md](docs/README.md) er inngangen til dokumentasjonen. Skriv gjeldende oppførsel i veiledningene; oppgavestatus hører til privat oppgavesporing.

- [docs/domain-rules.md](docs/domain-rules.md): domene-regler, avgifter, sjekklister, kilder
- [docs/beregninger.md](docs/beregninger.md): formler og sensorer
- [docs/sensorer.md](docs/sensorer.md): sensorer og attributter
- [docs/input-sensorer.md](docs/input-sensorer.md): hva integrasjonen trenger som input (effekt, energi, spotpris)
- [docs/development.md](docs/development.md): arkitektur
- [docs/testing.md](docs/testing.md): test-guide
- [docs/contributing.md](docs/contributing.md): oppdatere priser, rapportere feil
- [docs/galskapen.md](docs/galskapen.md): hvorfor 72 nettselskap tolker samme NVE-regel på 72 måter, og hva det betyr for koden
