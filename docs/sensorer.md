# Sensorer

6 devices og 55 entiteter: 50 sensorer, 4 binærsensorer og 1 knapp. 32 av sensorene er på som standard.

Tabellen teller sensorer. Binærsensorene og knappen står i devicene sine, men
ikke i tallene her: de er Kapasitetsvarsel og Måledata-problem på Nettleie,
Norgespris aktiv på Norgespris, Strømstøtte aktiv på Strømstøtte, og knappen
Lag fakturarapport.

| Device           | Aktive | Totalt |
| ---------------- | ------ | ------ |
| Nettleie         | 10     | 18     |
| Strømstøtte      | 5      | 6      |
| Norgespris       | 3      | 3      |
| Månedlig forbruk | 8      | 12     |
| Forrige måned    | 6      | 6      |
| Eksport          | 0      | 5      |

Aktivere flere: **Settings > Devices > Strømkalkulator > (device) > Entities**, slå på "Enabled". Coordinator beregner uansett, sensorer er bare visning.

Sensorer merket _(valgfri)_ er deaktivert som standard.

## Nettleie

Hoveddevicen, navngis "Nettleie ({nettselskap})".

### Energiledd

| Sensor     | Enhet   | Beskrivelse                                                |
| ---------- | ------- | ---------------------------------------------------------- |
| Energiledd | NOK/kWh | Det du betaler per kWh nå (bytter mellom dag- og nattsats) |
| Tariff     | -       | "dag" eller "natt" (styrer utility_meter)                  |

Dag: man-fre 06-22 (ikke helligdager). Natt: 22-06, helger, helligdager. Full regel: [beregninger.md](beregninger.md#energiledd).

En ferdig `utility_meter`-pakke som splitter forbruket på dag/natt-tariff ligger i [`packages/stromkalkulator_utility.yaml`](../packages/stromkalkulator_utility.yaml). Kopier den til `/config/packages/`, bytt ut sensornavnene, og aktiver `packages` i `configuration.yaml`.

Hos nettselskap med sesongpriser bærer Energiledd-sensoren attributtene `sesongprising`, `aktiv_periode` og `perioder`. Se [beregninger.md](beregninger.md#energiledd).

### Kapasitet

| Sensor                                  | Enhet  | Beskrivelse                                               |
| --------------------------------------- | ------ | --------------------------------------------------------- |
| Kapasitetstrinn                         | kr/mnd | Fast månedskostnad basert på snitt av topp-3 effektdager  |
| Snitt toppforbruk                       | kW     | Snitt av topp-3, bestemmer trinnet                        |
| Toppforbruk #1, #2, #3                  | kW     | De tre høyeste effektdagene denne måneden                 |
| Margin til neste trinn                  | kW     | Hvor mye mer du kan bruke før neste (dyrere) trinn        |
| Kapasitetsvarsel (binary_sensor)        | on/off | På når margin er under terskelen, til varsling/automasjon |
| _(valgfri)_ Kapasitetstrinn (nummer)    | -      | Trinnet du er på (1, 2, 3, ...)                           |
| _(valgfri)_ Kapasitetstrinn (intervall) | -      | kW-intervallet for ditt trinn (f.eks. "2-5 kW")           |

Toppforbruk #1-3 har attributtene `dato` (YYYY-MM-DD) og `time` (0-23).

Kapasitetsvarsel er en `binary_sensor` som slår til (on) når margin til neste trinn er under terskelen. Terskelen settes i options (Configure), default 2,0 kW. Bruk varselet i automasjoner som skrur ned last før du bikker over i et dyrere trinn.

Kapasitetstrinn bærer `fastledd_metode` (nettselskapets modell) og `fastledd_grunnlag_kw` (kW-verdien den modellen faktisk slår opp med). For de 69 oppføringene som bruker NVE-modellen er `fastledd_grunnlag_kw` det samme som `gjennomsnitt_kw`. To attributter dukker opp bare når de gjelder:

| Attributt                   | Når                                                         |
| --------------------------- | ----------------------------------------------------------- |
| `mangler_sikringsstorrelse` | Alut og Netera uten valgt hovedsikring. Sensoren er Ukjent. |
| `metode_uverifisert`        | Tinfos, som ikke publiserer metoden sin.                    |

Hos Alut og Netera fakturerer nettselskapet etter hovedsikringens størrelse, ikke målt effekt. Den velges i oppsettet eller under Configure. Til den er valgt står sensoren som Ukjent i stedet for å vise et gjettet beløp, og "Margin til neste trinn" og "Kapasitetsvarsel" ligger i ro, siden fastleddet ikke endrer seg med forbruket. Det samme gjelder Fjellnett, som ikke har trinn i det hele tatt. Se [beregninger.md](beregninger.md#nettselskap-med-en-annen-metode).

### Strømpris

| Sensor                                    | Enhet   | Beskrivelse                                      |
| ----------------------------------------- | ------- | ------------------------------------------------ |
| Total strømpris (før støtte)              | NOK/kWh | Spotpris + nettleie, før strømstøtte trekkes fra |
| Strømpris per kWh                         | NOK/kWh | Spotpris + energiledd, uten kapasitetsledd       |
| _(valgfri)_ Total strømpris (strømavtale) | NOK/kWh | Med strømselskapets pris i stedet for spotpris   |

### Diagnostikk (avgifter)

| Sensor                           | Enhet   | Beskrivelse                               |
| -------------------------------- | ------- | ----------------------------------------- |
| _(valgfri)_ Energiledd dag       | NOK/kWh | Dagsats inkl. alle avgifter og mva        |
| _(valgfri)_ Energiledd natt/helg | NOK/kWh | Natt/helg-sats inkl. alle avgifter og mva |
| _(valgfri)_ Offentlige avgifter  | NOK/kWh | Forbruksavgift + Enova inkl. mva          |
| _(valgfri)_ Forbruksavgift       | NOK/kWh | Elavgift inkl. mva                        |
| _(valgfri)_ Enovaavgift          | NOK/kWh | Enova-avgift inkl. mva                    |

## Strømstøtte

| Sensor                                       | Enhet   | Beskrivelse                                                                                                                                                             |
| -------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strømstøtte                                  | NOK/kWh | Statens støtte per kWh når spotpris > 96,25 øre (90% av overskytende)                                                                                                   |
| Spotpris etter støtte                        | NOK/kWh | Spotpris minus strømstøtte                                                                                                                                              |
| Total strømpris etter støtte                 | NOK/kWh | Reell totalpris: spotpris + nettleie - støtte                                                                                                                           |
| Totalpris inkl. avgifter                     | NOK/kWh | Prissensor for Energy Dashboard. Kapasitetsledd fordelt per kWh (unøyaktig ved avvikende forbruk). For korrekt total: bruk [Akkumulert strømkostnad](#energy-dashboard) |
| Strømstøtte aktiv nå (binary_sensor)         | on/off  | På når spotpris er over terskel                                                                                                                                         |
| Strømstøtte gjenstående kWh                  | kWh     | Hvor mye av månedens støtte-tak som er igjen (bolig=5000, fritidsbolig=0)                                                                                               |
| _(valgfri)_ Strømpris per kWh (etter støtte) | NOK/kWh | Som "Strømpris per kWh", men med støtte trukket fra                                                                                                                     |

## Norgespris

| Sensor                           | Enhet   | Beskrivelse                                                       |
| -------------------------------- | ------- | ----------------------------------------------------------------- |
| Total strømpris (norgespris)     | NOK/kWh | Hva du ville betalt med Norgespris: fast 50 øre + nettleie        |
| Strømpris (Norgespris-ordningen) | NOK/kWh | Ren strømdel: fast 50 øre under tak, spotpris over tak            |
| Prisforskjell (norgespris)       | NOK/kWh | Positiv = du betaler mer enn Norgespris (Norgespris er billigere) |
| Norgespris aktiv nå              | on/off  | På hvis du har valgt Norgespris                                   |

kWh-tak: bolig=5000, fritidsbolig=1000. Over taket betaler du spotpris.

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
| Månedlig nettleie total             | NOK   | Bunnlinjen: nettleie + avgifter - støtte                |
| Dagens kostnad                      | NOK   | Akkumulert kostnad siden midnatt                        |
| Estimert månedskostnad              | NOK   | Prognose for hele måneden, basert på forbruket hittil   |
| Norgespris besparelse               | NOK   | Akkumulert besparelse/tap vs alternativ avtale          |
| Norgespris-kompensasjon             | NOK   | Akkumulert (norgespris - spotpris) × kWh denne måneden  |
| _(valgfri)_ Månedlig nettleie       | NOK   | Bokført nettleie hittil: energiledd + fastledd          |
| _(valgfri)_ Månedlig avgifter       | NOK   | Bokført forbruksavgift + Enova inkl. mva                |
| _(valgfri)_ Månedlig strømstøtte    | NOK   | Bokført støtte denne måneden                            |
| _(valgfri)_ Akkumulert strømkostnad | NOK   | For Energy Dashboard med korrekte månedstotaler         |

Attributter på "Akkumulert strømkostnad": `strompris_kr`, `energiledd_kr`, `kapasitetsledd_kr`, `total_kwh`.

Attributter på "Månedlig nettleie total": `nettleie_kr`, `stromstotte_kr`, `forbruk_dag_kwh`, `forbruk_natt_kwh`, `forbruk_total_kwh`, `vektet_snittpris_kr_per_kwh`.

Attributter på "Månedlig nettleie": `energiledd_dag_kr`, `energiledd_natt_kr`, `avgifter_kr`, `kapasitetsledd_kr`. Splitten er fakturaens: energileddene er uten de offentlige avgiftene, som står for seg. De fire summerer til sensorverdien.

Attributter på "Månedlig avgifter": `forbruksavgift_kr`, `enovaavgift_kr`, `avgiftssone`. Bokføringen fører de to avgiftene under ett, så splitten er totalen fordelt etter forholdet mellom satsene. Endres forbruksavgiften midt i måneden (nyttår og 1. april), er splitten et anslag mens totalen er eksakt.

Alle månedssensorene over leser kroner kostnadskjernen har bokført per avregnet intervall. De regner ikke satser ganget med månedens kilowattimer, og viser derfor riktig beløp også når satsen eller strømstøtten endret seg underveis i måneden.

## Forrige måned

Lagres ved månedsskifte. Brukes til faktura-verifisering.

Devicen har også knappen **Lag fakturarapport**. Den lager en varsling (persistent notification) med en ferdig utfylt rapport, oppsett, forbruk, integrasjonens beregninger og en tom faktura-kolonne, som du kan sammenligne linje for linje og lime rett inn i et issue.

| Sensor                                | Enhet | Beskrivelse                               |
| ------------------------------------- | ----- | ----------------------------------------- |
| Forrige måned forbruk dagtariff       | kWh   | Dag-forbruk forrige måned                 |
| Forrige måned forbruk natt/helg       | kWh   | Natt/helg-forbruk forrige måned           |
| Forrige måned forbruk totalt          | kWh   | Totalt forbruk forrige måned              |
| Forrige måned nettleie                | NOK   | Sammenlign med fakturaen                  |
| Forrige måned toppforbruk             | kW    | Snitt av topp-3, bestemte kapasitetstrinn |
| Forrige måned Norgespris-kompensasjon | NOK   | Norgespris-kompensasjon for forrige måned |

Alle har `maaned`-attributt (f.eks. "januar 2026").

Nettleie-sensoren har også `energiledd_dag_kr`, `energiledd_natt_kr`, `avgifter_kr`, `stromstotte_kr`, `kapasitetsledd_kr`, `snitt_topp_3_kw`, `norgespris_differanse_kr` og `bokforte_kroner`.

Sensoren summerer de bokførte kronebeløpene fra månedsarkivet og legger til hele månedens kapasitetsledd. Satsendringer underveis i måneden bevares. Et eldre arkiv uten bokførte delbeløp vises som ukjent med `bokforte_kroner: false`; neste månedsskifte lager et komplett arkiv.

Forsinkede avlesninger kan også rette forrige måneds topptimer og fastledd. Beregningsgrunnlag og tariff fryses ved månedsskiftet. For årsvektet fastledd kan eldre lagring mangle dette grunnlaget; en sen korrigering gir da ukjent nettleie med `fastledd_grunnlag_bekreftet: false`, siden årets senere topper ikke kan brukes som historisk fasit.

Kapasitetstrinn beholder ørepriser. Midtnett og Areas tre områder har egne fastleddtabeller for konfigurert fritidsbolig, også ved fast bosted. Area område 3 har fortsatt uavklart energiledd for hytter og motstridende sesongkilder; se [begrensningene](begrensninger.md). Hos Etna er husholdningens fastledd bare bekreftet til og med 25 kW. Høyere fakturagrunnlag gir ukjent fastledd og total, også etter en sen korrigering av forrige måned.

Nettselskapets publiserte tabell ender ved 50–75 kW uten å avklare eksakt 75. Fra og med 75 kW er derfor fastleddet og avhengige totaler ukjent. Egendefinerte trinntabeller følger brukerens egne oppgitte priser.

Snapshotene her har `last_reset` satt til starten av inneværende måned. Verdien byttes i sin helhet ved månedsskiftet, og uten `last_reset` ville HA-statistikken bokført forskjellen mellom to måneder som et delta.

Toppforbruk-sensoren har `maaned`, `topp_1_dato`, `topp_1_kw`, `topp_1_time`, `topp_2_dato`, `topp_2_kw`, `topp_2_time`, `topp_3_dato`, `topp_3_kw`, `topp_3_time`.

## Eksport (solceller)

For plusskunder. Krever konfigurert eksport-effektsensor. Alle deaktivert som standard.

| Sensor                                    | Enhet | Beskrivelse                          |
| ----------------------------------------- | ----- | ------------------------------------ |
| _(valgfri)_ Månedlig eksport kWh          | kWh   | Eksportert energi denne måneden      |
| _(valgfri)_ Månedlig eksport inntekt      | NOK   | Inntekt (spotpris × kWh)             |
| _(valgfri)_ Månedlig nettokostnad         | NOK   | Forbrukskostnad minus eksportinntekt |
| _(valgfri)_ Forrige måned eksport kWh     | kWh   | Eksportert energi forrige måned      |
| _(valgfri)_ Forrige måned eksport inntekt | NOK   | Eksportinntekt forrige måned         |

Eksportinntekten beregnes med spotprisen for kvarteret energien ble levert i. Null og negative priser er gyldige. Mangler prisdekning, vises inntekt og nettokostnad som ukjent; inntektssensorens attributter viser kjent delbeløp og `kwh_uten_pris`. Nettokostnad krever også et kjent fastledd.

Dette er eksportens spotverdi. Innmatingsgodtgjørelse fra nettselskapet og egne vilkår i leverandørens plusskundeavtale er ikke inkludert.

## Vakthold på måledataene

| Sensor                           | Enhet  | Beskrivelse                        |
| -------------------------------- | ------ | ---------------------------------- |
| Måledata-problem (binary_sensor) | on/off | På når en input-sensor har sviktet |

Sensoren er `device_class: problem` og ligger under Diagnostikk. Den er aldri
spot-gatet: et bortfall av spotprisen er nettopp et av tilfellene den skal
melde, så den må virke når spotprisen mangler.

Tre ting slår den på:

- Utfall: en konfigurert input har stått `unavailable` eller `unknown` i mer
  enn 30 minutter. Grensen er fast og dekker HA-restart, oppdatering av en
  integrasjon og en nettverksglipp.
- Frossen energiteller: energimåleren rapporterer, men tallet har ikke økt
  på flere timer enn terskelen. Terskelen settes under Configure, default tre
  timer. Hev den på en hytte eller et anlegg som står tomt i perioder.
- Utløpt spotpris: spotprisen har vært borte lenger enn cachen på to timer.
  Forbruk, nettleie, avgifter og kjent Norgespris under forbrukstaket bokføres fortsatt.
  Spotavhengig kraftkostnad, strømstøtte og Norgespris-sammenligning mangler
  prisgrunnlag. Manglende dekning vises i datakvaliteten.

Attributter:

| Attributt               | Innhold                                                          |
| ----------------------- | ---------------------------------------------------------------- |
| `problemer`             | Én rad per aktivt problem: type, input, entity_id, siden, timer  |
| `antall_problemer`      | Antall aktive problemer                                          |
| `berorte_inputer`       | Rollene som svikter, f.eks. `["energi"]`                         |
| `sist_energi_okning`    | Da energitelleren sist økte                                      |
| `spotpris_gyldig`       | Om spotprisen kan regnes med nå                                  |
| `leverandorpris_gyldig` | Om leverandør-sensoren leverer, `null` hvis den ikke er satt opp |
| `frossen_terskel_timer` | Terskelen som gjelder                                            |

Hvert problem gir i tillegg et varsel under Innstillinger > Reparasjoner, så du
ser det uten å ha satt opp noe. Varselet forsvinner av seg selv når inputen er
tilbake. Et sprang i energitelleren som ble forkastet (målerbytte, sensorhikk
eller ekte forbruk som kom i ett jafs) gir sitt eget varsel med kWh-tallet, som
du bekrefter selv.

Strømleverandør-sensoren er med i oversikten, men alarmerer ikke: den mater bare
sammenligningssensoren «Total strømpris (strømavtale)».

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

### Kapasitetsvarsel og opphør

Bruk den eksisterende **Kapasitetsvarsel**-sensoren: den følger terskelen i
Configure (standard 2,0 kW), så automasjonen trenger ingen egen terskel.
Eksemplet under erstatter samme Home Assistant-varsel når kapasitetsvarselet
opphører. Det virker fra Home Assistant **2025.1**. Lim det inn i YAML-editoren
for én automasjon. Bytt entity-ID til din egen; ID-en avhenger av språket under
oppsett, nettselskap og navn du har endret selv.

```yaml
alias: Kapasitetsvarsel
triggers:
  - trigger: state
    entity_id: binary_sensor.nettleie_bkk_kapasitetsvarsel
    to: "on"
    id: warning
  - trigger: state
    entity_id: binary_sensor.nettleie_bkk_kapasitetsvarsel
    from: "on"
    to: "off"
    id: cleared
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: warning
        sequence:
          - action: persistent_notification.create
            data:
              notification_id: stromkalkulator_bkk_kapasitet
              title: "Kapasitetsvarsel"
              message: "{{ state_attr('binary_sensor.nettleie_bkk_kapasitetsvarsel', 'margin_kw') }} kW til neste kapasitetstrinn."
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - action: persistent_notification.create
            data:
              notification_id: stromkalkulator_bkk_kapasitet
              title: "Kapasitetsvarsel opphørt"
              message: "Kapasitetsvarselet er ikke lenger aktivt."
mode: queued
```

Opphør krever `on` → `off`: manglende data (`unknown`/`unavailable`) blir
ikke meldt som opphør. Bruk en egen varsel-ID per installasjon. Dette er et
varsel om beregnet margin i månedens kapasitetstrinn, ikke en prognose for hvor
mye last du kan legge på resten av timen. Laststyring hører hjemme i Effektvakt.

I Home Assistant **2026.7** ble formålsrettede triggers og conditions standard
i automasjonseditoren. Fra **2026.10** kan du velge triggeren direkte under
**Triggered by**, uten å skrive en ID. YAML-en over bruker eksplisitte ID-er,
som også virker i eldre versjoner. Se de offisielle
[juli-notene](https://www.home-assistant.io/blog/2026/07/01/release-20267/) og
[oktober-notene](https://www.home-assistant.io/blog/2026/10/07/release-202610/).

### Margin som gauge

```yaml
type: gauge
entity: sensor.nettleie_bkk_margin_til_neste_trinn
name: Margin til neste trinn
min: 0
max: 10
needle: true
severity:
  red: 0
  yellow: 1
  green: 2
```

Liten margin er rød; større margin er grønn. Tilpass skala og fargegrenser
til oppsettet ditt; `severity` er bare visning og endrer ikke varselterskelen.
Kortet virker i **2025.1**; det nye utseendet fra
[2026.4](https://www.home-assistant.io/blog/2026/04/01/release-20264/#gauge-card-redesign)
kommer automatisk. Ved høyeste trinn eller fastledd uten effekttrinn kan
marginen være 0 uten at et dyrere trinn finnes; les også Kapasitetsvarsel.

### Måleproblemer på dashboardet

Vis dette kortet mens **Måledata-problem** er på. Trykk på entiteten for å
se attributtet `problemer`; reparasjoner finnes også under Innstillinger.

```yaml
type: conditional
conditions:
  - entity: binary_sensor.nettleie_bkk_maledata_problem
    state: "on"
card:
  type: entities
  title: Sjekk input-sensorene
  entities:
    - entity: binary_sensor.nettleie_bkk_maledata_problem
    - entity: binary_sensor.nettleie_bkk_kapasitetsvarsel
```

Kortet virker i **2025.1**. I **2026.10** støtter korteditorens Visibility-fane
vilkårene fra automasjonseditoren og viser om hvert vilkår er oppfylt. Her
holder det med et enkelt state-vilkår. Se
[forbedringene i synlighet](https://www.home-assistant.io/blog/2026/10/07/release-202610/#show-a-card-only-when-it-matters).

## Faktura-verifisering

| Faktura-post          | Sensor                          | Hvor                            |
| --------------------- | ------------------------------- | ------------------------------- |
| Energiledd dag (kWh)  | Forrige måned forbruk dagtariff | State                           |
| Energiledd natt (kWh) | Forrige måned forbruk natt/helg | State                           |
| Energiledd dag (kr)   | Forrige måned nettleie          | Attributt: `energiledd_dag_kr`  |
| Energiledd natt (kr)  | Forrige måned nettleie          | Attributt: `energiledd_natt_kr` |
| Kapasitetsledd (kr)   | Forrige måned nettleie          | Attributt: `kapasitetsledd_kr`  |
| Kapasitetstrinn (kW)  | Forrige måned toppforbruk       | State (snitt topp-3)            |

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
| `weekly_max_power`               | dict   | Kun Fjellnett: ukestopper, nøklet på mandagsdato   |
| `monthly_consumption`            | dict   | `{"dag": float, "natt": float}` (kWh)              |
| `current_month`                  | string | `"YYYY-MM"`                                        |
| `daily_cost`                     | float  | Dagens akkumulerte kostnad (kr)                    |
| `monthly_accumulated_cost`       | float  | Akkumulert månedskostnad (kr)                      |
| `previous_month_consumption`     | dict   | Forbruk forrige måned                              |
| `previous_month_top_3`           | dict   | Topp-3 forrige måned                               |
| `previous_month_fastledd_snapshot` | dict/null | Historisk tariff og toppgrunnlag for sen korrigering |
| `previous_month_fastledd_grunnlag_bekreftet` | bool | Om historisk fastledd kan etterprøves |
| `previous_month_kapasitetsledd`  | int    | Kapasitetsledd forrige måned (kr/mnd)              |
| `previous_month_kapasitetstrinn` | string | Trinn-intervall forrige måned (f.eks. `"5-10 kW"`) |
| `monthly_export_kwh`             | float  | Eksport denne måneden                              |
| `monthly_export_revenue`         | float  | Eksportinntekt denne måneden                       |
| `eksportbok`                     | dict   | Eksportens prisruter, energi og månedsbalanser      |
| `ferdige_sum`                    | dict   | Forbruk og prisdekning utenfor det korte intervallvinduet |
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
