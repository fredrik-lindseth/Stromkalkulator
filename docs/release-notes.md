# Release notes-stil

## Regler

- Ikke forklar hva prosjektet er, brukerne har allerede installert det
- Bruk punktlister, ikke avsnitt med bold-tittel + beskrivelse
- Hold det kort og skannbart
- Ikke bruk `# v1.3.0` som heading, tittel settes på selve releasen
- Ingen AI-slop ("we're excited to announce", overdreven adjektivbruk)
- Ingen em-dashes, bruk komma eller punktum
- Krediter brukere som rapporterer bugs: `@brukernavn` + issue-referanse

## Mal

```markdown
## Bugfixes

- **Kort beskrivelse**: teknisk detalj på én linje

## Forbedringer

- Punktliste

## Vedlikehold

- Refaktorering, tester, docs

## Verifisering

**SHA256:** `abc123...` ([hvordan verifisere](https://github.com/fredrik-lindseth/Stromkalkulator/blob/main/SECURITY.md))

<details>
<summary>Alle commits</summary>

- feat: ...
- fix: ...
</details>
```

## Verifisering

SHA256 genereres automatisk av release-workflowen. Linjen MÅ være med. Lenk til SECURITY.md, ikke forklar attestation i releasen.

`gh release edit --notes` overskriver hele body-en. Hent eksisterende først:

```bash
gh release view vX.Y.Z --json body -q .body
```

## Commits

- Feat/fix-commits i `<details>`-fold på bunnen
- Dropp docs/test/chore med mindre relevant
- Bare de viktigste

Se [v1.3.0](https://github.com/fredrik-lindseth/Stromkalkulator/releases/tag/v1.3.0) for eksempel.

## CHANGELOG.md

`CHANGELOG.md` er utviklerloggen, release notes er brukerteksten. Samme arbeid beskrives i begge, men med ulikt språk og detaljnivå.

**En sluppet seksjon er historikk og skal ikke endres.** Sjekk hva som faktisk er publisert før du skriver: `gh release list` og `git log v$(gh release view --json tagName --jq .tagName)..HEAD`. Er øverste seksjon allerede sluppet, lag en ny for versjonen du jobber mot. Ellers beskriver du arbeid som brukerne ikke har fått, i notatene for en versjon de har.

Det skjedde i juli 2026: 13 punkter ble skrevet inn i `[1.14.0]` etter at den var publisert, av flere økter på rad. Fellen er at versjonen i `manifest.json` allerede er bumpet ved release, så filen ser ut som om den gjelder det du holder på med.

Sjekklisten før du skriver i CHANGELOG:

- [ ] Er øverste seksjon sluppet? Da lager du en ny.
- [ ] Havnet arbeidet fra forrige runde faktisk i en seksjon? Satsvakten, unique_id-endringen og ni prisoppdateringer sto bare i en GitHub-draft og manglet helt i CHANGELOG.
- [ ] Beskriver punktet nettoresultatet? Rettes en feil i samme uslupne vindu som den ble innført, skal bare sluttilstanden stå der.

## Publisering

Release-workflowen bygger releasen fra bunnen ved push til main når `manifest.json`-versjonen er ny: den lager zip, SHA256 og attestasjon og publiserer. Den sjekker `gh release view vX.Y.Z` og **hopper stille over hvis releasen (eller en draft med samme tag) allerede finnes**.

Har du en håndskrevet draft liggende som forhåndsvisning, MÅ den slettes før du bumper versjonen og pusher. Ellers bygger workflowen ingenting, og du sitter igjen med en draft uten zip og attestasjon.

```bash
gh release delete vX.Y.Z --repo fredrik-lindseth/Stromkalkulator --yes   # slett draften først
# bump manifest.json (+ pyproject.toml), commit, push -> workflowen bygger og publiserer
```
