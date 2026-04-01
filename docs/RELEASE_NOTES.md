# Hvordan skrive release notes

## Regler

- Ikke forklar hva prosjektet er. Brukerne har allerede installert det.
- Bruk punktlister, ikke avsnitt med bold-tittel + beskrivelse.
- Hold det kort og skannbart. Ingen vegger med tekst.
- Ikke bruk `# v1.3.0` som heading. Tittel settes på selve releasen.
- Unngå AI-slop: overdreven bruk av tankestreker, adjektiver, og "we're excited to announce".
- Krediter brukere som rapporterer bugs med `@brukernavn` og issue-referanse.

## Struktur

````markdown
## Bugfixes

- **Kort beskrivelse** — teknisk detalj på en linje

## Forbedringer

- Punktliste med endringer

## Vedlikehold

- Refaktoreringer, tester, docs-endringer

## Verifisering

**SHA256:** `abc123...` — [hvordan verifisere](SECURITY.md)

<details>
<summary>Alle commits</summary>

- feat: ...
- fix: ...
</details>
````

## Viktig om verifisering

Release-workflowen genererer SHA256 automatisk. SHA256-linjen **MÅ** være med. Lenk til SECURITY.md for detaljer, ikke forklar attestation i selve releasen.

Hvis du bruker `gh release edit --notes` overskriver du hele body-en — hent eksisterende body først med `gh release view vX.Y.Z --json body -q .body`.

## Commits i detaljer

- Legg feat/fix-commits i `<details>`-fold på bunnen
- Dropp docs/test/chore fra listen med mindre de er relevante
- Inkluder bare de viktigste

## Eksempel

Se [v1.3.0](https://github.com/fredrik-lindseth/Stromkalkulator/releases/tag/v1.3.0).
