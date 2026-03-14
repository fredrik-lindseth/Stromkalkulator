# Domene-regler — Strømkalkulator

## Viktige domene-regler

### Strømstøtte (2026)
```python
stromstotte = max(0, (spotpris - 0.9625) * 0.90)  # 90% over 96,25 øre
```

### Dag/natt-tariff
- **Dag**: Man-fre 06:00-22:00 (ikke helligdager)
- **Natt**: 22:00-06:00 + helger + helligdager

### Avgiftssoner
| Sone         | Forbruksavgift | MVA |
|--------------|----------------|-----|
| Standard     | 7,13 øre       | 25% |
| Nord-Norge   | 7,13 øre       | 0%  |
| Tiltakssonen | 0 øre          | 0%  |

## Fakta-sjekk

**Ved endringer i satser/avgifter:**
1. Finn offisiell kilde (lovdata.no, regjeringen.no, skatteetaten.no)
2. Lagre kopi i `docs/fakta/`
3. Verifiser mot fakturaer i `docs/fakturaer/`
4. Dokumenter kilden i koden

## Sjekklister

### Legge til ny sensor
- [ ] Definer sensor-klasse i `sensor.py`
- [ ] Legg til i `async_setup_entry()`
- [ ] Hent data fra `coordinator.data["key"]`
- [ ] Skriv test i `tests/test_*.py`
- [ ] Dokumenter i `docs/beregninger.md`

### Oppdatere satser (årlig ved nyttår)
- [ ] Finn offisiell kilde
- [ ] Oppdater `const.py` (avgifter, terskel)
- [ ] Oppdater `tso.py` (energiledd, kapasitetstrinn)
- Helligdager beregnes automatisk fra påskeformelen (ingen oppdatering nødvendig)
- [ ] Oppdater tester
- [ ] Verifiser mot faktura

### Oppdatere nettleiepriser
- [ ] Finn oppdaterte priser på nettselskapets nettside
- [ ] Oppdater `energiledd_dag`, `energiledd_natt`, `kapasitetstrinn` i `tso.py`
- [ ] Test at integrasjonen laster

### Fikse bug
- [ ] Reproduser bug
- [ ] Skriv test som feiler
- [ ] Fiks koden
- [ ] Verifiser at test passerer

## Offisielle kilder

| Tema           | Kilde                                                                                       |
|----------------|---------------------------------------------------------------------------------------------|
| Strømstøtte    | [lovdata.no](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)                      |
| Forbruksavgift | [skatteetaten.no](https://www.skatteetaten.no/satser/elektrisk-kraft/)                      |
| Norgespris     | [regjeringen.no](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) |
| Nettleiepriser | Nettselskapets egen nettside                                                                |
