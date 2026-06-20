# Prosedyre: verifiser neste måneds faktura

Stegene som må gjøres når en ny BKK-faktura kommer. Forutsetter at fakturaen er for "forrige måned" (kommer typisk rundt den 4. i hver måned). Eksempel: mai 2026-faktura kommer rundt 4. juni 2026.

## Forutsetninger

- SSH-tilgang til HomeAssistant
- BankID for å logge inn på elhub.no
- BKK-faktura som PDF
- Git-clone av dette repoet

## Stegene

### 1. Lagre PDF-faktura

Lagre `BKK_FakturaXXXXXXXX.pdf` i `Fakturaer/` med opprinnelig filnavn.

### 2. Eksporter HAN-data fra HA

```bash
scp scripts/research/export_invoice_hourly.py ha-local:/tmp/
ssh ha-local "python3 /tmp/export_invoice_hourly.py \
    --year 2026 --month 5 \
    --output /tmp/bkk_mai_2026_hourly.json \
    --fakturanr <ny-fakturanr>"
scp ha-local:/tmp/bkk_mai_2026_hourly.json tests/fixtures/
```

Spotprisen i fixturen er HA-ens lagrede NOK-pris fra den offisielle Nord
Pool-integrasjonen, altså med Nord Pools egen `exchangeRate` allerede bakt inn
(samme kursgrunnlag som BKK fakturerer fra). Verifiseringen under bruker den
direkte, så ingen EUR→NOK-omregning trengs for månedssjekken.

### 3. Last ned Elhub-data

1. Logg inn på [elhub.no](https://elhub.no)
2. Velg "Min strøm" eller tilsvarende
3. Velg ditt målepunkt
4. Eksporter timesverdier som CSV for hele måneden
5. Lagre originalen i `_private/Måleverdier/elhub_mai.csv` (gitignored, beholder rådata)
6. Kopier også til `Måleverdier/elhub_mai.csv` om du vil ha den committet. CSV-innholdet har ingen personlig info, men kun én demo-måned committes vanligvis.

### 4. Legg til fixture i `tests/test_faktura_bkk.py`

Kopier `FAKTURA_APRIL_2026`-blokken, endre navn til `FAKTURA_MAI_2026` og fyll inn nye tall fra fakturaen. Legg navnet til i `@pytest.fixture(params=[...])`-blokken.

### 5. Kjør verifisering

```bash
# Parametrisert faktura-test (validerer alle måneder, inkl. den nye, mot fakturasum)
pipx run --with hypothesis pytest tests/test_faktura_bkk.py -v

# Direkte sammenligning
python3 scripts/research/verify_invoice_hourly.py \
    --hourly tests/fixtures/bkk_mai_2026_hourly.json \
    --faktura mai_2026
```

### 6. Sjekk avvik mot april

Forventede avvik (basert på april 2026):

| Linje              | Forventet avvik |
| ------------------ | --------------- |
| Total kWh          | ±50 Wh          |
| Dag/natt-split     | ±100 Wh hver    |
| Topp 3 maks effekt | 3-8 W per topp  |
| Norgespris-komp    | 2-5 kr (0,2 %)  |

Norgespris-komp-avviket på ~0,2 % er dokumentert kurs-/avrundingsstøy, ikke en logikkfeil: spotprisen er allerede Nord Pools NOK-pris. Vil du grave i selve kursen, er den daglige `exchangeRate` arkivert (HA-sensor `sensor.nord_pool_no5_exchange_rate` + `just snapshot-kurs`). Bakgrunn: [../research/nok-omregning.md](../research/nok-omregning.md), [../research/bloomberg-verifisering.md](../research/bloomberg-verifisering.md).

Hvis avvik er innenfor: alt fungerer som dokumentert.

Hvis avvik er signifikant større: undersøk. Mulige årsaker:

- HAN-leser nedetid (sjekk `Kvalitet`-kolonnen i Elhub-CSV for "Beregnet"-rader)
- Endret målerprosess hos BKK
- Endret avgiftssatser (sjekk `const.py` og `dso.py`)

### 7. Lag faktura-rapport

Kopier `docs/fakturaer/bkk-april-2026.md` til `bkk-mai-2026.md` og oppdater tallene.

### 8. Oppdater referanse.md

Øk verifiserte måneder i `docs/fakturaer/referanse.md` og README-tabellen.

### 9. Anonymiser personlig data

Det nye fakturanummeret må mappes til en generisk verdi i `.anonymize_config.json` (gitignored, har dine ekte data + mappings til generiske):

```jsonc
{
  "replacements": {
    "<nytt-fakturanr>": "012345684", // legg til
  },
  "filename_mappings": {
    "<nytt-fakturanr>": "mai_2026", // legg til
  },
}
```

Kjør deretter:

```bash
# Dry-run først: se hva som vil bli endret
python3 scripts/anonymize_invoices.py --inplace --dry-run

# Anonymiser inplace (oppdaterer test-fixture, faktura-rapport, evt scripts)
python3 scripts/anonymize_invoices.py --inplace

# Anonymiser den nye PDF/.txt-fakturaen til docs/fakturaer/
python3 scripts/anonymize_invoices.py
```

Verifiser at ingen reell faktura-/kunde-/målepunkt-data er igjen i tracked filer:

```bash
git diff | grep -E '<dine ekte verdier>' || echo "OK, ingen treff"
```

### 10. Commit

```bash
git add Fakturaer/ Måleverdier/ tests/fixtures/ tests/test_faktura_bkk.py docs/fakturaer/
git commit -m "verifisering: BKK mai 2026"
```

`Fakturaer/` er gitignored, så PDF går ikke med (kun anonymisert markdown-rapport i `docs/fakturaer/`).

## Hvis nye spørsmål kommer opp

- Nye nettselskap-satser: oppdater `custom_components/stromkalkulator/dso.py`
- Nye avgiftsendringer: oppdater `custom_components/stromkalkulator/const.py`
- Måler-hardware-endring: oppdater `docs/måler-hardware.md`

## Hvis det er en ekte feil i integrasjonen

Lag en incident-rapport i `docs/incidents/` med:

1. Hva som ble oppdaget
2. Hvor mye det utgjør i kr
3. Reproduksjon
4. Fiks (kode + test)
