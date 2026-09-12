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

Exit 1 hvis seksjonen mangler, er tom, eller har en relativ lenke til en fil
som ikke finnes. Både `ci.yml` og `release.yml` henger på den exit-koden, så en
versjon uten note blir aldri publisert.

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

Flytter du en fil det lenkes til fra en uslupen seksjon, fanges det av
`pytest tests/test_release_notes.py` lokalt og av CI, ikke først i
release-jobben.

## Hva workflowen legger til

`release.yml` bygger body-en slik:

1. CHANGELOG-seksjonen, med «Dette må du gjøre selv» løftet øverst og relative
   lenker skrevet om til absolutte
2. `## Verifisering` med SHA256-linjen og lenke til `SECURITY.md`
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

CI sjekker at CHANGELOG har en seksjon for den nye versjonen (bare når taggen
ikke finnes fra før), og release-workflowen bygger zip, SHA256 og attestasjon
og publiserer med seksjonen som body.

Workflowen hopper stille over hvis releasen **eller en draft med samme tag**
allerede finnes. Har du en håndskrevet draft liggende, slett den før du pusher,
ellers sitter du igjen med en draft uten zip og attestasjon:

```bash
gh release delete vX.Y.Z --repo fredrik-lindseth/Stromkalkulator --yes
```

## Retting etter publisering

Rett i CHANGELOG.md først, så teksten i repoet er fasiten, og speil den til
releasen. `gh release edit --notes` overskriver hele body-en, så hent den
eksisterende først og behold Verifisering-delen og commit-folden:

```bash
gh release view vX.Y.Z --json body -q .body
```
