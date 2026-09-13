# Verifiserte fakturaer

Hver rapport her er en attest på at integrasjonen regner riktig for et gitt nettselskap, en gitt periode og en gitt avtaletype. Tallene er hentet fra ekte fakturaer og sammenlignet linje for linje mot integrasjonens beregninger.

## Verifiserte nettselskap

| Nettselskap | Prisområde | Avgiftssone | Antall verifiserte måneder | Siste verifisering | Avtale                             |
| ----------- | ---------- | ----------- | -------------------------- | ------------------ | ---------------------------------- |
| BKK         | NO5        | Standard    | 10                         | august 2026        | Spotpris (2025), Norgespris (2026) |

Vil du få inn ditt eget nettselskap? Se [verifiser-din-faktura.md](verifiser-din-faktura.md).

## Siste revalidering

Attesten er sist kjørt om igjen mot `559f799`, etter at avregningsserien L3a
endret hvordan energi, pris og tariff bokføres. Kommandoene er

```
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_<måned>_2026_hourly.json --faktura <måned>_2026
python3 scripts/research/verify_norgespris_eksakt.py
UV_PROJECT_ENVIRONMENT=.venv-unit uv run --frozen --python 3.13 --group unit \
    pytest tests/ -q
```

Alle linjene i tabellene under står uendret gjennom serien, for
verifiseringsskriptene og fixturene er ikke rørt av den. Det coordinatoren
regner, flyttet seg derimot: dag/natt-splitten for mai, juni og juli 2026
flyttet inntil 0,261 kWh over tariffgrensen uten at totalen, kapasitetsleddet
eller `monthly_cost_kr` endret seg, og den flyttet seg mot fakturaen.
Før/etter-tabellen og metoden står i
[revalidering-l3a-september-2026.md](../research/revalidering-l3a-september-2026.md).

Kronetallene endrer seg igjen når kostnadskjernen (L3b) lander. Da må alle ti
månedene kjøres på nytt; listen står i samme notat.

## Fakturaer

Hver lenke er en verifiseringsrapport med full gjennomgang: forbruk, priser, effektmålinger og sammenligning mot integrasjonen.

### 2026 (Norgespris, 2026-satser)

- [August 2026](bkk-august-2026.md) (linje for linje verifisert; time-for-time venter på Elhub-data, HAN-utfall 01.-08. august)
- [Juli 2026](bkk-juli-2026.md) (linje for linje verifisert; time-for-time delvis, HAN-utfall 29.-31. juli)
- [Juni 2026](bkk-juni-2026.md)
- [Mai 2026](bkk-mai-2026.md)
- [April 2026](bkk-april-2026.md)
- [Mars 2026](bkk-mars-2026.md)
- [Februar 2026](bkk-februar-2026.md)

### 2025 (spotpris + strømstøtte, 2025-satser)

- [Oktober 2025](bkk-oktober-2025.md)
- [November 2025](bkk-november-2025.md)
- [Desember 2025](bkk-desember-2025.md)

Hvilke sensorer og attributter du sammenligner mot fakturaen, står i [sensorer.md](../sensorer.md) og [verifiser-din-faktura.md](verifiser-din-faktura.md).
