# Verifiser at integrasjonen regner riktig for ditt nettselskap

**Det viktigste utfallet av en verifisering er at det stemmer.** Hver gang en bruker bekrefter at fakturaen matcher integrasjonens beregninger, er det en attest på at dette regner riktig. Ikke bare for deg, for alle som bruker integrasjonen for samme nettselskap.

Foreløpig er kun BKK (NO5) verifisert mot ekte fakturaer. Resten av landet stoler på satser fra nettselskapenes prislister, men har ikke hatt en faktisk faktura å sammenligne mot. Hjelp oss endre det.

## Hva du oppnår ved å verifisere

- **Bekreftelse for ditt nettselskap**, andre brukere ser at noen har stress-testet beregningene mot en ekte faktura
- **Synlig kreditt**, ditt nettselskap legges til i [REFERANSE.md](REFERANSE.md) med periode og dato (du krediteres med fornavn eller alias hvis du vil)
- **Skikkelig feilretting hvis noe avviker**, sjeldent, men da vet vi nøyaktig hva som må fikses

## Sånn gjør du det

### 1. Hent fakturaen din

Logg inn på "Mine sider" hos nettselskapet ditt og finn en månedsfaktura. Du trenger linjer for:

- Energiledd (dag og natt/helg, eventuelt flat)
- Forbruksavgift
- Enovaavgift
- Kapasitetsledd (eller "fastledd", varierer mellom selskap)
- Eventuelt strømstøtte eller Norgespris-kompensasjon

### 2. Sjekk satsene mot `dso.py`

Åpne [`custom_components/stromkalkulator/dso.py`](../../custom_components/stromkalkulator/dso.py) og finn ditt nettselskap. Verdiene `energiledd_dag_eks_mva` og `energiledd_natt_eks_mva` er **ren energiledd**, uten forbruksavgift, Enova eller mva. Coordinator legger på avgiftene basert på avgiftssone.

For å sammenligne med fakturaen din:

```
sluttpris (inkl. alt, øre/kWh) = (energiledd_eks_mva + 0.0713 + 0.01) * 1.25 * 100
```

**Eksempel (BKK 2026, Sør-Norge):**

```
energiledd_dag_eks_mva = 0.2877 NOK/kWh = 28.77 øre
+ forbruksavgift 7.13 + Enova 1.0 = 36.90 øre eks. mva
* 1.25 (mva)                       = 46.12 øre/kWh inkl. alt
```

For Nord-Norge: hopp over `* 1.25` (mva-fritak). For tiltakssone: hopp over forbruksavgift også (kun Enova).

Hvis fakturaen viser pris eks. mva, kan du sammenligne direkte mot `eks_mva`-attributtet på sensorene.

### 3. Sammenlign linje for linje

Bruk denne malen for hver fakturalinje:

| Priselement     | Forbruk (kWh)  | Pris (øre/kWh) | Faktura (kr) | Vår beregning (kr) | Avvik |
| --------------- | -------------- | -------------- | ------------ | ------------------ | ----- |
| Energiledd dag  |                |                |              | forbruk \* pris    |       |
| Energiledd natt |                |                |              | forbruk \* pris    |       |
| Forbruksavgift  |                |                |              | forbruk \* pris    |       |
| Enovaavgift     |                |                |              | forbruk \* pris    |       |
| Kapasitetsledd  | (antall dager) | (kr/mnd)       |              | kr/mnd             |       |

Avrundingsavvik på 0.01-0.05 kr per linje er normalt og forventet.

### 4. Sammenlign mot integrasjonens sensorer

Etter en hel måned bør disse sensorene matche fakturaen:

| Sensor                          | Sammenlign mot                 |
| ------------------------------- | ------------------------------ |
| `sensor.energiledd_dag`         | Pris på "Energiledd dag"       |
| `sensor.energiledd_natt_helg`   | Pris på "Energiledd natt/helg" |
| `sensor.forbruksavgift`         | Pris på "Forbruksavgift"       |
| `sensor.enovaavgift`            | Pris på "Enovaavgift"          |
| `sensor.kapasitetstrinn`        | Linje "Kapasitet X-Y kW"       |
| `sensor.kapasitetstrinn_nummer` | Hvilket trinn (1, 2, 3, …)     |

Sensor-navn kan ha suffix (`_2`, `_3` osv.) hvis du har flere instanser av integrasjonen.

Hver sensor har attributtene `eks_mva`, `inkl_mva` og `ore_per_kwh_eks_mva` for direkte fakturasammenligning.

### 5. For Norgespris-kunder

Norgespris-kompensasjonen er en separat linje på fakturaen. Selve fastprisen er 50 øre/kWh inkl. mva i Sør-Norge (40 øre i Nord-Norge/tiltakssonen).

Kompensasjonsraten varierer per måned basert på spotpris. Du kan utlede gjennomsnittlig spotpris fra fakturaen:

```
spotpris-snitt (øre/kWh inkl. mva) = 50 + |kompensasjon-rate i øre|
```

### 6. Sjekk det fakturaen IKKE viser

Selve nettleie-fakturaen viser ikke kraftpris (det går via strømleverandøren), så den fanger ikke feil i spotpris-håndtering, strømstøtte eller Norgespris-besparelse. Disse må sjekkes separat ved å sammenligne integrasjonens egne sensorer mot tilsvarende tall fra nettselskapet eller strømleverandøren.

**For Norgespris-kunder:** logg inn på "Mine sider" hos nettselskapet og finn "spart med Norgespris hittil i [måned]". Sammenlign med `sensor.manedlig_forbruk_norgespris_besparelse`. Avvik over 10 % tyder på en bug i mva-håndtering eller spotpris-input. Se [incident 004](../incidents/004-spotpris-mva-feilbehandling.md) for hva slags feil dette har avdekket før.

**For spot-kunder:** sammenlign `sensor.totalpris_inkl_avgifter` mot snittprisen strømleverandøren rapporterer (f.eks. Tibber). Forventet avvik er små rundinger.

**For plusskunder:** verifiser at `monthly_export_revenue_kr` matcher det strømleverandøren utbetaler. Kraftleverandører betaler typisk spotpris eks. mva.

## Hva vi trenger fra deg

### Hvis det stemmer (mest sannsynlig utfall)

Send inn en kort bekreftelse, den blir en attest. Du trenger:

- **Nettselskap** og **prisområde** (NO1-NO5)
- **Periode** (måned/år)
- **Forbruk** per kategori (dag, natt/helg, totalt) i kWh
- **Pris** per linje (øre/kWh)
- **Beløp** per linje (kr)
- **Kapasitetstrinn** (hvilket trinn og kr/mnd)
- **MVA-sats** (25% eller 0% for Nord-Norge)
- **Konklusjon:** "matchet innenfor avrundingsfeil" (eller liste over linjer som avvek)

### Hva du IKKE trenger å sende

- Navn, adresse, kundenummer, fakturanummer
- KID, kontonummer, betalingsinfo
- Strømleverandør (kraftleveranse er separat)

## Hvordan sende inn

### Alternativ 1: Issue på Forgejo

Bruk malen i [`.forgejo/issue_template/faktura-verifisering.md`](../../.forgejo/issue_template/faktura-verifisering.md). Fyll inn tabellen og send inn.

### Alternativ 2: Issue på GitHub

[Opprett et issue](https://github.com/fredrik-lindseth/Stromkalkulator/issues) og bruk samme mal.

### Alternativ 3: PR med ferdig rapport

Hvis du er komfortabel med Markdown og git: kopier en eksisterende rapport (f.eks. [BKK_Faktura_april_2026.md](BKK_Faktura_april_2026.md)), tilpass for ditt nettselskap, og lag en PR.

## Hva skjer etter du har sendt inn

1. Vi sammenligner dine tall mot beregningen vår
2. **Hvis det matcher** (det vanlige): Vi legger til en verifiseringsrapport for ditt nettselskap i [REFERANSE.md](REFERANSE.md) og oppdaterer "Verifiserte nettselskap"-tabellen. Du krediteres med fornavn eller alias.
3. **Hvis det er avvik:**
   - Avvik på øre-nivå (avrunding): vi noterer det i rapporten og lukker
   - Avvik på krone-nivå: vi finner feilen i `dso.py` eller `const.py`, fikser den, og krediterer deg for funnet

Begge utfall er verdifulle, men match er det vanlige, og det er det som bygger tillit til integrasjonen over tid.

## Vanlige avvik og hva de betyr

| Avvik                                | Sannsynlig årsak                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| Energiledd avviker i sats            | `dso.py`-verdier er utdatert, send inn for å få fikset                             |
| Energiledd avviker i forbruk         | Tariff-bytte (dag/natt) skjer feil, kan være helligdager eller `helg_som_natt`     |
| Forbruksavgift avviker               | Avgiftssone er feil konfigurert (Nord-Norge vs Sør-Norge)                          |
| Kapasitetsledd avviker               | Trinn-grenser er feil i `dso.py`, eller ditt forbruksmønster brytes ned annerledes |
| Strømstøtte avviker (2025-fakturaer) | Terskel eller dekningsgrad har endret seg                                          |
| MVA på 0% når du forventet 25%       | Avgiftssone er satt til Nord-Norge eller tiltakssonen                              |

## Eksisterende verifikasjoner

Se [REFERANSE.md](REFERANSE.md) for en oppdatert liste over verifiserte nettselskap og perioder.
