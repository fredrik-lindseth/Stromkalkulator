# Incident 002: Feil reverse-beregning av energiledd eks. avgifter

**Dato:** mars 2026
**Oppdaget under:** Fakturaverifisering februar 2026
**Status:** Fikset

## Symptomer

Attributtet `eks_avgifter_mva` på EnergileddDagSensor og EnergileddNattSensor viste feil verdi sammenlignet med BKK-fakturaen.

| Sensor | Vårt attributt | Faktura (eks. mva) | Avvik |
|---|---|---|---|
| Energiledd dag | 30.40 øre | 28.77 øre | +1.63 øre |
| Energiledd natt | 12.13 øre | 10.50 øre | +1.63 øre |

Feilen var konsistent: alltid +1.63 øre for høy.

## Rotårsak

Reverse-beregningen blandet inkl. mva og eks. mva verdier i feil rekkefølge.

```python
# FEIL: Trekker fra eks. mva avgifter fra inkl. mva sum, deretter deler på mva
energiledd_eks_avgifter = energiledd_dag - forbruksavgift - ENOVA_AVGIFT
energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)

# Tallene:
# (0.4613 - 0.0713 - 0.01) / 1.25 = 0.3040 (30.40 øre) ← FEIL
```

```python
# RIKTIG: Del på mva først, trekk fra avgifter etterpå
energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT

# Tallene:
# 0.4613 / 1.25 - 0.0713 - 0.01 = 0.2877 (28.77 øre) ← RIKTIG
```

Feilen oppstod fordi `energiledd_dag` (fra tso.py) er inkl. mva, mens `FORBRUKSAVGIFT_ALMINNELIG` og `ENOVA_AVGIFT` er eks. mva. Når man trekker eks. mva verdier fra en inkl. mva verdi og deretter deler på (1 + mva), får man feil resultat.

Matematisk: `(a*1.25 - b) / 1.25 != a - b` (med mindre b = 0).

## Påvirkning

- **Kun diagnostikk-attributt**: Feilen påvirket KUN `extra_state_attributes["eks_avgifter_mva"]` på to sensorer
- **Ingen påvirkning på prisberegninger**: Totalpris, strømstøtte, Norgespris og alle andre sensorer bruker `energiledd_dag`/`energiledd_natt` direkte (inkl. alt), og er upåvirkede
- **Ingen påvirkning på Energy Dashboard**: Dashboard-sensoren bruker `total_price_inkl_avgifter` som beregnes korrekt
- **Påvirket fakturasammenligning**: Brukere som sammenlignet `eks_avgifter_mva` med fakturaen så feil tall

## Fiks

Endret beregningsrekkefølgen i både `EnergileddDagSensor` og `EnergileddNattSensor`:

```python
# Før (feil)
energiledd_eks_avgifter = energiledd_dag - forbruksavgift - ENOVA_AVGIFT
if mva_sats > 0:
    energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)

# Etter (riktig)
energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
```

Fiksen fungerer korrekt for alle tre avgiftssoner:

- **Standard** (mva 25%): `0.4613 / 1.25 - 0.0713 - 0.01 = 0.2877` (matcher faktura)
- **Nord-Norge** (mva 0%): `verdi / 1.0 - avgifter` (ingen endring i praksis)
- **Tiltakssonen** (mva 0%, forbruksavgift 0%): `verdi / 1.0 - 0 - 0.01` (korrekt)

## Lærdom

### 1. Ikke bland inkl. mva og eks. mva i aritmetikk

Når du har en sum som er inkl. mva og skal trekke fra komponenter som er eks. mva, må du først konvertere til samme basis. Del på (1 + mva) først, deretter trekk fra.

### 2. Fakturaverifisering avdekker subtile feil

Denne feilen var usynlig i daglig bruk fordi den kun påvirket et diagnostikk-attributt. Den ble oppdaget fordi vi systematisk sammenlignet hvert tall på fakturaen med våre beregninger. Uten fakturaverifisering ville feilen levd videre.

### 3. Skriv tester som matcher den faktiske fakturaen

`test_reverse_energiledd_dag_eks_avgifter` og `test_reverse_energiledd_natt_eks_avgifter` i `tests/test_faktura_februar_2026.py` verifiserer nøyaktig denne beregningen mot fakturaens tall.
