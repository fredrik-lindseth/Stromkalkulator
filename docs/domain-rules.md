# Domene-regler

## Strømstøtte (2026)

```python
stromstotte = max(0, (spotpris - 0.9625) * 0.90)  # 90% over 96,25 øre
```

## Dag/natt-tariff

- Dag: man-fre 06:00-22:00 (ikke helligdager)
- Natt: 22:00-06:00, helger, helligdager

## Avgiftssoner

| Sone         | Strømsoner          | Forbruksavgift | MVA |
| ------------ | ------------------- | -------------- | --- |
| Sør-Norge    | NO1, NO2, NO5       | 7,13 øre/kWh   | 25% |
| Nord-Norge   | NO3, NO4            | 7,13 øre/kWh   | 0%  |
| Tiltakssonen | Finnmark/Nord-Troms | 0 øre/kWh      | 0%  |

Settes automatisk fra nettselskap. Kan overstyres i innstillinger.

## Endre satser

1. Finn offisiell kilde (lovdata.no, regjeringen.no, skatteetaten.no)
2. Verifiser mot fakturaer i `docs/fakturaer/`. Beregnet total bør stemme innenfor ±2%.
3. Dokumenter kilden i koden: `# Kilde: [URL] YYYY-MM-DD`

## Sjekklister

### Legge til ny sensor

- [ ] Sensor-klasse i `sensor.py`
- [ ] Registrer i `async_setup_entry()`
- [ ] Hent data fra `coordinator.data["key"]`
- [ ] Test i `tests/`
- [ ] Dokumenter i `docs/beregninger.md`

### Oppdatere satser (årlig ved nyttår)

- [ ] Finn offisiell kilde
- [ ] Oppdater `const.py` (avgifter, terskel) og `dso.py` (energiledd, kapasitetstrinn)
- [ ] Kjør `pipx run pytest tests/ -v`
- [ ] Verifiser mot faktura

Helligdager beregnes fra påskeformelen, ingen oppdatering nødvendig.

### Fikse bug

- [ ] Reproduser
- [ ] Skriv test som feiler
- [ ] Fiks
- [ ] Test passerer

## Offisielle kilder

| Tema           | Kilde                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------- |
| Strømstøtte    | [lovdata.no](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)                      |
| Forbruksavgift | [skatteetaten.no](https://www.skatteetaten.no/satser/elektrisk-kraft/)                      |
| Norgespris     | [regjeringen.no](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) |
| Nettleiepriser | Nettselskapets egen nettside                                                                |
