# Design: Strømpris per kWh (uten kapasitetsledd)

**Dato:** 2026-04-01
**Status:** Godkjent
**Bakgrunn:** Feature request — bruker ønsker totalpris per kWh uten estimert kapasitetsledd

## Problem

Alle eksisterende totalpris-sensorer inkluderer `kapasitetsledd_per_kwh` (månedlig kapasitetspris fordelt på timer). Dette er et estimat som ikke reflekterer den faktiske variable kWh-prisen. Brukere ønsker å se den "rene" kWh-prisen (strøm + nettleie) uten denne estimeringen.

## Løsning

To nye sensorer som viser faktisk variabel kWh-pris:

### Sensor 1: Strømpris per kWh (før støtte)

- **Nøkkel:** `strompris_per_kwh`
- **Device:** Nettleie
- **Enhet:** NOK/kWh
- **Formel:**
  - Standard: `spotpris + energiledd`
  - Norgespris: `norgespris + energiledd`
- **Attributter:** `spotpris`, `energiledd`

### Sensor 2: Strømpris per kWh (etter støtte)

- **Nøkkel:** `strompris_per_kwh_etter_stotte`
- **Device:** Strømstøtte
- **Enhet:** NOK/kWh
- **Formel:**
  - Standard: `(spotpris - strømstøtte) + energiledd`
  - Norgespris: `norgespris + energiledd` (ingen strømstøtte)
- **Attributter:** `spotpris`, `stromstotte`, `energiledd`

## Hva endres IKKE

Eksisterende sensorer beholdes som de er — de nye komplementerer, erstatter ikke.

## Filer som berøres

1. `coordinator.py` — beregn nye verdier
2. `sensor.py` — to nye sensor-klasser + registrering
3. `strings.json` — norske navn
4. `translations/en.json` — engelske navn
5. `translations/nb.json` — norske navn
6. `manifest.json` — versjonsbump til 1.4.0
7. `docs/SENSORS.md` — dokumenter nye sensorer
8. `docs/beregninger.md` — dokumenter formler
9. `tests/` — tester for nye beregninger og sensorer
