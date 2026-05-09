# Beregninger

Alle formler integrasjonen bruker. Avgiftsoppslag og sensoroversikt: [domain-rules.md](domain-rules.md), [SENSORS.md](SENSORS.md).

## Mva-konvensjon

Alle tall i formlene under er **inkl. mva** (i Sør-Norge), samme enhet som `STROMSTOTTE_LEVEL` og `NORGESPRIS_INKL_MVA_STANDARD`.

Spotpris fra HA-core nordpool-integrasjonen leveres eks. mva. Coordinator normaliserer til inkl. mva ved oppstart av hver beregningssyklus:

```python
mva_sats = get_mva_sats(avgiftssone)  # 0.25 i Sør-Norge, 0.0 nord/tiltakssone
if spotpris_inkl_mva:  # konfig-flagg, default False
    spot_price = sensor_value
else:
    spot_price = sensor_value * (1 + mva_sats)
```

For eksportinntekt (plusskunder) brukes `spot_price_eks_mva` siden privat selger ikke har utgående mva. Se [incident 004](incidents/004-spotpris-mva-feilbehandling.md).

## Nettleie

Nettleie = kapasitetsledd + energiledd.

### Kapasitetsledd

Snittet av maks timesforbruk på de tre dagene med høyest forbruk i måneden bestemmer trinn. Vi akkumulerer kWh per klokketime og tar høyeste fullførte time som dagens topp (samme metode som Elhub).

```
1. Akkumuler kWh per klokketime
2. Spor høyeste fullførte time per dag
3. Velg topp-3 dager
4. Snitt = sum / 3
5. Slå opp riktig trinn fra DSO-tabellen
```

Eksempel BKK: dager med 4.2, 3.8, 5.1 kW gir snitt 4.37 kW, trinn 2-5 kW = 250 kr/mnd.

Kapasitetsledd fordelt per kWh (brukt i Totalpris-sensoren):

```
fastledd_per_kwh = (kapasitetsledd / dager_i_måned) / 24
```

### Energiledd

- **Dag**: Man-fre 06:00-22:00 (ikke helligdager)
- **Natt/helg**: 22:00-06:00, helger, helligdager

Bevegelige helligdager (påske, pinse, Kristi himmelfartsdag) beregnes fra påskeformelen. Faste: 1. januar, 1. mai, 17. mai, 25.-26. desember.

DSO-spesifikt unntak: Glitre Nett, Tensio TN/TS har `helg_som_natt: False` (kun klokkeslett styrer dag/natt, helg/helligdag bryr seg ikke).

## Offentlige avgifter (2026)

DSO-en lagrer ren energiledd. Coordinator legger på forbruksavgift, Enova og mva basert på sone. Vises separat på sensoren "Offentlige avgifter".

| Sone         | Forbruksavgift | Enova    | Sum eks. mva | MVA | Sum inkl. mva |
| ------------ | -------------- | -------- | ------------ | --- | ------------- |
| Standard     | 7,13 øre       | 1,00 øre | 8,13 øre     | 25% | 10,16 øre/kWh |
| Nord-Norge   | 7,13 øre       | 1,00 øre | 8,13 øre     | 0%  | 8,13 øre/kWh  |
| Tiltakssonen | 0 øre          | 1,00 øre | 1,00 øre     | 0%  | 1,00 øre/kWh  |

Fra 2026: flat sats for forbruksavgift hele året, lik for Standard og Nord-Norge. Forskjellen er kun MVA.

```python
def get_forbruksavgift(avgiftssone: str) -> float:
    if avgiftssone == "tiltakssone":
        return 0.0
    return 0.0713

def get_mva_sats(avgiftssone: str) -> float:
    return 0.0 if avgiftssone in ("nord_norge", "tiltakssone") else 0.25
```

Kilde: [Skatteetaten](https://www.skatteetaten.no/satser/elektrisk-kraft/).

## Strømstøtte

```
strømstøtte = max(0, (spotpris - 0.9625) * 0.90)
```

Terskel 96,25 øre/kWh inkl. mva (2026, 77 øre eks. mva). Dekningsgrad 90%. Basert på spotpris fra Nord Pool, time for time.

kWh-tak avhengig av boligtype:

| Boligtype                  | Strømstøtte-tak |
| -------------------------- | --------------- |
| Bolig                      | 5000 kWh/mnd    |
| Fritidsbolig               | 0 (ingen rett)  |
| Fritidsbolig (fast bosted) | 5000 kWh/mnd    |

Over taket settes støtten til 0 resten av måneden. `stromstotte_gjenstaaende` viser hvor mye som er igjen.

Kilde: [Forskrift om strømstønad](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791).

### Eksempler

| Spotpris   | Strømstøtte | Pris etter støtte |
| ---------- | ----------- | ----------------- |
| 0.50 NOK   | 0.00 NOK    | 0.50 NOK          |
| 0.9625 NOK | 0.00 NOK    | 0.9625 NOK        |
| 1.00 NOK   | 0.03 NOK    | 0.97 NOK          |
| 1.50 NOK   | 0.48 NOK    | 1.02 NOK          |
| 2.00 NOK   | 0.93 NOK    | 1.07 NOK          |

Næring, fjernvarme og borettslag med fellesmåling støttes ikke.

## Norgespris

Fast pris fra nettselskapet, alternativ til spotpris. Kilde: [Regjeringens strømtiltak](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/).

| Område                  | Pris inkl. mva | MVA       |
| ----------------------- | -------------- | --------- |
| Sør-Norge               | 50 øre/kWh     | 25%       |
| Nord-Norge/Tiltakssonen | 40 øre/kWh     | 0%        |

Basispris eks. mva er 40 øre/kWh. Norgespris-kunder får ikke strømstøtte.

kWh-tak per måned: Bolig/Fast bosted = 5000, Fritidsbolig = 1000. Over taket betaler du spotpris resten av måneden.

```python
def get_norgespris(avgiftssone: str) -> float:
    return 0.40 if avgiftssone in ("nord_norge", "tiltakssone") else 0.50
```

## Total strømpris

```
# Uten støtte
totalpris = spotpris + energiledd + fastledd_per_kwh

# Med støtte
totalpris_etter_stotte = (spotpris - strømstøtte) + energiledd + fastledd_per_kwh

# Uten kapasitetsledd (variabel kWh-pris)
strompris_per_kwh = spotpris + energiledd
strompris_per_kwh_etter_stotte = (spotpris - strømstøtte) + energiledd
```

### Totalpris inkl. avgifter (Energy Dashboard prissensor)

`sensor.totalpris_inkl_avgifter` er prissensor for Energy Dashboard. Kapasitetsleddet fordeles per kWh, så månedstotalen blir [unøyaktig ved avvikende forbruk](../README.md#kapasitetsledd-i-energy-dashboard).

```
totalpris_inkl_avgifter = spotpris - støtte + energiledd + kapasitetsledd_per_kwh
                        + forbruksavgift_inkl_mva + enova_inkl_mva
```

### Akkumulert strømkostnad (anbefalt for Energy Dashboard)

`sensor.akkumulert_stromkostnad` akkumulerer kostnad med kapasitetsledd fordelt lineært over tid. Brukes som "Use an entity tracking total costs".

```
# Per oppdatering (hvert minutt):
strom_kostnad += energy_kwh * (spotpris - støtte)   # eller norgespris
energiledd_kostnad += energy_kwh * energiledd
kapasitetsledd_kostnad += elapsed_seconds * (kapasitetsledd / seconds_in_month)

akkumulert_kostnad = strom_kostnad + energiledd_kostnad + kapasitetsledd_kostnad
```

Kapasitetsleddet tikker uavhengig av forbruk, så månedstotalen treffer fakturaen.

## Strømselskap-pris

Hvis konfigurert (f.eks. Tibber):

```
electricity_company_total = strømselskap_pris + energiledd + fastledd_per_kwh
```

Strømselskap-prisen inkluderer typisk spotpris + påslag + evt. mva.

## Komplett eksempel (Sør-Norge)

Spotpris 1.20, energiledd dag 0.4613, kapasitetsledd 400 kr/mnd, 30 dager.

```
fastledd_per_kwh = (400 / 30) / 24 = 0.56 NOK/kWh
strømstøtte = (1.20 - 0.9625) * 0.90 = 0.21 NOK/kWh
totalpris uten støtte = 1.20 + 0.4613 + 0.56 = 2.22 NOK/kWh
totalpris med støtte = 0.99 + 0.4613 + 0.56 = 2.01 NOK/kWh
```

## Dagens kostnad

Akkumuleres gjennom dagen, nullstilles ved midnatt:

```python
daily_cost += (total_price_inkl_avgifter - støtte) * energy_kwh
```

## Estimert månedskostnad

Projiserer fra forbruket hittil. Kapasitetsledd er fast og legges til uten projisering:

```python
estimert_total = (variable_kostnad / day_of_month) * days_in_month + kapasitetsledd
```

Mer presist utover i måneden.

## Månedlig forbruk

Riemann-sum fra effektsensoren:

```python
elapsed_hours = (now - last_update).total_seconds() / 3600
energy_kwh = current_power_kw * elapsed_hours

if is_day_rate:
    monthly_consumption["dag"] += energy_kwh
else:
    monthly_consumption["natt"] += energy_kwh
```

Nullstilles automatisk ved månedsskifte.

### Månedlig kostnad

```python
nettleie_total = forbruk_dag * energiledd_dag + forbruk_natt * energiledd_natt + kapasitetsledd
avgifter = total_forbruk * (forbruksavgift_inkl_mva + enova_inkl_mva)
stromstotte = total_forbruk * gjennomsnitt_stromstotte_per_kwh
total = nettleie_total + avgifter - stromstotte
```

## Forrige måned

Ved månedsskifte kopieres `_monthly_consumption` og topp-3 til "forrige måned"-variabler, og nåværende måned nullstilles. Lagres til disk.

Kapasitetsledd og kapasitetstrinn beregnes ved månedsskifte og persisteres, slik at forrige måneds nettleie er stabil.

## Eksportinntekt (plusskunder)

Når brukeren har konfigurert eksport-effektsensor, akkumuleres inntekt fra solcellesalg. Privat selger har ikke utgående mva, så strømleverandøren betaler spotpris **eks. mva**:

```python
if export_energy_kwh > 0 and spot_price_valid:
    _monthly_export_revenue += spot_price_eks_mva * export_energy_kwh
```

`monthly_net_cost_kr = monthly_cost_kr - monthly_export_revenue_kr`. I Nord-Norge og tiltakssonen er `spot_price_eks_mva == spot_price` (mva = 0).

## Norgespris-kompensasjon

BKK og andre nettselskap krediterer time for time: `(norgespris_fast - spotpris) × kWh`. Vi akkumulerer det samme. Begge er inkl. mva i Sør-Norge:

```python
_monthly_norgespris_compensation += (NORGESPRIS_INKL_MVA - spot_price) * energy_kwh
```

Beregnes for alle (også spot-kunder), så sammenligning fungerer begge veier. Hopper over akkumulering hvis spotpris-sensor er ugyldig (mer enn 2 timer uten data), for å unngå falsk besparelse.

## Nøyaktighet

1-5% avvik fra faktura er normalt: integrasjonen bruker Riemann-sum fra effektsensor, fakturaen bruker måleren direkte. Strømstøtte kan avvike mer (faktura bruker time-for-time). Se [REFERANSE.md](fakturaer/REFERANSE.md) for verifiserte fakturaer.

## Datakilder

- Effektsensor (W): typisk fra AMS-leser via HAN
- Spotpris (NOK/kWh): Nord Pool "Current price"
- Strømselskap-sensor (valgfri): totalpris fra leverandør

Oppdateres hvert minutt. Topp-3 effektdager persisteres til disk.
