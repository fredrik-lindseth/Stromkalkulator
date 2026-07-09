# Incident 005: Strømstøtte-terskel var flat i mva-frie soner

**Dato:** 9. juli 2026
**Status:** løst
**Berørte versjoner:** alle før denne fiksen (strømstøtte-stien i nord_norge og tiltakssonen)

## Symptomer

Review i juli 2026 fant at kunder i mva-frie soner (NO4/Nordland/Troms og
tiltakssonen) fikk feil strømstøtte. Mellom 77 og 96,25 øre/kWh ble det beregnet
null støtte, og over 96,25 øre ble støtten for liten. Sør-Norge (standard) var
riktig.

## Rotårsak

`_calculate_stromstotte` sammenlignet spotpris mot en flat konstant
`STROMSTOTTE_LEVEL = 0,9625` (const.py). Spotprisen normaliseres først til inkl.
mva per avgiftssone (incident 004): i standard-sonen ganges den med 1,25, i
mva-frie soner er mva-satsen 0 og spot forblir uendret.

Terskelen er egentlig 77 øre/kWh eks. mva (Forskrift § 5). mva-kompensasjonen
(x1,25) hører kun til der mva faktisk betales. Verdien 0,9625 er 77 x 1,25, altså
terskelen for standard-sonen. I mva-frie soner skal terskelen være 77 øre.

Fordi terskelen var en flat konstant, ble spot i nord (som med rette IKKE ble
mva-oppjustert) målt mot en terskel som var mva-oppjustert. Resultatet var at
nord-kunder i praksis fikk et 96,25-øres krav der de skulle hatt 77 øre.

### Hvorfor incident 004-fiksen ikke fanget nord-siden

Incident 004 handlet om samme klasse feil: enhets-mismatch mellom spot og
terskel. Den fiksen gjorde spotprisen enhetsriktig, den normaliserer nå til
inkl. mva per sone. Men terskelen forble en flat konstant.

For standard-sonen var det tilstrekkelig: 0,9625 er korrekt terskel der. For
mva-frie soner ble spot korrekt IKKE oppjustert (mva = 0), men terskelen ble
heller ikke nedjustert til 77 øre. Normaliseringen ble altså enhetsriktig for
den ene siden av sammenligningen (spot), mens terskelen forble flat. Nord-siden
av det samme enhetsproblemet gjensto, usynlig, fordi ingen test dekket støtte i
mva-frie soner (test_spotpris_mva.py testet kun selve normaliseringen).

## Konsekvenser

For nord_norge og tiltakssonen (terskel skal være 0,77):

- Spot mellom 0,77 og 0,9625: null støtte i stedet for `(spot - 0,77) * 0,9`.
- Spot over 0,9625: støtte beregnet som `(spot - 0,9625) * 0,9` i stedet for
  `(spot - 0,77) * 0,9`, altså for lite med `0,1925 * 0,9 = 0,17` kr/kWh.

Terskel-attributtet og note-teksten på strømstøtte-sensorene viste også flat
96,25 øre for alle soner.

Norgespris var allerede sonebevisst (`get_norgespris_inkl_mva`); støtten var det
ikke.

## Berørte beregninger

I `coordinator.py`:

- `_calculate_stromstotte`: sammenligning og støttebeløp brukte flat terskel.
- Alt som avhenger av `stromstotte`: `spotpris_etter_stotte`, `total_price`
  (uten Norgespris), `kroner_spart_per_kwh`, `_monthly_norgespris_diff`,
  `_monthly_accumulated_cost_strom` og månedlig strømstøtte-estimat.

## Løsning

1. Ny konstant `STROMSTOTTE_TERSKEL_EKS_MVA = 0,77` og helper
   `get_stromstotte_terskel(avgiftssone) = 0,77 * (1 + get_mva_sats(avgiftssone))`
   i `const.py`, samme mønster som `get_norgespris_inkl_mva`.
2. `_calculate_stromstotte` tar nå en `terskel`-parameter (default beholder
   standard-sonens 0,9625 for bakoverkompatible kall). Coordinator sender inn
   `get_stromstotte_terskel(self.avgiftssone)`.
3. Coordinator eksponerer `stromstotte_terskel` i data-dicten.
4. Sensor-attributtene (`StromstotteSensor`, `StromstotteAktivSensor`) bruker den
   sonebevisste terskelen i `terskel`, `over_terskel` og note-teksten, med
   `STROMSTOTTE_LEVEL` som trygg fallback.

`STROMSTOTTE_LEVEL` beholdes som navngitt konstant (standard-sonens terskel).

## Tester

`tests/test_stromstotte_nord.py` dekker alle tre avgiftssoner rundt begge
grensene (77 og 96,25 øre), inkludert regresjonstesten: spot 0,87 (mellom 77 og
96,25) gir positiv støtte i nord/tiltak, men null i standard. Egne tester på
helperen og på at sensor-attributtene viser sonebevisst terskel.

## Lærdom

1. **Normaliser enhet og terskel sammen.** Incident 004 gjorde spot
   enhetsriktig, men lot terskelen stå flat. Når to størrelser sammenlignes, må
   begge behandles sonebevisst, ikke bare den ene.
2. **En konstant som er "riktig for standard" er en skjult sone-antagelse.**
   0,9625 så ut som en universell terskel, men bar i seg en 25 %-mva som ikke
   gjelder overalt. Slike verdier bør utledes via en sone-helper, ikke hardkodes.
3. **Fiks hele feilklassen, ikke bare det observerte symptomet.** Incident 003
   dokumenterte intensjonen (96,25 for standard, 77 for nord). At kun sør-siden
   ble fikset i 004, viser verdien av å lete etter speilingen av en feil i de
   andre sonene.

## Kilder

- [Forskrift om strømstønad § 5](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)
- NVE/Elinett 2026: 90 % over 77 øre eks. mva, mva-kompensasjon kun der mva betales
- [Incident 003](003-no3-mva-feilklassifisering.md): dokumenterte den sonebevisste intensjonen
- [Incident 004](004-spotpris-mva-feilbehandling.md): fikset sør-siden av samme enhetsproblem
