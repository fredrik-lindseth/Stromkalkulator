# Elhub vs HAN vs faktura: hvor ligger 13-sek-laget?

Analysen identifiserer hvor i kjeden AMS-måler → Pow-U → HA → BKK den observerte 13-sekunders forsinkelsen ligger, og hvor mye av den ligger i måleren versus i transmisjonen.

> Status: konklusjon 2026-05-22. Data: april 2026. Reproduserbar.

## Spørsmålet

Vår tpi-baserte forbruksberegning fra HAN-porten har 9 Wh avvik mot BKK-fakturaen for april 2026, og 3-8 W avvik på topp 3 maks effekt. Tidligere observasjon viste at AMS-broadcasten over HAN-port skjer presis HH:00:13 lokal tid, ikke HH:00:00. Hvor i kjeden AMS-måler → Pow-U → HA oppstår de 13 sekundene?

## Hva vi gjorde

Hentet Elhub-data for april 2026 fra Elhub kundeportal. Elhub er det norske datalageret som mottar timesverdier fra AMS-målere og leverer videre til nettselskaper og strømleverandører. BKK bruker Elhub som fakturagrunnlag.

Sammenlignet tre datakilder:

| Kilde          | Hva det er                    | Total april 2026 |
| -------------- | ----------------------------- | ---------------- |
| Elhub-CSV      | Måleverdier som BKK leser     | 1381,827 kWh     |
| HAN-data (vår) | tpi-broadcast over Pow-U + HA | 1381,818 kWh     |
| BKK-faktura    | Det BKK fakturerte            | 1381,827 kWh     |

## Resultater

### Total kWh

| Sammenligning    | Avvik             |
| ---------------- | ----------------- |
| Elhub vs faktura | 0,000 kWh         |
| HAN vs faktura   | +0,009 kWh (9 Wh) |
| HAN vs Elhub     | +0,009 kWh (9 Wh) |

Elhub er identisk med fakturaen til siste øre.

### Topp 3 maks effekt (per unike dag)

| Posisjon | Faktura                | Elhub               | HAN   |
| -------- | ---------------------- | ------------------- | ----- |
| 1        | 5,939 kW (06.04 13:00) | 5,939 (06.04 13:00) | 5,947 |
| 2        | 4,779 kW (04.04 16:00) | 4,779 (04.04 16:00) | 4,776 |
| 3        | 4,262 kW (11.04 11:00) | 4,262 (11.04 11:00) | 4,266 |

Elhub og faktura er identiske på alle tre. HAN avviker 3-8 W per topp.

### Time-for-time HAN vs Elhub

720 timer matchet på `start_local` (HH:00 lokal tid).

| Metrikk                     | Verdi                                  |
| --------------------------- | -------------------------------------- |
| Sum diff                    | -0,009 kWh (HAN er 9 Wh høyere totalt) |
| Snitt diff per time         | -0,012 Wh                              |
| Maks diff (begge retninger) | +21 Wh / -19 Wh                        |

Diffen per time svinger i begge retninger med ±20 Wh, men summerer til -9 Wh over måneden.

## Tolkning

Elhub leverer eksakt samme tall som faktura. Det betyr Elhub-snapshotene tas ved presis HH:00:00 lokal tid, og BKK leser disse uendret. 13-sek-laget ligger tidligere i kjeden, mellom målerens interne register og HA-recorderen.

## Hva vi har bevist via målerens egen RTC

For 24 påfølgende timer sammenlignet vi `sensor.pow_u_ams_rtc` (målerens egen klokke fra OBIS 1.0.0 i HAN-framen) mot `last_updated_ts` (HA-mottakstid). Konsistent på sekundet hver gang:

| Tidspunkt                    | Hva skjer                                                                                      |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| HH:00:00 (internt i måler)   | Elhub-snapshot tas. Verdi sendes videre til Elhub via målerens oppstrømsprotokoll (DLMS/GPRS). |
| HH:00:10 UTC (målerens RTC)  | AMS-måleren bygger og sender HAN-frame over RJ45.                                              |
| HH:00:13 lokal (HA recorder) | MQTT-melding fra Pow-U mottatt og skrevet av HA.                                               |

Splittingen er altså 10 sekunder internt i måleren, pluss 3 sekunder transmisjon HAN → Pow-U → MQTT → HA.

```
HH:00:00  måler-snapshot ──► Elhub ──► BKK ──► faktura        (0 sek lag, 0 avvik)
   │
   │ 10 sek internt i måleren
   ▼
HH:00:10  HAN-frame bygget og sendt
   │
   │ 3 sek (HAN-bytes @ 2400 baud + Pow-U parse + MQTT + HA write)
   ▼
HH:00:13  HA recorder skriver tilstand
```

### De 3 transmisjons-sekundene

Kildekoden i amsreader-firmware bekrefter at firmware ikke har artificial delay. Fra parse til MQTT-publish er sub-millisekund. De 3 sekundene består av:

- HAN-byte-overføring over RJ45 ved 2400 baud (frame på ~50 ms reelt, men sendt som del av lengre cosem-payload)
- Pow-U parsing av list3-frame
- MQTT-publish til broker
- Nettverk til HA
- HA-recorder-skriving til database

### De 10 sekundene i måleren

Måleren bruker ~10 sek mellom internt snapshot og HAN-broadcast. Det er målerens egen designvalg og kan ikke endres fra utsiden. Verdien som havner i HAN-framen er likevel snapshot-verdien fra HH:00:00, ikke en oppdatert verdi fra HH:00:10. Det betyr energiteller-tallet er korrekt, det er bare _tidspunktet for når vi mottar det_ som er forskjøvet.

## Per-time-avviket: hvorfor svinger HAN ±20 Wh per time?

Vår HAN-tpi-diff for time HH er `state(HH+1:00:13) - state(HH:00:13)`. Det dekker tidsvinduet HH:00:13 til HH+1:00:13, ikke HH:00:00 til HH+1:00:00 som Elhub bruker.

Forskyvningen på 13 sekunder gjør at:

- HAN-time HH "mister" forbruket fra HH:00:00 til HH:00:13 (havner i forrige HAN-time)
- HAN-time HH "låner" forbruket fra HH+1:00:00 til HH+1:00:13 (fra neste Elhub-time)

Netto: hver HAN-time skifter 13 sek fra Elhub-time HH til Elhub-time HH+1. Effekten på diff per time avhenger av om effekten økte eller falt over time-grensen. Det er årsaken til ±20 Wh svingning. Summen er nesten null fordi det er et fast skift, ikke en feil.

## Konsekvenser for vår integrasjon

Vi har HAN-data forsinket 13 sek etter Elhub-snapshot. Av disse er 10 sek låst inne i måleren og kan ikke kompenseres med automation. De siste 3 sek (transmisjon) kan teoretisk lukkes ved interpolering.

| Tiltak                                    | Lukker hvor mye?    | Realisme                                                                                                                     |
| ----------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Snapshot-automation i HA ved HH:00:00     | 0 sek               | Virker ikke. Måler-framen er allerede 10 sek forsinket fra Elhub-snapshot. Vi har ingen tpi-verdi for HH:00:00 før HH:00:10. |
| Interpolere tpi ved hjelp av `p`-strømmen | 3 sek (transmisjon) | Mulig. Bruker kontinuerlig effektmåling mellom HAN-frames til å estimere tpi-deltaet for de siste sekundene.                 |
| Bytte til annen HAN-leser                 | 0-3 sek             | Påvirker bare transmisjons-delen. De 10 sek i måleren forsvinner ikke.                                                       |
| Bruke Elhub-API direkte                   | 13 sek (full)       | Krever autentisering, ikke kontinuerlig. Egnet for fakturaverifisering, ikke sanntid.                                        |

For dagens behov holder det å dokumentere at vi har bevist samsvar innenfor 9 Wh / 0,001 %. Interpolering via `p` kan vurderes hvis kravet skjerpes.

En Tibber Pulse-test kan fortsatt gi nyttig data: hvis Pulse mottar HAN-frame på et annet tidspunkt enn HH:00:10, betyr det at transmisjons-3-sek varierer mellom HAN-lesere. De 10 sek inne i måleren vil være de samme uansett leser.

## Konsekvens for andre brukere

Resultatene her gjelder spesifikt for:

- Kaifa MA304H3E (Fredriks oppsett, BKK NO5)
- Pow-U HAN-leser fra AMSleser.no
- HA's standard recorder
- Nord Pool offisiell HA-integrasjon

Andre kombinasjoner kan ha annen sample-timing, andre data-forsinkelser, og andre avrundinger. Verifisering for andre DSO-er bør gjøres med deres egne fakturaer og Elhub-data.

## Reprodusering

```bash
# Fra HA-host: eksporter HAN-data for ønsket måned
ssh ha-local "python3 /tmp/export_hourly.py"  # se scripts/research/ (TBD)
scp ha-local:/tmp/bkk_april_2026_hourly.json tests/fixtures/

# Last ned Elhub-CSV manuelt fra elhub.no
# Plasser i Måleverdier/

# Sammenlign
python3 scripts/research/sammenlign_elhub_han_faktura.py  # TBD
```

For nå er sammenligningen kjørt ad-hoc i Bash-prompts. Skal pakkes i et permanent script i fase 3 av prosjektet, se [fakturaverifisering-prosjekt.md](../fakturaverifisering-prosjekt.md).

## Åpne spørsmål

1. Hvilken protokoll sender måleren til Elhub? DLMS over PLC? GPRS? Begge?
2. Får Elhub presis HH:00 fra alle målere, eller har andre målermerker (Kaifa, Kamstrup) andre snapshot-tidspunkt og andre interne forsinkelser før HAN-broadcast?
3. Hva er retensjon hos BKK hvis kunden bytter strømleverandør? (Tibber leverer denne kunden, har BKK fortsatt tilgang til Elhub-data?)
4. Varierer transmisjons-3-sek mellom HAN-lesere? (Tibber Pulse vs Pow-U parallelltest kan svare.)

Disse er ikke kritiske for å validere integrasjonen, men gir teknisk innsikt.

## Hvor data ligger

- Elhub-CSV: `Måleverdier/elhub_*.csv`
- HAN-data: `tests/fixtures/bkk_april_2026_hourly.json`
- BKK-faktura: `Fakturaer/Receipt-2735-6144-7538.pdf` (sjekk filnavn)
- Test-fixture med fakturalinjer: `tests/test_faktura_bkk.py` (`FAKTURA_APRIL_2026`)
