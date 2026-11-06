# Kontrakt: input og konfigurasjon

Kontrakten beskriver inputadapteren, energibaselinen, tariffmodus, migrering og diagnostikk. Den utfyller [avregningskontrakten](avregning.md).

## 1. Typede inputresultater

Adapteren i `inputadapter.py` er den eneste veien inn til en sensorverdi.
Setup, options, reconfigure og runtime bruker den samme. Den returnerer ett av
tre resultater, aldri et bart tall og aldri `None` som betyr flere ting.

| Resultat        | Felt                                                                                                                                                                       | Betyr                                                                  | Regnes det videre på?        |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- |
| `Gyldig`        | `verdi` (float, normalisert), `enhet_normalisert`, `observed_at` (aware datetime fra `last_updated`), `avlest_kl` (aware datetime, da adapteren leste staten), `raa_enhet` | Entiteten finnes og leverer et endelig tall i en enhet som kan regnes om | Ja                           |
| `Utilgjengelig` | `grunn`, `entity_id`                                                                                                                                                       | Entiteten leverer ikke akkurat nå, men oppsettet er i orden            | Nei, forrige tilstand står   |
| `Ugyldig`       | `grunn`, `entity_id`, `raa_enhet`                                                                                                                                          | Entiteten leverer en verdi som ikke kan brukes i beregningen                   | Nei, og det skal være synlig |

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
| `feil_dimensjon` | Enheten er gyldig, men for feil størrelse, for eksempel kWh der W kreves   |
| `feil_valuta`    | Prisenhet i annen valuta enn NOK eller øre, for eksempel EUR/MWh              |
| `ikke_kumulativ` | Energisensor uten `state_class` `total_increasing` eller `total`              |
| `urimelig_verdi` | Prisverdi der absoluttverdien er over 100 **etter** normalisering til NOK/kWh |

Grensen for `urimelig_verdi` er 100 NOK/kWh etter normalisering og gjelder absoluttverdien. Negative spotpriser er gyldige.

At entiteten mangler er altså `Utilgjengelig(finnes_ikke)`, ikke `Ugyldig`.
Det er med vilje: en slettet sensor er ikke en feilkonfigurasjon som skal
avvises, det er en måling som ikke kommer inn. Den skal aldri kaste
`UpdateFailed`. Resten av kjeden regner videre på det som fortsatt kommer inn.

Fire regler gjelder alle roller i runtime:

- Et ikke-gyldig resultat blir ikke 0, men fravær av måling.
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

Andre enheter avvises. Valutaer utenom NOK og øre gir `feil_valuta`; integrasjonen konverterer ikke valuta.

## 3. Krav til energisensoren

Energisensoren er en kumulativ importteller, OBIS 1.8.0. Integrasjonen leser differansen
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
  Er den nye enheten en annen dimensjon enn den antatte dimensjonen, er det en
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

At antakelsen ble gjort er likevel synlig: `raa_enhet` er `None` i
`input_resultater` (punkt 10), så diagnostikken viser hvilke roller som kjører
på antatt enhet.

## 5. Energibaseline

Baselinen er den forrige energiavlesningen som deltaet måles fra.

Store-skjema v2 for baseline:


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
- Migreringen gjøres ved lasting: er versjonen i
  dataene ukjent, forkastes baselinen én gang og resten av filen beholdes.
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

- Hva som skjer med baselinen når et delta avvises, både det negative og det
  som er større enn `MAX_ENERGY_DELTA_KWH`, står i [avregning.md
  C1](avregning.md#c1-fordelingsregel-jevnt-over-tid) sammen med bokføringen av
  det avviste deltaet. Regelen eies der, og gjentas ikke her.
- En gammel baseline uten `source_identity`
  forkastes én gang ved lasting. Månedsdata beholdes. Neste avlesning setter ny
  baseline med kilde og gir delta 0. Det koster hver bruker inntil ett
  pollintervall med forbruk, og alternativet, å stole på en verdi med ukjent måler, er verre.
- Fjernes energisensoren fra konfigurasjonen, nullstilles baselinen. Settes den
  inn igjen senere, er det per definisjon en ny kilde.
- Verdien lagres normalisert. Gamle lagrede verdier er rå sensorverdier, og det
  er den andre grunnen til at de forkastes én gang: enheten er ukjent.

## 6. Tariffmodus

`CONF_TARIFFMODUS` er et felt på entryet med tre verdier.

| Modus                | Hvor satsene kommer fra                                                  | Hvem har den                                                                                      |
| -------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `catalog`            | `dso.py`, løpende ved hver oppstart og hver oppdatering av integrasjonen | Alle nye oppsett med et kjent nettselskap, og alle som svarer «følg katalogen» på repair-varselet |
| `manual`             | Eksplisitte satser lagret på entryet                                     | Egendefinert, og alle som svarer «behold mine satser»                                             |
| `legacy_unconfirmed` | `dso.py`, men entryet har en lagret sats med ukjent opprinnelse       | Alt som migreres fra v4 og har lagrede energiledd                                                 |

Tre presiseringer:

- `catalog` henter *alle* DSO-regler løpende, ikke bare energiledd. Perioder,
  kapasitetstrinn, fastledd-metode, helligdager og terskelregler leses fra
  `dso.py` ved hver oppstart. Ingenting av det skal fryses på entryet.
- `legacy_unconfirmed` **regner med katalogen**. Det er dette som retter feilen
  fra 1.16.0-tiden. Modusen sier bare at det er ukjent om den lagrede satsen
  var brukerens vilje, og den lagrede satsen blir stående urørt på entryet til
  brukeren har svart.
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
Coordinatoren faller til riktig fallback, og baselinen nullstilles når
energisensoren fjernes.

## 7. Config v5, den ene migreringen

Config v5 migreres i `async_migrate_entry` i `__init__.py`. Migreringskjeden omfatter også eldre konfigurasjoner, og versjoner over 5 avvises.

En bruker på 1.16.0 skal ikke miste noen akkumulator. Migreringen rører bare
`entry.data`, aldri Store-filen med måledata, og aldri `entry_id` eller
entitetenes unique-id-er.

| Entry-type i dag                     | Kjennetegn i `entry.data`                                 | Modus etter v5                                  | Endres satsene?                           | Repair?                                                                |
| ------------------------------------ | --------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| Egendefinert                         | `tso == "custom"`                                         | `manual`                                        | Nei                                       | Nei fra v5. Eget varsel gjelder fastledd                            |
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

Et eksempel fra en BKK-konfigurasjon har `energiledd_dag: 0.28774` lagret mens `dso.py` sier `0.2877`. Den lagrede
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
bli stående på en utdatert sats i påvente av svar ville videreført feilen.

## 9. Egendefinert fastledd

Egendefinert har ingen forhåndsutfylte kapasitetstrinn. Uten en kilde er fastleddet ukjent, som beskrevet i [incident 006](../incidents/006-kapasitetstrinn-uten-kilde.md).

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
  og oppslaget bruker den øverste prisen for alt over. Det er ikke nødvendig å skrive `inf`.
- Tomt felt er lovlig og betyr at tabellen er ukjent. Det er ikke det samme som null.

**Hva ukjent fastledd betyr per sensor.** Uten tabell er kapasitetsleddet
`None`, ikke 0. Mønsteret finnes allerede for sikringsstørrelse
(`fastledd_mangler_sikringsvalg` i `coordinator.py` og `sensor.py`), og flagget `fastledd_ukjent` oppfører seg likt.

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

Diagnostikken leser dette fra coordinatoren og ikke fra sensorstates eller rå
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

## 11. Oversettelser

`tests/test_oversettelser.py` kontrollerer at `strings.json`, `translations/nb.json` og `translations/en.json` holdes i synk.

## 12. Tilgrensende regler

Energi- og prisintervaller beskrives i [avregningskontrakten](avregning.md). Diagnostikkens JSON aliaserer identifikatorer som kan peke på et anlegg. Effekt- og energisensorer uten enhet godtas uten repair-varsel, som beskrevet i punkt 4.1.
