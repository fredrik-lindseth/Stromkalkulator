# Kastbar Home Assistant-testlab

Docker-delen av `stromkalkulator-52kpgv4`: offisielt HA-image med frontend,
egen pålogging, templates og helpers som mates av eksisterende BKK-timeverdier.
Hver kjøring får eget Compose-prosjekt, ledig loopback-port og midlertidig config.

## Kjør

Krever Python 3.12+ og Docker med Compose. Docker må være startet på forhånd.
På Apple Silicon emuleres linux/amd64 for å teste samme image som CI.

```bash
just test-e2e target=current
```

Bygger **committet HEAD** gjennom `scripts/release_publish.py build` (den
faktiske etterfølgeren til planens `--build-only`), monterer den utpakkede
ZIP-en read-only, kjører scenarioene og stopper containere/nettverk i `finally`.
Ucommittede integrasjonsendringer er ikke med. Velg en annen commit med
`python3 tests_e2e/run.py run --sha <commit>`.

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
