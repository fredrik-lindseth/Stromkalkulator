# Sikkerhet og verifisering

## Verifiser releases

Alle releases inkluderer en [artifact attestation](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds) som kryptografisk binder ZIP-filen til kildekoden og GitHub Actions-workflowen som bygde den.

`stromkalkulator.zip` er også filen HACS selv laster ned og installerer (`zip_release` er satt i `hacs.json`), ikke bare et vedlegg til release-siden. Attestasjonen dekker dermed nøyaktig det som legges i `custom_components/stromkalkulator/` på systemet ditt.

### Hvorfor?

Custom integrasjoner i Home Assistant kjører med full tilgang til systemet ditt. Du bør kunne verifisere at koden du installerer faktisk kommer fra kildekoden du kan lese på GitHub.

### Verifiser med GitHub CLI

1. Last ned `stromkalkulator.zip` fra [siste release](https://github.com/fredrik-lindseth/Stromkalkulator/releases/latest)

2. Verifiser attestasjonen:

   ```bash
   gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
   ```

3. Du skal se noe som:

   ```text
   ✓ Verification succeeded!
   ```

   Outputen viser hvilken commit og workflow som bygde filen.

### Verifiser SHA256-checksum

Hver release inkluderer en SHA256-checksum i release notes, sammen med commiten ZIP-en er bygget fra. Sjekk at filen du lastet ned matcher:

```bash
sha256sum stromkalkulator.zip
```

Sammenlign outputen med checksum i release notes.

### Bygg ZIP-en selv og sammenlign

Fra og med v1.17.0 er bygget deterministisk: ZIP-en pakkes fra git-objektene på commiten taggen peker på, med faste tidsstempler og rettigheter fra git. Da kan du bygge den samme filen selv og få samme sha256, uten å stole på hverken oss eller GitHub:

```bash
git clone https://github.com/fredrik-lindseth/Stromkalkulator
cd Stromkalkulator
python3 scripts/release_publish.py build --sha vX.Y.Z --output /tmp/stromkalkulator.zip
```

Utskriften er sha256-en. Den skal være identisk med den i release notes og med den du lastet ned.

Vil du sjekke hele kjeden i ett kall, altså at tagg, ZIP og attestasjon peker på samme artefakt:

```bash
just release-verify vX.Y.Z
```

Releaser fra før v1.17.0 ble pakket med `zip -r` fra arbeidstreet på runneren, så tidsstempler og katalogoppføringer kom derfra. De kan ikke bygges byte-likt. Kommandoen sammenligner da filene i ZIP-en mot treet taggen peker på i stedet.

## Rapportere sikkerhetsproblemer

Finner du en sikkerhetsrelatert feil? Opprett et issue på [GitHub](https://github.com/fredrik-lindseth/Stromkalkulator/issues) eller kontakt maintainer direkte.
