# Edge cases og åpne spørsmål i tariff-håndtering

Plassholder for kjente nyanser i strømtariff-beregning som ikke er fullt avklart, men som vi har observert i ekte fakturaer. Hver oppføring beskriver hva vi har sett, hva vi har antatt, og hva som bør bekreftes med flere datapunkter.

## Julaften og nyttårsaften som lavtariff

BKKs fakturaer for desember 2025 viser at hele 24.12 og 31.12 behandles som natt-tariff (lavtariff), inkludert timene 06:00-22:00 som vanligvis er dag-tariff på hverdager.

Helligdagsfredsloven (LOV-1995-02-24-12) § 2 lister helligdagene i Norge, og 24.12 og 31.12 er ikke blant dem. § 5 sier riktignok at det gjelder helligdagsfred (handelsforbud, ro-regler) fra kl. 16:00 julaften, men den bestemmelsen gjelder ikke nyttårsaften.

Fra v1.13.0 inneholder `HELLIGDAGER_FASTE` i `const.py` bare offisielle helligdager. Per-DSO `helligdager_ekstra` i `dso.py` lar hvert nettselskap definere ekstra dager som skal regnes som lavtariff. BKK har `["12-24", "12-31"]`. Andre DSO-er har default (uten ekstra dager) inntil faktura-data bekrefter hva som gjelder. Verifisert mot 6 BKK-fakturaer (oktober 2025 til april 2026).

Vi vet fortsatt ikke om andre DSO-er behandler 24.12 og 31.12 likt. Mulige varianter er lavtariff på 24.12 først *fra kl. 16:00*, som ville matchet helligdagsfreds-§ 5, at 31.12 regnes som en vanlig ukedag, eller helt andre regler.

Vil du bidra, send inn fakturaer fra desember/januar via [bidra med faktura](../fakturaer/bidra-med-faktura.md). Viser fakturaen din hele 24.12 eller 31.12 som natt-tariff, legg dagene til DSO-ens `helligdager_ekstra` i en PR.

## Plassholdere for fremtidige edge cases

Når vi oppdager flere slike nyanser, dokumenteres de her med samme struktur: hva vi har sett, hva vi antar, og hva som bør bekreftes.
