# Release notes

## CHANGELOG.md

Det finnes én tekst, og den ligger i repoet. `## [X.Y.Z]`-seksjonen i
`CHANGELOG.md` er det brukerne får se på GitHub-releasen; workflowen henter den
med `scripts/release_notes.py` og bruker den som body. Skriv den derfor som
brukertekst, ikke som utviklerlogg.

Tidligere ble noten skrevet for hånd i en GitHub-draft. Da lå den utenfor
repoet, workflowen publiserte rå commit-liste i stedet, og teksten måtte limes
inn igjen manuelt etterpå (stromkalkulator-1dk4).

Se selv hva en gitt versjon gir:

```bash
python3 scripts/release_notes.py 1.16.0
```

Exit 1 hvis seksjonen mangler, er tom, har en relativ lenke til en fil som ikke
finnes, eller har en tom `### Dette må du gjøre selv`. Både `ci.yml` og
`release.yml` henger på den exit-koden, så en versjon uten note blir aldri
publisert.

## Stil

- Ikke forklar hva prosjektet er, brukerne har allerede installert det
- Punktlister, ikke avsnitt med bold-tittel og lang beskrivelse
- Kort og skannbart
- Ingen AI-slop ("we're excited to announce", overdreven adjektivbruk)
- Ingen em-dashes, bruk komma eller punktum
- Krediter brukere som rapporterer bugs: `@brukernavn` + issue-referanse

Underoverskriftene er Keep a Changelog-kategoriene (`### Fikset`, `### Lagt
til`, `### Endret`, `### Verifisert`, `### Dokumentert`), pluss `### Dette må
du gjøre selv`. Ikke skriv noen `# v1.3.0`-heading, tittelen settes på selve
releasen.

## Dette må du gjøre selv

Krever oppgraderingen noe aktivt av brukeren, bytte av entitets-id, bekreftelse
av et enhetsbytte, et nytt felt som må velges, skal det stå i en egen
`### Dette må du gjøre selv`-kategori. Kategorien er frivillig; de fleste
releaser har ingenting der.

```markdown
## [1.17.0]

### Dette må du gjøre selv

- Sett terskelen for frossen energisensor under Innstillinger > Enheter og
  tjenester > Strømkalkulator > Konfigurer. Default er 3 timer.

### Lagt til

- Ny `binary_sensor.maaledata_problem` som varsler når en input-sensor svikter
```

Du trenger ikke skrive den først i CHANGELOG; `release_notes.py` løfter den
øverst i release-body-en uansett hvor i seksjonen den står, så den ikke drukner
under «Lagt til» og «Fikset». Rekkefølgen skal ikke avhenge av at noen husker
den. Overskriften matches uten hensyn til store bokstaver.

Står overskriften der uten punkter under seg, feiler scriptet med exit 1 og sier
hvilken versjon og hvilken kategori det gjelder. Den løftes øverst uansett, så
tom ville den blitt en naken overskrift på toppen av en publisert release. Blanke
linjer teller ikke som innhold. Skriv punktene, eller slett overskriften.

Hvorfor den finnes: v1.15.0 byttet sensortyper og enheter, og noten på GitHub
hadde en håndskrevet ramme om hva brukeren måtte gjøre. I CHANGELOG lå de samme
fire punktene spredt under «Endret» og «Lagt til», så den som skummet fikk aldri
beskjeden. Nå som CHANGELOG er eneste kilde, må formatet bære den selv.

## Lenker

Skriv relative lenker som ellers i repoet, altså
`[incident 006](docs/incidents/006-kapasitetstrinn-uten-kilde.md)`.
`release_notes.py` skriver dem om til absolutte URL-er mot taggen som slippes
(`.../blob/v1.17.0/docs/...`) før de havner i release-body-en. Relative lenker
er døde på en releaseside, og taggen brukes framfor `main` så lenken viser
innholdet slik det var ved releasen, også om et år.

- Absolutte URL-er står urørt
- Anker uten fil (`#lagt-til`) peker på `CHANGELOG.md` i repoet, på riktig tag
- Peker en relativ lenke på en fil som ikke finnes, feiler scriptet med exit 1
  framfor å publisere en død lenke. Slett eller rett stien.
- Referansestil virker også: `[regler][r1]` med `[r1]: docs/domain-rules.md`
  nederst. Det er definisjonen som skrives om, siden det er der målet står.
- Mål i vinkelparenteser, `[x](<docs/en fil.md>)`, virker og er eneste måten å
  skrive en sti med mellomrom i. En sti med parentes i navnet må skrives slik.
- Autolenker (`<https://...>`) står urørt. De må ha et skjema for å være lenker,
  så de er alltid absolutte.

Flytter du en fil det lenkes til fra en usluppen seksjon, fanges det av
`pytest tests/test_release_notes.py` lokalt og av CI, ikke først i
release-jobben.

## Hva workflowen legger til

`release.yml` bygger body-en slik:

1. CHANGELOG-seksjonen, med «Dette må du gjøre selv» løftet øverst og relative
   lenker skrevet om til absolutte
2. `## Verifisering` med commiten ZIP-en er bygget fra, SHA256-linjen og lenke
   til `SECURITY.md`
3. `<details>`-fold med alle commits siden forrige tag

De to siste er automatiske. Ikke skriv dem inn i CHANGELOG.

## En sluppet seksjon er historikk

Sjekk hva som faktisk er publisert før du skriver:

```bash
gh release list
git log v$(gh release view --json tagName --jq .tagName)..HEAD
```

Er øverste seksjon allerede sluppet, lag en ny `## [Ikke sluppet]` over. Ellers
beskriver du arbeid som brukerne ikke har fått, i notatene for en versjon de
har. Det skjedde i juli 2026: 13 punkter havnet i `[1.14.0]` etter at den var
publisert, av flere økter på rad. Fellen er at versjonen i `manifest.json`
allerede er bumpet ved release, så filen ser ut som om den gjelder det du
holder på med.

Sjekkliste før du skriver i CHANGELOG:

- [ ] Er øverste seksjon sluppet? Da lager du en ny.
- [ ] Havnet arbeidet fra forrige runde faktisk i en seksjon?
- [ ] Beskriver punktet nettoresultatet? Rettes en feil i samme uslupne vindu
      som den ble innført, skal bare sluttilstanden stå der.

## Publisering

1. Døp `## [Ikke sluppet]` om til `## [X.Y.Z]` og les gjennom teksten som
   bruker
2. Bump versjonen i `manifest.json` og `pyproject.toml`
3. Commit og push til main

Resten gjør `release.yml`. Den starter CI for nettopp den commiten, venter på
hele grafen, og publiserer først når artefakten er bygget, lastet opp og
verifisert.

### Releaseporten

`release.yml` er den eneste workflowen som kjører på push til main. Den kaller
`ci.yml` (`workflow_call`) for sin egen commit og har `needs: ci`, så unit,
kvalitet, begge HA-målene, HACS-validering og Hassfest må være grønne for
*samme SHA* før releasejobben starter. HACS og Hassfest lå før i egne
workflows; da kunne en release gå ut før de var ferdige. De kjøres fortsatt
nattlig fra `validate.yml` og `hassfest.yml`, siden begge kan bli røde av
endringer utenfor repoet.

Det som slippes, kommer fra hovedgrenen. To vakter sier det:

- `release.yml` kjører publiseringsjobben bare når ref-en er `main` eller en
  `v*`-tagg. En `workflow_dispatch` fra en annen gren kjører CI, og stopper der.
- `release_publish.py` spør GitHub om kandidaten er hovedgrenens spiss eller en
  commit den har passert (`compare`-status `identical` eller `behind`). Er den
  ikke det, stopper flyten før noe skrives. Vakten står i scriptet og ikke bare
  i workflowen, så den gjelder også når flyten kjøres for hånd.

Prøvekjøringen mot en engangstagg trenger en ekte workflow-kjøring for å få en
attestasjon, og den må kunne gå fra en gren. Derfor finnes `proveslipp`, et
eget felt i dispatch-skjemaet som gir `--proveslipp`. Den veien slipper bare
manifestversjon `0.0.0` gjennom, og den releasen merkes som prerelease og blir
aldri `latest`. Hukes feltet av på en gren med en ekte versjon, stopper flyten.

Selve flyten ligger i `scripts/release_publish.py`, som er dekket av
`tests/test_release_publish.py`. Rekkefølgen er:

1. **Les tilstanden** (`plan`). Er versjonen sluppet fra før, bevises den mot
   sin egen tagg og jobben stopper der. Peker taggen på en annen commit, blir
   det full stopp.
2. **Bygg ZIP-en** (`build`) fra git-objektene på kandidat-SHA-en, ikke fra
   arbeidstreet. Bygget er deterministisk: faste tidsstempler, rettigheter fra
   git-modus, sortert rekkefølge. Samme commit gir byte-lik fil.
3. **Attester** bygget, før noe legges ut.
4. **Verifiser og publiser** (`publish`). Attestasjonen sjekkes mot repo,
   kilde-SHA, signer-workflow og ZIP-ens sha256. Taggen opprettes eksplisitt på
   SHA-en. Draften opprettes eller gjenopptas, ZIP-en lastes opp og *leses
   tilbake* med ny sha256-utregning. `draft=false` er siste kall.

### Når noe feiler halvveis

Det finnes ingen offentlig release før siste kall, så det er ingenting å rydde.
Kjør jobben om igjen på samme commit («Re-run failed jobs» beholder SHA-en,
eller kjør workflowen manuelt på taggen). Hvert steg er idempotent:

- Taggen finnes og peker riktig: den står, og flyttes aldri.
- Draften finnes: den gjenbrukes, og body-en skrives ikke over. Har du redigert
  den for hånd, blir redigeringen stående.
- Draften er laget for en *annen* commit: stopp, før taggen opprettes. Body-en
  sier hvilken commit ZIP-en er bygget fra, og den setningen skal ikke kunne
  bli usann fordi en draft ble stående igjen fra et tidligere forsøk. Slett
  draften, eller slipp endringen som en ny versjon. En draft du har laget i
  nettleseren peker på en gren og ikke en commit, og den gjenbrukes som før.
- ZIP-en ligger der alt: den lastes ned og sammenlignes. Stemmer sha256-en, er
  den ferdig. Stemmer den ikke, stopper flyten framfor å bytte en fil vi ikke
  vet hva er. HACS installerer nøyaktig den filen, så det er ikke et sted for
  automatikk. Slett asset-et bevisst, eller slipp en ny versjon.

En håndskrevet draft med samme tag er ikke lenger et problem som gjør at
releasen aldri kommer ut. Flyten gjenopptar den og publiserer den.

### Se hva som ville skjedd

```bash
just release-zip            # bygg ZIP-en, se sha256-en
just release-plan           # les tilstanden på GitHub, skriv ingenting
just release-verify v1.16.0 # etterprøv en release som alt er ute
```

Ingen av dem skriver noe. `release-plan` hopper over attestasjonssjekken, siden
den kjøres før byggesteget har attestert noe. I workflowen finnes det i tillegg
`workflow_dispatch` med `dry_run`, som kjører hele flyten uten å skrive.

### Det som ikke er bevist ennå

Flyten er kjørt mot en GitHub-etterligning som husker tilstand mellom kall, og
lesesiden er kjørt mot ekte GitHub og ekte `gh attestation verify`. Skrivesiden
er aldri kjørt mot et ekte repo, for det ville krevd å publisere noe. Fire ting
kan derfor bare bekreftes av den første ekte kjøringen:

- At `setup-uv` sin cache og `uv run --frozen` finner Python 3.13 og 3.14 på
  `ubuntu-latest`, som ikke har dem forhåndsinstallert. uv henter dem selv, men
  det er ikke prøvd her.
- At minimum-grenen løser `aiohasupervisor`-prereleasen på runneren. `--frozen`
  gjør dette til et nedlastingsspørsmål og ikke et løsningsspørsmål, men lokal
  maskin og runner har ulike hjul tilgjengelig.
- At `gh api` sine skrivekall (opprette tagg, opprette draft, laste opp asset,
  `make_latest`) oppfører seg som etterligningen antar.
- At de to validatorene er stabile nok til å stå i releaseporten.
- At `compare`-statusen hovedgren-vakten leser, er `identical` for en fersk
  push til main. Statusverdiene er GitHubs dokumenterte fire, og etterligningen
  regner dem ut med ekte git, men kallet er aldri gjort mot ekte GitHub.
- At jobbens `if` hopper over publiseringen slik den skal ved dispatch fra en
  annen gren. Skulle den likevel starte, stopper vakten i scriptet.

Prøvekjøringen mot en engangstagg, som står i akseptansekriteriene for
stromkalkulator-5k7d7qp, er fortsatt ikke gjort. Veien er nå ryddet:
`proveslipp` fra en gren med manifestversjon `0.0.0`, og taggen slettes
etterpå. Den krever et push, og er derfor ikke kjørt her.

Feiler noe av det, feiler det på rett side: jobben stopper, ingenting blir
publisert, og neste kjøring på samme commit gjenopptar. Det er billigere å
oppdage det slik enn å bygge inn en omvei rundt noe vi ikke vet om er et
problem.

### Actionversjonene

Gjennomgått 13. september 2026 (stromkalkulator-3m5o02u). Premisset om at det
finnes en nyere major for alle fire, holdt bare for to av dem.

`actions/checkout` gikk fra `@v6` til `@v7`. Den eneste bruddendringen i v7 er
at den nekter å sjekke ut hodet i en fork-PR under `pull_request_target` og
`workflow_run`. Vi bruker ingen av de to eventene. Resten er en ESM-omskriving
og avhengighetsbumper, og v7.0.1 har ryddet tre feil i den. Begge majorene
kjører node24. En feil i checkout kan ikke gi en gal release, bare en stoppet
en: ZIP-en bygges fra git-objektene og bindes av attestasjonen etterpå.

`extractions/setup-just` gikk fra `@v3` til `@v4`. Hele diffen er at den
underliggende `setup-crate` løftes fra v1.4.0 til v2.0.0, altså node20 til
node24. Inputene er uendret.

`codecov/codecov-action` står på `@v6`. `v6`- og `v7`-taggene peker på nøyaktig
samme commit: Codecov skriver selv at v6.0.2 er «a copy of the v7.0.0 release»,
laget for at oppdateringen skal være valgfri. Bumpen ville vært et navnebytte.

`astral-sh/setup-uv` gikk fra `@v7` til `@v10.1.0`, altså en eksakt versjon og
ikke en majortagg. Det er ikke en flytende tagg, men det bryter med mønsteret i
resten av filen, så grunnen står her og i `ci.yml`: Astral sluttet å publisere
major- og minortagger fra og med v8.0.0, som et svar på tj-actions-angrepet.
`@v8`, `@v9` og `@v10` finnes ikke. `@v7` finnes, men sluttet å bevege seg i
mars 2026 og får ingen fikser. Valget sto mellom en frossen tagg og en pinnet
versjon som må bumpes for hånd, og da er det siste ærligere. Bruddene i v8 til
v10 treffer ingenting vi bruker: det gamle `manifest-file`-formatet er borte
(vi setter det ikke), `prune-cache` er nå av som default (koster cachestørrelse,
ikke riktighet), og `enable-cache: auto` slår seg av under `pull_request_target`,
`workflow_run` og `release` (vi setter `true`, og kjører på `pull_request` og
`workflow_call`).

`actions/attest-build-provenance@v4` er allerede nyeste major, og `v4`-taggen
peker på v4.2.2. Den er det sikkerhetskritiske steget, og den ble ikke rørt.

Ikke bevist: ingen av bumpene er kjørt på en runner. `actionlint` er grønn, men
den sjekker syntaks, ikke at en action oppfører seg. Først kjøring bekrefter
det.

De tre nattlige workflowene, `validate.yml`, `fri-nettleie-sjekk.yml` og
`hassfest.yml`, står fortsatt på `actions/checkout@v6`. Samme vurdering gjelder
dem; de lå utenfor mandatet i denne runden.

### Det v1.16.0 viser

`just release-verify v1.16.0` feller i dag, og det er riktig:

```text
✓ tagg: v1.16.0 peker på 9dad0dd9ec54
✓ innhold: filene er de samme som i 9dad0dd9ec54, men ZIP-en er ikke byte-lik
! attestasjon: expected SourceRepositoryDigest to be 9dad0dd9..., got c7e7c70d...
```

Taggen peker på én commit, attestasjonen sier ZIP-en ble bygget fra en annen.
Innholdet var likt, så ingen brukere fikk feil kode, men bindingen manglet.
`SECURITY.md` sier det samme, siden det er der brukerne blir bedt om å kjøre
kommandoen. Det er nettopp den gamle flyten som gjorde det mulig, og det er
derfor `plan` bare advarer om eldre releaser mens `verify` feller: en release
som alt er ute, blir ikke bedre av at hver push til main etterpå går rød.

#### Kan det rettes i ettertid?

Mekanisk ja, og det er verdt å skrive ned hvorfor vi lar være
(stromkalkulator-4xkynb1). Filen sier ellers at det ikke går, og det er feil.

`actions/attest-build-provenance` tar `subject-digest` og `subject-name` i
stedet for `subject-path`. En `workflow_dispatch` på taggen `v1.16.0` gir
`github.sha` = 9dad0dd, så en kjøring der som laster ned den publiserte ZIP-en
og attesterer digesten hennes, ville lagt igjen en attestasjon med
`sourceRepositoryDigest` 9dad0dd og riktig subject. `gh attestation verify`
godtar treffet når én av attestasjonene på digesten passer, så `release-verify`
ville blitt grønn.

Vi gjør det ikke. Attestasjonen ville sagt at denne workflowen bygget denne
filen fra 9dad0dd, og det skjedde aldri: filen kom fra en kjøring på c7e7c70
med den gamle `zip -r`-flyten. Hele poenget med provenans er at den forteller
hva som faktisk hendte. Signerer vi en penere historie for å få vår egen
kommando grønn, er alle senere attestasjoner fra oss verdt mindre, og brukeren
kan ikke se forskjell. Det er heller ikke gratis i den forstand at ingenting
publiseres: en attestasjon er en permanent oppføring i en offentlig
gjennomsiktighetslogg.

Den gale attestasjonen kan ikke fjernes heller. REST-API-et har `POST` og
`GET` på `/repos/{owner}/{repo}/attestations`, ingen `DELETE`, og `gh
attestation` har bare `download`, `trusted-root` og `verify`. Og selv om den
kunne slettes, ville v1.16.0 stått uten provenans i det hele tatt, som er
verre enn en som ikke stemmer.

Å flytte taggen til c7e7c70 ville bundet attestasjonen, men taggen flyttes
ikke: git oppdaterer ikke en tagg som har endret seg hos en klient som alt har
hentet den, så de som har v1.16.0 ville stille blitt liggende igjen. ZIP-en er
uansett ikke byte-reproduserbar fra noen av de to commitene, siden den er
pakket før flyten ble deterministisk.

Det som står igjen, er derfor å si det der brukerne ser det. `SECURITY.md` gjør
det alt. Det siste punktet er en kort note i release-body-en for v1.16.0, og
den krever skrivetilgang på GitHub.

## Retting etter publisering

Rett i CHANGELOG.md først, så teksten i repoet er fasiten, og speil den til
releasen. `gh release edit --notes` overskriver hele body-en, så hent den
eksisterende først og behold Verifisering-delen og commit-folden:

```bash
gh release view vX.Y.Z --json body -q .body
```
