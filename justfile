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

# Arkiver Nord Pools daglige EUR/NOK (exchangeRate) for Norgespris-verifisering.
# Kjør hver gang du er i repoet (minst månedlig): gratis-API-et rekker bare ~2 mnd
# bakover, så ferske kurser må fanges før de faller ut. Merger inn i arkivet under
# _private/. Bakgrunn: docs/research/bloomberg-verifisering.md.
snapshot-kurs area="NO5":
    python3 scripts/research/snapshot_nordpool_exchangerate.py --area {{area}}

# Kjør hele testpakken + linting.
test:
    pipx run --with hypothesis pytest tests/ -v
    ruff check custom_components/stromkalkulator/ tests/
