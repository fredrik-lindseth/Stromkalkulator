# Sensorer

Komplett oversikt over alle sensorer og devices i Strømkalkulator.

## Oversikt

Integrasjonen oppretter **5 devices** med totalt **44 sensorer**. Av disse er **32 aktive** som standard — resten er deaktivert og kan slås på ved behov.

| Device           | Beskrivelse                        | Aktive | Totalt |
|------------------|------------------------------------|--------|--------|
| Nettleie         | Energiledd, kapasitet, avgifter    | 11     | 19     |
| Strømstøtte      | Strømstøtte og totalpris           | 6      | 7      |
| Norgespris       | Norgespris-sammenligning           | 3      | 3      |
| Månedlig forbruk | Forbruk og kostnader denne måneden | 7      | 10     |
| Forrige måned    | Forbruk og kostnader forrige måned | 5      | 5      |

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
| Totalpris inkl. avgifter          | kr/kWh | **Anbefalt for Energy Dashboard** — din totale strømpris inkl. nettleie, avgifter og støtte |
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
| Månedlig Norgespris-differanse      | kr     | Akkumulert besparelse/tap i kroner denne måneden sammenlignet med alternativ avtale    |

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
| Estimert månedskostnad    | kr    | Prognose for hva hele måneden vil koste, basert på forbruket hittil (oppdateres daglig mer presist) |

### Attributter

**Månedlig forbruk totalt** har:
- `dag_kwh` - Forbruk på dagtariff
- `natt_kwh` - Forbruk på natt/helg-tariff
- `dag_pct` - Prosentandel av forbruket som er på dagtariff
- `natt_pct` - Prosentandel av forbruket som er på natt/helg-tariff

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

## Bruksscenarier

### Energy Dashboard

Energy Dashboard trenger to ting: en **forbruksmåler** (kWh) og en **prissensor** (kr/kWh).

| Felt i Energy Dashboard       | Hva du velger                    | Kilde              |
|-------------------------------|----------------------------------|---------------------|
| **Consumed energy**           | Din kWh-forbrukssensor           | AMS-leser via HAN-port |
| **Use an entity with current price** | **Totalpris inkl. avgifter** | Strømkalkulator     |

**Steg for steg:**
1. **Settings > Dashboards > Energy**
2. Under **Electricity grid**, klikk **Add consumption**
3. **Consumed energy** — velg din kWh-sensor (f.eks. fra Tibber Pulse eller AMS-leser)
4. Slå på **Use an entity with current price**
5. Velg **Totalpris inkl. avgifter** (`sensor.totalpris_inkl_avgifter_*`)

> **Merk:** Strømkalkulator gir deg prisen — forbruksmåleren (kWh) kommer fra din AMS-leser (f.eks. Tibber Pulse).

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

### Nøyaktighet

- **1-5% avvik fra faktura er normalt** (avrunding, målefeil)
- Strømstøtte kan avvike mer (fakturaen bruker time-for-time priser)
- Forbruk beregnes fra effekt, ikke fra strømmåler

Se [beregninger.md](beregninger.md) for detaljerte formler.
