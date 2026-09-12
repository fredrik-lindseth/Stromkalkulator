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

Exit 1 hvis seksjonen mangler eller er tom. Både `ci.yml` og `release.yml`
henger på den exit-koden, så en versjon uten note blir aldri publisert.

## Stil

- Ikke forklar hva prosjektet er, brukerne har allerede installert det
- Punktlister, ikke avsnitt med bold-tittel og lang beskrivelse
- Kort og skannbart
- Ingen AI-slop ("we're excited to announce", overdreven adjektivbruk)
- Ingen em-dashes, bruk komma eller punktum
- Krediter brukere som rapporterer bugs: `@brukernavn` + issue-referanse
- Er det noe brukeren må gjøre selv (bytte entitets-id, bekrefte enhetsbytte,
  velge et nytt felt), skal det stå tydelig, gjerne først

Underoverskriftene er Keep a Changelog-kategoriene (`### Fikset`, `### Lagt
til`, `### Endret`, `### Verifisert`, `### Dokumentert`). Ikke skriv noen
`# v1.3.0`-heading, tittelen settes på selve releasen.

## Hva workflowen legger til

`release.yml` bygger body-en slik:

1. CHANGELOG-seksjonen, ordrett
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
