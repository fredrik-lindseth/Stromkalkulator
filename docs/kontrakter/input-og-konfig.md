# Kontrakt: input og konfigurasjon

Denne kontrakten binder K1 (inputadapter, baseline, slettede inputs), K2
(tariffmodus og config v5), K3 (Egendefinert uten gjettet fastledd) og D2
(diagnostikk). Den avgjør hva integrasjonen godtar som input, hvordan verdier
normaliseres, hva som lagres om energibaselinen, hvor tariffsatsene kommer fra,
og hva én migrering til config v5 setter for hver type entry som finnes i dag.

Reglene her er ikke forslag. Endres noe av det, endres det her først, og
tasken som bygger på det følger etter.

## Hvorfor kontrakten finnes

Tre feil har samme rot, nemlig at det ikke står skrevet noe sted hva et
gyldig input er og hvor en sats kommer fra.

Den dyreste er satsene. Oppsettsflyten lagrer katalogens energiledd på entryet
(`config_flow.py`, `async_step_sensors`), og coordinatoren lar den lagrede
verdien vinne over `dso.py` så lenge nettselskapet ikke har
`energiledd_perioder` (`coordinator.py`, rate-oppløsningen i `__init__`).
Resultatet er at en satsoppdatering i `dso.py` ikke når fram til noen som
allerede har satt opp anlegget. Sju nettselskap fikk nye tariffer i august og
september 2026, og av dem er det bare Sør Aurdal som slår gjennom, fordi den
har sesongperioder og da ignoreres den lagrede verdien. Options-flyten redder
det ikke: den avleder energiledd på nytt bare når brukeren *bytter*
nettselskap, så en vanlig lagring i innstillingene beholder den gamle satsen.

Den andre er enhetene. Coordinatoren leser `state.state` som et tall og bryr
seg ikke om `unit_of_measurement` (`_read_sensor_float`, `_read_price_sensor`,
`_compute_energy_delta`). En kW-sensor blir lest som W, en NOK/MWh-sensor blir
lest som NOK/kWh. Config-flyten har en delvis vakt for spotprisen
(`_validate_spot_sensor`), men den avviser der den burde regnet om, og
feilteksten sier i dag at EUR/MWh går bra, mens coordinatoren deretter leser
den som NOK/kWh.

Den tredje er `custom`, som har ti oppdiktede kapasitetstrinn i `dso.py`.
Trinnene ser ut som priser og er det ikke.

## 1. Typede inputresultater

Adapteren i `inputadapter.py` er den eneste veien inn til en sensorverdi.
Setup, options, reconfigure og runtime bruker den samme. Den returnerer ett av
tre resultater, aldri et bart tall og aldri `None` som betyr flere ting.

| Resultat        | Felt                                                                                                                                                                       | Betyr                                                                  | Regnes det videre på?        |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- |
| `Gyldig`        | `verdi` (float, normalisert), `enhet_normalisert`, `observed_at` (aware datetime fra `last_updated`), `avlest_kl` (aware datetime, da adapteren leste staten), `raa_enhet` | Entiteten finnes og leverer et endelig tall i en enhet vi kan regne om | Ja                           |
| `Utilgjengelig` | `grunn`, `entity_id`                                                                                                                                                       | Entiteten leverer ikke akkurat nå, men oppsettet er i orden            | Nei, forrige tilstand står   |
| `Ugyldig`       | `grunn`, `entity_id`, `raa_enhet`                                                                                                                                          | Entiteten leverer noe vi ikke har lov til å regne på                   | Nei, og det skal være synlig |

`observed_at` og `avlest_kl` er to ulike tider, og begge trengs. Energien
bokføres etter `observed_at` ([avregning.md
B1](avregning.md#b1-energiavlesning)), mens en prisprøve hører til prisruten
`avlest_kl` faller i ([avregning.md
A2.1](avregning.md#a21-prisruten-og-hva-det-vil-si-at-en-prisprøve-er-observert)).
Adapteren leverer begge og velger ikke mellom dem.

Grunnene er faste strenger, ikke fritekst, siden diagnostikken og
oversettelsene slår opp på dem.

`Utilgjengelig`-grunner:

| Grunn              | Når                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `finnes_ikke`      | `hass.states.get(entity_id)` er `None`. Entiteten er slettet, omdøpt eller ikke lastet ennå |
| `utilgjengelig`    | State er `unavailable`                                                                      |
| `ukjent`           | State er `unknown`                                                                          |
| `ikke_konfigurert` | Rollen er valgfri og brukeren har ikke satt noen entitet                                    |

`Ugyldig`-grunner:

| Grunn            | Når                                                                           |
| ---------------- | ----------------------------------------------------------------------------- |
| `ikke_tall`      | State lar seg ikke lese som float                                             |
| `ikke_endelig`   | NaN eller inf                                                                 |
| `ukjent_enhet`   | `unit_of_measurement` er satt til noe tabellen i punkt 2 ikke dekker          |
| `feil_dimensjon` | Enheten er gyldig, men for feil størrelse, for eksempel kWh der vi ber om W   |
| `feil_valuta`    | Prisenhet i annen valuta enn NOK eller øre, for eksempel EUR/MWh              |
| `ikke_kumulativ` | Energisensor uten `state_class` `total_increasing` eller `total`              |
| `urimelig_verdi` | Prisverdi der absoluttverdien er over 100 **etter** normalisering til NOK/kWh |

Grensen i `urimelig_verdi` gjelder etter normalisering, ikke i sensorens egen
enhet. `config_flow` bruker i dag 2000 i sensorens egen enhet, og det holdt så
lenge MWh-enheter ble avvist. Punkt 2 godtar `NOK/MWh`, og 2000 NOK/MWh er
2 NOK/kWh, som NO1, NO2 og NO5 har passert i ekte timer. En grense som avviser
ekte data er verre enn ingen grense. Norske timespriser har toppet seg i
størrelsesorden ti kroner per kWh, så 100 NOK/kWh ligger en størrelsesorden over
ekte data og fanger fortsatt det grensen er til for: en sensor som leverer noe
helt annet enn en pris, for eksempel en teller uten enhet. Den regnes på
absoluttverdien, så negative spotpriser passerer; de er gyldige
([avregning.md B2](avregning.md#b2-prisintervall)).

At entiteten mangler er altså `Utilgjengelig(finnes_ikke)`, ikke `Ugyldig`.
Det er med vilje: en slettet sensor er ikke en feilkonfigurasjon vi skal
avvise, det er en måling som ikke kommer inn. Den skal aldri kaste
`UpdateFailed`. Resten av kjeden regner videre på det som fortsatt kommer inn.

Fire regler gjelder alle roller i runtime:

- Et ikke-gyldig resultat blir aldri 0. Dagens `_read_sensor_float` returnerer
  0.0 for unavailable, og en 0 er en måling som sier «du bruker ingenting».
  Den skal bli fravær av måling.
- Et ikke-gyldig resultat overskriver aldri en cache og aldri energibaselinen.
- `Ugyldig` ved runtime som skyldes enhet skal gi vakthold-problemtypen `enhet`
  og et repair. En sensor som bytter enhet under drift er en ekte feil.
- «Forrige tilstand står» ved `Utilgjengelig` gjelder **visningen**. Cachen av
  siste prisverdi er til for prissensorene i denne integrasjonen og mates aldri
  inn i avregningen. Et avregningsintervall uten egen prisprøve har ingen pris,
  aldri naboens ([avregning.md C2.5 og
  C4](avregning.md#c4-intervaller-uten-data-eller-uten-pris)).

## 2. Enhetstabell

Normaliseringen skjer i adapteren, én gang, og resten av koden ser bare
normaliserte verdier. Sammenligningen av enhetsstrengen er
whitespace-trimmet og case-insensitiv, og `ore` godtas som skrivemåte for
`øre`.

| Rolle                    | Godtatte enheter     | Normalisert til | Faktor    |
| ------------------------ | -------------------- | --------------- | --------- |
| effekt, eksporteffekt    | `W`                  | `W`             | 1         |
|                          | `kW`                 | `W`             | 1000      |
|                          | `MW`                 | `W`             | 1 000 000 |
| energi                   | `Wh`                 | `kWh`           | 0,001     |
|                          | `kWh`                | `kWh`           | 1         |
|                          | `MWh`                | `kWh`           | 1000      |
| spotpris, leverandørpris | `NOK/kWh`, `kr/kWh`  | `NOK/kWh`       | 1         |
|                          | `øre/kWh`, `ore/kWh` | `NOK/kWh`       | 0,01      |
|                          | `NOK/MWh`, `kr/MWh`  | `NOK/kWh`       | 0,001     |
|                          | `øre/MWh`, `ore/MWh` | `NOK/kWh`       | 0,00001   |

Alt annet avvises. Det gjelder også `EUR/kWh` og `EUR/MWh`, som får
`feil_valuta`. Vi har ingen valutakurs i integrasjonen, og å lese euro som
kroner er verre enn å si nei. Feilteksten `spot_unit_invalid` i
`strings.json` sier i dag at EUR/MWh er greit, og den teksten er feil og skal
rettes av K1.

Øre/kWh avvises i dag i config-flyten. Etter denne kontrakten godtas den og
regnes om. Det er den ene endringen som gjør en tidligere avvist sensor
gyldig, og det er riktig vei: brukeren fikk beskjed om å bygge en
template-sensor for noe adapteren kan gjøre selv.

Normaliseringen må være dimensjonsriktig begge veier, altså at en verdi som
normaliseres og regnes tilbake gir samme tall innenfor float-presisjon. Det
skal stå som en hypothesis-test.

## 3. Krav til energisensoren

Energisensoren er en kumulativ importteller, OBIS 1.8.0. Vi leser differansen
mellom avlesninger, så alt annet enn en teller som bare går oppover gir
meningsløse deltaer.

Kravet er at `state_class` er `total_increasing` eller `total`. Mangler
`state_class` helt, er resultatet `Ugyldig(ikke_kumulativ)`. `measurement` er
også `Ugyldig(ikke_kumulativ)`: det er en øyeblikksverdi, ikke en teller.

`total` godtas fordi noen AMS-integrasjoner bruker den for tellere som kan
nullstilles ved målerbytte. Nullstillingen er dekket av at et negativt delta
forkastes og baselinen flyttes til den nye standen. Etter en nullstilling til 0
kommer det ikke noe stort sprang senere, og det er meningen: telleren starter
forfra, og det som går tapt er forbruket mellom siste avlesning på den gamle
telleren og den første på den nye. Et målerbytte der den nye telleren starter
høyere enn den gamle sto, gir derimot ett stort positivt delta, og det fanges av
`MAX_ENERGY_DELTA_KWH` og `energi_delta_forkastet`-varselet, som viser brukeren
tallet framfor å skjule det. Er den nye telleren en ny entitet, er den uansett
en ny kilde etter punkt 5, og deltaet er 0.

Kravet gjelder både i config-flyten (feilnøkkel på feltet) og ved runtime.

## 4. Sensor uten enhet

Dette er avgjort, og valget er Fredriks.

En sensor uten `unit_of_measurement` skal aldri avvises. Adapteren antar
rollens egen enhet med faktor 1, setter `raa_enhet` til `None`, og resultatet er
`Gyldig` med `enhet_antatt` sann. Det som skiller rollene, er om antakelsen
sier fra: prisrollene får et repair-varsel, effekt og energi får ingen.

En prissensor uten `unit_of_measurement` godtas som `NOK/kWh`, og det reises
**ett** repair-varsel som ber brukeren bekrefte at det stemmer. Integrasjonen
skal virke fra første minutt, og feilen skal være synlig.

- Varselet har id `prisenhet_ubekreftet_{entry_id}` og er fiksbart. Fix-flowen
  er en bekreftelse som skriver et flagg på entryet, etter samme mønster som
  `EgendefinertSatserRepairFlow` i `repairs.py`, slik at det ikke kommer
  tilbake ved neste omstart.
- Flagget er `CONF_PRISENHET_BEKREFTET`, og det er **per rolle**: en liste over
  de rollene brukeren har bekreftet, for eksempel `["spotpris"]`. Er rollen i
  listen, reises varselet ikke på nytt for den. Et enkelt ja/nei-flagg for hele
  entryet ville gjort at en bruker som bekreftet spotprisen og senere la til en
  leverandørprissensor uten enhet aldri fikk spørsmålet om den.
- Får sensoren senere en enhet, gjelder enheten, og flagget er uten betydning.
  Er den nye enheten en annen dimensjon enn det vi antok, er det en
  runtime-enhetsendring og håndteres som i punkt 1.
- Varselet reises ikke for en sensor som har enhet. Det er hele poenget: den
  som har en Nord Pool-sensor med `NOK/kWh` skal ikke se noe.

Regelen gjelder både spotpris og leverandørpris. Det står **ett** varsel om
gangen per entry, og det nevner de rollene som er ubekreftede akkurat nå, i
plassholderen. Bekreftelsen skriver alle rollene varselet nevnte inn i flagget.
Kommer en ny ubekreftet rolle til senere, reises varselet på nytt, én gang, for
den rollen.

Sensoren avvises ikke, og den godtas ikke stille.

### 4.1 Effekt- og energisensor uten enhet

En effekt- eller eksporteffektsensor uten `unit_of_measurement` **skal** leses
som `W`, og en energisensor uten enhet **skal** leses som `kWh`. Ingen av dem
gir repair-varsel og ingen av dem avvises.

Det er dagens oppførsel, og det er grunnen: en avvisning ville slått ut
oppsett som virker i dag, hos brukere som ikke har gjort noe galt og som ikke
har noen knapp å trykke på. Varselet i punkt 4 er forbeholdt prisrollene fordi
avgjørelsen der er Fredriks og gjelder pris.

At antakelsen ble gjort er likevel synlig: `raa_enhet` er `None` i
`input_resultater` (punkt 10), så diagnostikken viser hvilke roller som kjører
på antatt enhet.

Om effekt og energi også bør få et varsel, er ikke avgjort her. Det er en egen
avgjørelse med egen kost, ikke noe en utfører skal ta underveis; se punkt 12.

## 5. Energibaseline

Baselinen er den forrige avlesningen vi måler delta fra. I dag er den
`_last_tpi_kwh` pluss `_last_tpi_time`, den er ubundet til noen kilde, den
lagres som rå sensorverdi uten enhet, og den forkastes hvis den er eldre enn
`TPI_STALE_HOURS`. Det gjør at et målerbytte ser ut som forbruk, og at en
hytte som står avslått i en uke mister baselinen sin uten å si fra.

Ny form, Store-skjema v2:

| Felt              | Type           | Betyr                                                                 |
| ----------------- | -------------- | --------------------------------------------------------------------- |
| `schema_version`  | int            | 2 for denne formen                                                    |
| `source_identity` | str eller null | Entitetens `unique_id` fra entity-registeret                          |
| `entity_id`       | str            | Entity-id-en slik den var ved avlesningen, kun til visning og feilsøk |
| `value_kwh`       | float          | Avlesningen normalisert til kWh etter punkt 2                         |
| `observed_at`     | str            | ISO 8601 i UTC, fra statens `last_updated`                            |

**«v2» er en skjemaversjon i dataene, ikke `Store`-konstruktørens major
version.** Denne regelen eies her og gjelder hele Store-filen, også
[avregning.md D](avregning.md#d-persistens-og-migrering):

- `Store(hass, 1, f"{DOMAIN}_{entry_id}")` blir stående som den er. Versjonen
  skrives i selve dataene, i nøkkelen `skjema_versjon` på toppnivå i filen.
  Baseline-dicten bærer i tillegg sin egen `schema_version` etter tabellen
  over, slik at en baseline som flyttes eller logges ut av filen fortsatt vet
  hva den er. De to er ikke samme felt, og de leses hver for seg.
- Migreringen gjøres i vår egen kode ved lasting: kjenner vi ikke versjonen i
  dataene igjen, forkastes baselinen én gang og resten av filen beholdes.
- Grunnen til at konstruktøren ikke bumpes, er ikke design, den er
  testmiljøet: HAs `Store` krever en `_async_migrate_func`-override for et
  major-bump, og en override betyr en subklasse av `Store`, som ikke lar seg
  laste i unit-miljøet der `Store` er en `MagicMock`. Det skal stå her, ellers
  ser valget vilkårlig ut, og den neste bumper konstruktøren og får en rød
  suite uten å skjønne hvorfor.
- Det er også den varsomme veien: en eldre utgave av integrasjonen kan
  fortsatt lese filen og beholde månedsdataene sine, siden det bare er
  baselinen som er ny. Et major-bump ville gjort filen uleselig for den.

Regler:

- Kildeidentiteten er `unique_id` fra entity-registeret. Entity-id alene er
  ikke fysisk identitet: den følger med ved omdøping, og to ulike målere kan
  arve samme entity-id.
- Ny kilde, altså at `source_identity` er en annen enn den lagrede, gir delta
  0 ved første avlesning. Månedsdata og akkumulatorer røres ikke. Den nye
  baselinen skrives med en gang.
- Samme kilde etter omstart gjenopptar fra lagret baseline, uansett alder.
  Aldersgrensen `TPI_STALE_HOURS` faller bort som kriterium for å forkaste:
  vernet mot det gigantiske spranget er `MAX_ENERGY_DELTA_KWH` og
  `energi_delta_forkastet`-varselet, som forteller brukeren tallet i stedet for
  å kaste det i stillhet. Et døgn nede skal gi de 30 kWh fordelt over
  intervallene forbruket faktisk skjedde i, ikke 30 kWh som forsvinner.

  **Denne regelen eies her.** Baselinens levetid står bare i dette punktet, og
  [avregning.md C5](avregning.md#c5-omstart) viser hit framfor å gjenta den. De
  to dokumentene sa i første utgave hver sin ting om `TPI_STALE_HOURS`, og
  grunnen var at de ble skrevet av hver sin agent som ikke leste den andre. To
  steder å lese samme regel er ett for mye. K1 fjerner den siste bruken av
  konstanten, og står den da igjen i `const.py` uten bruker, fjernes den i samme
  commit.
- Hva som skjer med baselinen når et delta avvises, både det negative og det
  som er større enn `MAX_ENERGY_DELTA_KWH`, står i [avregning.md
  C1](avregning.md#c1-fordelingsregel-jevnt-over-tid) sammen med bokføringen av
  det avviste deltaet. Regelen eies der, og gjentas ikke her.
- En gammel baseline uten `source_identity`, altså alt som ligger lagret i dag,
  forkastes én gang ved lasting. Månedsdata beholdes. Neste avlesning setter ny
  baseline med kilde og gir delta 0. Det koster hver bruker inntil ett
  pollintervall med forbruk, og alternativet, å stole på en verdi vi ikke vet
  hvilken måler kom fra, er verre.
- Fjernes energisensoren fra konfigurasjonen, nullstilles baselinen. Settes den
  inn igjen senere, er det per definisjon en ny kilde.
- Verdien lagres normalisert. Gamle lagrede verdier er rå sensorverdier, og det
  er den andre grunnen til at de forkastes én gang: vi vet ikke hvilken enhet
  de var i.

## 6. Tariffmodus

`CONF_TARIFFMODUS` er et felt på entryet med tre verdier.

| Modus                | Hvor satsene kommer fra                                                  | Hvem har den                                                                                      |
| -------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `catalog`            | `dso.py`, løpende ved hver oppstart og hver oppdatering av integrasjonen | Alle nye oppsett med et kjent nettselskap, og alle som svarer «følg katalogen» på repair-varselet |
| `manual`             | Eksplisitte satser lagret på entryet                                     | Egendefinert, og alle som svarer «behold mine satser»                                             |
| `legacy_unconfirmed` | `dso.py`, men entryet har en lagret sats vi ikke vet om er bevisst       | Alt som migreres fra v4 og har lagrede energiledd                                                 |

Tre presiseringer:

- `catalog` henter *alle* DSO-regler løpende, ikke bare energiledd. Perioder,
  kapasitetstrinn, fastledd-metode, helligdager og terskelregler leses fra
  `dso.py` ved hver oppstart. Ingenting av det skal fryses på entryet.
- `legacy_unconfirmed` **regner med katalogen**. Det er dette som retter feilen
  fra 1.16.0-tiden. Modusen sier bare at vi ennå ikke vet om den lagrede satsen
  var brukerens vilje, og den lagrede satsen blir stående urørt på entryet til
  brukeren har svart. Vi overskriver den ikke.
- Tall-likhet er ikke brukerintensjon. At en lagret sats tilfeldigvis er lik
  katalogens betyr ikke at brukeren har valgt den, og at den er ulik betyr ikke
  at brukeren har skrevet den. Derfor har ingen entry `manual` etter
  migreringen uten at brukeren enten kjører Egendefinert eller har svart på
  varselet.

**Sesong-DSO.** Har nettselskapet `energiledd_perioder`, gjelder periodene,
også for `manual`. En fast dag- og nattsats gir ikke mening for et selskap som
bytter pris flere ganger i året, og dette er allerede dagens oppførsel. Det nye
er at det skal være synlig: sensoren `energiledd` får attributtet
`manual_ignorert: true` når entryet står i `manual` og DSO-en har perioder.
Ingen repair, siden tallene ikke endrer seg.

**Egendefinert.** `custom` er alltid `manual`. Det finnes ingen katalog å falle
tilbake på.

**Options og reconfigure.** Energiledd vises som overstyringsfelt, ikke som
påkrevde tall med forrige verdi som default. Katalogverdien står som hint.
Tomt felt betyr `catalog`, altså at overstyringen fjernes fra `entry.data`.
Et utfylt felt betyr `manual`. Dette gjelder også en bruker som står i
`legacy_unconfirmed`: åpner de innstillingene og lagrer uten å røre feltet, er
svaret «følg katalogen», og modusen blir `catalog`.

**Hva feltet står med når skjemaet åpnes.** Feltet forhåndsutfylles kun i
`manual`. Home Assistant-frontenden viser `suggested_value` og sender verdien
tilbake ved lagring selv om brukeren ikke rørte feltet, så et forslag i
`legacy_unconfirmed` ville gjort at et besøk i innstillingene låste den
utdaterte satsen som `manual` og slettet satsvarselet. Da hadde brukeren mistet
både satsoppdateringen og varselet som skulle fortalt om den, ved å gjøre noe
helt normalt. I `catalog` og `legacy_unconfirmed` står feltet tomt, og
katalogtallet står som hint i stegbeskrivelsen. En test som fyller inn feltene
selv kan ikke se dette; prøven skal regne ut forhåndsutfyllingen fra det ekte
skjemaet og sende den tilbake urørt.

**Bytte til Egendefinert.** Skjemaet ble tegnet for det gamle nettselskapet,
der energiledd er en overstyring som står tomt når katalogen gjelder.
Egendefinert har ingen katalog, og et tomt felt ville gitt en sats fra
ingensteds. Entryet arver derfor satsen anlegget faktisk lå på: overstyringen
om den finnes, ellers forrige nettselskaps katalogverdi. Brukeren retter tallet
mot sin egen prisliste. Det som *ikke* skal skje, er å fylle inn
`DSO_LIST["custom"]` sine defaulttall, for de er en mal og ikke en pris
(incident 006).

**Andre valgfrie felt.** Et tømt entitetsfelt fjerner bindingen. Det gjelder
energisensor, eksportmåler og leverandørpris, i både options og reconfigure.
Dagens `{**current, **user_input}` gjør at et tømt felt beholder gammel verdi,
og det er grunnen til at ingen får fjernet en sensor de en gang valgte.
Coordinatoren faller til riktig fallback, og baselinen nullstilles når
energisensoren fjernes.

## 7. Config v5, den ene migreringen

Config v5 er den eneste nye migreringen i denne serien. Den ligger i
`async_migrate_entry` i `__init__.py`, sammen med v1 til v4, og kjeden fra v1
skal fortsatt komme helt fram. Nedgraderingsvernet flyttes til `> 5`.

En bruker på 1.16.0 skal ikke miste noen akkumulator. Migreringen rører bare
`entry.data`, aldri Store-filen med måledata, og aldri `entry_id` eller
entitetenes unique-id-er.

| Entry-type i dag                     | Kjennetegn i `entry.data`                                 | Modus etter v5                                  | Endres satsene?                           | Repair?                                                                |
| ------------------------------------ | --------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| Egendefinert                         | `tso == "custom"`                                         | `manual`                                        | Nei                                       | Nei fra v5. K3 reiser sitt eget om fastledd                            |
| Kjent DSO med sesongperioder         | DSO har `energiledd_perioder`                             | `catalog`, lagret sats fjernes fra `entry.data` | Nei, periodene gjaldt allerede            | Nei                                                                    |
| Kjent DSO, lagret sats lik katalogen | Avvik under terskelen i punkt 8                           | `catalog`, lagret sats fjernes fra `entry.data` | Nei                                       | Nei                                                                    |
| Kjent DSO, lagret sats avviker       | Avvik over terskelen                                      | `legacy_unconfirmed`, lagret sats blir stående  | Ja, katalogen gjelder fra første oppstart | Ja, med valg                                                           |
| Kjent DSO uten lagret energiledd     | Feltene mangler                                           | `catalog`                                       | Nei                                       | Nei                                                                    |
| Utfaset DSO (`supported: False`)     | Står igjen for varselets skyld                            | `catalog`, lagret sats fjernes fra `entry.data` | Nei                                       | Nei fra v5. Det eksisterende `dso_migration`-varselet gjelder fortsatt |
| Fusjonert DSO                        | `tso` står i `DSO_MIGRATIONS` og er tatt ut av `DSO_LIST` | `catalog`, lagret sats fjernes fra `entry.data` | Ja, det nye selskapets katalog gjelder    | Nei fra v5. `dso_migration`-varselet forteller alt om flyttingen       |
| Ukjent DSO                           | `tso` finnes verken i `DSO_LIST` eller `DSO_MIGRATIONS`   | `manual`                                        | Nei                                       | Nei                                                                    |

Oppslaget i `DSO_MIGRATIONS` skjer **før** sjekken på om nettselskapet finnes
i `DSO_LIST`. Et fusjonert selskap er tatt ut av listen, så det ser ellers ut
som et ukjent nettselskap, og ville fått `manual`. Deretter flytter
`async_setup_entry` entryet over til selskapet som overtok, og da hadde det
regnet videre med det gamle selskapets sats på det nye, for godt, uten
tariffvarsel. Den lagrede satsen hører til selskapet de forlater.

Utfaset og fusjonert mister begge den lagrede satsen, slik at `catalog` alltid
betyr at entryet ikke bærer en sats. Ukjent DSO beholder sin: det finnes ingen
katalog å falle tilbake på, og tallet er alt de har.

Rad to og rad tre fjerner begge den lagrede satsen fra `entry.data`, slik at
entryet ikke drifter på nytt ved neste prisendring, og i begge tilfeller merker
brukeren ingenting fordi tallet er det samme. På en sesong-DSO er den lagrede
satsen dessuten alt uten virkning, siden periodene styrer; å la den ligge ville
bare vært å beholde et tall som ser ut som en regel og ikke er det.

## 8. Når repair-varselet om satser reises, og når det ikke gjør det

Varselet `tariff_ubekreftet_{entry_id}` reises **kun** når entryets lagrede
energiledd faktisk avviker fra det `dso.py` sier i dag. Et varsel hos en bruker
som allerede ligger riktig er en falsk positiv, og falske positiver er grunnen
til at forrige runde med vakthold ble avvist to ganger.

Avvik regnes slik:

- Sammenlign dag og natt hver for seg.
- Regn begge om til inkl. mva med entryets egen avgiftssone, gjennom
  `compute_energiledd_inkl_mva`. Det er tallet brukeren ser, og det er der en
  forskjell betyr noe.
- Avviket er signifikant når den absolutte differansen er minst
  `0,000075 NOK/kWh` inkl. mva, altså 0,0075 øre/kWh.
- Er minst én av de to signifikant, reises varselet. Ellers ikke.

Terskelen er ikke vilkårlig, og den er ikke 0,01 øre. Fredriks egen BKK-entry
har `energiledd_dag: 0.28774` lagret mens `dso.py` sier `0.2877`. Den lagrede
verdien er ikke en gammel BKK-sats og heller ikke et brukervalg: den kommer fra
v1-migreringen, som regnet 46,13 øre inkl. mva tilbake til eks. mva og rundet
til fem desimaler. Forskjellen er 0,005 øre/kWh inkl. mva, den er usynlig på
alle sensorer, og den skal ikke gi et varsel.

Terskelen ligger mellom den støyen og det minste ekte steget:

- Støyen fra v1-migreringens femdesimalavrunding er 0,005 øre, pluss inntil
  0,0006 øre fra selve avrundingen. Terskelen ligger over den.
- 0,01 øre/kWh er minste kvantum på prislistene, altså en ekte endring på ett
  steg. En terskel på nøyaktig 0,0001 NOK/kWh ville sluppet den gjennom i
  flyttall: `0.4614 - 0.4613` er `9.9999e-05`, som ikke er `>= 1e-4`. Terskelen
  ligger under den.
- Den minste ekte endringen i `dso.py`-historikken er Elvia fra 0,2915 til
  0,2899, altså 0,16 øre eks. mva. Den passerer med to størrelsesordener.

Varselet har to valg, og begge lukker det:

- «Følg katalogen»: modus blir `catalog`, den lagrede satsen fjernes fra
  `entry.data`.
- «Behold mine satser»: modus blir `manual`, den lagrede satsen blir stående og
  gjelder.

Så lenge varselet står ubesvart, regner entryet med katalogen. Å la brukeren
bli stående på en utdatert sats mens vi venter på et svar ville vært å
videreføre nettopp feilen vi retter.

Testene skal dekke begge retninger for hvert varsel i denne kontrakten, altså
både at det kommer når det skal og at det ikke kommer når det ikke skal. Et
varsel uten en negativ test er ikke ferdig.

## 9. Egendefinert fastledd

De ti kapasitetstrinnene på `custom` i `dso.py` er en mal, ikke priser. De
fjernes. Det følger av samme regel som incident 006: mangler kilden, skal
tallet være ukjent, ikke plausibelt.

**Formatet på brukerens trinntabell** er ett tekstfelt, med par skilt av komma
og kW-grense skilt fra pris med kolon:

```
2:155,5:250,10:415
```

- Venstre side er den øvre kW-grensen for trinnet, høyre side er prisen i
  kr/mnd **inkl. mva**, slik den står på nettselskapets prisliste. Det er den
  samme konvensjonen som `kapasitetstrinn` i `dso.py`.
- Desimaltegn kan være komma eller punktum. `155,5` og `155.5` er samme tall.
  Siden komma også skiller par, tolkes et komma med siffer på begge sider og
  uten kolon etter som desimaltegn.
- Mellomrom rundt tall og skilletegn ignoreres.
- Grensene må være strengt stigende. Er de ikke det, er feltet ugyldig.
- Det øverste trinnet gjelder alt over nest øverste grense. Brukeren skriver
  det som et par med en grense som er høyere enn alt de kan komme til å bruke,
  og oppslaget bruker den øverste prisen for alt over. Vi krever ikke at de
  skriver `inf`.
- Tomt felt er lovlig og betyr «jeg vet ikke». Det er ikke det samme som null.

**Hva ukjent fastledd betyr per sensor.** Uten tabell er kapasitetsleddet
`None`, ikke 0. Mønsteret finnes allerede for sikringsstørrelse
(`fastledd_mangler_sikringsvalg` i `coordinator.py` og `sensor.py`), og det nye
flagget `fastledd_ukjent` oppfører seg likt.

| Sensor                                                                                                                                                              | Verdi uten trinntabell                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `kapasitetstrinn`                                                                                                                                                   | Ukjent, med attributtet `fastledd_ukjent: true`                               |
| `trinn_nummer`                                                                                                                                                      | Ukjent                                                                        |
| `margin_neste_trinn`                                                                                                                                                | Ukjent                                                                        |
| `maanedlig_nettleie`                                                                                                                                                | Ukjent                                                                        |
| `maanedlig_total`                                                                                                                                                   | Ukjent                                                                        |
| `estimert_maanedskostnad`                                                                                                                                           | Ukjent                                                                        |
| `akkumulert_kostnad`                                                                                                                                                | Ukjent                                                                        |
| `energiledd`, `energiledd_dag`, `energiledd_natt`                                                                                                                   | Tall som før. Energileddet er per kWh og har ingenting med fastleddet å gjøre |
| `strompris_per_kwh`, `total_price`, `total_pris_inkl_avgifter`, `total_pris_etter_stotte`, `total_pris_norgespris`, `strompris_norgespris`                          | Tall, regnet uten fastledd, med attributtet `fastledd_ukjent: true`           |
| `maanedlig_forbruk_*`, `maks_forbruk_*`, `gjennomsnitt_forbruk`, `tariff`, `stromstotte*`, `offentlige_avgifter`, `forbruksavgift`, `enovaavgift`, eksportsensorene | Uberørt                                                                       |

`trinn_intervall` er allerede `None` når det underliggende feltet mangler, og
trenger ingen egen regel.

Historiske tall skrives ikke om. Et eksisterende Egendefinert-oppsett får et
repair som åpner innstillingene, og det som alt ligger i forrige måned blir
stående.

## 10. Hva coordinatoren eksponerer for diagnostikken

D2 leser dette fra coordinatoren og skal ikke lese sensorstates eller rå
`entry.data` selv. Alt kommer fra samme fullførte oppdatering, så
diagnostikken aldri viser en blanding av to polls.

- `input_resultater`: siste resultat per rolle (`effekt`, `energi`,
  `spotpris`, `eksport`, `leverandorpris`), med type (`gyldig`,
  `utilgjengelig`, `ugyldig`), grunn, rå enhet (`raa_enhet`, som er `None` når
  sensoren ikke oppgir noen, punkt 4.1), normalisert enhet og alder på
  siste gyldige avlesning. Gyldige resultater viser også normalisert `verdi`,
  `observed_at` og `avlest_kl`; andre resultater har `None` i disse feltene.
  Entity-id-er aliaseres av diagnostikklaget, ikke
  her.
- `tarifforigin`: modus (`catalog`, `manual`, `legacy_unconfirmed`), DSO-id, om
  sesongperioder styrer, og de effektive satsene eks. og inkl. mva som faktisk
  ble brukt i denne oppdateringen.
- `baseline`: `source_identity` (aliasert av diagnostikklaget), `value_kwh`,
  `observed_at`, `schema_version`, og om den ble forkastet ved siste lasting.
- `fastledd_ukjent` og `fastledd_mangler_sikringsvalg` som de er.
- `avregning_grunnlag`: oppdateringstid, siste godkjente energistand og siste
  lukkede og åpne intervaller med pris, kvalitet, satser, kWh før intervallet
  og kroner per komponent. Frosset med resten av oppdateringen, uten full
  forbrukshistorikk. Avregningsbokens statusfelt følger samme snapshot.

### 10.1 Hva som ikke skal i loggen

Diagnostikkdumpen er allowlistet fordi brukere limer den inn i offentlige
issues. `home-assistant.log` havner samme sted, og skal behandles likt.

`source_identity` er `unique_id` fra entity-registeret, og hos AMS- og
Elhub-integrasjoner er det målepunkt-ID eller målerserienummer, altså en
identifikator som peker på én bestemt husstand. Den skal aldri stå i en
loggmelding. Diagnostikken aliaserer den, og loggen har ikke noe alias å ty
til, så den utelates: meldingen ved et kildebytte sier at kilden er en annen,
ikke hvilken. Samme regel gjelder alt annet som identifiserer et anlegg utenfor
Home Assistant: målernummer, anleggsadresse og kundenummer.

Entity-id er noe annet. Det er et navn brukeren har valgt selv inne i sin egen
installasjon, og uten det vet han ikke hvilken sensor en melding gjelder.
Entity-id står derfor i loggen og i repair-plassholderne, sammen med den rå
enheten en sensor faktisk rapporterer, som er det varselet handler om. Et
repair uten dem er et varsel brukeren ikke kan handle på.

## 11. Nye nøkler som må inn alle tre steder

`tests/test_oversettelser.py` krever at `strings.json`,
`translations/nb.json` og `translations/en.json` holdes i synk. Kontrakten
innfører disse, og tasken som legger til nøkkelen legger den inn alle tre
stedene i samme commit.

- Feilnøkler på config- og options-felt: `enhet_ukjent`, `enhet_feil_dimensjon`,
  `enhet_feil_valuta`, `energi_ikke_kumulativ`, `trinntabell_ugyldig`.
- Issues: `prisenhet_ubekreftet`, `tariff_ubekreftet` med fix-flow og to valg,
  `vakthold_enhet`.
- Teksten i `spot_unit_invalid` rettes, siden den både lover at EUR/MWh går bra
  og sier at øre/kWh ikke godtas. Etter denne kontrakten er det motsatt.

## 12. Hva kontrakten ikke avgjør

- Hvordan energi fordeles over tid og prisintervaller. Det er
  avregningskontrakten, `docs/kontrakter/avregning.md`.
- Hvor prisen kommer fra når spotsensoren er borte. Også avregningskontrakten,
  [C4](avregning.md#c4-intervaller-uten-data-eller-uten-pris): den kommer ikke
  noe sted fra, og intervallet blir `uten_pris`.
- Hva observasjonstiden til en **prisprøve** er. `observed_at` fra
  `last_updated` i punkt 1 er energiavlesningens tid; prisprøver snappes til
  prisruten sin etter [avregning.md
  A2.1](avregning.md#a21-prisruten-og-hva-det-vil-si-at-en-prisprøve-er-observert).
- Hvilke felt diagnostikkens JSON har og hvordan de aliaseres. D1.
- Hvilke HA-versjoner som er minimum, og hvilke API-er adapteren får bruke.
  Testmiljøtasken.
- Om en effekt- eller energisensor uten enhet også skal gi et repair-varsel.
  Punkt 4.1 avgjør bare at den godtas stille i dag. Et varsel til ville truffet
  hver bruker med en AMS-integrasjon som ikke setter enhet, og det er en
  avgjørelse for Fredrik, ikke for tasken som er innom.
