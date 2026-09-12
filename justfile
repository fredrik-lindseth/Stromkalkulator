# Strømkalkulator — repro-targets for research-verifisering.
#
# Krever `just` (https://github.com/casey/just). På macOS: `brew install just`.
# Lag en Makefile-shim om `just` ikke er ønskelig i miljøet ditt.

set shell := ["bash", "-uc"]

default:
    @just --list

# Kjør alle verify-scripts som støtter --emit-markdown og oppdater
# docs/research/_generated/. Krever ikke internett — bruker kun lokale
# fixturer i tests/fixtures/ og Måleverdier/.
verify-all:
    @echo "→ match_norgespris_variants (april 2026)"
    python3 scripts/research/match_norgespris_variants.py --emit-markdown
    @echo "→ match_norgespris_alle_maaneder (alle måneder m/faktura)"
    python3 scripts/research/match_norgespris_alle_maaneder.py --emit-markdown
    @echo "→ match_strommstotte_variants (april 2026)"
    python3 scripts/research/match_strommstotte_variants.py --emit-markdown
    @echo "→ oppdater GENERATED-blokker i docs/research/*.md"
    python3 scripts/research/inject_generated.py

# Bare april (raskt fornuftssjekk).
verify-april:
    python3 scripts/research/match_norgespris_variants.py --emit-markdown
    python3 scripts/research/match_strommstotte_variants.py --emit-markdown

# Regenerer snapshot-fixturer (Nord Pool EUR/MWh + Norges Bank EUR/NOK).
# Krever internett.
regen-fixtures start="2026-01-01" end="2026-05-22" area="NO5":
    python3 scripts/research/snapshot_nordpool_eur.py \
        --start {{start}} --end {{end}} --area {{area}} \
        --output tests/fixtures/nordpool_eur_no5_2026.json
    python3 scripts/research/snapshot_nb_eur_nok.py \
        --start {{start}} --end {{end}} \
        --output tests/fixtures/nb_eur_nok_2026.json

# Arkiver Nord Pools daglige EUR/NOK (exchangeRate) og publiserte NOK-kvarterpriser.
# Kjør hver gang du er i repoet (minst månedlig): gratis-API-et rekker bare ~2 mnd
# bakover, så ferske data må fanges før de faller ut. Merger inn i arkivene under
# _private/. Kvarterprisene trengs for eksakt Norgespris-verifisering, se
# docs/research/norgespris-eksakt-match.md.
snapshot-kurs area="NO5":
    python3 scripts/research/snapshot_nordpool_exchangerate.py --area {{area}}
    python3 scripts/research/snapshot_nordpool_nok.py --area {{area}}

# Verifiser Norgespris-linjen mot publiserte Final-priser (alle måneder med dekning).
verify-norgespris:
    python3 scripts/research/verify_norgespris_eksakt.py

# Kjør hele testpakken + linting.
test:
    pipx run --with hypothesis --with pyyaml pytest tests/ -v
    ruff check custom_components/stromkalkulator/ tests/
    pipx run mypy custom_components/stromkalkulator/ --ignore-missing-imports

# Filen skal være identisk, alle entitetsreferanser skal finnes, og
# test-sensorene skal stå i en grei tilstand. Exit 1 hvis ikke.
# Sjekk at testpakken i repoet er i takt med den som kjører på HA.
sjekk-testpakke host="ha-local":
    python3 scripts/sjekk_testpakke.py --host {{host}}

# Viser diff først, kopierer bare hvis den er ulik, og ber om restart etterpå
# (HA laster ikke packages på nytt av seg selv).
# Legg repoets testpakke ut på HA.
deploy-testpakke host="ha-local":
    #!/usr/bin/env bash
    set -euo pipefail
    fjern=/config/packages/stromkalkulator_test.yaml
    lokal=packages/stromkalkulator_test.yaml
    tmp=/tmp/stromkalkulator_test_fjern.yaml
    feil=/tmp/stromkalkulator_test_ssh.err
    # ssh svarer 255 på sine egne feil (vert nede, auth, ukjent host). Da vet vi
    # ikke om pakken ligger på HA, og skal ikke vise en diff som later som den
    # mangler. Alt annet enn 0 kommer fra `cat` og betyr at filen ikke finnes.
    set +e
    ssh -o IdentitiesOnly=yes {{host}} "cat $fjern" > "$tmp" 2>"$feil"
    kode=$?
    set -e
    if [[ $kode -eq 255 ]]; then
        echo "ssh mot {{host}} feilet (255). Vet ikke om pakken ligger der, så ingen diff. Avbryter." >&2
        cat "$feil" >&2
        exit 1
    fi
    if [[ $kode -ne 0 ]]; then
        echo "Fant ikke $fjern på {{host}} (cat ga $kode). Pakken er ikke lagt ut ennå."
        : > "$tmp"
    fi
    if diff -u "$tmp" "$lokal" > /tmp/stromkalkulator_test.diff; then
        echo "Testpakken på {{host}} er allerede identisk med repoets. Gjør ingenting."
        exit 0
    fi
    echo "Diff mot {{host}} (fjern → repo):"
    cat /tmp/stromkalkulator_test.diff
    read -r -p "Kopier repoets pakke til {{host}}? [j/N] " svar
    [[ "$svar" == "j" ]] || { echo "Avbrutt."; exit 1; }
    ssh -o IdentitiesOnly=yes {{host}} "cat > $fjern" < "$lokal"
    echo "Kopiert. Start HA på nytt for at pakken skal leses:"
    echo "  ssh -o IdentitiesOnly=yes {{host}} 'ha core restart'"
    echo "Deretter: just sjekk-testpakke"
