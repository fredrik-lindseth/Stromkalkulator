# Reproducible Releases Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gjøre det mulig for brukere å kryptografisk verifisere at ZIP-filen i en GitHub Release ble bygd fra kildekoden i repoet.

**Architecture:** Bruker GitHub Artifact Attestations (basert på Sigstore) for å generere provenance-attestasjoner som binder release-artefakter til spesifikke commits og workflow-kjøringer. SHA256-checksum inkluderes i release notes.

**Tech Stack:** GitHub Actions, `actions/attest-build-provenance@v2`, Sigstore, `gh attestation verify`

---

### Task 1: Oppdater release workflow med attestation og checksums

**Files:**
- Modify: `.github/workflows/release.yml`

**Step 1: Oppdater permissions**

Legg til `id-token: write` og `attestations: write`:

```yaml
permissions:
  contents: write
  id-token: write
  attestations: write
```

**Step 2: Flytt ZIP-bygging før release-opprettelse**

ZIP-filen må lages *før* releasen slik at SHA256-checksum kan inkluderes i release body.

Rekkefølge etter endring:
1. Checkout
2. Get version
3. Check if release exists
4. Create ZIP
5. Generate SHA256
6. Get changelog
7. Create release (med SHA256 i body)
8. Upload ZIP
9. Attest build provenance

**Step 3: Legg til SHA256-checksum steg**

```yaml
- name: Generate SHA256 checksum
  id: checksum
  if: steps.check_release.outputs.exists == 'false'
  run: |
    SHA256=$(shasum -a 256 dist/stromkalkulator.zip | awk '{print $1}')
    echo "sha256=$SHA256" >> $GITHUB_OUTPUT
```

Merk: `shasum` brukes i stedet for `sha256sum` for macOS-kompatibilitet, men siden dette kjører på `ubuntu-latest` kan vi bruke `sha256sum` i stedet. Bruk `sha256sum`.

```yaml
- name: Generate SHA256 checksum
  id: checksum
  if: steps.check_release.outputs.exists == 'false'
  run: |
    SHA256=$(sha256sum dist/stromkalkulator.zip | awk '{print $1}')
    echo "sha256=$SHA256" >> $GITHUB_OUTPUT
```

**Step 4: Oppdater release body med checksum og verifiseringsinstruksjoner**

```yaml
body: |
  ## Endringer

  ${{ steps.changelog.outputs.commits }}

  ## Verifisering

  **SHA256:** `${{ steps.checksum.outputs.sha256 }}`

  Verifiser at denne releasen ble bygd fra kildekoden:
  ```bash
  gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
  ```
```

**Step 5: Legg til attestation-steg**

Etter ZIP-opplasting:

```yaml
- name: Attest build provenance
  if: steps.check_release.outputs.exists == 'false'
  uses: actions/attest-build-provenance@v2
  with:
    subject-path: dist/stromkalkulator.zip
```

**Step 6: Verifiser YAML-syntaks**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`
Expected: Ingen output (ingen feil)

**Step 7: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "feat: legg til artifact attestation og SHA256 i releases"
```

---

### Task 2: Opprett SECURITY.md med verifiseringsinstruksjoner

**Files:**
- Create: `SECURITY.md`

**Step 1: Skriv SECURITY.md**

```markdown
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
```

**Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: legg til SECURITY.md med verifiseringsinstruksjoner"
```

---

### Task 3: Legg til verifiserings-badge og seksjon i README

**Files:**
- Modify: `README.md`

**Step 1: Legg til SLSA-badge i badge-seksjonen**

Etter codecov-badgen, legg til:

```markdown
<a href="SECURITY.md"><img src="https://slsa.dev/images/gh-badge-level1.svg" alt="SLSA 1"></a>
```

**Step 2: Legg til verifiserings-seksjon før "Lisens"**

```markdown
## Verifisering av releases

Alle releases har en kryptografisk attestasjon som beviser at ZIP-filen ble bygd fra kildekoden i dette repoet. Se [SECURITY.md](SECURITY.md) for detaljer.

```bash
gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator
```
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: legg til verifiserings-badge og seksjon i README"
```

---

### Task 4: Test workflowen

**Files:**
- Ingen nye filer

**Step 1: Valider workflow-syntaks lokalt**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`
Expected: Ingen output

**Step 2: Sjekk at actionlab/attest-build-provenance@v2 finnes**

Run: `curl -s -o /dev/null -w '%{http_code}' https://github.com/actions/attest-build-provenance`
Expected: `200`

**Step 3: Test release-flow med version-bump**

For å teste ekte attestation:
1. Bump versjon i `manifest.json` (f.eks. `1.1.0` → `1.1.1`)
2. Push til main
3. Sjekk at release opprettes med SHA256 og attestation
4. Verifiser: `gh release download v1.1.1 -p stromkalkulator.zip && gh attestation verify stromkalkulator.zip --repo fredrik-lindseth/Stromkalkulator`

Merk: Attestation kan bare testes fullt ut ved å kjøre workflowen på GitHub. Lokal testing verifiserer bare YAML-syntaks.

**Step 4: Commit versjon-bump**

```bash
git add custom_components/stromkalkulator/manifest.json
git commit -m "chore: bump versjon til 1.1.1 for å teste attestation"
```
