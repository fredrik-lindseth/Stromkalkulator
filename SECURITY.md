# Sikkerhet og verifisering

## Verifiser releases

Alle releases inkluderer en [artifact attestation](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds) som kryptografisk binder ZIP-filen til kildekoden og GitHub Actions-workflowen som bygde den.

### Hvorfor?

Custom integrasjoner i Home Assistant kjører med full tilgang til systemet ditt. Du bør kunne verifisere at koden du installerer faktisk kommer fra kildekoden du kan lese på GitHub.

### Verifiser med GitHub CLI

1. Last ned `stromkalkulator.zip` fra [siste release](https://github.com/fredrik-lindseth/Stromkalkulator/releases/latest)

2. Verifiser attestasjonen:

   ```bash
   gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
   ```

3. Du skal se noe som:

   ```
   ✓ Verification succeeded!
   ```

   Outputen viser hvilken commit og workflow som bygde filen.

### Verifiser SHA256-checksum

Hver release inkluderer en SHA256-checksum i release notes. Sjekk at filen du lastet ned matcher:

```bash
sha256sum stromkalkulator.zip
```

Sammenlign outputen med checksum i release notes.

## Rapportere sikkerhetsproblemer

Finner du en sikkerhetsrelatert feil? Opprett et issue på [GitHub](https://github.com/fredrik-lindseth/Stromkalkulator/issues) eller kontakt maintainer direkte.
