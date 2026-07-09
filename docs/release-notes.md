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
