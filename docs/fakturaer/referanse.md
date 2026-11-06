# Verifiserte fakturaer

Hver rapport her er en attest på at integrasjonen regner riktig for et gitt nettselskap, en gitt periode og en gitt avtaletype. Tallene er hentet fra ekte fakturaer og sammenlignet linje for linje mot integrasjonens beregninger.

## Verifiserte nettselskap

| Nettselskap | Prisområde | Avgiftssone | Antall verifiserte måneder | Siste verifisering | Avtale                             |
| ----------- | ---------- | ----------- | -------------------------- | ------------------ | ---------------------------------- |
| BKK         | NO5        | Standard    | 12                         | oktober 2026       | Spotpris (2025), Norgespris (2026) |

Vil du få inn ditt eget nettselskap? Se [verifiser-din-faktura.md](verifiser-din-faktura.md).

## Kontroller beregningene

Fakturatestene kontrollerer satser og formler, mens replay-testene kjører avlesninger og priser gjennom coordinatoren. [Utviklerkontrollen](utviklerkontroll.md) beskriver hvordan du sammenligner forbruk, kapasitetstrinn og kostnadskomponenter ved kodeendringer. Hver månedsrapport viser datadekning og avvik for den fakturaen.

## Fakturaer

Hver lenke er en verifiseringsrapport med full gjennomgang: forbruk, priser, effektmålinger og sammenligning mot integrasjonen.

### 2026 (Norgespris, 2026-satser)

- [Oktober 2026](bkk-oktober-2026.md) (745 timer inkludert vintertid; én estimert Elhub-time; Norgespris avviker −0,0025 kr med endelige priser)

- [August 2026](bkk-august-2026.md) (linje for linje og time for time verifisert; 177 av 744 timer har kWh fra Elhub etter HAN-utfallet 01.-08. august)
- [September 2026](bkk-september-2026.md) (linje for linje og time for time verifisert; Norgespris treffer på -0,004 kr mot publiserte Final-priser)
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
