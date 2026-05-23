# Edge cases og åpne spørsmål i tariff-håndtering

Plassholder for kjente nyanser i strømtariff-beregning som ikke er fullt avklart, men som vi har observert i ekte fakturaer. Hver oppføring beskriver hva vi har sett, hva vi har antatt, og hva som bør bekreftes med flere datapunkter.

## Julaften og nyttårsaften som lavtariff

**Observasjon:** BKKs fakturaer for desember 2025 viser at hele 24.12 og 31.12 behandles som natt-tariff (lavtariff), inkludert timer 06:00-22:00 som vanligvis er dag-tariff på hverdager.

**Lovgrunnlag:** Helligdagsfredsloven (LOV-1995-02-24-12) § 2 lister helligdagene i Norge. **24.12 og 31.12 er IKKE helligdager etter loven.** § 5 sier dog at *fra kl. 16:00 julaften gjelder helligdagsfred* (handelsforbud, ro-regler), men det gjelder ikke nyttårsaften.

**Antagelse i koden:** `HELLIGDAGER_FASTE` i `const.py` inkluderer både 24.12 og 31.12. Det matcher BKKs konvensjon og gir korrekt dag/natt-split for desember 2025-fakturaen (avvik 0,03 kWh på 1554 kWh, innenfor flytetalls-presisjon).

**Begrensning:** Vi har dette bekreftet kun mot BKK. Vi vet ikke om alle norske nettselskaper behandler 24.12 og 31.12 likt. Andre DSO-er kan tenkes å:
- Bare ha lavtariff på 24.12 *fra kl. 16:00* (matcher helligdagsfreds-§ 5)
- Behandle 31.12 som vanlig ukedag
- Ha helt andre regler for spesielle dager

**Hva som bør gjøres på sikt:**
- Innhente fakturaer fra Elvia, Tensio, Lnett, Lede for desember/januar (Norgespris-måned eller strømstøtte-måned) for å se hvordan andre DSO-er gjør det
- Hvis det viser seg å være DSO-spesifikt: flytte helligdag-listen til `dso.py` så hver DSO kan ha sin egen liste
- Dokumentere bransje-konvensjonen om vi finner den

**Spores i dcat:** `stromkalkulator-21h9` (DSO-spesifikk helligdag-overstyring).

## Plassholdere for fremtidige edge cases

Når vi oppdager flere slike nyanser, dokumenteres de her med samme struktur:
- Hva vi har sett
- Hva vi antar
- Hva som bør bekreftes
