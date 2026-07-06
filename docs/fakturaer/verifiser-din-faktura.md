# Verifiser at integrasjonen regner riktig for ditt nettselskap

Når du bekrefter at fakturaen din matcher integrasjonens beregninger, fungerer det som en attest for alle som bruker samme nettselskap. Foreløpig er kun BKK (NO5) verifisert mot ekte fakturaer. Hjelp oss verifisere resten.

Denne guiden tar deg gjennom verifiseringen steg for steg, uansett hvilken AMS-måler, HAN-leser eller DSO du har.

## 1. Hva er forventet avvik?

Integrasjonen treffer fakturaen innenfor disse toleransene:

| Linje                                             | Forventet avvik                |
| ------------------------------------------------- | ------------------------------ |
| Månedstotal forbruk                               | 0 til 50 Wh                    |
| Energiledd, avgifter, kapasitetsledd, strømstøtte | inntil 0,02 kr                 |
| Norgespris-kompensasjon                           | inntil 0,05 % (foreløpige priser i HA) |

Større avvik enn dette tyder på reell feil i satser, konfigurasjon eller hardware-oppsett.

## 2. Sjekk integrasjonens tall først

1. Åpne Home Assistant og finn enheten "Forrige måned" (en del av integrasjonen).
2. Trykk på knappen `Lag faktura-rapport`.
3. En notifikasjon dukker opp med ferdig utfylt rapport.
4. Kopier rapporten og sammenlign linje for linje mot fakturaen din.

Hvis alle linjer er innenfor toleransene i tabellen over, er du ferdig. Send rapporten inn som verifisering (se [seksjon 7](#7-send-inn-verifiseringen)).

## 3. Dokumenter hardware-oppsettet ditt

Hvis du finner avvik, noter ned følgende før du går videre. Du trenger informasjonen for både feilsøking og for å sende inn issue.

| Felt              | Hvor finner du det                                             |
| ----------------- | -------------------------------------------------------------- |
| DSO (nettselskap) | "Mine sider" hos nettselskapet                                 |
| Prisområde        | NO1 til NO5, står på fakturaen                                 |
| Avgiftssone       | Standard / Nord-Norge / Tiltakssonen, står på fakturaen        |
| Målermerke        | Frontpanelet på AMS-måleren (Aidon, Kaifa, Kamstrup, ...)      |
| Målermodell       | Typenummer, samme sted                                         |
| HAN-leser         | Pow-U, Tibber Pulse, Tibber Bridge, ESPHome AMS, ...           |
| Spot-integrasjon  | Offisiell `nordpool`, custom_components/nordpool, manuell, ... |
| Avtaletype        | Spotpris + strømstøtte, Norgespris, fastpris, ...              |

## 4. Verifiser kilden med Elhub

Elhub har de offisielle timesverdiene som DSO fakturerer på. Sammenligning mot Elhub viser om avviket sitter hos HAN-leseren eller hos DSO.

1. Logg inn på [elhub.no](https://elhub.no) med BankID.
2. Velg "Min side" og last ned timesverdier (CSV) for fakturaperioden.
3. Sammenlign Elhub-totalen mot fakturaen din:

| Resultat                     | Konklusjon                                            |
| ---------------------------- | ----------------------------------------------------- |
| Elhub matcher fakturaen      | Avviket sitter hos HAN-leseren din, ikke hos DSO      |
| Elhub matcher ikke fakturaen | Kontakt DSO, det er sannsynligvis en faktureringsfeil |
| Elhub matcher HA-tallene     | HAN-leseren er presis, problemet ligger andre steder  |

## 5. Verifiseringsskript for utviklere

Hvis du vil dykke i timesnivå, finnes det et Python-skript som reproduserer hele BKK-beregningen fra rå timesdata.

### 5a. Eksporter timesdata fra Home Assistant

```bash
ssh ha-local "python3 /config/scripts/export_invoice_hourly.py \
    --start 2026-04-01 \
    --end 2026-05-01 \
    --output /config/timesdata_april_2026.json"
```

Se [`scripts/research/export_invoice_hourly.py`](../../scripts/research/export_invoice_hourly.py) for tilpasning til ditt oppsett.

### 5b. Kjør verifiseringen lokalt

```bash
git clone https://github.com/fredrik-lindseth/Stromkalkulator hacs-strømkalkulator
cd hacs-strømkalkulator
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/dine_timesdata.json \
    --faktura april_2026 \
    --shift-seconds 13
```

### 5c. Velg riktig `--shift-seconds`

HAN-broadcast kommer noen sekunder etter timeskifte. Parameteren kompenserer for dette og avhenger av målermerke og HAN-leser.

| Kombinasjon                | Foreslått `--shift-seconds` |
| -------------------------- | --------------------------- |
| Kaifa + Pow-U              | 13                          |
| Aidon + Pow-U              | 13                          |
| Kamstrup + Pow-U           | 8                           |
| Tibber Pulse (alle målere) | 0 til 5, eksperimenter      |
| Tibber Bridge              | 0 til 5, eksperimenter      |
| ESPHome AMS                | 0 til 10, eksperimenter     |
| Andre kombinasjoner        | 0 til 15, eksperimenter     |

Test flere verdier og se hvilken som gir lavest avvik på månedstotalen.

## 6. Sensorer for direkte sammenligning

Hvis du heller vil sammenligne sensorer direkte mot fakturaen, bruk denne tabellen.

| Sensor                                          | Fakturalinje                           |
| ----------------------------------------------- | -------------------------------------- |
| `sensor.energiledd_dag`                         | Energiledd dag                         |
| `sensor.energiledd_natt_helg`                   | Energiledd natt/helg                   |
| `sensor.forbruksavgift`                         | Forbruksavgift                         |
| `sensor.enovaavgift`                            | Enovaavgift                            |
| `sensor.kapasitetstrinn`                        | Kapasitet X-Y kW                       |
| `sensor.kapasitetstrinn_nummer`                 | Trinn-nummer (1, 2, 3, ...)            |
| `sensor.manedlig_forbruk_norgespris_besparelse` | "Spart med Norgespris" på "Mine sider" |

Alle sensorer har attributtene `eks_mva`, `inkl_mva` og `ore_per_kwh_eks_mva`. Sensor-navn kan ha suffiks (`_2`, `_3` osv.) hvis du har flere instanser.

For Nord-Norge: spotpris og avgifter er mva-fri. For tiltakssonen: ingen forbruksavgift.

## 7. Send inn verifiseringen

### Hvis det stemmer (vanligste utfall)

Lag et issue på Forgejo eller GitHub og bruk malen i [`.forgejo/issue_template/faktura-verifisering.md`](../../.forgejo/issue_template/faktura-verifisering.md). Eller send en PR med en ny verifiseringsrapport, kopier strukturen fra [bkk-april-2026.md](bkk-april-2026.md).

Vi trenger:

- Nettselskap og prisområde
- Periode
- Forbruk per kategori (dag, natt/helg, totalt)
- Pris og beløp per fakturalinje
- Kapasitetstrinn
- MVA-sats
- Avtaletype (spot, Norgespris, fastpris)
- Hardware-oppsett fra [seksjon 3](#3-dokumenter-hardware-oppsettet-ditt)

Du krediteres i [referanse.md](referanse.md) med fornavn eller alias.

### Hvis du finner reelt avvik

Lag et issue med:

- Konkrete tall (din beregning vs faktura, avvik i kr og Wh)
- Hardware-oppsett fra [seksjon 3](#3-dokumenter-hardware-oppsettet-ditt)
- Anonymisert faktura-bilde (fjern navn, adresse, kundenummer, KID)
- Output fra `verify_invoice_hourly.py` hvis du har kjørt det
- Resultat fra Elhub-sammenligningen hvis du har gjort den

### Personvern

Ikke ta med:

- Navn, adresse, kundenummer, fakturanummer
- KID, kontonummer, betalingsinfo
- Strømleverandør (kraftleveranse er separat)

## 8. Vanlige avvik og hva de betyr

| Avvik                                   | Sannsynlig årsak                                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Energiledd avviker i sats               | `dso.py`-verdier er utdatert, send inn for å få fikset                                                  |
| Energiledd avviker i forbruk            | Tariff-bytte (dag/natt) skjer feil, sjekk helligdager og `helg_som_natt`                                |
| Forbruksavgift avviker                  | Avgiftssone er feil konfigurert (Nord-Norge vs Sør-Norge)                                               |
| Kapasitetsledd avviker                  | Trinn-grenser i `dso.py` er feil, eller forbruksmønster brytes ned annerledes                           |
| Strømstøtte avviker (2025-fakturaer)    | Terskel eller dekningsgrad har endret seg                                                               |
| Månedstotal avviker med > 50 Wh         | HAN-leser-shift, prøv andre `--shift-seconds`-verdier                                                   |
| Norgespris-kompensasjon avviker > 0,2 % | Spotpris-håndtering (eks/inkl. mva), se [incident 004](../incidents/004-spotpris-mva-feilbehandling.md). Avvik på 0,04-0,05 % er normalt: HA-recorderen kan ha foreløpige priser, se [research/norgespris-eksakt-match.md](../research/norgespris-eksakt-match.md) |

## Eksisterende verifikasjoner

Se [referanse.md](referanse.md) for oppdatert liste over verifiserte nettselskap og perioder.
