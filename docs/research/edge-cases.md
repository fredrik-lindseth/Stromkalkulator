# Edge cases og åpne spørsmål i tariff-håndtering

Plassholder for kjente nyanser i strømtariff-beregning som ikke er fullt avklart, men som vi har observert i ekte fakturaer. Hver oppføring beskriver hva vi har sett, hva vi har antatt, og hva som bør bekreftes med flere datapunkter.

## Julaften og nyttårsaften som lavtariff

**Observasjon:** BKKs fakturaer for desember 2025 viser at hele 24.12 og 31.12 behandles som natt-tariff (lavtariff), inkludert timer 06:00-22:00 som vanligvis er dag-tariff på hverdager.

**Lovgrunnlag:** Helligdagsfredsloven (LOV-1995-02-24-12) § 2 lister helligdagene i Norge. **24.12 og 31.12 er IKKE helligdager etter loven.** § 5 sier dog at *fra kl. 16:00 julaften gjelder helligdagsfred* (handelsforbud, ro-regler), men det gjelder ikke nyttårsaften.

**Implementering (v1.13.0):** `HELLIGDAGER_FASTE` i `const.py` inneholder bare offisielle helligdager. Per-DSO `helligdager_ekstra` i `dso.py` lar hvert nettselskap definere ekstra dager som skal regnes som lavtariff. BKK har `["12-24", "12-31"]`. Andre DSO-er har default (uten ekstra dager) inntil faktura-data bekrefter hva som gjelder. Verifisert mot 6 BKK-fakturaer (oktober 2025 til april 2026).

**Åpne spørsmål:** Vi vet fortsatt ikke om andre DSO-er behandler 24.12 og 31.12 likt. Mulige varianter:
- Lavtariff på 24.12 *fra kl. 16:00* (matcher helligdagsfreds-§ 5)
- 31.12 som vanlig ukedag
- Helt andre regler

**Hvordan bidra:** Send inn fakturaer fra desember/januar via [bidra med faktura](../fakturaer/bidra-med-faktura.md). Hvis fakturaen din viser hele 24.12 eller 31.12 som natt-tariff, legg dem til DSO-ens `helligdager_ekstra` i en PR.

## Plassholdere for fremtidige edge cases

Når vi oppdager flere slike nyanser, dokumenteres de her med samme struktur:
- Hva vi har sett
- Hva vi antar
- Hva som bør bekreftes
