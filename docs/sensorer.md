# Sensorer

6 devices, 53 sensorer totalt (35 aktive som standard).

| Device           | Aktive | Totalt |
| ---------------- | ------ | ------ |
| Nettleie         | 11     | 19     |
| Strømstøtte      | 6      | 7      |
| Norgespris       | 4      | 4      |
| Månedlig forbruk | 8      | 12     |
| Forrige måned    | 6      | 6      |
| Eksport          | 0      | 5      |

Aktivere flere: **Settings > Devices > Strømkalkulator > (device) > Entities**, slå på "Enabled". Coordinator beregner uansett, sensorer er bare visning.

Sensorer merket _(valgfri)_ er deaktivert som standard.

---

## Nettleie

Hoveddevicen, navngis "Nettleie ({nettselskap})".

### Energiledd

| Sensor     | Enhet  | Beskrivelse                                                |
| ---------- | ------ | ---------------------------------------------------------- |
| Energiledd | kr/kWh | Det du betaler per kWh nå (bytter mellom dag- og nattsats) |
| Tariff     | -      | "dag" eller "natt" (styrer utility_meter)                  |

Dag: man-fre 06-22 (ikke helligdager). Natt: 22-06, helger, helligdager.

### Kapasitet

| Sensor                                  | Enhet  | Beskrivelse                                                 |
| --------------------------------------- | ------ | ----------------------------------------------------------- |
| Kapasitetstrinn                         | kr/mnd | Fast månedskostnad basert på snitt av topp-3 effektdager    |
| Snitt toppforbruk                       | kW     | Snitt av topp-3, bestemmer trinnet                          |
| Toppforbruk #1, #2, #3                  | kW     | De tre høyeste effektdagene denne måneden                   |
| Margin til neste trinn                  | kW     | Hvor mye mer du kan bruke før neste (dyrere) trinn          |
| Kapasitetsvarsel                        | -      | "on" når margin er under terskelen, til varsling/automasjon |
| _(valgfri)_ Kapasitetstrinn (nummer)    | -      | Trinnet du er på (1, 2, 3, ...)                             |
| _(valgfri)_ Kapasitetstrinn (intervall) | -      | kW-intervallet for ditt trinn (f.eks. "2-5 kW")             |

**Toppforbruk #1-3** har attributter `dato` (YYYY-MM-DD) og `time` (0-23).

### Strømpris

| Sensor                                    | Enhet  | Beskrivelse                                      |
| ----------------------------------------- | ------ | ------------------------------------------------ |
| Total strømpris (før støtte)              | kr/kWh | Spotpris + nettleie, før strømstøtte trekkes fra |
| Strømpris per kWh                         | kr/kWh | Spotpris + energiledd, uten kapasitetsledd       |
| _(valgfri)_ Total strømpris (strømavtale) | kr/kWh | Med strømselskapets pris i stedet for spotpris   |

### Diagnostikk (avgifter)

| Sensor                           | Enhet  | Beskrivelse                               |
| -------------------------------- | ------ | ----------------------------------------- |
| _(valgfri)_ Energiledd dag       | kr/kWh | Dagsats inkl. alle avgifter og mva        |
| _(valgfri)_ Energiledd natt/helg | kr/kWh | Natt/helg-sats inkl. alle avgifter og mva |
| _(valgfri)_ Offentlige avgifter  | kr/kWh | Forbruksavgift + Enova inkl. mva          |
| _(valgfri)_ Forbruksavgift       | kr/kWh | Elavgift inkl. mva                        |
| _(valgfri)_ Enovaavgift          | kr/kWh | Enova-avgift inkl. mva                    |

---

## Strømstøtte

| Sensor                                       | Enhet  | Beskrivelse                                                                                                                                                             |
| -------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strømstøtte                                  | kr/kWh | Statens støtte per kWh når spotpris > 96,25 øre (90% av overskytende)                                                                                                   |
| Spotpris etter støtte                        | kr/kWh | Spotpris minus strømstøtte                                                                                                                                              |
| Total strømpris etter støtte                 | kr/kWh | Reell totalpris: spotpris + nettleie - støtte                                                                                                                           |
| Totalpris inkl. avgifter                     | kr/kWh | Prissensor for Energy Dashboard. Kapasitetsledd fordelt per kWh (unøyaktig ved avvikende forbruk). For korrekt total: bruk [Akkumulert strømkostnad](#energy-dashboard) |
| Strømstøtte aktiv nå                         | -      | "Ja"/"Nei" om spotpris er over terskel                                                                                                                                  |
| Strømstøtte gjenstående kWh                  | kWh    | Hvor mye av månedens støtte-tak som er igjen (bolig=5000, fritidsbolig=0)                                                                                               |
| _(valgfri)_ Strømpris per kWh (etter støtte) | kr/kWh | Som "Strømpris per kWh", men med støtte trukket fra                                                                                                                     |

---

## Norgespris

| Sensor                                | Enhet  | Beskrivelse                                                       |
| ------------------------------------- | ------ | ----------------------------------------------------------------- |
| Total strømpris (norgespris)          | kr/kWh | Hva du ville betalt med Norgespris: fast 50 øre + nettleie        |
| Strømpris (Norgespris-ordningen)      | kr/kWh | Ren strømdel: fast 50 øre under tak, spotpris over tak            |
| Prisforskjell (norgespris)            | kr/kWh | Positiv = du betaler mer enn Norgespris (Norgespris er billigere) |
| Norgespris aktiv nå                   | -      | "Ja"/"Nei" om du har valgt Norgespris                             |

kWh-tak: bolig=5000, fritidsbolig=1000. Over taket betaler du spotpris.

---

## Månedlig forbruk

Nullstilles automatisk ved månedsskifte.

### Forbruk

| Sensor                     | Enhet | Beskrivelse                               |
| -------------------------- | ----- | ----------------------------------------- |
| Månedlig forbruk dagtariff | kWh   | Forbruk på dagtariff denne måneden        |
| Månedlig forbruk natt/helg | kWh   | Forbruk på natt/helg-tariff denne måneden |
| Månedlig forbruk totalt    | kWh   | Sum av dag og natt                        |

Attributter på "Månedlig forbruk totalt": `dag_kwh`, `natt_kwh`, `dag_pct`, `natt_pct`.

### Kostnader

| Sensor                              | Enhet | Beskrivelse                                             |
| ----------------------------------- | ----- | ------------------------------------------------------- |
| Månedlig nettleie total             | kr    | Bunnlinjen: nettleie + avgifter - støtte                |
| Dagens kostnad                      | kr    | Akkumulert kostnad siden midnatt                        |
| Estimert månedskostnad              | kr    | Prognose for hele måneden, basert på forbruket hittil   |
| Norgespris besparelse               | kr    | Akkumulert besparelse/tap vs alternativ avtale          |
| Norgespris-kompensasjon             | kr    | Akkumulert (norgespris - spotpris) × kWh denne måneden  |
| _(valgfri)_ Månedlig nettleie       | kr    | Nettleie hittil: energiledd dag + natt + kapasitetsledd |
| _(valgfri)_ Månedlig avgifter       | kr    | Forbruksavgift + Enova inkl. mva                        |
| _(valgfri)_ Månedlig strømstøtte    | kr    | Estimert støtte denne måneden                           |
| _(valgfri)_ Akkumulert strømkostnad | kr    | For Energy Dashboard med korrekte månedstotaler         |

Attributter på "Akkumulert strømkostnad": `strompris_kr`, `energiledd_kr`, `kapasitetsledd_kr`, `total_kwh`.

Attributter på "Månedlig nettleie total": `nettleie_kr`, `stromstotte_kr`, `forbruk_dag_kwh`, `forbruk_natt_kwh`, `forbruk_total_kwh`, `vektet_snittpris_kr_per_kwh`.

---

## Forrige måned

Lagres ved månedsskifte. Brukes til faktura-verifisering.

| Sensor                                | Enhet | Beskrivelse                               |
| ------------------------------------- | ----- | ----------------------------------------- |
| Forrige måned forbruk dagtariff       | kWh   | Dag-forbruk forrige måned                 |
| Forrige måned forbruk natt/helg       | kWh   | Natt/helg-forbruk forrige måned           |
| Forrige måned forbruk totalt          | kWh   | Totalt forbruk forrige måned              |
| Forrige måned nettleie                | kr    | Sammenlign med fakturaen                  |
| Forrige måned toppforbruk             | kW    | Snitt av topp-3, bestemte kapasitetstrinn |
| Forrige måned Norgespris-kompensasjon | kr    | Norgespris-kompensasjon for forrige måned |

Alle har `maaned`-attributt (f.eks. "januar 2026").

**Nettleie-sensoren** har også: `energiledd_dag_kr`, `energiledd_natt_kr`, `kapasitetsledd_kr`, `snitt_topp_3_kw`, `norgespris_differanse_kr`.

**Toppforbruk-sensoren** har: `maaned`, `topp_1_dato`, `topp_1_kw`, `topp_1_time`, `topp_2_dato`, `topp_2_kw`, `topp_2_time`, `topp_3_dato`, `topp_3_kw`, `topp_3_time`.

---

## Eksport (solceller)

For plusskunder. Krever konfigurert eksport-effektsensor. Alle deaktivert som standard.

| Sensor                                    | Enhet | Beskrivelse                          |
| ----------------------------------------- | ----- | ------------------------------------ |
| _(valgfri)_ Månedlig eksport kWh          | kWh   | Eksportert energi denne måneden      |
| _(valgfri)_ Månedlig eksport inntekt      | kr    | Inntekt (spotpris × kWh)             |
| _(valgfri)_ Månedlig nettokostnad         | kr    | Forbrukskostnad minus eksportinntekt |
| _(valgfri)_ Forrige måned eksport kWh     | kWh   | Eksportert energi forrige måned      |
| _(valgfri)_ Forrige måned eksport inntekt | kr    | Eksportinntekt forrige måned         |

---

## Energy Dashboard

To alternativer for kostnadsdelen.

### Alternativ 1: Prissensor

Bruk `Totalpris inkl. avgifter`. Enklest, men kapasitetsleddet blir feil ved avvikende forbruk.

1. **Settings > Dashboards > Energy > Add consumption**
2. Velg din kWh-sensor under "Consumed energy"
3. Slå på "Use an entity with current price"
4. Velg `Totalpris inkl. avgifter`

### Alternativ 2: Akkumulert kostnad (anbefalt)

Bruk `Akkumulert strømkostnad`. Kapasitetsleddet fordeles lineært over tid, månedstotalen matcher fakturaen.

1. Aktiver: **Settings > Devices > Månedlig forbruk > Entities > Akkumulert strømkostnad**
2. **Settings > Dashboards > Energy > Add consumption**
3. Velg din kWh-sensor under "Consumed energy"
4. Slå på "Use an entity tracking total costs"
5. Velg `Akkumulert strømkostnad`

Forbruksmåleren (kWh) kommer fra din AMS-leser, ikke Strømkalkulator.

---

## Eksempler

Topp-3 effektdager som entities-kort:

```yaml
type: entities
title: Topp-3 effektdager
entities:
  - entity: sensor.toppforbruk_1
    secondary_info: attribute
    attribute: dato
  - entity: sensor.toppforbruk_2
    secondary_info: attribute
    attribute: dato
  - entity: sensor.toppforbruk_3
    secondary_info: attribute
    attribute: dato
  - entity: sensor.snitt_toppforbruk
  - entity: sensor.kapasitetstrinn
```

Varsel ved nærhet til neste trinn:

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.nettleie_bkk_margin_til_neste_trinn
        below: 1.0
    action:
      - service: notify.mobile_app
        data:
          message: "{{ states('sensor.nettleie_bkk_margin_til_neste_trinn') }} kW til neste kapasitetstrinn."
```

---

## Faktura-verifisering

| Faktura-post          | Sensor                          | Hvor                            |
| --------------------- | ------------------------------- | ------------------------------- |
| Energiledd dag (kWh)  | Forrige måned forbruk dagtariff | State                           |
| Energiledd natt (kWh) | Forrige måned forbruk natt/helg | State                           |
| Energiledd dag (kr)   | Forrige måned nettleie          | Attributt: `energiledd_dag_kr`  |
| Energiledd natt (kr)  | Forrige måned nettleie          | Attributt: `energiledd_natt_kr` |
| Kapasitetsledd (kr)   | Forrige måned nettleie          | Attributt: `kapasitetsledd_kr`  |
| Kapasitetstrinn (kW)  | Forrige måned toppforbruk       | State (snitt topp-3)            |

---

## Tekniske detaljer

- Oppdateres hvert minutt
- Forbruk med energi-sensor (anbefalt): delta fra meter-register, eksakt mot faktura
- Forbruk uten energi-sensor: Riemann-sum fra effektsensor, 1-5 % avvik per måned
- Lagring: `/config/.storage/stromkalkulator_<entry_id>` (unik per instans)
- Se [input-sensorer.md](input-sensorer.md) for sensor-oppsett

### Manuelt redigere lagret data

Stopp HA først, ellers overskrives endringene.

```bash
ha core stop
# rediger /config/.storage/stromkalkulator_<entry_id>
ha core start
```

Finn `entry_id` i URL-en under Settings > Devices & Services > Strømkalkulator.

#### Felt

| Felt                             | Type   | Beskrivelse                                        |
| -------------------------------- | ------ | -------------------------------------------------- |
| `daily_max_power`                | dict   | `{"YYYY-MM-DD": {"kw": float, "hour": int}}`       |
| `monthly_consumption`            | dict   | `{"dag": float, "natt": float}` (kWh)              |
| `current_month`                  | string | `"YYYY-MM"`                                        |
| `daily_cost`                     | float  | Dagens akkumulerte kostnad (kr)                    |
| `monthly_accumulated_cost`       | float  | Akkumulert månedskostnad (kr)                      |
| `previous_month_consumption`     | dict   | Forbruk forrige måned                              |
| `previous_month_top_3`           | dict   | Topp-3 forrige måned                               |
| `previous_month_kapasitetsledd`  | int    | Kapasitetsledd forrige måned (kr/mnd)              |
| `previous_month_kapasitetstrinn` | string | Trinn-intervall forrige måned (f.eks. `"5-10 kW"`) |
| `monthly_export_kwh`             | float  | Eksport denne måneden                              |
| `monthly_export_revenue`         | float  | Eksportinntekt denne måneden                       |
| `monthly_cost`                   | float  | Total forbrukskostnad denne måneden (kr)           |

#### Eksempler

Nullstille toppforbruk:

```json
{ "daily_max_power": {} }
```

Korrigere én dag:

```json
{ "daily_max_power": { "2026-04-03": { "kw": 4.2, "hour": 17 } } }
```

Nullstille månedlig forbruk:

```json
{ "monthly_consumption": { "dag": 0.0, "natt": 0.0 } }
```

Se [beregninger.md](beregninger.md) for formler.
