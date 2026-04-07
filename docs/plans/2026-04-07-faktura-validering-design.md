# Design: Bedre faktura-validering

**Dato:** 2026-04-07
**Bakgrunn:** Etter validering av BKK-faktura mars 2026 mangler vi tre datapunkter for full fakturasammenligning.

## Endring 1: Norgespris-kompensasjon (kr)

BKK beregner Norgespris-kompensasjonen time for time: `(norgespris_fast - spotpris) × kWh`. Dette er den største posten på fakturaen (-1550.68 kr i mars) og vi har ingen måte å verifisere den på.

**Løsning:** Ny akkumulator `_monthly_norgespris_compensation` i coordinator.

- Beregning per oppdatering: `(NORGESPRIS_INKL_MVA - spotpris) × energy_kwh`
- Beregnes alltid, uavhengig av `har_norgespris` (spot-kunder kan sammenligne)
- Arkiveres til `_previous_month_norgespris_compensation` ved månedsskifte
- Persisteres i storage
- Eksponeres som `monthly_norgespris_compensation_kr` og `previous_month_norgespris_compensation_kr`

## Endring 2: Forrige måneds kapasitetsledd

Kapasitetstrinn og pris beregnes i dag on-the-fly i `ForrigeMaanedNettleieSensor` fra `previous_month_top_3`. Trinnet eksponeres ikke som eget datapunkt.

**Løsning:** Beregn kapasitetsledd ved månedsskifte i coordinator og lagre resultatet.

- Nye felter: `_previous_month_kapasitetsledd` (int, kr/mnd) og `_previous_month_kapasitetstrinn` (str, f.eks. "2-5 kW")
- Beregnes fra `_previous_month_top_3` ved månedsskifte (etter arkivering)
- Persisteres i storage
- `ForrigeMaanedNettleieSensor` bruker lagret verdi i stedet for å beregne selv

## Endring 3: Klokkeslett for maks effekt

Fakturaen viser "4.798 kW, 25.03 kl. 16:00". Vi lagrer dato og kW, men ikke timen.

**Løsning:** Utvid `_daily_max_power`-formatet.

- Gammelt format: `{"2026-03-25": 4.798}`
- Nytt format: `{"2026-03-25": {"kw": 4.798, "hour": 16}}`
- Migrasjon i `_load_stored_data`: float → `{"kw": float, "hour": null}`
- `_validate_daily_max_power` oppdateres for nytt format
- `_get_top_3_days()` returnerer det nye formatet
- Sensor-attributter utvides med `topp_1_time`, `topp_2_time`, `topp_3_time`

### Bakoverkompatibilitet

- Storage-migrasjon håndterer gammelt float-format transparent
- Sensorer som bruker `top_3` oppdateres til å lese `kw`-feltet
- `avg_top_3_kw`-beregning leser fra `kw`-nøkkelen

## Berørte filer

- `coordinator.py` — akkumulator, storage, migrasjon, månedsskifte
- `sensor.py` — eksponering av nye datapunkter, oppdatert top_3-lesing
- `tests/` — nye tester for alle tre endringer
