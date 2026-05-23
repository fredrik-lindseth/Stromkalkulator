# Ikke-validerte scenarier: kodegjennomgang

Researchrapport. Ingen kodeendringer gjort. Referanser per 1.13.0 (commit
935f600). Linjenumre kan flytte seg.

Tre scenarier dokumentert i `docs/begrensninger.md §2`:

1. DST-overgang (mars/oktober)
2. Negative spotpriser
3. Norgespris-tak 5000 kWh/mnd

---

## 1. DST-overgang

### Hvor håndteres time-aggregering

- Time-bytting: `coordinator.py:516-536`. Sammenligner `now.hour` (lokal time
  via `dt_util.now()`) mot `self._current_hour`. Når de er ulike, lagrer
  forrige times energi i `_daily_max_power[prev_date]`.
- Dato-bytting: `coordinator.py:508,522-524`. Bruker `now.strftime("%Y-%m-%d")`.
- Måneds-bytting: `coordinator.py:702-704`. Bruker `now.strftime("%Y-%m")`.
- `dt_util.now()` returnerer aware lokal HA-tid (Europe/Oslo i drift).
- Energi-akkumulering: `coordinator.py:471-486`. Bruker
  `(now - self._last_update).total_seconds() / 3600`, deretter cappet til
  `MAX_ELAPSED_HOURS = 0.1` (6 min) i `const.py:310`.

### Sannsynlig adferd

`dt_util.now()` gir aware datetime. Subtraksjon mellom to aware datetimes gir
reell elapsed-tid uavhengig av DST. Riemann-summen er derfor korrekt.

- **Vår-DST (29. mars 2026, 23-timersdøgn):** Klokken hopper 02:00 til 03:00.
  Coordinator polles hvert minutt. Vanligvis er gapet 1 min, så det skjer
  ingenting spesielt. Hvis HA er nede over hoppet, blir gapet >6 min og
  cappes til 6 min av `MAX_ELAPSED_HOURS`. Ingen feilakkumulering.

  Hour-bytting: `self._current_hour` går fra 1 til 3 (timme 2 eksisterer
  ikke). Den manglende timen lagres aldri som maks-time fordi
  `_current_hour_energy` for "time 2" aldri akkumulerer. Korrekt — den timen
  eksisterer ikke. Forrige time (1) får sin energi lagret når polling kl 03:xx
  detekterer hour-bytte.

- **Høst-DST (25. oktober 2026, 25-timersdøgn):** Klokken hopper 03:00 til
  02:00. Timme 2 oppleves to ganger.

  `_current_hour` går fra 2 til 2 — ingen hour-bytte i `coordinator.py:518`.
  Resultat: energiakkumulering for "andre time 2" legges sammen med
  "første time 2" i `_current_hour_energy`. Når klokken endelig blir 3 (etter
  to passeringer av timme 2), arkiveres den summerte timen som maks.

  **Det er en bug, men en liten en.** En "25-timersdag" får én logisk time
  som er kunstig høyere fordi to fysiske timer (02:00-03:00 CEST + 02:00-03:00
  CET) legges sammen. Kan i ekstreme tilfeller løfte den dagen inn i topp-3
  feil. Konkret eksempel: noen som lader EV om natten kan få "natt-timen"
  doblet og dermed feil høyere snitt-topp i oktober.

### Identifiserte bugs

1. **Høst-DST: doblet time akkumuleres som én logisk time** (linje 516-536).
   `now.hour == self._current_hour` triggrer ikke hour-bytte. `fold` brukes
   aldri til å skille de to passeringene. Effekt: forhøyet topp-time
   i oktober for noen brukere. Konsekvens på kapasitetsledd: typisk
   ingen, fordi nettselskapet selv aggregerer per fysisk klokke-time.
2. **Naiv datetime som faller inn fra tester eller utenfra:** `_is_day_rate`
   bruker `now.hour`, fungerer for naiv tid. `_async_update_data` får alltid
   aware fra `dt_util.now()`. OK i produksjon. Tester må bruke aware tid hvis
   de skal etterligne reell DST-adferd. Eksisterende `test_dst_overgang.py`
   bruker delvis naiv tid (linje 97-103), men cap-en redder oss.
3. **Ingen bruk av `range(24)` for aggregering** — sjekket, ikke funnet i
   coordinator. Topp-3-utvelgelse er via sortert dict, ikke hardkodet.
4. **`days_in_month` ignorerer DST**: `coordinator.py:88-91` antar 24 timer
   per dag i `seconds_in_month = dim * 24 * 3600` (linje 684). I oktober
   blir reell sekunder-i-måneden 1 time lengre, i mars 1 time kortere.
   Effekt på `_monthly_accumulated_cost_kapasitetsledd`: under 0,15 % avvik
   per måned, smøres ut over hele måneden, marginal.

### Foreslåtte testscenarier

- 25. oktober 2026 02:00 → 02:30 → (DST-skifte) → 02:30 → 03:00 med aware
  datetime og `fold` 0/1. Verifiser at maks-time for 2026-10-25 ikke
  overstiger forventet kW.
- Polling-gap som krysser DST: før-hopp + etter-hopp med 90 minutter mellom.
  Verifiser at cap (6 min) forhindrer feilakkumulering.
- Måneds-rollover natt til 1. november (etter høst-DST i samme måned) —
  verifiser `_handle_month_rollover` skriver riktig forrige måned.

### Prioritering

**Akademisk → viktig.** Den dobbelte oktober-timen er en reell, identifiserbar
bug, men effekten på faktura er minimal (1 av ~720 timer i måneden).
Nettselskapet bruker fysisk timestempling, så det smitter ikke over i
faktisk kapasitetsledd. Sjekk en gang etter høst-DST 2026 mot ekte faktura.

---

## 2. Negative spotpriser

### Hvor håndteres det

- Spot-lesing: `coordinator.py:566-593`. Ingen `abs()`, ingen `max(0, ...)`.
  Negative tall passerer rett igjennom.
- Strømstøtte: `coordinator.py:435-448`. `spot_price > STROMSTOTTE_LEVEL`
  (0,9625) → returnerer 0 ved negativ spot. Korrekt: ingen strømstøtte når
  prisen allerede er under terskelen.
- Norgespris-kompensasjon: `coordinator.py:664`.
  `(norgespris - spot_price) * energy_kwh`. Ved negativ spot blir
  `(0,50 - (-0,30)) * kWh = 0,80 * kWh` — positiv kompensasjon, dvs.
  Norgespris-kunden "taper" 0,80 kr/kWh fordi spot ville vært bedre.
- `kroner_spart_per_kwh`: linje 656-660. Ved negativ spot for ikke-Norgespris-
  kunde: `alternativ_pris = norgespris = 0,50`, `total_price = spot - 0 +
  energiledd + fastledd ≈ -0,30 + 0,29 ≈ -0,01`. Differanse blir 0,51 kr/kWh
  (spotkunden sparer).

### Forventet adferd vs implementert

| Scenario                          | Forventet              | Implementert | Korrekt? |
| --------------------------------- | ---------------------- | ------------ | -------- |
| Strømstøtte ved spot < 0          | 0 kr/kWh               | 0 kr/kWh     | Ja       |
| Norgespris-komp ved spot < 0      | Negativ for kunden     | Positiv tap-verdi | Ja, fortegnet er konsistent med rest av kjeden |
| `spotpris_etter_stotte` ved spot < 0 | = spot (ingen støtte) | spot - 0 = spot | Ja  |
| `total_price` for spot-kunde ved spot < 0 | spot + energiledd + fastledd | Samme | Ja, kan bli negativ |

### Negative tall i koden

- `coordinator.py:469`: `current_power_kw = current_power_w / 1000`. Ingen
  abs. Eksport-sensoren leses separat (`coordinator.py:498-502`) med eksplisitt
  `if export_power_kw > 0`-guard.
- `coordinator.py:498`: `_read_sensor_float` har `clamp_max` men ikke
  `clamp_min`. Negativ effekt-sensor leverer negativ kW direkte. For
  plusskunder uten egen eksport-sensor kan dette bety at `current_power_kw`
  går negativ ved netto-eksport. `energy_kwh = current_power_kw * elapsed_hours`
  blir da negativ. Linje 487: `if energy_kwh > 0` filtrerer bort. Negativ
  energi telles ikke som forbruk, men telles heller ikke som eksport. Det
  kreves egen eksport-sensor for å fange opp.
- `coordinator.py:486`: `current_power_kw > 0` guard hindrer Riemann-bidrag
  ved netto-eksport. OK.

### Identifiserte bugs

1. **Ikke en bug, men dokumentasjons-gap:** Negativ Norgespris-kompensasjon-tall
   vises som "negativt = spot dyrere enn norgespris" i `sensor.py:1416`. Ved
   negativ spot vil sensoren vise STORE positive tall (kunden taper), som er
   konsistent med formelen. Bruker uten kontekst kan mistolke. Akademisk.
2. **`STROMSTOTTE_LEVEL`-sjekken er strikt `>`** (linje 446). Ved spot = 0,9625
   eksakt: ingen støtte. Konsistent med tests. OK.
3. **Negative spot + Norgespris-tak overskredet** (linje 627-628): faller
   tilbake til `spot_price + energiledd + fastledd_per_kwh`. Hvis spot er
   negativ kan total_price gå negativ. Korrekt — det reflekterer at strømmen
   bokstavelig talt subsidierer brukeren i den timen.

### Foreslåtte testscenarier

- Spot = -0,50, monthly_total = 1000 (under tak), `har_norgespris=False`.
  Verifiser `total_price < energiledd + fastledd` (spot trekker fra).
- Spot = -0,50, `har_norgespris=True`. Verifiser Norgespris-kompensasjon
  for den timen blir negativ for kunden (`(0,50 - (-0,50)) * kWh = +1,00 * kWh`).
- Sjekk at `_monthly_norgespris_compensation` i sum kan være negativ totalt
  over en måned med en blanding av negative og positive timer.

### Prioritering

**Akademisk.** Koden håndterer negative tall matematisk korrekt. Ingen
abs/max-bugs. Verifikasjon mot ekte faktura ville være fint men er ikke
påtrengende — Norge har sjeldent vedvarende negativ spot, og effekten på
total fakturasum er liten.

---

## 3. Norgespris-tak 5000 kWh/mnd

### Hvor håndteres det

- `coordinator.py:611-614`:
  ```
  norgespris_max = get_norgespris_max_kwh(self.boligtype)
  norgespris_over_tak = monthly_total_kwh >= norgespris_max
  ```
- `coordinator.py:615-624`: Hvis tak overskredet bruker `har_norgespris`-kunder
  spot-pris uten strømstøtte (Norgespris-kunder får ikke strømstøtte per
  forskrift).
- `coordinator.py:627-630`: Sammenligningsverdi `total_pris_norgespris` bytter
  fra norgespris til spot ved tak.
- `coordinator.py:674-681`: Akkumulert stat_cost bytter fra norgespris til
  spot ved tak.
- Helper: `const.py:136-146`, `get_norgespris_max_kwh`.

### Sannsynlig adferd

Implementeringen er **enkel og kronologisk** men har en subtilitet:

- `monthly_total_kwh` brukes som live-teller. Mens forbruket akkumulerer mot
  taket, brukes Norgespris. I det øyeblikket teller passerer 5000, bytter
  alle kommende timer i samme måned til spot. Dette **matcher forskriftens
  kronologiske telling**.
- Forrige måneds beregning bruker arkivert forbruk, så grensen treffer på
  samme måte historisk.

### Identifiserte bugs / mangler

1. **Ingen sub-time-allokering ved tak-overgang.** Hvis taket nås midt i en
   time, bruker hele timen den prisen som var aktiv da `_async_update_data`
   kjørte. Coordinator polles hvert minutt, så feilen er <1 minutts forbruk i
   feil prisbucket. Marginalt (under 0,1 kWh feil for typisk husholdning).
2. **Live-bytte mellom Norgespris og spot midt i måneden.** Når forbruket
   passerer 5000 kWh, vil `total_pris_norgespris`-sammenligningssensoren
   plutselig vise spot-pris i stedet for norgespris. Det er **riktig
   adferd**, men kan forvirre brukere som ikke vet om taket.
3. **`monthly_consumption_total_kwh` lekker ut til både strømstøtte- og
   Norgespris-grenser.** Begge bruker `>= 5000`. Bra konsistens.
4. **Edge case:** En spot-kunde (`har_norgespris=False`) som forbruker > 5000
   kWh treffer strømstøtte-taket samtidig. Strømstøtten blir 0 etter 5000.
   Konsistent med Forskrift § 5.
5. **`monthly_norgespris_compensation` regnes også over taket**
   (`coordinator.py:664`, betinget kun av `energy_kwh > 0 and spot_price_valid`).
   For en Norgespris-kunde som forbruker > 5000 kWh: timene over taket gir
   `(norgespris - spot) * kWh`-bidrag, men kunden betaler faktisk spot for de
   timene. Sammenligningssensoren overdriver "kompensasjonen" når man er over
   taket. **Reell bug.**

### Konkret feilkilde for storforbrukere

For en bruker som forbruker 6000 kWh/mnd:

- Timene 1-5000: Norgespris 0,50. Kompensasjon = (0,50 - spot) * kWh, vises
  som hvor mye man har spart.
- Timene 5001-6000: Bør betale spot. Men sensor-akkumulator blander begge
  buckets. Hvis spot snittet 1,50 over måneden, vises "kompensasjon" som
  6000 * (0,50 - 1,50) = -6000 kr, mens faktisk besparelse er
  5000 * (0,50 - 1,50) = -5000 kr (kunden taper kun for timene under tak).

Avvik for 6000-kWh-kunde i april 2026 (snitt-spot 1,30): ca 800 kr på
kompensasjons-sensoren, alt for høyt absolutt-tall. Brukeren ser ikke
direkte feil prising av strøm — `total_price` byttes korrekt — men
verifikasjonssensoren `monthly_norgespris_compensation_kr` skjevviser.

### Foreslåtte testscenarier

- `monthly_consumption = ConsumptionData(dag=4999, natt=0)`, `har_norgespris=True`,
  spot=1.20: verifiser total_price = norgespris + energiledd + fastledd.
- `monthly_consumption = ConsumptionData(dag=5001, natt=0)`, `har_norgespris=True`,
  spot=1.20: verifiser total_price = spot + energiledd + fastledd.
- Sekvens: kjør 6000 timers økning gjennom 5000-grensen, verifiser at
  `_monthly_norgespris_compensation` ikke akkumulerer feil etter taket.
- Fritidsbolig (1000 kWh-tak) verifisering med samme mønster.

### Prioritering

**Viktig.** Selve prisberegningen er korrekt. Verifikasjonssensoren
(`monthly_norgespris_compensation_kr`) er **feil over taket** for husholdninger
som forbruker >5000 kWh. Dette er en stor kategori (varmtvann + EV-lading
gir lett 6000-8000 kWh i vintermånedene). Fix: gate akkumulering på
`not norgespris_over_tak`, evt. estimat-allokering per time over/under tak.
