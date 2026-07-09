# Incident 002: Feil reverse-beregning av energiledd eks. avgifter

**Dato:** mars 2026
**Status:** fikset
**Oppdaget under:** fakturaverifisering februar 2026

## Symptomer

Attributtet `eks_avgifter_mva` på EnergileddDagSensor og EnergileddNattSensor avvek fra BKK-fakturaen.

| Sensor          | Vårt attributt | Faktura (eks. mva) | Avvik     |
| --------------- | -------------- | ------------------ | --------- |
| Energiledd dag  | 30.40 øre      | 28.77 øre          | +1.63 øre |
| Energiledd natt | 12.13 øre      | 10.50 øre          | +1.63 øre |

Konsistent +1.63 øre for høyt.

## Rotårsak

Reverse-beregningen blandet inkl. mva og eks. mva i feil rekkefølge.

```python
# Feil: trekker fra eks. mva avgifter fra inkl. mva sum, deretter deler på mva
energiledd_eks_avgifter = energiledd_dag - forbruksavgift - ENOVA_AVGIFT
energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)
# (0.4613 - 0.0713 - 0.01) / 1.25 = 0.3040  → feil

# Riktig: del på mva først, trekk fra avgifter etterpå
energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
# 0.4613 / 1.25 - 0.0713 - 0.01 = 0.2877  → riktig
```

`energiledd_dag` er inkl. mva, mens `FORBRUKSAVGIFT_ALMINNELIG` og `ENOVA_AVGIFT` er eks. mva. `(a*1.25 - b) / 1.25 != a - b` med mindre `b = 0`.

## Påvirkning

Kun `extra_state_attributes["eks_avgifter_mva"]` på to sensorer. Totalpris, strømstøtte, Norgespris og Energy Dashboard-sensoren er upåvirkede (de bruker inkl.-mva-verdiene direkte). Brukere som sammenlignet `eks_avgifter_mva` med fakturaen så feil tall.

## Fiks

Endret beregningsrekkefølgen i `EnergileddDagSensor` og `EnergileddNattSensor`:

```python
energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
```

Fungerer for alle tre avgiftssoner (Standard, Nord-Norge, Tiltakssonen).

## Lærdom

1. **Ikke bland inkl. mva og eks. mva i aritmetikk.** Konverter til samme basis først (del på (1 + mva)), trekk fra etterpå.
2. **Fakturaverifisering avdekker subtile feil.** Diagnostikk-attributter brukes sjelden til daglig, og ble bare fanget gjennom systematisk sammenligning.
3. **Tester må matche faktiske fakturaer.** `test_reverse_energiledd_*` i `tests/test_faktura_februar_2026.py`.

   > Note: `tests/test_faktura_februar_2026.py` er siden konsolidert inn i `tests/test_faktura_bkk.py` (samme testnavn, `test_reverse_energiledd_dag_eks_avgifter` / `test_reverse_energiledd_natt_eks_avgifter`). Historisk referanse over, ikke omskrevet.
