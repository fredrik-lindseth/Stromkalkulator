# Domene-regler

## Strømstøtte (2026)

```python
stromstotte = max(0, (spotpris - 0.9625) * 0.90)  # 90% over 96,25 øre
```

Terskel per år, kWh-tak og sonebevisst terskel: [beregninger.md](beregninger.md#strømstøtte) (kanonisk).

## Dag/natt-tariff

Kanonisk definisjon: [beregninger.md](beregninger.md#energiledd). Kort:

- Dag: man-fre 06:00-22:00 (ikke helligdager)
- Natt: 22:00-06:00, helger, helligdager

### Hvilke dager er helligdag?

Default-listen (`HELLIGDAGER_FASTE` i `const.py`) er offisielle norske helligdager etter helligdagsfredsloven § 2:

- 01-01 Nyttårsdag, 05-01 Arbeidernes dag, 05-17 Grunnlovsdag, 12-25 1. juledag, 12-26 2. juledag
- Bevegelige (skjærtorsdag, langfredag, 1./2. påskedag, Kristi himmelfartsdag, 1./2. pinsedag) beregnes fra påskeformelen.

Julaften (24.12) og nyttårsaften (31.12) er **ikke** offisielle helligdager etter loven, men flere nettselskaper behandler dem som lavtariff hele døgnet. Dette håndteres per DSO via `helligdager_ekstra` i `dso.py`:

```python
"bkk": {
    ...
    "helligdager_ekstra": ["12-24", "12-31"],
    ...
},
```

BKK er verifisert mot ekte fakturaer. Andre DSO-er starter uten `helligdager_ekstra` (alle desember-hverdager teller som dag) inntil faktura-data bekrefter at lavtariff er riktig. Se [bidra med faktura](fakturaer/bidra-med-faktura.md) hvis du har en faktura fra et annet prisområde og kan dokumentere hva som gjelder.

Glitre Nett, Tensio TN/TS og Stannum bruker `helg_som_natt: false`, der kun klokkeslett styrer dag/natt. Helger og helligdager teller som vanlige hverdager.

## Avgiftssoner

Mva-fritak er fylkesbasert (mval. § 6-6), ikke prisområdebasert. NO4 faller i sin helhet i fritaksfylkene, men NO3 dekker i hovedsak Trøndelag og Møre og Romsdal, som betaler 25% mva. Se [incident 003](incidents/003-no3-mva-feilklassifisering.md).

| Sone         | Fylker                                | Forbruksavgift | MVA |
| ------------ | -------------------------------------- | -------------- | --- |
| Sør-Norge    | Resten av landet (inkl. NO3-fylkene)  | 7,13 øre/kWh   | 25% |
| Nord-Norge   | Nordland, Troms                       | 7,13 øre/kWh   | 0%  |
| Tiltakssonen | Finnmark/Nord-Troms                    | 0 øre/kWh      | 0%  |

Default settes fra prisområde (NO4 → Nord-Norge, NO3 → Sør-Norge), med DSO-spesifikk `avgiftssone`-override for unntak (f.eks. Bindal Kraftnett i NO3 som ligger i Nordland). Kan overstyres i innstillinger.

## Endre satser

1. Finn offisiell kilde (lovdata.no, regjeringen.no, skatteetaten.no)
2. Verifiser mot fakturaer i `docs/fakturaer/`. Beregnet total bør stemme innenfor ±2%.
3. Dokumenter kilden i koden: `# Kilde: [URL] YYYY-MM-DD`

## Sensor-enheter og device_class

Skill mellom **satser** og **pengebeløp**. De behandles ulikt, og å blande dem koster brukerne statistikk.

| Type       | Eksempel                       | Enhet             | device_class | state_class   |
| ---------- | ------------------------------ | ----------------- | ------------ | ------------- |
| Sats       | Energiledd, totalpris          | `NOK/kWh`         | ingen        | `MEASUREMENT` |
| Sats       | Kapasitetstrinn                | `kr/mnd`          | ingen        | `MEASUREMENT` |
| Pengebeløp | Månedskostnad, differanse      | `NOK`             | `MONETARY`   | `TOTAL`       |

`MONETARY` skal ha ISO 4217-kode (`NOK`), ikke `kr`. Ikke fordi HA validerer det, for det gjør den ikke: `SensorDeviceClass.MONETARY` står ikke i `DEVICE_CLASS_UNITS`. Grunnen er frontenden, som i `compute_state_display.ts` formaterer `MONETARY`-sensorer med `Intl.NumberFormat` og `style: "currency"`. `currency: "kr"` er ikke en gyldig trebokstavskode, så kallet kaster og faller tilbake til rått tall uten valutaformatering.

**En sats uten `MONETARY` har ingenting å hente på ISO 4217.** Å døpe om `kr/mnd` til `NOK` gir null gevinst, mister `/mnd`, og koster en repair hos hver bruker. Det ble gjort med kapasitetstrinn i `0ccb02d` og rullet tilbake før det rakk ut i en release.

### Enhetsbytte er brytende

Endrer du enheten på en sensor med `state_class`, kan ikke HA konvertere lagret langtidsstatistikk. Hver berørt bruker får ett repair-varsel per sensor, med to valg: oppdatere enheten på historikken uten å konvertere, eller slette all historikk. Det første bevarer dataene når verdiene er uendret, som når `kr` blir `NOK`.

Sjekk før du bytter enhet:

- [ ] Har sensoren `state_class`? Uten den finnes ingen statistikk, og ingen repair.
- [ ] Er gevinsten reell, eller er det kosmetikk?
- [ ] Er byttet ført opp i release-noten med hvilket valg brukeren skal ta?

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
- [ ] Kjør `pipx run --with hypothesis pytest tests/ -v`
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
