# Test-strategi-vurdering

Status 2026-05-23, etter at 1.13.0 ble klar for release. 2057 passed, 25 skipped, 61.9 sek lokalt.
Coverage (line) totalt 86 %.

| Modul                       | Cover |
| --------------------------- | ----- |
| `coordinator.py`            | 99 %  |
| `const.py` / `dso.py`       | 100 % |
| `button.py` / diagnostics   | 100 % |
| `sensor.py`                 | 80 %  |
| `config_flow.py`            | 69 %  |
| `__init__.py`               | 50 %  |

## 1. Dekningsanalyse

Solid:

- `coordinator.py` har 99 % linjedekning og kjøres via parametriserte unit-
  tester, replay (`test_coordinator_replay.py`), Hypothesis-oracle og en
  8 760-timers brute-force (`test_property.py::test_exhaustive_every_hour_of_2026`).
- DSO-data: 49 nye tester for Lnett/Lede/Elvia + et generisk
  `test_dso_data_validation.py` over alle DSO-er. 25 skipped er deterministiske
  dimensjons-skips for DSO-er uten dag/natt-tariff (`flat sats`, linje 235)
  eller med custom-priser (linje 216, 230, 251). Beholdes som de er.
- Hver av de fire incident-ene har dedikerte regresjons-tester
  (`test_storage_key.py` for 001, `test_faktura_bkk.py:272-294` for 002,
  `test_config_flow.py:368` + `test_init_setup.py:150` for 003,
  `test_spotpris_mva.py` for 004).

Svakt:

- **`__init__.py` 50 % — `async_migrate_entry` (v1→v2→v3) har ingen ekte
  tester.** Linje 96-155 treffes aldri. Eneste test som rører `entry.version`
  er `test_diagnostics.py:46`, og den bare leser feltet. Migrering kjører
  på alle brukere ved oppgradering, ufanget exception stopper oppstart kald.
  Største enkeltgap i suiten.
- `config_flow.py` 69 %: linje 78-84, 122/124, 135-149, 191-197, 235-241,
  252. Options-flow og energiledd-overstyring. Vanskelig uten
  `pytest-homeassistant-custom-component` — avveining er rimelig.
- `sensor.py` 80 %: 201 missed lines, mest `extra_state_attributes`-
  branches og None-fallbacks. Lavere risiko.
- **Bare 3 av 6 BKK-fakturaer har asserts.** `docs/fakturaer/` har okt/nov/
  des 2025 + feb/mars/april 2026. Bare feb/mars/april kodet inn som
  `FAKTURA_*`-dicts i `test_faktura_bkk.py:31-110`. Fixturene
  `bkk_januar_2026_hourly.json` og `bkk_desember_2025_hourly.json` ligger
  på disk uten testkobling. Vinter-måneder er der bias-bugs i
  Norgespris-kompensasjon ville være synligst — vi mister halvparten av
  vår beste oracle.

Faktura-replayet er "the test that matters" for nettleie. Det fanget
Norgespris-fortegnsbugen (`test_coordinator_replay.py:7-11`). Men dekker
bare BKK Sør-Norge med husholdning. Ingen end-to-end-replay for
Lnett/Lede/Elvia.

## 2. Test-arkitektur

Type-miks er bevisst og fornuftig: unit (de fleste), integration via
coordinator-replay, property via Hypothesis (`HEAVY = 10 000 examples`,
`test_property.py:172`), exhaustive (8 760-timers brute-force), differential
(to uavhengige implementasjoner mot hverandre).

Sterkt:

- Hypothesis-testene går mot **ekte** coordinator-metoder (cached instans i
  `_bkk_coordinator()`, linje 138-146) i stedet for å speile produksjonskoden
  i test-fil. Det er en bevisst korreksjon etter at en tidligere variant var
  en false-positive (se commit `98cd37a` og `test_coordinator_replay.py:7-11`).
- `conftest.py` mocker HA én gang sentralt og eksponerer 6 sentrale helpers
  (`_make_state`, `_make_entry`, `_make_hass`, `_run_update`, `coord_module`,
  `bkk_kapasitetstrinn`). Få test-filer reimplementerer dette.

Svakt / risiko:

- `test_property.py` bruker en **modul-lokal cached coordinator**
  (`_BKK_COORDINATOR_CACHE`, linje 138) som overlever på tvers av Hypothesis-
  eksempler for ytelse. Topp-3-testene muterer `_daily_max_power`
  (linje 122-124). I praksis OK fordi alle setter før de leser, men fragilt.
- Topp 15 slowest er Hypothesis (4 sek per test). ~40 av 62 sek kommer fra
  `test_property.py`. Der ville parallellisering hatt størst effekt.
- Hypothesis er begrenset til fire områder (kapasitetstrinn, topp-3-avg,
  dag/natt, strømstøtte). Underutnyttet for `_compute_energy_delta` (Riemann/
  tpi), spotpris-MVA-normalisering, Norgespris-tak-bytting og månedsskifte.
- Ingen snapshot-tester. Det er greit — faktura-replay er bedre oracle enn
  syrupy ville vært.

## 3. Test-data-strategi

Avhengighet av spesifikke fakturaer er tydelig men disiplinert. Tre
`FAKTURA_*`-dicts er hard-kodet i `test_faktura_bkk.py`, fixturene er
i JSON-form (`tests/fixtures/bkk_*_hourly.json`). Hourly-fixturene
(70-78 kB hver) er hentet fra ekte Elhub/HAN-broadcast, ikke håndskrevet.

Edge-data som mangler:

- **DST-overgang oktober 2026 i replay.** `test_dst_overgang.py` har gode
  `_is_day_rate`-unit-tester, men ingen full-måneds-replay over høst-DST.
  Bug 1 i `ikke-validerte-scenarier.md:57-66` (doblet time akkumuleres som
  én logisk time) er ikke fanget. `test_dst_overgang.py:116-130` tester at
  samme klokketid to ganger ikke dobbelttellet **energi** (Riemann-cap redder
  oss), men ikke at timen havner i `_daily_max_power` med for høy verdi.
- **Negative spotpriser.** Ingen integration-test for en hel måned med
  blandet positiv/negativ spot. Scenariene i
  `ikke-validerte-scenarier.md:151-159` er ikke implementert.
- **Tak-overgang + månedsskifte i samme test.** 6 000-kWh-kunde krysser
  5 000-taket 23:55 siste dag, månedsskifte 00:00. Vi har separate tester
  (`test_norgespris_compensation_tak.py`, `test_coordinator_update.py:510`),
  ikke kombinasjon.
- **Spot-sensor vedvarende nedetid.** `test_coordinator_robustness.py::
  TestSpotprisCaching:24` dekker TTL og caching, ikke 2+ timer der
  `spot_price_valid = False` slår inn på alle akkumulatorer. Incident 004
  sin etterspill (falsk Norgespris-besparelse ved manglende spot) ble fikset,
  men ingen test verifiserer at `_monthly_norgespris_diff` ikke korrumperes.
- **Andre DSO-er enn BKK i full replay.** Ingen replay for Lnett/Lede/Elvia.
  Bevisst fordi vi mangler deres ekte data, men kan syntetiseres.

## 4. Regresjons-strategi

Fire dokumenterte incidents (001-004). Alle har dedikerte tester:

| Incident                         | Regresjons-test                                       |
| -------------------------------- | ----------------------------------------------------- |
| 001: delt storage mellom entries | `test_storage_key.py` (4 tester, helt målrettet)      |
| 002: reverse energiledd          | `test_faktura_bkk.py:272-294`                         |
| 003: NO3 mva-feilklassifisering  | `test_config_flow.py:368-401`, `test_init_setup.py:150` |
| 004: spot eks/inkl mva           | `test_spotpris_mva.py` (9 tester)                     |

Solid mønster. Alle er ekte verifisering, ingen rene "denne bugen kom ikke
tilbake"-attrapper.

Neste bugs sannsynligvis:

- **v3→v4-migrering** når den kommer — vi har ingen mal.
- **DSO-fusjon** (`_MIGRATION_INDEX`, `__init__.py:41`) er ikke testet
  end-to-end. Hvis et nytt par fusjonerer og vi legger inn `DSOFusjon`,
  har vi ingen test som verifiserer at `_migrate_storage_file` faktisk
  flytter filen. Kun storage-key-migrering
  (`test_persistens.py::TestMigrationFromDSOStorage`) er dekket.

## 5. CI og kjøring

62 sek lokalt, deterministisk på to back-to-back-runs. Ingen flakiness.

CI (`.github/workflows/ci.yml`) er minimal:

- `pytest-cov` installeres i CI, ikke i lokalt venv. Legg i
  `[project.optional-dependencies].dev`.
- Ingen parallellisering. `pytest-xdist` ville kutte 62 sek til ~25 sek
  (Hypothesis dominerer og er trivielt parallelliserbart).
- `mypy ... || true` maskerer typefeil. Lav prioritet uten hard gating.

## 6. Top 10 anbefalinger

1. **Migration-tester for `async_migrate_entry`.** Type: unit. Skriv 6 tester
   (v1→v2 med energiledd-overstyring, v1→v2 uten, v1→v2 med korrupt verdi,
   v2→v3 standard-sone (issue triggres), v2→v3 nord-norge (ingen issue),
   v3→v3 no-op). Det er en hel fil (`tests/test_migration.py`). Risiko:
   migrering kjører på alle eksisterende brukere ved oppgradering, og en
   ufanget exception der stopper integrasjonen kald. **Største enkeltgap i
   suiten.** Kompleksitet: lav.

2. **Aktiver januar 2026 og desember 2025 som FAKTURA_*-dicts.** Type:
   integration (replay). Fixturene finnes allerede. Skriv to nye dicts i
   `test_faktura_bkk.py` og legg dem i `FAKTURA_MAP` i
   `test_coordinator_replay.py:34`. Forventet feilfangst: bias-bugs i
   høyforbruks-måneder (vinter), DST-overgang i mars/oktober når oktober-
   faktura kommer. Kompleksitet: lav, ~30 min hvis fakturaen er digitalisert
   i `docs/fakturaer/bkk-desember-2025.md`.

3. **Full-måneds-replay som krysser høst-DST.** Type: integration.
   Bygg en syntetisk hourly-fixture for oktober 2026 (25 timer 25. oktober)
   og verifiser at `_daily_max_power["2026-10-25"]` ikke får dobbelttellet
   timen. Direkte adressering av bug 1 i
   `ikke-validerte-scenarier.md:57`. Kompleksitet: middels (krever syntetisk
   data + en bevisst design-avgjørelse på om `fold` skal håndteres).

4. **Hypothesis på `_compute_energy_delta`/Riemann.** Type: property. Genere
   tilfeldige polling-sekvenser (tidsstempel + power_w) og verifiser at
   akkumulert kWh aldri overstiger `MAX_ELAPSED_HOURS * max_power` per
   syklus. Forventet feilfangst: regression når noen endrer clamping eller
   håndtering av negative deltas. Kompleksitet: middels.

5. **Negative spot-priser end-to-end.** Type: integration. Skriv en replay
   med konstruert hourly-fixture der 50 timer har spot < 0. Verifiser at
   `_monthly_norgespris_diff` kan bli negativ i sum, at `_monthly_cost`
   ikke går negativt for spot-kunde uten Norgespris, at
   `_monthly_accumulated_cost_strom` håndterer det. Kompleksitet: lav-
   middels.

6. **Spot-sensor-nedetid > 2 timer.** Type: integration. Sekvens: 60 polls
   med valid spot → 120 polls med `unavailable` → 60 polls med valid spot.
   Verifiser at `_monthly_norgespris_diff` og `_monthly_accumulated_cost_strom`
   ikke akkumulerer noe i down-perioden, men at energiledd og Norgespris-
   under-tak fortsatt akkumulerer. Adresserer eksplisitt incident 004 sin
   etterspill. Kompleksitet: middels.

7. **DSO-fusjon end-to-end-test.** Type: integration. Lag en syntetisk
   `DSOFusjon`-entry, bygg storage-fil for "gammel" DSO, kjør
   `async_setup_entry`, verifiser at storage-filen er flyttet og at
   coordinator leser fra ny nøkkel. Kompleksitet: middels (krever litt
   filesystem-mocking).

8. **Coverage-gate i CI på `coordinator.py`/`const.py`.** Type: tooling.
   Krev 95 % linjedekning på `coordinator.py` (vi har 99 % nå) og 100 % på
   `const.py`. Ikke gate på `sensor.py` (80 %) eller `config_flow.py`
   (69 %) før vi har en plan for å gate-løfte dem. Codecov-action er
   allerede satt opp men ingen treshold. Kompleksitet: lav.

9. **pytest-xdist for utviklerflyt.** Type: tooling. Legg
   `pytest-xdist` i dev-deps og default-flagg `-n auto` i `addopts`.
   Hypothesis er trygt parallelliserbart, og 62 sek → ~25 sek senker
   barrieren for "kjør hele suiten før commit" markant. Kompleksitet:
   lav. Sjekk at `coord_module`-fixturen ikke deler state mellom workers
   (den reloader modulen per test, så bør være OK).

10. **Norgespris-tak + månedsskifte-kombinasjon.** Type: integration. Storforbruker
    krysser 5 000-taket klokken 23:55 siste dag i måneden, månedsskifte trigges
    kl 00:00. Verifiser at `_previous_month_norgespris_compensation` og
    `_previous_month_consumption_total_kwh` arkiveres korrekt, og at den nye
    måneden starter på `norgespris_over_tak = False`. To tester i en ny
    `test_tak_og_maned_kombo.py`. Kompleksitet: lav-middels.

## Kritisk flagg

`async_migrate_entry` har null tester. Det er én funksjon som kjører på
hver eneste oppgraderings-installasjon. Hvis vi shipper 1.14.0 med en
v3→v4-migrering, eller bare endrer eksisterende v1/v2-stier ved et uhell,
har vi ingen sikkerhetsnett. Anbefaling 1 over er P0.
