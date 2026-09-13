# Kastbar Home Assistant-testlab

Docker-delen av `stromkalkulator-52kpgv4`: offisielt HA-image med frontend,
egen pålogging, templates og helpers som mates av eksisterende BKK-timeverdier.
Hver kjøring får eget Compose-prosjekt, ledig loopback-port og midlertidig config.

## Kjør

Krever Python 3.12+ og Docker med Compose. Docker må være startet på forhånd.
På Apple Silicon emuleres linux/amd64 for å teste samme image som CI.
Hold vertsmaskinen våken hele kjøringen, særlig for `vakthold`: testen måler
ekte varighet, og Docker/HA må fortsette å kjøre under hele utfallet. På macOS
kan `caffeinate -i python3 tests_e2e/run.py vakthold` hindre automatisk dvale
mens kommandoen kjører; la lokket være åpent.

```bash
just test-e2e target=current
```

Bygger **committet HEAD** gjennom `scripts/release_publish.py build` (den
faktiske etterfølgeren til planens `--build-only`), monterer den utpakkede
ZIP-en read-only, kjører scenarioene og stopper containere/nettverk i `finally`.
Ucommittede integrasjonsendringer er ikke med. Velg en annen commit med
`python3 tests_e2e/run.py run --sha <commit>`.

`ci.yml` kaller `e2e.yml` for standardløpet på pull requests og for hver
releasekandidat. Current-E2E er dermed obligatorisk i `release.yml` sin
SHA-bundne port. Den kan også kjøres ved manuell dispatch. Jobben sjekker ut
`github.sha`, og redigert evidens lastes opp som `ha-e2e-current-<SHA>`.
Feil, kansellering, manglende eller hoppet over jobb stopper release.
Docker inngår ikke i pre-push eller vanlig lokal `just test`.
`upgrade` og `vakthold` må kjøres særskilt. Bevar kandidat-SHA,
exit-kode og scenario-trace som dokumentasjon på en fullført kjøring; et
tidlig feilende scenario betyr at etterfølgende scenarioer ikke er prøvd.
Kjør uten pipe til `tail`, eller bruk `set -o pipefail`, slik at testens
exit-kode ikke erstattes av utskriftskommandoens.

Image: `ghcr.io/home-assistant/home-assistant:2026.9.2`, linux/amd64-manifest
`sha256:542890f4a7ef9269b7a5ac23ada303b327537c62fa0f866e49daebc61cb44caa`.
Digest ble lest fra GHCR 13. september 2026. Ved oppgradering må Compose,
imageverdien i `run.py` og current-testmålet vurderes sammen.

## En instans du kan klikke i

```bash
python3 tests_e2e/run.py up
```

Kommandoen skriver URL, lab-mappe og sti til lokal påloggingsfil. Brukeren
heter `testlab`; passordet er tilfeldig generert og står bare i filen.
Instansen lever til `down`. Bruk lab-mappen som ble skrevet ut:

```bash
python3 tests_e2e/run.py replay --run-dir /sti/til/lab
python3 tests_e2e/run.py scenario --run-dir /sti/til/lab --name outage_han
python3 tests_e2e/run.py scenario --run-dir /sti/til/lab --name recover_inputs
python3 tests_e2e/run.py scenario --run-dir /sti/til/lab --name outage_spot
python3 tests_e2e/run.py scenario --run-dir /sti/til/lab --name recover_inputs
python3 tests_e2e/run.py down --run-dir /sti/til/lab
```

`outage_han` gjør effekt og energisensor utilgjengelige; `outage_spot`
fjerner spotverdien. De blir stående slik til recovery, helperen endres i UI,
eller HA restartes. La laben kjøre i virkelige timer for å teste grace/cache
og varsler etter lange utfall. `recover_inputs` gjenoppretter tidligere
states og enheter. Disse manuelle utfallene er ikke automatisk beståtte
tester av flertimersvakten. Et spotutfall ved faktisk døgnskifte må kjøres
over dette skiftet, eller deterministisk i `tests_ha/`.

Helpers er synlige under Utviklerverktøy. Energitellerne har separate
identiteter og beholdes over restart. API-driveren finner template- og
integrasjonsentiteter gjennom registry/unique_id, slik at oversettelser av
navn ikke påvirker testene. Avspillingen bruker timefixturens `p_max_w` som
syntetisk effekt, ikke som eksakt momentan effekt mellom målinger.

## Hva som sjekkes

| Scenario | Påstand |
| --- | --- |
| `test_onboarding` | Ekte DSO-/sensor-flow oppretter entry og null baseline |
| `test_energy_increase` | +1,25 kWh input gir +1,25 kWh i integrasjonen |
| `test_restart_no_double_booking` | Restart beholder totalen; neste økning bokføres én gang |
| `test_meter_change` | Ny fysisk kilde på 50 000 kWh er baseline, ikke forbruk |
| `test_remove_optional` | Options/reload gjør eksport-utdata utilgjengelige |
| `test_invalid_unit_recovery` | Ugyldig enhet reiser repair som forsvinner ved recovery |
| `test_missing_input_recovery` | Slettet energy-state gir ingen falsk energi, recovery virker |
| `test_meter_jump` | +1000 kWh avvises, neste normale økning fungerer |
| `replay` | Hele juni-fixturens energi når frem til HA-integrasjonens total |

En måned spilles komprimert med 0,05 sekunders minstetid per timeverdi.
Batcher begrenses til 25 kWh og venter på HA-totalen før neste batch.
Det tar hensyn til HAs 10 sekunders refresh-debounce og integrasjonens
100 kWh sprangvern, uten å endre noen av dem. HAs ordinære minuttpoll kjører
samtidig. En historisk timepris blir ikke nødvendigvis brukt av en egen
HA-poll; dette er ikke verifisering av historisk spotavregning.

## Oppgraderingsveien fra v1.16.0

```bash
python3 tests_e2e/run.py upgrade            # rundt 15 minutter
python3 tests_e2e/run.py upgrade --fra v1.15.0
```

Installerer den sluppet utgaven først, setter opp to anlegg gjennom dens egen
config-flow, kjører opp akkumulatorene, bytter integrasjonen mens containeren
står stille, og starter igjen. Alt før byttet skjer i den gamle kodens hender,
så lagringsfilen og config-entryene har formen den faktisk skrev. Det er
forskjellen på dette og `tests_ha/test_store_migrering.py`, som mater en
håndbygget etterligning av samme fil.

| Scenario | Påstand |
| --- | --- |
| `test_onboarding_egendefinert` | Egendefinert uten trinntabell settes opp likt i begge utgavene |
| `seed_akkumulatorer` | Forbruk, effekt og kroner på begge anlegg før byttet |
| `test_oppgradering_beholder_akkumulatorene` | 11 akkumulatorsensorer per anlegg tall for tall, og begge entryene lastet |
| `test_baselinen_forkastes_en_gang` | Den kildeløse baselinen gjenopptas ikke og gir ikke falskt forbruk |
| `test_fastleddet_er_et_periodebelop` | `monthly_cost_kr` er samme tall som akkumulert kostnad, og 8 kWh rører ikke fastleddet |
| `test_statistikken_folger_skiftet` | Recorderens sum følger differansen, så skiftet blir ikke lest som en nullstilling |
| `test_egendefinert_uten_fastledd` | Sju kapasitetsavhengige sensorer er Ukjent, resten har tall, og varselet forklarer |
| `test_satsvarsel_kun_ved_avvik` | Katalogsats og egendefinert får ikke satsvarselet |
| `test_satsvarsel_etter_avvik` | En lagret sats som spriker får det, med begge satsene i teksten |

Døgnmaks bokføres først når en klokketime er ferdig, og forrige måned krever
et månedsskifte. Ingen av delene rekker en lab som lever i minutter, så begge
seedes inn i lagringsfilen den gamle utgaven selv skrev, med nøkler som alt
står der. `skriv_lagring` nekter å legge til en nøkkel som ikke fantes: en
seedet nøkkel utgaven aldri skrev, beviser ingenting om hva den skrev.

Størrelsen på fallet i `monthly_cost_kr` hører ikke hjemme her. HA bruker
dagens klokke, så fastleddet blir dagens andel av inneværende måned, ikke
mai sin. De 64 til 145 kronene er målt mot ekte fakturaer i
[docs/research/revalidering-l3b-september-2026.md](../docs/research/revalidering-l3b-september-2026.md).
Laben prøver mekanismen: at de to veiene til månedskostnaden nå er én, og at
fastleddet ikke lenger henger på kilowattimene.

## Vaktholdet i ekte tid

```bash
python3 tests_e2e/run.py vakthold                      # rundt 40 minutter
python3 tests_e2e/run.py vakthold --cache-minutter 95   # rundt 2 timer og 20
```

Ikke med i `just test-e2e`, og skal ikke bli det: grace-vinduet er 30 minutter,
målt på klokken. Skal laben si noe om et ekte utfall, må utfallet vare like
lenge som et ekte et.

Spotcachen på to timer er den ene dyre biten og står av som default.
`--cache-minutter 95` tar den med, og da tar kjøringen over to timer.
Rangeringen mellom `spot_utfall` og utfallsraden er alt voktet i
`tests/test_vakthold.py`, så den lange turen er en slippport framfor noe man
kjører jevnlig.

| Scenario | Påstand |
| --- | --- |
| `test_vakthold_stille_naar_alt_er_friskt` | Null varsler når ingenting er galt |
| `test_maalerbytte_varsler_ikke` | Ny kilde er en baseline, ikke et sprang og ikke et varsel |
| `test_sprang_varsler_med_riktig_sensor` | +1000 kWh avvises, varselet navngir telleren og tallet |
| `test_vakthold_tier_rett_etter_omstart` | Tom spotcache ved oppstart varsler ikke |
| `test_vakthold_tier_innenfor_grace` | Et utfall innenfor grace-vinduet varsler ikke |
| `test_vakthold_varsler_etter_grace` | `input_utfall` navngir effekt, energi og spotpris |
| `test_vakthold_spot_utlopt` | `spot_utfall` tar over, og spot står ikke også i utfallsvarselet (kun med `--cache-minutter`) |
| `test_vakthold_delvis_friskmelding` | Teksten skrives om, varselet blir stående |
| `test_vakthold_friskmelding` | Alle vaktholdsvarsler forsvinner |
| `test_frossen_teller_varsles` | Telleren svarer men står stille, og varselet peker på den |
| `test_strombrudd_er_ikke_frossen_teller` | Samme alder, men HA var av i gapet: ingen varsel |

Template-sensorene i laben gjenoppstår ved omstart, så en omstart midt i et
utfall friskmelder inputene. Omstartsvakten prøves derfor for seg, før
utfallet. Frossen teller og strømbrudd seedes gjennom lagringsfilen, for begge
handler om hva `last_energy_increase` og `last_update` sto på da HA startet.

Sommertid prøves ikke her. Laben kan ikke flytte klokken, og
`tests/test_dst_overgang.py` eier begge overgangene med kontrollert tid.

### Oppstart etter restart

`Driver.ready()` venter etter autentisering på både `/api/config` med
`state == "RUNNING"` og hovedentiteten for hvert lagrede anlegg. API-et kan
svare før dette; en tidligere driver sendte da `update_entity` mens entiteten
ikke fantes. Det ga «Entity … not found» og kunne la frossen-scenarioet lese en
tom varselliste (stromkalkulator-516lois).

Denne readiness-sjekken er en del av alle scenarioer etter restart. En endring
her skal verifiseres med full `vakthold`, inkludert
`test_strombrudd_er_ikke_frossen_teller`; manuell ekstra venting er ikke
tilstrekkelig bevis.

## To forskjellige avstemminger

`report.json` viser både kilderegnskapet og det HA faktisk bokførte:

- Juni-fixturen: 1033,626 kWh; faktura: 1033,628 kWh.
- Historisk dag: 590,682 mot 590,646 kWh; natt: 442,944 mot 442,982 kWh.
- Kildeavvikene på −2/+36/−38 Wh vises, med 10 Wh total- og 50 Wh split-toleranse.
- HA-totalens **økning** må matche de sendte kWh innen 2 Wh.
- HA-dag/natt rapporteres på dagens klokke. `historical_ha_tariff_verified`
  står derfor alltid `false`.

Referansen er juni-transkripsjonen i `tests/test_faktura_bkk.py`,
`FAKTURA_JUNI_2026`. Juni har ingen norske helligdager, så kildekontrollen
gjør en uavhengig ukedag/klokkeslett-split uten å kopiere tariffmotoren.
Referansen gjelder bare juni. Andre checked-in `bkk_*_hourly.json` kan velges
med `up --fixture <navn>`; deres fakturareferanse merkes uverifisert, og
replay avbryter tydelig ved kildehull.

Dette oppfyller ikke en bokstavelig påstand om at komprimert HA-dag/natt
matcher en historisk faktura: det krever styrt tid eller historiske
avregningsinnganger. Kronefasit, tariffskifte, DST, månedsskifte og årsskifte
hører fortsatt til deterministisk replay og ekte-HA-testene.

## Personvern og opprydding

Rå fixture-metadata monteres aldri: `fixture.py` kopierer kun tidsstempel,
kWh, spotpris og effekt til en midlertidig JSON-fil. Fakturanummer,
kildesensornavn, målerens absolutte startstand og `_private/` følger ikke med.
Den syntetiske telleren starter på 10 000 kWh. Repoet monteres heller ikke
inn; bare `tests_e2e/`, den utpakkede ZIP-en og de rensede timene.

Evidens lagres i gitignorede `tests_e2e/artifacts/<prosjekt>/`: begrenset og
redigert HA-logg, navngitt scenario-trace, versjonsinfo og eventuell rapport.
Config, auth-fil og HA storage beholdes bare i den lokale midlertidige
mappen og lastes aldri opp i CI. `down` sletter ikke disse filene, så feil
kan undersøkes; mappen kan senere slettes av eieren.

`e2e.yml` har 28 minutters kjøregrense, 35 minutters totalgrense og et
`always()`-steg som stopper jobbens prosjekt. Forventet tid er 10–20 minutter
på varm cache. Lokalt current-løp 13. september 2026 brukte omtrent 10 minutter
fra bootstrap til 720 avspilte timer og bestod alle scenarioene. En separat
tvunget feil bekreftet opprydding av både containere og nettverk; de øvrige
Docker-prosjektene fortsatte å kjøre. Eksportert evidens fra begge kjøringer
ble kontrollert for testlabens passord og token, uten treff. GitHub-jobben
er ennå ikke verifisert i CI.
Hard terminering av Docker-daemonen kan hindre cleanup; kjør `down` etterpå.

## Verifiser harnesset

```bash
python3 -m unittest discover -s tests_e2e -p 'test_*.py' -v
python3 tests_e2e/run.py run --force-failure
```

Den første kjører uten Docker og tester kildeavstemming, metadatafilter,
prosjektavgrensning, redigering og cleanup ved feil/evidensfeil.
Den andre feiler med vilje etter server-onboarding, før scenarioene: kontroller at `docker compose ls`
ikke viser prosjektet, og at bare redigert evidens ligger i artifacts.
Offline cleanup-tester beviser ikke faktisk containeropprydding;
den tvungne live-feilen må også kjøres.

API-kontraktene følger HAs [REST API](https://developers.home-assistant.io/docs/api/rest/)
og [WebSocket API](https://developers.home-assistant.io/docs/api/websocket/).
Onboarding/config-flow er kontrollert mot installert current-kilde.
