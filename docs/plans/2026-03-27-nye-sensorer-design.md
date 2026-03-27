# Design: Margin til neste trinn, Norgespris-besparelse, Strømstøtte-tak

*Dato: 2026-03-27*

## Bakgrunn

Tre nye features identifisert fra gap-analyse mot [visjonen](../visjon.md):

1. Gi brukere verktøy til å reagere på kapasitetstrinn i sanntid
2. Akkumulert månedlig sammenligning mellom spot og Norgespris
3. Korrekt strømstøtte-beregning med 5000 kWh månedlig tak

## Feature 1: Margin til neste kapasitetstrinn

### Nye sensorer

**MarginNesteTrinnSensor** (enhet: kW)

- Viser kW igjen til neste trinngrense
- Beregning: `neste_trinn_grense - avg_power`
- Viser 0 hvis brukeren allerede er på høyeste trinn
- Extra state attributes:
  - `neste_trinn_pris` (kr/mnd)
  - `nåværende_trinn_pris` (kr/mnd)

**KapasitetVarselSensor** (binary sensor)

- `on` når margin < konfigurerbar terskel
- Default terskel: 2.0 kW
- Brukeren bygger automasjoner på denne (varsling, slå av lading, etc.)

### Konfigurasjon

Ny parameter i options flow: `kapasitet_varsel_terskel`

- Type: float
- Default: 2.0 kW
- Konfigurerbar etter oppsett

### Beregning i coordinator

```python
# Finn neste trinngrense
for threshold, price in kapasitetstrinn:
    if avg_power <= threshold:
        neste_grense = threshold
        neste_pris = price
        break

margin = neste_grense - avg_power
varsel = margin < terskel
```

## Feature 2: Akkumulert Norgespris-besparelse

### Ny sensor

**MaanedligNorgesprisDifferanseSensor** (enhet: kr)

- Akkumulert kr spart/tapt denne måneden vs alternativet
- Positiv = du sparer med nåværende avtale
- Negativ = du taper

### Beregning

Hver oppdatering (hvert minutt):

```python
forbruk_kwh = current_power_kw * elapsed_hours

if har_norgespris:
    # Bruker har Norgespris — sammenlign med spot+støtte
    min_pris = norgespris_total
    alternativ_pris = spot_total_etter_stotte
else:
    # Bruker har spot — sammenlign med Norgespris
    min_pris = spot_total_etter_stotte
    alternativ_pris = norgespris_total

differanse_kr = (alternativ_pris - min_pris) * forbruk_kwh
_monthly_norgespris_diff += differanse_kr
```

### Lagring

- Ny felt i coordinator: `_monthly_norgespris_diff: float`
- Lagres i `_store` sammen med resten
- Nullstilles ved månedsskifte

### Tilgjengelig for alle brukere

Både spot- og Norgespris-brukere ser sammenligningen.

## Feature 3: 5000 kWh strømstøtte-tak

### Endring i eksisterende beregning

Når `månedlig_total_forbruk >= 5000 kWh`:

- Strømstøtte settes til 0 for resten av måneden
- Påvirker alle strømstøtte-avhengige sensorer:
  - `StromstotteSensor`
  - `SpotprisEtterStotteSensor`
  - `TotalPrisEtterStotteSensor`
  - `TotalPrisInklAvgifterSensor`
  - `MaanedligStromstotteSensor`

### Ny sensor

**StromstotteForbrukGjenstaaendeSensor** (enhet: kWh)

- Viser gjenstående kWh av 5000-taket
- Beregning: `max(0, 5000 - månedlig_total_forbruk)`

### Diagnostikk

Extra state attribute på strømstøtte-sensoren: `tak_naadd: true/false`

### Konstant

Ny i `const.py`:

```python
STROMSTOTTE_MONTHLY_CAP_KWH = 5000
```

## Sensorer — oppsummert

| Sensor | Enhet | Device | Ny/endret |
| -------- | ------- | -------- | ----------- |
| MarginNesteTrinnSensor | kW | Nettleie | Ny |
| KapasitetVarselSensor | binary | Nettleie | Ny |
| MaanedligNorgesprisDifferanseSensor | kr | Månedlig | Ny |
| StromstotteForbrukGjenstaaendeSensor | kWh | Strømstøtte | Ny |
| StromstotteSensor | kr/kWh | Strømstøtte | Endret (tak) |
| SpotprisEtterStotteSensor | kr/kWh | Strømstøtte | Endret (tak) |
| TotalPrisEtterStotteSensor | kr/kWh | Strømstøtte | Endret (tak) |
| TotalPrisInklAvgifterSensor | kr/kWh | Strømstøtte | Endret (tak) |
| MaanedligStromstotteSensor | kr | Månedlig | Endret (tak) |
