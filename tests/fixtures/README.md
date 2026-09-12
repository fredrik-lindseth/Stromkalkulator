# Test-fixturer for fakturaverifisering

Snapshot-data for å reverifisere BKK-fakturaer time for time selv om
integrasjonen slettes eller sensorer får nye entity-IDer i Home Assistant.

## Filer

### `bkk_<måned>_2026_hourly.json` og `bkk_desember_2025_hourly.json`

Time-for-time forbruk + spotpris + maks effekt, eksportert fra HA recorder.

| Fil                             | Periode             | Timer | Total kWh | Faktura  | Status                                 |
| ------------------------------- | ------------------- | ----- | --------- | -------- | -------------------------------------- |
| `bkk_desember_2025_hourly.json` | 01.12.25 - 01.01.26 | 744   | 1554,723  | 1554,721 | Gammel strømstøtte (ikke Norgespris)   |
| `bkk_januar_2026_hourly.json`   | 01.01.26 - 01.02.26 | 744   | 1936,106  | -        | Ingen faktura mottatt (overgangsmåned) |
| `bkk_februar_2026_hourly.json`  | 01.02.26 - 01.03.26 | 672   | 1673,783  | 1673,786 | Norgespris, verifisert                 |
| `bkk_mars_2026_hourly.json`     | 01.03.26 - 01.04.26 | 743   | 1553,224  | 1553,217 | Norgespris, verifisert                 |
| `bkk_april_2026_hourly.json`    | 01.04.26 - 01.05.26 | 720   | 1381,827  | 1381,827 | Norgespris, verifisert                 |
| `bkk_mai_2026_hourly.json`      | 01.05.26 - 01.06.26 | 744   | 1179,306  | 1179,303 | Norgespris, verifisert                 |
| `bkk_juni_2026_hourly.json`     | 01.06.26 - 01.07.26 | 720   | 1033,626  | 1033,628 | Norgespris, verifisert                 |

Februar har 28 dager (672 timer), mars 31 dager med DST-overgang 29.03 (kun
23 timer den dagen, total 743 timer i måneden).

Eksportert med `scripts/research/export_invoice_hourly.py` mot HA SQLite-DB.
Desember 2025 og første halvdel av januar 2026 kommer fra Tibber Pulse-sensor,
resten fra Pow-U HAN-modul (installert 30.01.26). Begge måler samme fysiske
meter, så akkumulerte kWh-verdier er kontinuerlige.

### `elhub_<måned>_<år>.json`

Intervallenergi per time, hentet rett fra Elhub-CSV-en. Dette er
fakturagrunnlaget BKK leser, og det er uavhengig av HAN-måleren: en måned der
HAN-leseren var nede har likevel full Elhub-dekning. Fasiten i
`tests/replay/fasit.py` måles mot disse.

| Fil | Timer | Sum kWh | Faktura total |
| --- | ---: | ---: | ---: |
| `elhub_februar_2026.json` | 672 | 1673,786 | 1673,786 |
| `elhub_mars_2026.json` | 743 | 1553,217 | 1553,217 |
| `elhub_april_2026.json` | 720 | 1381,827 | 1381,827 |
| `elhub_mai_2026.json` | 744 | 1179,303 | 1179,303 |
| `elhub_juni_2026.json` | 720 | 1033,628 | 1033,628 |
| `elhub_juli_2026.json` | 744 | 938,763 | 938,763 |

Bare `Fra` og `Volum` er med. Kundenavn, målepunkt-ID og
registreringstidspunkt blir liggende i den private CSV-en, på samme måte som
`bkk_*_hourly.json` ikke har navn eller fakturanummer.

August 2026 mangler, for Elhub-CSV-en er ikke lastet ned. Måneden er derfor
merket ufullstendig i `tests/test_replay_hendelser.py` og avstemmes ikke mot
faktura; HAN-fixturen mangler 176 av 744 timer og duger ikke som erstatning.

### `final_pris_<måned>_<år>.json`

Nord Pools publiserte Final-priser for NO5, en rad per time med de fire
kvarterprisene og timesnittet. Timesprisen er det uvektede snittet uten
mellomavrunding, altså A2 i [avregningskontrakten](../../docs/kontrakter/avregning.md).
Rader med `kilde: "fallback"` kommer fra EUR-fixturen ganget med
exchangeRate-arkivet og har `kvarter: null`; det gjelder 1. til 4. mai 2026,
som har falt ut av gratis-vinduet i NOK-arkivet.

Finnes for mai, juni, juli og august 2026. Lenger tilbake rekker ikke
prisarkivet, og `just snapshot-kurs` må kjøres månedlig for at det ikke skal
krympe videre.

### Regenerere elhub- og final_pris-fixturene

```bash
python3 scripts/research/lag_replay_fixtures.py
python3 scripts/research/lag_replay_fixtures.py --sjekk   # feiler ved drift
```

Krever de private arkivene i `_private/Måleverdier/`.

### `nordpool_eur_no5_2026.json`

Time-for-time Nord Pool day-ahead spotpris for NO5 (Bergen), råpris i EUR/MWh.

Hentet fra hvakosterstrommen.no sin offentlige API (speil av Nord Pool).
Direkte Nord Pool dataportal-API krever innlogging for data eldre enn ~30 dager,
så vi snapshot'er for å kunne reverifisere uten tilgang til den.

NOK-konvertering må gjøres med daglig NB-kurs fra `nb_eur_nok_2026.json`
(forward-fill for helger/helligdager). HKS sin egen NOK-konvertering bruker
en delayed/forward-filled versjon av NB-kurs som ikke matcher BKKs same-day-kurs,
derfor lagrer vi kun EUR-prisen herfra.

### `nb_eur_nok_2026.json`

Daglige EUR/NOK-kurser fra Norges Bank (ECB-konsertasjonskursen 14:15 CET).
Kun bankdager. For helger/helligdager må man forward-fill'e siste publiserte
kurs.

## Reverifiser en faktura uten internett

```bash
# Sjekk én måned mot BKK-faktura (krever forbruksdata i fixtures/)
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_februar_2026_hourly.json \
    --faktura februar_2026

# Verifiser at Norgespris-spotsnitt matcher faktura (krever Elhub-CSV i
# _private/Måleverdier/ eller egne kjente verdier i FAKTURA_*-konstantene).
# Scriptet foretrekker lokale snapshot-fixturer over API-kall.
python3 scripts/research/verify_norgespris_kurs.py
```

## Regenerere snapshotene

```bash
# Nord Pool EUR/MWh for hele 2026 så langt
python3 scripts/research/snapshot_nordpool_eur.py \
    --start 2026-01-01 --end 2026-05-22 \
    --area NO5 \
    --output tests/fixtures/nordpool_eur_no5_2026.json

# NB EUR/NOK for hele 2026 så langt
python3 scripts/research/snapshot_nb_eur_nok.py \
    --start 2026-01-01 --end 2026-05-22 \
    --output tests/fixtures/nb_eur_nok_2026.json

# Hourly forbruk fra HA-host (krever SSH-tilgang til kjørende HA-instans)
scp scripts/research/export_invoice_hourly.py ha-local:/tmp/export.py
ssh ha-local "python3 /tmp/export.py --year 2026 --month 3 --output /tmp/mars.json"
scp ha-local:/tmp/mars.json tests/fixtures/bkk_mars_2026_hourly.json
```

For måneder der Pow-U-sensorene ikke var aktive (før 30.01.26), bruk
fallback-kjede med Tibber Pulse-sensoren:

```bash
python3 /tmp/export.py --year 2026 --month 1 \
    --tpi-entity sensor.tibber_pulse_laegdesvingen_86_a_last_meter_consumption \
    --tpi-entity sensor.pow_u_ams_tpi \
    --p-entity sensor.tibber_pulse_laegdesvingen_86_a_power \
    --p-entity sensor.pow_u_ams_p \
    --output /tmp/januar.json
```

Senere `--tpi-entity` overskriver tidligere ved overlapp.

## Personvern

Time-for-time forbruk (timestamps + kWh + watt + EUR-spotpris) er ikke å regne
som personlig identifiserbar informasjon i en åpen-kildekode-kontekst.
Filene inneholder ikke navn, adresse, målepunkt-ID eller fakturanummer
(`fakturanr`-feltet er satt til tom streng eller eksempelnummer i fixturene
som blir committet).

Originale Elhub-CSV-eksporter ligger i `_private/Måleverdier/` (gitignored)
fordi de inneholder kundenavn og målepunkt-ID i metadata.
