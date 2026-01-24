# Veien mot HACS Default Repository

Dette dokumentet beskriver prosessen for å publisere integrasjonen i HACS default repository.

## Status

| Steg                         | Status       | Link                                               |
|------------------------------|--------------|----------------------------------------------------|
| Brand-bilder (icon/logo)     | Ferdig       |                                                    |
| PR til home-assistant/brands | Åpen (draft) | https://github.com/home-assistant/brands/pull/9262 |
| Vente på merge av brands PR  | Gjenstår     |                                                    |
| PR til hacs/default          | Gjenstår     |                                                    |
| Vente på merge av HACS PR    | Gjenstår     |                                                    |

---

## Sjekkliste for HACS Default

Basert på https://hacs.xyz/docs/publish/include

### Forutsetninger

- [x] Repository er offentlig på GitHub
- [x] Kan legges til som custom repository i HACS
- [x] Har GitHub release (ikke bare tags)
- [x] HACS Action workflow (`.github/workflows/validate.yml`)
- [x] Hassfest validation (i CI)

### Repository-krav

- [x] Har description på GitHub
- [x] Har topics på GitHub
- [x] Har README med brukerveiledning
- [x] Issues er aktivert

### hacs.json

- [x] Har `name` definert
- [x] Har `country` satt til `["NO"]` (Norge-spesifikk)
- [x] Har `homeassistant` minimum versjon

Nåværende `hacs.json`:
```json
{
  "name": "Strømkalkulator",
  "homeassistant": "2025.1.0",
  "render_readme": true,
  "country": ["NO"]
}
```

### Brands (kun for integrasjoner)

- [x] PR til home-assistant/brands opprettet
- [ ] PR til home-assistant/brands merget

**Merk:** HACS-revieweren sjekker at brands er på plass. Du KAN sende inn HACS PR før brands er merget, men den vil bli draftet til brands er klart.

---

## Vanlige spørsmål

### Kan jeg merge til HACS uten å merge til brands først?

**Teknisk ja, praktisk nei.** HACS sine automatiske sjekker inkluderer "Check brands" som krever at integrasjonen finnes i home-assistant/brands. PR-en vil bli satt som draft til brands er merget.

**Anbefaling:** Vent til brands-PR er merget før du markerer HACS PR som "Ready for review".

### Er det enkelt å bytte navn i etterkant?

**Ja, men det krever arbeid:**

1. **Domain-endring** (f.eks. `stromkalkulator` → `strompris`):
   - Krever ny PR til både brands og hacs/default
   - Brukere må reinstallere integrasjonen
   - Mister historikk og konfigurasjon
   - **Ikke anbefalt etter publisering**

2. **Display name-endring** (f.eks. "Strømkalkulator" → "Strømpris"):
   - Bare endre `name` i `hacs.json` og `manifest.json`
   - Oppdater strings.json
   - Ingen reinstallering nødvendig
   - **Enkelt å gjøre når som helst**

**Konklusjon:** Bestem deg for domain (`stromkalkulator`) før du sender inn. Display name kan endres senere.

### Er dette passende for en liten integrasjon?

**Ja.** HACS default har mange små, nisje-integrasjoner. Denne integrasjonen:
- Løser et reelt problem (norsk strømpris-beregning)
- Er godt dokumentert
- Har tester og CI
- Ingen tilsvarende i Home Assistant core
- Er Norge-spesifikk (markert med `country`)

---

## PR-tekst for hacs/default

### Fremgangsmåte

1. Fork `hacs/default`
2. Opprett ny branch fra `master`
3. Legg til i `integration`-filen (alfabetisk sortert):
   ```
   "fredrik-lindseth/Stromkalkulator",
   ```
4. Opprett PR med teksten under

### PR-mal (fyll ut i GitHub)

**Title:** `Add Stromkalkulator integration`

**Body:**

```
## Repository

https://github.com/fredrik-lindseth/Stromkalkulator

## Checklist

- [x] I am the owner (or a major contributor) to the repository I want to add
- [x] I have read the [general requirements](https://hacs.xyz/docs/publish/start)
- [x] I have read the [integration requirements](https://hacs.xyz/docs/publish/integration)
- [x] I have read the [include requirements](https://hacs.xyz/docs/publish/include)
- [x] The repository has a valid `hacs.json` file
- [x] The repository uses GitHub releases (not just tags)
- [x] The repository has been added to [home-assistant/brands](https://github.com/home-assistant/brands/pull/9262)

## Description

Strømkalkulator is a Home Assistant integration that calculates actual electricity prices in Norway, including:
- Grid tariffs (energiledd + kapasitetsledd)
- Government taxes (forbruksavgift, Enova)
- Electricity subsidy (strømstøtte)
- Norgespris (fixed price alternative)

The integration provides a single sensor for Home Assistant's Energy Dashboard that shows your true cost per kWh.

## Why should this be included?

- Solves a real problem for Norwegian Home Assistant users
- No equivalent functionality in Home Assistant core
- Well documented with tests and CI
- Country-specific (Norway only)
```

---

## Navneforslag

Hvis du vurderer å endre navn før publisering:

### Korte navn

| Navn           | Beskrivelse                                  |
|----------------|----------------------------------------------|
| `strompris`    | Kort, presist - viser din faktiske strømpris |
| `stromkostnad` | Fokus på hva du betaler                      |
| `stromtotal`   | Alt-i-ett pris                               |
| `totalpris`    | Totalprisen                                  |
| `reelpris`     | Faktisk/reell pris                           |

### Lengre navn

| Navn             | Beskrivelse     |
|------------------|-----------------|
| `faktisk_pris`   | Matcher tagline |
| `full_strompris` | Alt inkludert   |

### Notater

- Unngå "norsk" i navnet - det er kun relevant i Norge uansett
- Unngå "regnskap" - det er ingen regnskapsfunksjonalitet
- Unngå "kraft" - tvetydig
- `stromkalkulator` fungerer fint - beskriver at det "kalkulerer" strømrelaterte ting

### Beslutning

**Nåværende:** `stromkalkulator`

**Anbefaling:** Behold nåværende navn. Det fungerer, og navnebytte etter publisering er upraktisk.

---

## Tidsestimat

| Steg             | Estimert ventetid          |
|------------------|----------------------------|
| brands PR review | 1-4 uker                   |
| HACS PR review   | 1-3 måneder (stor backlog) |

Se [HACS backlog](https://github.com/hacs/default/pulls?q=is%3Apr+is%3Aopen+draft%3Afalse+sort%3Acreated-asc) for nåværende status.
