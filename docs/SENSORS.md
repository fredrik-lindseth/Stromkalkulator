# Sensorer

Komplett oversikt over alle sensorer og devices i Strømkalkulator.

## Oversikt

Integrasjonen oppretter **6 devices** med totalt **52 sensorer**. Av disse er **34 aktive** som standard, resten er deaktivert og kan slås på ved behov.

| Device           | Beskrivelse                        | Aktive | Totalt |
|------------------|------------------------------------|--------|--------|
| Nettleie         | Energiledd, kapasitet, avgifter    | 11     | 19     |
| Strømstøtte      | Strømstøtte og totalpris           | 6      | 7      |
| Norgespris       | Norgespris-sammenligning           | 3      | 3      |
| Månedlig forbruk | Forbruk og kostnader denne måneden | 8      | 12     |
| Forrige måned    | Forbruk og kostnader forrige måned | 6      | 6      |
| Eksport          | Solcelle-eksport for plusskunder   | 0      | 5      |

### Aktivere flere sensorer

Gå til **Settings > Devices > Strømkalkulator > (velg device) > Entities**. Klikk på en deaktivert sensor og slå på "Enabled". Sensoren begynner å oppdateres ved neste minutt.

Sensorer merket *(valgfri)* er deaktivert som standard. Å deaktivere en sensor påvirker ikke beregningene — coordinator beregner alle verdier uansett. Sensorer er bare visning.

---

## Device: Nettleie

Hoveddevicen med nettleie-priser, kapasitetstrinn og offentlige avgifter. Devicen navngis "Nettleie ({ditt nettselskap})".

### Energiledd

| Sensor         | Enhet  | Beskrivelse                                                                      |
|----------------|--------|----------------------------------------------------------------------------------|
| Energiledd     | kr/kWh | Hva du betaler per kWh til nettselskapet akkurat nå (bytter mellom dag- og nattsats) |
| Tariff         | -      | Hvilken tariffperiode som gjelder nå: "dag" eller "natt" (styrer utility_meter)   |

**Tariff-regler:**
- **Dag**: Man-fre 06:00-22:00 (ikke helligdager)
- **Natt**: 22:00-06:00, helger, og helligdager

### Kapasitet

| Sensor                       | Enhet  | Beskrivelse                                                                            |
|------------------------------|--------|----------------------------------------------------------------------------------------|
| Kapasitetstrinn              | kr/mnd | Fast månedskostnad basert på ditt høyeste strømforbruk (snitt av 3 topp-dager)         |
| Snitt toppforbruk            | kW     | Snittet av de 3 dagene du har brukt mest strøm denne måneden — bestemmer kapasitetstrinn |
| *(valgfri)* Kapasitetstrinn (nummer)     | -      | Hvilket trinn du er på nå (1, 2, 3, ...) — lavere er billigere                        |
| *(valgfri)* Kapasitetstrinn (intervall)  | -      | kW-intervallet for ditt aktive trinn (f.eks. "2-5 kW")                                |
| Toppforbruk #1               | kW     | Høyeste effektdag denne måneden — den dagen du brukte mest strøm                      |
| Toppforbruk #2               | kW     | Nest høyeste effektdag denne måneden                                                   |
| Toppforbruk #3               | kW     | Tredje høyeste effektdag denne måneden                                                 |
| Margin til neste trinn       | kW     | Hvor mye mer strøm du kan bruke før du rykker opp til neste (dyrere) kapasitetstrinn   |
| Kapasitetsvarsel             | -      | Slår seg "on" når du er nær neste kapasitetstrinn — bruk til varsling/automatisering   |

**Toppforbruk #1-3** har attributter:
- `dato` - Datoen for toppforbruket (f.eks. "2026-04-05")
- `time` - Timen da toppen inntraff (0-23, f.eks. 17 betyr kl. 17:00-18:00)

### Strømpris

| Sensor                        | Enhet  | Beskrivelse                                                                                      |
|-------------------------------|--------|--------------------------------------------------------------------------------------------------|
| Total strømpris (før støtte)  | kr/kWh | Alt du betaler per kWh akkurat nå: spotpris + nettleie (før eventuell strømstøtte trekkes fra)    |
| *(valgfri)* Total strømpris (strømavtale) | kr/kWh | Som over, men med strømselskapets pris istedenfor spotpris (valgfri — krever ekstern prissensor)  |
| Strømpris per kWh             | kr/kWh | Spotpris + energiledd uten kapasitetsledd — den variable kostnaden per kWh du bruker              |

### Diagnostikk (avgifter)

| Sensor               | Enhet  | Beskrivelse                                                                       |
|-----------------------|--------|-----------------------------------------------------------------------------------|
| *(valgfri)* Energiledd dag        | kr/kWh | Nettleie-satsen for dagtimer (hverdager 06-22), inkludert alle avgifter og mva     |
| *(valgfri)* Energiledd natt/helg  | kr/kWh | Nettleie-satsen for natt/helg/helligdager, inkludert alle avgifter og mva          |
| *(valgfri)* Offentlige avgifter   | kr/kWh | Sum av forbruksavgift og Enova-avgift inkl. mva — dette er statens påslag per kWh  |
| *(valgfri)* Forbruksavgift        | kr/kWh | Elavgiften (statlig avgift på strømforbruk) inkl. mva                              |
| *(valgfri)* Enovaavgift           | kr/kWh | Enova-avgiften (finansierer energieffektivisering) inkl. mva                       |

---

## Device: Strømstøtte

Sensorer for strømstøtte-beregning og totalpris inkl. alle avgifter.

| Sensor                            | Enhet  | Beskrivelse                                                                                 |
|-----------------------------------|--------|---------------------------------------------------------------------------------------------|
| Strømstøtte                       | kr/kWh | Statens støtte per kWh når spotpris er over 96,25 øre (du får dekket 90% av overskytende)   |
| Spotpris etter støtte             | kr/kWh | Hva spotprisen effektivt koster deg etter at strømstøtten er trukket fra                    |
| Total strømpris etter støtte      | kr/kWh | Din reelle totalpris akkurat nå: spotpris + nettleie - strømstøtte                          |
| Totalpris inkl. avgifter          | kr/kWh | Kan brukes i Energy Dashboard som prissensor. Kapasitetsleddet fordeles per kWh, noe som gir unøyaktige månedstotaler. For korrekte totaler, bruk [Akkumulert strømkostnad](#energy-dashboard). |
| Strømstøtte aktiv nå              | -      | "Ja" / "Nei" — om spotprisen akkurat nå er høy nok til at du får strømstøtte               |
| Strømstøtte gjenstående kWh       | kWh    | Hvor mange kWh du har igjen før du treffer støtte-taket. Avhenger av boligtype: bolig=5000 kWh/mnd, fritidsbolig=0 (ingen rett) |
| *(valgfri)* Strømpris per kWh (etter støtte)  | kr/kWh | Spotpris + energiledd - strømstøtte, uten kapasitetsledd — variabel kWh-kostnad etter støtte |

---

## Device: Norgespris

Sammenligning mellom din spotprisavtale og Norgespris (fast 50 øre/kWh). kWh-tak avhenger av boligtype: bolig=5000 kWh/mnd, fritidsbolig=1000 kWh/mnd. Over taket betaler du spotpris.

| Sensor                              | Enhet  | Beskrivelse                                                                           |
|-------------------------------------|--------|---------------------------------------------------------------------------------------|
| Total strømpris (norgespris)        | kr/kWh | Hva du ville betalt per kWh med Norgespris: fast 50 øre + nettleie                   |
| Prisforskjell (norgespris)          | kr/kWh | Hvor mye du sparer/taper per kWh sammenlignet med Norgespris (positiv = du betaler mer) |
| Norgespris aktiv nå                 | -      | "Ja" / "Nei" — om du har valgt Norgespris som din strømavtale                        |

**Prisforskjell tolkning:**
- **Positiv verdi** = Du betaler mer enn Norgespris (Norgespris er billigere)
- **Negativ verdi** = Du betaler mindre enn Norgespris (spotpris er billigere)

---

## Device: Månedlig forbruk

Sporer forbruk og kostnader for inneværende måned. Nullstilles automatisk ved månedsskifte.

### Forbruk

| Sensor                     | Enhet | Beskrivelse                                                                         |
|----------------------------|-------|-------------------------------------------------------------------------------------|
| Månedlig forbruk dagtariff | kWh   | Strøm brukt på dagtariff denne måneden (hverdager 06:00-22:00, ikke helligdager)    |
| Månedlig forbruk natt/helg | kWh   | Strøm brukt på natt/helg-tariff denne måneden (netter, helger og helligdager)       |
| Månedlig forbruk totalt    | kWh   | Alt strømforbruk denne måneden — sum av dag og natt                                 |

### Kostnader

| Sensor                    | Enhet | Beskrivelse                                                                                       |
|---------------------------|-------|---------------------------------------------------------------------------------------------------|
| *(valgfri)* Månedlig nettleie         | kr    | Nettleie hittil denne måneden: energiledd (dag + natt) + kapasitetsledd                           |
| *(valgfri)* Månedlig avgifter         | kr    | Offentlige avgifter hittil: forbruksavgift + Enova-avgift inkl. mva                               |
| *(valgfri)* Månedlig strømstøtte      | kr    | Estimert strømstøtte du har tjent inn denne måneden (faktisk støtte beregnes time-for-time)        |
| Månedlig nettleie total   | kr    | Bunnlinjen: nettleie + avgifter - strømstøtte — det du faktisk betaler for nettdelen               |
| Dagens kostnad            | kr    | Hva strømmen har kostet deg i dag — akkumulert kostnad siden midnatt                               |
| *(valgfri)* Akkumulert strømkostnad | kr | Akkumulert total strømkostnad denne måneden, for Energy Dashboard med korrekt kapasitetsledd. Se [Energy Dashboard](#energy-dashboard). |
| Månedlig Norgespris-differanse | kr | Akkumulert besparelse/tap i kroner denne måneden sammenlignet med alternativ avtale     |
| Norgespris-kompensasjon   | kr    | Akkumulert kompensasjon (norgespris - spotpris) × kWh denne måneden                                |
| Estimert månedskostnad    | kr    | Prognose for hva hele måneden vil koste, basert på forbruket hittil (oppdateres daglig mer presist) |

### Attributter

**Månedlig forbruk totalt** har:
- `dag_kwh` - Forbruk på dagtariff
- `natt_kwh` - Forbruk på natt/helg-tariff
- `dag_pct` - Prosentandel av forbruket som er på dagtariff
- `natt_pct` - Prosentandel av forbruket som er på natt/helg-tariff

**Akkumulert strømkostnad** har:
- `strompris_kr` - Akkumulert strømpris (spot eller Norgespris, etter støtte)
- `energiledd_kr` - Akkumulert energiledd-kostnad
- `kapasitetsledd_kr` - Akkumulert kapasitetsledd (tidsbasert, ikke kWh-basert)
- `total_kwh` - Totalt forbruk denne måneden

**Månedlig nettleie** har:
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd

**Månedlig nettleie total** har:
- `nettleie_kr` - Nettleie-delen av totalkostnaden
- `avgifter_kr` - Avgifts-delen av totalkostnaden
- `stromstotte_kr` - Strømstøtte-fradraget
- `forbruk_dag_kwh` / `forbruk_natt_kwh` / `forbruk_total_kwh` - Forbruk
- `vektet_snittpris_kr_per_kwh` - Gjennomsnittlig pris per kWh for hele måneden

---

## Device: Forrige måned

Lagrer forrige måneds data for faktura-verifisering. Oppdateres automatisk ved månedsskifte.

### Forbruk

| Sensor                              | Enhet | Beskrivelse                                                                    |
|-------------------------------------|-------|--------------------------------------------------------------------------------|
| Forrige måned forbruk dagtariff     | kWh   | Strøm brukt på dagtariff forrige måned (hverdager 06:00-22:00)                |
| Forrige måned forbruk natt/helg     | kWh   | Strøm brukt på natt/helg-tariff forrige måned (netter, helger, helligdager)   |
| Forrige måned forbruk totalt        | kWh   | Totalt strømforbruk forrige måned                                              |

### Kostnader og effekt

| Sensor                     | Enhet | Beskrivelse                                                                          |
|----------------------------|-------|--------------------------------------------------------------------------------------|
| Forrige måned nettleie     | kr    | Hva du betalte i nettleie forrige måned — bruk til å sammenligne med fakturaen       |
| Forrige måned toppforbruk  | kW    | Snitt av de 3 dagene med høyest forbruk forrige måned — bestemte kapasitetstrinn     |
| Forrige måned Norgespris-kompensasjon | kr | Norgespris-kompensasjon for forrige måned                                     |

### Attributter

Alle sensorer har:
- `måned` - Hvilken måned dataene gjelder (f.eks. "januar 2026")

**Nettleie-sensor har også:**
- `energiledd_dag_kr` - Kostnad for dagforbruk
- `energiledd_natt_kr` - Kostnad for nattforbruk
- `kapasitetsledd_kr` - Kapasitetsledd
- `snitt_topp_3_kw` - Gjennomsnitt av topp-3 effektdager
- `norgespris_differanse_kr` - Norgespris-differanse for måneden

**Toppforbruk-sensor har også:**
- `topp_1_dato`, `topp_1_kw` - Høyeste dag
- `topp_2_dato`, `topp_2_kw` - Nest høyeste dag
- `topp_3_dato`, `topp_3_kw` - Tredje høyeste dag

---

## Device: Eksport (solceller)

Sensorer for plusskunder med solceller. Sporer eksportert energi og inntekt. Alle sensorer er deaktivert som standard og krever at en eksport-effektsensor er konfigurert.

| Sensor                         | Enhet | Beskrivelse                                              |
|--------------------------------|-------|----------------------------------------------------------|
| *(valgfri)* Månedlig eksport kWh        | kWh   | Eksportert energi denne måneden                          |
| *(valgfri)* Månedlig eksport inntekt    | kr    | Inntekt fra eksport (spotpris × kWh)                     |
| *(valgfri)* Månedlig nettokostnad       | kr    | Forbrukskostnad minus eksportinntekt                     |
| *(valgfri)* Forrige måned eksport kWh   | kWh   | Eksportert energi forrige måned                          |
| *(valgfri)* Forrige måned eksport inntekt | kr  | Eksportinntekt forrige måned                             |

---

## Bruksscenarier

### Energy Dashboard

Energy Dashboard trenger to ting: en **forbruksmåler** (kWh) og en **kostnadskilde**. Strømkalkulator gir deg to alternativer for kostnadsdelen:

#### Alternativ 1: Prissensor (kr/kWh)

Bruk **Totalpris inkl. avgifter** som prissensor. Enklest å sette opp, men månedstotalen for kapasitetsleddet blir unøyaktig fordi et fast beløp (kr/mnd) fordeles per kWh.

| Felt i Energy Dashboard       | Hva du velger                    | Kilde              |
|-------------------------------|----------------------------------|---------------------|
| **Consumed energy**           | Din kWh-forbrukssensor           | AMS-leser via HAN-port |
| **Use an entity with current price** | **Totalpris inkl. avgifter** | Strømkalkulator     |

#### Alternativ 2: Akkumulert kostnad (anbefalt)

Bruk **Akkumulert strømkostnad** for korrekte månedstotaler. Denne sensoren akkumulerer kostnad der kapasitetsleddet fordeles lineært over tid, ikke per kWh. Månedstotalen matcher fakturaen uavhengig av forbruksmengde.

Sensoren er deaktivert som standard. Aktiver den under **Settings > Devices > Månedlig forbruk > Entities**.

| Felt i Energy Dashboard       | Hva du velger                        | Kilde              |
|-------------------------------|--------------------------------------|---------------------|
| **Consumed energy**           | Din kWh-forbrukssensor               | AMS-leser via HAN-port |
| **Use an entity tracking total costs** | **Akkumulert strømkostnad** | Strømkalkulator     |

**Steg for steg (alternativ 2):**
1. Aktiver sensoren: **Settings > Devices > Månedlig forbruk > Entities > Akkumulert strømkostnad**
2. **Settings > Dashboards > Energy**
3. Under **Electricity grid**, klikk **Add consumption**
4. **Consumed energy** - velg din kWh-sensor (f.eks. fra Tibber Pulse eller AMS-leser)
5. Slå på **Use an entity tracking total costs**
6. Velg **Akkumulert strømkostnad** (`sensor.akkumulert_stromkostnad_*`)

> **Merk:** Strømkalkulator gir deg prisen — forbruksmåleren (kWh) kommer fra din AMS-leser (f.eks. Tibber Pulse).

### Toppforbruk og kapasitetstrinn

Sensorene **Toppforbruk #1-3** viser de tre dagene med høyest strømforbruk denne måneden. Snittet av disse bestemmer kapasitetstrinnet. Dato og klokkeslett for hver topp ligger i attributtene `dato` og `time`.

Finn dine entity-ID-er under **Developer Tools > States** og søk etter "toppforbruk". Entity-ID-ene varierer avhengig av nettselskap og instans (f.eks. `sensor.toppforbruk_1` eller `sensor.nettleie_elvia_toppforbruk`).

#### Entities-kort

Viser topp-3 med dato som sekundærinformasjon. Bytt ut entity-ID-ene med dine egne:

```yaml
type: entities
title: Topp-3 effektdager
entities:
  - entity: sensor.toppforbruk_1           # Bytt med din entity-ID
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

#### Markdown-kort med tabell

Viser kW, dato og klokkeslett i en kompakt tabell:

```yaml
type: markdown
title: Toppforbruk denne måneden
content: |
  | # | kW | Dato | Kl. |
  |---|---:|------|-----|
  {% set s1 = 'sensor.toppforbruk_1' %}
  {% set s2 = 'sensor.toppforbruk_2' %}
  {% set s3 = 'sensor.toppforbruk_3' %}
  | 1 | {{ states(s1) }} | {{ state_attr(s1, 'dato') }} | {{ state_attr(s1, 'time') }}:00 |
  | 2 | {{ states(s2) }} | {{ state_attr(s2, 'dato') }} | {{ state_attr(s2, 'time') }}:00 |
  | 3 | {{ states(s3) }} | {{ state_attr(s3, 'dato') }} | {{ state_attr(s3, 'time') }}:00 |

  **Snitt:** {{ states('sensor.snitt_toppforbruk') }} kW
```

#### Automasjon: varsle ved nærhet til neste trinn

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.nettleie_bkk_margin_til_neste_trinn  # Bytt med din entity-ID
        below: 1.0
    action:
      - service: notify.mobile_app
        data:
          message: >
            Du er {{ states('sensor.nettleie_bkk_margin_til_neste_trinn') }} kW
            fra neste kapasitetstrinn.
```

### Sammenligne Norgespris

Bruk **Prisforskjell (norgespris)** for å se om Norgespris lønner seg:

```yaml
# Eksempel: Varsle når Norgespris er billigere
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.prisforskjell_norgespris
        above: 0.10  # 10 øre billigere
    action:
      - service: notify.mobile_app
        data:
          message: "Norgespris er nå 10+ øre billigere enn spotpris"
```

### Faktura-verifisering

Bruk "Forrige måned"-sensorene når fakturaen kommer:

| Faktura-post          | Sensor                        | Hvor                            |
|-----------------------|-------------------------------|---------------------------------|
| Energiledd dag (kWh)  | Forrige måned forbruk dagtariff | State                         |
| Energiledd natt (kWh) | Forrige måned forbruk natt/helg | State                         |
| Energiledd dag (kr)   | Forrige måned nettleie        | Attributt: `energiledd_dag_kr`  |
| Energiledd natt (kr)  | Forrige måned nettleie        | Attributt: `energiledd_natt_kr` |
| Kapasitetsledd (kr)   | Forrige måned nettleie        | Attributt: `kapasitetsledd_kr`  |
| Kapasitetstrinn (kW)  | Forrige måned toppforbruk     | State (snitt topp-3)            |

---

## Tekniske detaljer

### Oppdateringsfrekvens

- Alle sensorer oppdateres **hvert minutt**
- Månedlig forbruk beregnes med Riemann-sum fra effekt-sensoren
- Makseffekt lagres per dag og nullstilles ved månedsskifte

### Persistens

- All data lagres til disk og overlever restart
- Lagringsformat: `/config/.storage/stromkalkulator_<entry_id>` (unik per instans)

### Manuelt redigere lagrede data

Integrasjonen lagrer all akkumulert data i en JSON-fil per instans. Du kan redigere denne filen direkte for å korrigere feil data uten å miste alt.

#### Finn lagringsfilen

1. Finn din `entry_id`: **Settings > Devices & Services > Strømkalkulator** og klikk på instansen. Entry-ID-en vises i URL-en (f.eks. `config/integrations/integration/stromkalkulator#...`)
2. Filen ligger i `/config/.storage/stromkalkulator_<entry_id>`

Alternativt, list alle lagringsfiler:

```bash
ls /config/.storage/stromkalkulator_*
```

#### Stopp HA, rediger, start HA

Stopp Home Assistant for du redigerer, ellers overskrives endringene dine.

```bash
ha core stop
# rediger filen
ha core start
```

#### Eksempler

**Nullstille toppforbruk (begynne på nytt denne måneden):**

Sett `daily_max_power` til tom dict. Toppforbruk bygges opp igjen fra scratch.

```json
{
  "daily_max_power": {},
  ...
}
```

**Korrigere en enkelt toppforbruksdag:**

Endre kW-verdien for en spesifikk dato. `hour` er timen (0-23) da toppen inntraff.

```json
{
  "daily_max_power": {
    "2026-04-03": {"kw": 4.2, "hour": 17},
    "2026-04-08": {"kw": 3.8, "hour": 7},
    "2026-04-12": {"kw": 5.1, "hour": 18}
  },
  ...
}
```

**Fjerne en feilaktig toppdag:**

Slett bare den aktuelle datoen fra `daily_max_power`. Resten beholdes.

**Nullstille månedlig forbruk:**

```json
{
  "monthly_consumption": {"dag": 0.0, "natt": 0.0},
  ...
}
```

**Korrigere forrige måneds kapasitetstrinn:**

Hvis forrige måned viser feil trinn (f.eks. etter delt data mellom instanser):

```json
{
  "previous_month_kapasitetsledd": 250,
  "previous_month_kapasitetstrinn": "2-5 kW",
  ...
}
```

#### Komplett feltbeskrivelse

| Felt | Type | Beskrivelse |
|------|------|-------------|
| `daily_max_power` | dict | Toppforbruk per dag: `{"YYYY-MM-DD": {"kw": float, "hour": int}}` |
| `monthly_consumption` | dict | Forbruk denne måneden: `{"dag": float, "natt": float}` (kWh) |
| `current_month` | string | Nåværende måned: `"YYYY-MM"` |
| `daily_cost` | float | Dagens akkumulerte kostnad (kr) |
| `monthly_accumulated_cost` | float | Akkumulert totalkostnad denne måneden (kr) |
| `previous_month_consumption` | dict | Forbruk forrige måned: `{"dag": float, "natt": float}` (kWh) |
| `previous_month_top_3` | dict | Topp-3 forrige måned (samme format som `daily_max_power`) |
| `previous_month_kapasitetsledd` | int | Kapasitetsledd forrige måned (kr/mnd) |
| `previous_month_kapasitetstrinn` | string | Trinn-intervall forrige måned (f.eks. `"5-10 kW"`) |
| `monthly_export_kwh` | float | Eksportert energi denne måneden (kWh) |
| `monthly_export_revenue` | float | Eksportinntekt denne måneden (kr) |
| `monthly_cost` | float | Total forbrukskostnad denne måneden (kr) |

### Nøyaktighet

- **1-5% avvik fra faktura er normalt** på grunn av Riemann-sum vs. strømmålerens kWh-teller
- Strømstøtte kan avvike mer (fakturaen bruker time-for-time priser)
- Forbruk beregnes fra effekt, ikke fra strømmåler
- **Kapasitetsledd i Energy Dashboard kan avvike mye mer** med prissensoren (Totalpris inkl. avgifter), fordi kapasitetsleddet er et fast beløp per måned som fordeles som kr/kWh. Bruk «Akkumulert strømkostnad» for korrekte månedstotaler. Se [forklaring](../README.md#kapasitetsledd-i-energy-dashboard)

Se [beregninger.md](beregninger.md) for detaljerte formler.
