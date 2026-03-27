# Incident 002: Feil reverse-beregning av energiledd eks. avgifter

**Dato:** mars 2026
**Oppdaget under:** Fakturaverifisering februar 2026
**Status:** Fikset

## Symptomer

Attributtet `eks_avgifter_mva` pa EnergileddDagSensor og EnergileddNattSensor viste feil verdi sammenlignet med BKK-fakturaen.

| Sensor | Vart attributt | Faktura (eks. mva) | Avvik |
|---|---|---|---|
| Energiledd dag | 30.40 ore | 28.77 ore | +1.63 ore |
| Energiledd natt | 12.13 ore | 10.50 ore | +1.63 ore |

Feilen var konsistent: alltid +1.63 ore for hoy.

## Rotarsak

Reverse-beregningen blandet inkl. mva og eks. mva verdier i feil rekkefolge.

```python
# FEIL: Trekker fra eks. mva avgifter fra inkl. mva sum, deretter deler pa mva
energiledd_eks_avgifter = energiledd_dag - forbruksavgift - ENOVA_AVGIFT
energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)

# Tallene:
# (0.4613 - 0.0713 - 0.01) / 1.25 = 0.3040 (30.40 ore) <- FEIL
```

```python
# RIKTIG: Del pa mva forst, trekk fra avgifter etterpaa
energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT

# Tallene:
# 0.4613 / 1.25 - 0.0713 - 0.01 = 0.2877 (28.77 ore) <- RIKTIG
```

Feilen oppstod fordi `energiledd_dag` (fra tso.py) er inkl. mva, mens `FORBRUKSAVGIFT_ALMINNELIG` og `ENOVA_AVGIFT` er eks. mva. Nar man trekker eks. mva verdier fra en inkl. mva verdi og deretter deler pa (1 + mva), far man feil resultat.

Matematisk: `(a*1.25 - b) / 1.25 != a - b` (med mindre b = 0).

## Pavirkning

- **Kun diagnostikk-attributt**: Feilen pavirket KUN `extra_state_attributes["eks_avgifter_mva"]` pa to sensorer
- **Ingen pavirkning pa prisberegninger**: Totalpris, stromstotte, norgespris og alle andre sensorer bruker `energiledd_dag`/`energiledd_natt` direkte (inkl. alt), og er upavirkede
- **Ingen pavirkning pa Energy Dashboard**: Dashboard-sensoren bruker `total_price_inkl_avgifter` som beregnes korrekt
- **Pavirket fakturasammenligning**: Brukere som sammenlignet `eks_avgifter_mva` med fakturaen sa feil tall

## Fiks

Endret beregningsrekkefolgen i bade `EnergileddDagSensor` og `EnergileddNattSensor`:

```python
# For (feil)
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

Nar du har en sum som er inkl. mva og skal trekke fra komponenter som er eks. mva, ma du forst konvertere til samme basis. Del pa (1 + mva) forst, deretter trekk fra.

### 2. Fakturaverifisering avdekker subtile feil

Denne feilen var usynlig i daglig bruk fordi den kun pavirket et diagnostikk-attributt. Den ble oppdaget fordi vi systematisk sammenlignet hvert tall pa fakturaen med vare beregninger. Uten fakturaverifisering ville feilen levd videre.

### 3. Skriv tester som matcher den faktiske fakturaen

`test_reverse_energiledd_dag_eks_avgifter` og `test_reverse_energiledd_natt_eks_avgifter` i `tests/test_faktura_februar_2026.py` verifiserer noyaktig denne beregningen mot fakturaens tall.
