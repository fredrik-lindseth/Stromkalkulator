# HAN-målinger og fakturagrunnlag

Home Assistant mottar måleverdier fra en HAN-leser. Elhub leverer nettselskapets registrerte intervallforbruk, som brukes ved fakturering. Bruk [Elhub-data](elhub-api.md) som grunnlag for fakturakontroll, og HAN-data til å kontrollere hva integrasjonen faktisk har mottatt.

## Tidspunktet for målingen

Tidspunktet en verdi gjelder for og tidspunktet Home Assistant mottar den er ikke nødvendigvis det samme. Kaifa og Aidon beskriver timesverdier som dannes ved hel time og sendes på HAN-porten ti sekunder senere. Kamstrups HAN-NVE-grensesnitt oppgir utsending fem sekunder etter timegrensen.[^kaifa][^aidon][^kamstrup]

I referanseoppsettet med Kaifa MA304H3E og Pow-U fra AMSleser.no registreres timesverdiene rundt tretten sekunder etter hel time. Dette er målt for det oppsettet og skal ikke brukes som standard for andre lesere. Nettverk, MQTT og lagring kommer i tillegg til målerens utsendingstid.

Målerens utsendingstid gjør ikke tidsstemplene i Elhub feil. Bruk måletiden når den er tilgjengelig, og behold tidssone og UTC-offset gjennom eksport og sortering. Ved overgang til vintertid er to lokale kl. 02 ulike timer.

## Forbruk fra recorderen

`export_invoice_hourly.py` bruker differansen i den kumulative energitelleren (`tpi`, OBIS 1-0:1.8.0) som forbrukskilde. Recorderens aggregering og mottakstid kan flytte små energimengder mellom nabotimer. Det kan påvirke dag/natt-splitt, topptimer og prising selv om månedstotalen nesten er uendret.

`verify_invoice_hourly.py` har `--shift-seconds` for korreksjon av en kjent forskyvning. Standardverdien er 13 sekunder for referanseoppsettet. Korreksjonen er et anslag basert på nabotimenes forbruk; den rekonstruerer ikke manglende målinger. Bruk den bare med kjent måletiming, og sammenlign med Elhub. Se [valg av tidsforskyvning](../../fakturaer/verifiser-din-faktura.md#5c-velg-riktig---shift-seconds).

For eksakt Norgespris-avstemming brukes Elhubs intervallforbruk sammen med [endelige spotpriser](../priser/norgespris-eksakt-match.md). En riktig månedstotal i kWh er ikke nok når timefordelingen avviker.

## Integrasjonens input

Strømkalkulator kan bruke kumulativ energi eller beregne energi fra effekt over tid. Måletid, manglende data og fordeling over intervaller følger [input-kontrakten](../../kontrakter/input-og-konfig.md) og [avregningskontrakten](../../kontrakter/avregning.md). En tidskorreksjon i fakturaskriptet er ikke en innstilling som automatisk endrer integrasjonens løpende bokføring.

Forbruk fra en annen måler eller HAN-leser må kontrolleres med dens tidsstempler og egne fakturaer. Behold kvalitetsmerking fra Elhub og kildeinformasjon når data brukes til å fylle hull. [Månedsprosedyren](../../fakturaer/neste-maaned-prosedyre.md) beskriver eksport, utfylling og anonymisering.

## Målerspesifikasjoner

[Spesifikasjonsoversikten](specifications/README.md) inneholder lokale kopier og kildehenvisninger for Kaifa, Aidon og Kamstrup. Velg dokumentet som gjelder målerens modell og grensesnitt.

[^kaifa]: [Kaifa KFM_001](specifications/kaifa-kfm-001.pdf).
[^aidon]: [Aidon RJ45 HAN Interface v1.6](specifications/aidon-rj45-han-interface-v1.6-EN.pdf).
[^kamstrup]: [Kamstrup HAN-NVE Interface rev. 3.1](specifications/kamstrup-han-nve-rev3.1.pdf).
