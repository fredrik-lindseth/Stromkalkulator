# Avregningskontrakt

Denne kontrakten binder avregningskjernen (`avregning.py`, L1), replay-fasiten
(L2), coordinatoren (L3a), kostnadskjernen (L3b) og sensorene (L3c). Endres noe
her, endres alle fem. Den er skrevet fordi coordinatoren i dag priser hvert
poll-delta med øyeblikkspris i en åpen klokketime-bøtte, mens regelverket og
fakturaen er timebasert.

Invarianten alt hviler på:

> Samme observerte målehistorikk skal gi samme avregning uavhengig av når
> integrasjonen pollet. Energi bokføres etter avlesningens observasjonstid,
> ikke etter pollens.

Tall i dokumentet er målt, ikke antatt. Kildene står ved hvert tall.

## A. Beslutningsport: priskilde, avrunding, gyldighet, måletyper

### A1 Avregningsintervallet er klokketimen, uttrykt i UTC

Et avregningsintervall er halvåpent, `[start, slutt)`, og lagres i UTC.
Standard lengde er 60 minutter, og intervallgrensene faller sammen med
klokketimen i Europe/Oslo (som alltid er en hel UTC-time, også over
sommertidsskiftene).

Europe/Oslo brukes kun til to ting: å avgjøre dag- eller natt-tariff, og å
avgjøre hvilken fakturamåned intervallet hører til. Begge avgjøres av
intervallets **start**, ikke slutt. Alt annet regnes i UTC.

Poll-tidspunktet er behandlingstid. Det har ingen plass i avregningen utover å
være anledningen til at en avlesning ble hentet.

### A2 Timeprisen er det uvektede snittet av kvarterprisene

Prisen for et avregningsintervall er Nord Pools publiserte day-ahead-pris for
budområdet, i NOK/kWh eks. mva. Leveres prisen i kvartersoppløsning, er
timeprisen det **uvektede aritmetiske snittet av de fire kvarterprisene, regnet
ved full presisjon uten mellomavrunding**.

Belegget er fakturaen: juni 2026-fakturaens Norgespris-linje reproduseres med
0,00 kr avvik med Elhub-kWh ganger snittet av Nord Pools publiserte
Final-kvarterpriser, og mai og juli innenfor 0,005 kr. Se
[norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md).

Alternativet var å bruke Nord Pools publiserte timespris slik den står, altså
avrundet til to desimaler NOK/MWh. Forskjellen er målt på kvarterarkivet for
NO5 (`_private/Måleverdier/nordpool_nok_kvarter_no5.json`, 3120 hele timer,
5. mai til 11. september 2026): snittet av de fire kvarterne er selv et
tosifret desimaltall i bare 810 av 3120 timer, og avstanden mellom rått snitt
og tosifret avrunding er maks 0,005 og typisk 0,0025 NOK/MWh. For en måned på
2000 kWh er det maks 1 øre, typisk et halvt. Valget er altså ikke materielt,
og da velger vi den varianten som ikke kaster informasjon.

**Fra prissensoren, ikke fra API-et.** I drift leser integrasjonen prisen fra
brukerens prissensor, som er en trinnfunksjon av observerte states, ikke en
liste med intervaller. Prisen for et avregningsintervall bygges slik:

1. Prøvene observert i `[start, slutt)` danner en trinnfunksjon i intervallet.
2. Første prøve i intervallet utvides bakover til `start`. En prøve observert
   før `start` bæres aldri inn i intervallet.
3. Prisen er det tidsvektede snittet av trinnfunksjonen over hele intervallet.
4. Har intervallet ingen egen prøve, har det **ingen pris**. Se C4.

For en timesoppløst prissensor gir dette sensorens egen verdi. For en
kvartersoppløst sensor der alle fire kvarterne kommer, gir det nøyaktig
snittet i A2. Kommer bare noen av dem, blir prisen tidsvektet over de som kom,
og intervallet merkes `pris_delvis` (`pris_prover` mot `pris_prover_ventet`,
1 for time, 4 for kvarter).

### A3 Avrunding

Ingen mellomavrunding. Energi (kWh), pris (NOK/kWh) og kroner akkumuleres ved
full flyttallspresisjon gjennom hele kjeden. Avrunding skjer kun ved
presentasjon, i data-dicten: kWh til tre desimaler, kroner til to, priser til
fire. Det er samme presisjon som i dag.

Merverdiavgift legges på per intervall, etter avgiftssonen, på samme måte som
i dag. Priskontrakten er eks. mva hele veien inn.

### A4 Gyldighetsdato og prisårgang

Prisen hører til leveringsdøgnet, ikke til publiseringsdøgnet. På dager der
valutamarkedet var stengt på auksjonsdagen publiserer Nord Pool en foreløpig
NOK-kurs som senere korrigeres til Final. Integrasjonen ser bare den årgangen
som fantes i leveringstimen.

Kontrakten: **en avregning rettes aldri bakover.** Et lukket intervall beholder
prisen det ble avregnet med, og revisjonsstatusen (`foreløpig` eller `final`)
lagres som felt slik at diagnostikken kan vise den. Målt effekt av årgangen er
0,04 til 0,05 % av Norgespris-kompensasjonen, altså 0,1 til 0,6 kr per måned.
Etterkontroll mot faktura bruker prisarkivet og Final-priser, ikke sensoren.

### A5 Støttede måle- og avtaletyper

Versjon 1 dekker **timesavregnede forbruksmålepunkt for husholdning** i NO1 til
NO5, med spotavtale eller Norgespris.

Er noen husholdninger kvartersavregnet hos Elhub i dag? Nei. Referansepunktet i
`_private/Måleverdier/README.md` står som `Avregningsmetode: Timesavregnet` med
måleserien `KWH 60 Forbruk`. Statnetts beskrivelse av overgangen til
kvartersoppløsning sier det samme generelt: 15-minutterskravet gjelder
produksjon (utenom plusskunder), utveksling mellom nettområder og stort
forbruk, mens øvrige målere fortsetter med timesoppløsning, og Elhub
transformerer timesverdiene til kvarter før rapportering til eSett
([Statnett: Quarterly resolution and the energy markets][statnett], lest
12.09.2026). Husholdningen avregnes altså på time, selv om engrosmarkedet
kjører kvarter.

Bryteren for den dagen dette endrer seg: `opplosning_minutter` på prisintervall
og avregnet intervall (60 i v1). Å sette den til 15 krever at både prissensoren
er kvartersnativ og at målepunktet faktisk er kvartersavregnet hos Elhub. Alt
annet i kontrakten er skrevet oppløsningsuavhengig, så bryteren skal ikke koste
mer enn en konfigurasjonsverdi og et nytt sett fasittall.

Ikke dekket i v1: kvartersavregnede målepunkt, næringskunder, plusskunder på
egne avregningsregler for produksjon.

## B. Datakontrakt

### B1 Energiavlesning

Det integrasjonen leser fra energisensoren. En avlesning er en observasjon av
en kumulativ teller, ikke et forbruk.

| Felt | Type | Betydning |
| --- | --- | --- |
| `source_identity` | str | Registry `unique_id` for entiteten. Identiteten til den fysiske kilden, ikke `entity_id`. |
| `entity_id` | str | Kun for visning og diagnostikk. Kan endres av brukeren uten at kilden er en annen. |
| `value_kwh` | float | Kumulativ teller, normalisert til kWh av inputadapteren (K1). |
| `observed_at` | datetime (UTC, aware) | Entitetens `last_updated`. Dette er tiden energien gjelder for, ikke polltiden. |
| `kvalitet` | enum | `malt`, `estimert`, `avvist`. |
| `schema_version` | int | Skjemaversjon for avlesningen. |

`observed_at` er alltid tidssoneklar. En naiv datetime er en programmeringsfeil
og skal kaste, ikke tolkes som lokal tid.

### B2 Prisintervall

| Felt | Type | Betydning |
| --- | --- | --- |
| `start_utc` | datetime (UTC) | Inklusiv. |
| `slutt_utc` | datetime (UTC) | Eksklusiv. |
| `nok_per_kwh_eks_mva` | float \| None | `None` betyr ingen pris. Aldri 0 som erstatning. |
| `omrade` | str | NO1 til NO5. |
| `opplosning_minutter` | int | 60 eller 15. |
| `kilde` | enum | `sensor`, `arkiv`, `manuell`. |
| `revisjon` | enum | `forelopig`, `final`, `ukjent`. |
| `pris_prover` | int | Antall observerte prøver i intervallet. |
| `pris_prover_ventet` | int | 1 ved timesoppløsning, 4 ved kvarter. |

Negative priser er gyldige og klippes ikke.

### B3 Avregnet intervall

| Felt | Type | Betydning |
| --- | --- | --- |
| `start_utc` | datetime (UTC) | Inklusiv. |
| `slutt_utc` | datetime (UTC) | Eksklusiv. |
| `kwh` | float | Fordelt energi, se C1. |
| `lokal_maned` | str | `YYYY-MM` i Europe/Oslo, avgjort av `start_utc`. |
| `lokal_time` | int | 0 til 23 i Europe/Oslo, avgjort av `start_utc`. |
| `tariff` | enum | `dag` eller `natt`, avgjort av `start_utc` i Europe/Oslo. |
| `pris` | prisintervall \| None | Se B2. |
| `regelkilde` | str | Hvilken sats- og avgiftsårgang som ble brukt. |
| `kvalitet` | enum | `komplett`, `delvis_pris`, `uten_pris`, `ufullstendig`. |
| `apen` | bool | `True` så lenge `slutt_utc` ligger fram i tid. |

Fastledd (kapasitetsledd) er ikke energi og hører ikke hjemme i et avregnet
intervall. Det akkumuleres over tid mot en egen NOK-per-periode-flate og
avstemmes i sak 33f81xu.

## C. Invarianter og fordelingsregel

### C1 Fordelingsregel: jevnt over tid

Et godkjent målerdelta mellom to avlesninger fordeles **jevnt over tid** på de
avregningsintervallene vinduet `(forrige observed_at, ny observed_at]` dekker,
prorata på sekunder i hvert intervall.

Valget er tatt med Elhub som dommer, og det koster noe å ta det. Målingen ligger
i `scripts/research/maal_fordelingsregel.py` (juni 2026: 720 timer Elhub-kWh som
fasit, timepriser fra kvarterarkivet, fasitsum 704,28 kr eks. mva). Telleren
simuleres med jitter på pollintervallet, 20 kjøringer per rad:

| Poll | Jevnt over tid | Snap til sluttintervall | Snap til startintervall |
| --- | --- | --- | --- |
| 5 min | -0,07 .. -0,03 kr (spenn 0,04) | -0,19 .. +0,14 kr (spenn 0,34) | -0,27 .. -0,01 kr (spenn 0,26) |
| 30 min | -0,46 .. -0,05 kr (spenn 0,41) | -0,96 .. +1,32 kr (spenn 2,28) | -1,61 .. +0,59 kr (spenn 2,19) |
| 3 t (gap) | -3,17 .. -0,95 kr (spenn 2,21) | -3,37 .. +7,06 kr (spenn 10,43) | -14,35 .. -0,43 kr (spenn 13,92) |

Kolonnen som avgjør er spennet, for det er prisen på invarianten: hvor mye
avregningen flytter seg når bare polltiden endrer seg. Jevn fordeling er
kontinuerlig i polltid og har et spenn som er en tiendedel av snapping ved lange
gap. Snapping er diskontinuerlig: ett sekunds forskyvning av en poll kan flytte
et helt delta over en intervallgrense.

Jevn fordeling er ikke eksakt heller, og det skal stå: den antar konstant
effekt gjennom hele pollvinduet, mens den ekte effekten skifter ved
timegrensen. Restfeilen er systematisk liten (under 0,07 kr per måned ved
5-minutters poll) og skrumper mot null når pollintervallet er kort. Ved vanlig
drift (poll hvert tiende sekund) er den ikke målbar.

Randtilfeller:

- To avlesninger med samme `observed_at` og ulik teller: vinduet har lengde
  null og kan ikke fordeles. Avlesningen er `avvist`, ikke bokført.
- Negativt delta (målerreset eller kildebytte): ikke bokført, deltaet settes
  til 0 og baseline flyttes. Kilde og hendelse føres i diagnostikken.
- Delta over `MAX_ENERGY_DELTA_KWH`: avvist som i dag, og ført som
  `avregning_avvist_kwh`.

### C2 Invariantene

1. **Bevaring.** Summen av fordelte kWh over intervallene er nøyaktig lik det
   godkjente målerdeltaet (innenfor flyttallsslakk, 1e-9 kWh).
2. **Ingen dobbeltbokføring.** En avlesning identifisert ved
   (`source_identity`, `observed_at`, `value_kwh`) bokføres én gang. Kommer den
   igjen, er den en duplikat og forkastes.
3. **Monotoni i observasjonstid.** En avlesning med `observed_at` eldre enn
   siste behandlede observasjon bokføres ikke på nytt. Den logges som forsinket.
4. **Pris følger energien.** Strømstøtte, Norgespris og energiledd regnes med
   satsene og prisen som gjaldt i energiens eget intervall, aldri med prisen
   som gjelder når pollen skjer.
5. **Aldri null, aldri naboens pris.** Et intervall uten pris får ikke prisen
   0, og ikke prisen fra et annet intervall. Se C4.
6. **Polltidsuavhengighet.** To avspillinger av samme observerte historikk med
   ulike polltidspunkt gir samme avregning når avlesningene er de samme.
   Endres avlesningenes `observed_at`, er historikken en annen.
7. **Restartlikhet.** Samme hendelsesrekke, med eller uten omstart midt i, gir
   samme avregning. Se C5.
8. **Fastledd er utenfor.** Kapasitetsleddet akkumuleres tidsbasert og summerer
   ikke over energiintervaller.

### C3 Sommertid

Fordi intervallene er UTC og halvåpne, er sommertidsskiftene ikke et
spesialtilfelle i fordelingen: UTC-tidslinjen er sammenhengende gjennom begge.
Det som er et spesialtilfelle er merkelappene, og de avgjøres alltid av
`start_utc` omregnet til Europe/Oslo:

| Sak | UTC-intervall | Lokal merkelapp | Fakturamåned |
| --- | --- | --- | --- |
| D1 | 2026-03-29T00:00Z | 2026-03-29 01:00 CET | 2026-03 |
| D2 | 2026-03-29T01:00Z | 2026-03-29 03:00 CEST | 2026-03 |
| D3 | 2026-10-25T00:00Z | 2026-10-25 02:00 CEST | 2026-10 |
| D4 | 2026-10-25T01:00Z | 2026-10-25 02:00 CET | 2026-10 |
| D5 | 2026-03-31T22:00Z | 2026-04-01 00:00 CEST | 2026-04 |

D1 og D2 er vårskiftet: lokal time 02 finnes ikke, og det skal ikke finnes noe
intervall med den merkelappen. D3 og D4 er høstskiftet: to ulike intervaller
har samme lokale merkelapp `02:00`, og de skal holdes fra hverandre av
`start_utc`, aldri av veggklokken. D5 viser at fakturamåneden skifter ved lokal
midnatt, ikke ved UTC-midnatt.

Veggklokke-aritmetikk (`hour`-sammenligning, `utcoffset`-sjekker,
`replace(hour=...)`) hører ikke hjemme i avregningskjernen. Den skal regne i
UTC og be `zoneinfo` om merkelappene.

### C4 Intervaller uten data eller uten pris

Tre ulike ting, som ikke skal blandes:

- **Uten pris**: intervallet har energi, men ingen prisprøve. kWh bokføres i
  intervallet, prisen står `None`, kvaliteten er `uten_pris`, og energien
  summeres synlig i `kwh_uten_pris`. Ingen kroner regnes for den energien, og
  den fylles ikke inn senere. Norgespris-kunder får fortsatt strømdelen sin,
  siden den er fastpris og ikke avhenger av spot; det er spotavhengige beløp
  som står stille.
- **Delvis pris**: intervallet har færre prisprøver enn ventet
  (`pris_prover < pris_prover_ventet`). Prisen er det tidsvektede snittet av
  det som kom, kvaliteten er `delvis_pris`, og energien summeres i
  `kwh_delvis_pris`. Dette er ikke en feil, bare en merket usikkerhet.
- **Uten data**: intervallet har ingen energi bokført. Det finnes da ikke i
  boken. Et hull i boken er ikke null forbruk, og skal ikke vises som det. Er
  hullet forårsaket av at integrasjonen var nede, er det synlig gjennom at
  `avregning_sist_observert` er eldre enn intervallet.

### C5 Omstart

Ved omstart gjenopptas avregningen fra den persisterte boken, ikke fra null:

- Siste behandlede observasjon (`source_identity`, `observed_at`, `value_kwh`)
  leses fra Store og er baseline for neste delta. Er kilden en annen enn den
  lagrede, er deltaet 0 og baseline flyttes (K1).
- Åpne intervaller leses tilbake med sin bokførte kWh og lukkes når tiden
  passerer `slutt_utc`, ikke ved første poll.
- Første poll etter omstart er en helt vanlig avlesning. Den utløser ingen
  varsling i seg selv, og deltaet den bærer fordeles over intervallene det
  faktisk tilhører, ikke inn i timen HA kom opp igjen.
- Er den lagrede observasjonen eldre enn `TPI_STALE_HOURS`, forkastes den, og
  den første avlesningen etter omstart blir ny baseline uten å bokføre noe
  delta. Da mangler intervallene i mellomtiden data (C4, «uten data»), og de
  skal ikke fylles.

### C6 Prøvetabell (normativ)

Radene er fasit for fordelingsregelen. `tests/test_avregningskontrakt.py`
kjører dem, og L1 og L2 skal kjøre dem mot sin egen implementasjon.

| Sak | Fra (UTC) | Til (UTC) | Delta kWh | Fordeling (UTC-start=kWh) |
| --- | --- | --- | --- | --- |
| F1 | 2026-06-15T10:30:00Z | 2026-06-15T10:45:00Z | 0.400 | 2026-06-15T10:00:00Z=0.400 |
| F2 | 2026-06-15T10:45:00Z | 2026-06-15T11:15:00Z | 1.200 | 2026-06-15T10:00:00Z=0.600; 2026-06-15T11:00:00Z=0.600 |
| F3 | 2026-06-15T09:20:00Z | 2026-06-15T12:10:00Z | 8.500 | 2026-06-15T09:00:00Z=2.000; 2026-06-15T10:00:00Z=3.000; 2026-06-15T11:00:00Z=3.000; 2026-06-15T12:00:00Z=0.500 |
| F4 | 2026-06-15T10:00:00Z | 2026-06-15T11:00:00Z | 2.000 | 2026-06-15T10:00:00Z=2.000 |
| F5 | 2026-03-29T00:30:00Z | 2026-03-29T01:30:00Z | 4.000 | 2026-03-29T00:00:00Z=2.000; 2026-03-29T01:00:00Z=2.000 |
| F6 | 2026-10-25T00:30:00Z | 2026-10-25T01:30:00Z | 4.000 | 2026-10-25T00:00:00Z=2.000; 2026-10-25T01:00:00Z=2.000 |

F5 og F6 er de to sommertidsskiftene. At de ser trivielle ut er hele poenget:
i UTC er de vanlige timer, og fordelingen skal ikke merke skiftet.

## D. Persistens og migrering

Lagringsnøkkelen er `entry.entry_id`, som før ([incident
001](../incidents/001-delt-data-mellom-instanser.md)).

Store-versjonene:

| Versjon | Hvem | Innhold |
| --- | --- | --- |
| 1 | dagens utgave | Månedssummer, døgnmakser, akkumulerte kroner. Ingen kildeidentitet, ingen observasjonstid. |
| 2 | K1 | Som v1, pluss `source_identity` og normalisert kWh på baseline. |
| 3 | denne serien | Som v2, pluss `skjema_versjon`, siste behandlede observasjon og åpne intervaller. |

Migrering v2 til v3 er enveis og gjør dette:

- Gamle månedssummer beholdes som **åpningsbalanse** for inneværende måned. De
  får ikke intervallhistorikk, for den finnes ikke og kan ikke rekonstrueres.
- Måneden migreringen skjer i merkes `avregning_ufullstendig: true`. Flagget
  ligger i data-dicten, vises i diagnostikken, og fjernes ved første
  månedsskifte etter migreringen.
- Første avlesning etter migrering blir baseline. Ingen intervaller bokføres
  bakover.
- v2-feltene skrives videre uendret i v3-filen så lenge 1.17-serien lever, slik
  at en nedgradering ikke mister månedsdata. Nedgradering er ellers ikke støttet.

Skjemaversjonen står også i data-dicten (`avregning_skjema`), så en bruker som
rapporterer en feil kan si hvilken bok tallene kom fra.

## Felttabell for data-dicten

Grensesnittet L1, L2, L3a, L3b og L3c bygger mot. Nye felt:

| Felt | Type | Betydning |
| --- | --- | --- |
| `avregning_skjema` | int | Store-skjemaversjon boken ble lest fra (3). |
| `avregning_ufullstendig` | bool | Måneden mangler intervallhistorikk fordi den krysset migreringen. |
| `avregning_sist_observert` | str \| None | ISO UTC for siste behandlede avlesnings `observed_at`. |
| `avregning_kilde` | str \| None | `source_identity` for energikilden boken er ført mot. |
| `avregning_siste_intervall` | str \| None | ISO UTC-start for siste lukkede intervall. |
| `avregning_apne_intervaller` | int | Antall intervaller i boken som ennå ikke er lukket. |
| `avregning_avvist_kwh` | float | kWh forkastet denne måneden (sprang, målerreset, duplikat). |
| `kwh_uten_pris` | float | kWh bokført denne måneden i intervaller uten pris. |
| `kwh_delvis_pris` | float | kWh bokført denne måneden i intervaller med færre prisprøver enn ventet. |

Felt som beholdes med samme navn, men får rettet betydning:

| Felt | Betydning etter denne kontrakten |
| --- | --- |
| `monthly_consumption_dag_kwh` | Sum kWh over avregnede intervaller med `tariff = dag` i måneden, ikke sum av poll-bøtter. |
| `monthly_consumption_natt_kwh` | Tilsvarende for `natt`. |
| `monthly_consumption_total_kwh` | Sum over alle avregnede intervaller i måneden. |
| `current_hour_energy` | kWh bokført i det åpne intervallet, ikke i en veggklokke-bøtte. |
| `daily_cost_kr` | Kroner fra intervaller med lokal dato lik i dag (L3b). |
| `monthly_accumulated_cost_strom_kr` | Kroner fra intervallenes egen pris, ikke fra prisen ved polltid (L3b). |
| `monthly_accumulated_cost_energiledd_kr` | Som over, med satsen som gjaldt i intervallet (L3b). |
| `monthly_accumulated_cost_kapasitetsledd_kr` | Uendret. Fastledd akkumuleres tidsbasert, ikke over energiintervaller. |
| `is_day_rate` | Uendret: tariffen akkurat nå, for visning. Avregningen bruker intervallets egen `tariff`. |

Felt som forsvinner: ingen i denne omgang. L3b og L3c avgjør hva som kan
pensjoneres når kronene flyttes inn i boken.

## Hva denne kontrakten pensjonerer

Punkt 7 og 8 i [begrensninger.md](../begrensninger.md) (gap-bøtte og
øyeblikksprising av gap-forbruk) er beskrivelser av dagens adferd, og begge
brytes av C1 og C2. De skal fjernes derfra når L3a er inne, ikke før.

[statnett]: https://www.statnett.no/en/for-stakeholders-in-the-power-industry/system-operation/the-power-market/quarterly-resolution-and-the-energy-markets/
