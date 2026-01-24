# Agent Instructions

Retningslinjer for AI-assistenter som jobber med dette prosjektet.

Dette prosjektet bruker **[Beads](https://github.com/steveyegge/beads)** (`bd`) for oppgavesporing.

## Kom i gang

```bash
bd ready          # Finn arbeid uten blokkere
bd prime          # Full workflow-kontekst
```

## Arbeidsflyt

### 1. Start av okt - Sjekk status

```bash
bd ready              # Se hva som er klart
bd list               # Se alle apne oppgaver
bd show <id>          # Se avhengigheter for en oppgave
```

### 2. Ta en oppgave

```bash
bd update <id> --status in_progress   # Marker som pagar
bd blocked                            # Sjekk hva som blokkerer
```

### 3. Fakta-sjekk (for beregninger)

**For endringer i stromstotte, avgifter, priser:**

1. **Sjekk docs/fakta/** - offisielle kilder fra lovdata.no, regjeringen.no
2. **Verifiser mot fakturaer** - se `Fakturaer/*.txt` for reelle eksempler
3. **Dokumenter kilden** - legg til URL i koden eller docs/fakta/

```bash
bd comments add <id> "Kilde: lovdata.no/... - terskel er 77 ore eks. mva"
```

### 4. Implementering (TDD)

1. **Skriv tester forst** - definer forventet oppforsel
2. **Implementer kode** - fa testene til a passere
3. **Kjor linting** - `ruff check custom_components/ tests/`
4. **Kjor alle tester** - `pipx run pytest tests/ -v`

### 5. Fullforing

```bash
bd close <id>         # Marker som ferdig
bd ready              # Sjekk hva som na er klart
bd sync               # Sync med git
```

---

## Beads-kommandoer

| Kommando                                    | Beskrivelse                             |
|---------------------------------------------|-----------------------------------------|
| `bd ready`                                  | Vis oppgaver uten blokkere (start her!) |
| `bd list`                                   | Vis alle apne oppgaver                  |
| `bd show <id>`                              | Vis detaljer og avhengigheter           |
| `bd create "Tittel" -p 1`                   | Opprett P1-oppgave                      |
| `bd update <id> --status in_progress`       | Marker som pagar                        |
| `bd close <id>`                             | Lukk oppgave                            |
| `bd dep add <child> <parent> --type blocks` | Legg til avhengighet                    |
| `bd blocked`                                | Vis blokkerte oppgaver                  |
| `bd sync`                                   | Sync med git (kjor ved okt-slutt)       |

### Prioriteter

- **P0** - Kritisk, ma fikses na
- **P1** - Hoyt, neste i ko
- **P2** - Medium, planlagt
- **P3** - Lavt, nice-to-have

---

## Sjekkliste for vanlige oppgaver

### Legge til ny sensor

```bash
bd create "Ny sensor: sensor_navn" -p 2 --description "Beregner X basert pa Y"
```

- [ ] Definer sensor i `sensor.py`
- [ ] Legg til data i `coordinator.py` `_async_update_data()`
- [ ] Skriv test i `tests/test_*.py`
- [ ] Dokumenter i `docs/beregninger.md`
- [ ] Oppdater sensor-tabell i README.md

### Endre stromstotte/avgifter

```bash
bd create "Oppdater stromstotte til 2027" -p 1 --description "Ny terskel fra lovdata"
```

- [ ] Finn offisiell kilde (lovdata.no, regjeringen.no, skatteetaten.no)
- [ ] Lagre kilde i `docs/fakta/`
- [ ] Oppdater konstanter i `const.py`
- [ ] Oppdater tester i `tests/test_stromstotte.py`
- [ ] Oppdater `docs/beregninger.md`
- [ ] Oppdater `packages/stromkalkulator_test.yaml`
- [ ] Verifiser mot faktura i `Fakturaer/`

### Legge til nytt nettselskap (TSO)

- [ ] Finn priser pa nettselskapets nettside
- [ ] Legg til i `const.py` TSO_LIST
- [ ] Skriv test i `tests/test_energiledd.py`
- [ ] Oppdater TSO-liste i README.md
- [ ] Folg guide i `docs/CONTRIBUTING.md`

### Fikse bug

```bash
bd create "Bug: beskrivelse" -p 1 --description "Reproduksjon: ..."
```

- [ ] Reproduser bug
- [ ] Skriv test som feiler
- [ ] Fiks koden
- [ ] Verifiser at test passerer

---

## Kvalitetskontroll

### Tester og linting

```bash
# Kjor alle tester
pipx run pytest tests/ -v

# Sjekk kode
ruff check custom_components/stromkalkulator/ tests/
```

### Live-validering i Home Assistant

1. Kopier `packages/stromkalkulator_test.yaml` til HA
2. Sjekk `sensor.test_alle_tester_ok` = true
3. Sammenlign med faktura manuelt

---

## Kilder og fakta

| Tema               | Kilde                                                                                       |
|--------------------|---------------------------------------------------------------------------------------------|
| Stromstotte-satser | [lovdata.no](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791)                      |
| Forbruksavgift     | [skatteetaten.no](https://www.skatteetaten.no/satser/elektrisk-kraft/)                      |
| Norgespris         | [regjeringen.no](https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/) |
| Nettleiepriser     | Nettselskapets egen nettside                                                                |

Lagre alltid kopi av offisielle kilder i `docs/fakta/`.

---

## Dokumentasjon

- [docs/ROADMAP.md](docs/ROADMAP.md) - Feature-oversikt og progress
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arkitektur og design
- [docs/beregninger.md](docs/beregninger.md) - Formler og sensorer
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) - Legge til nettselskap

## Sjekke tidligere arbeid

```bash
bd list --all                        # Beads-historikk (inkl. lukkede)
git log --oneline --grep="feature"   # Git-historikk
cat docs/ROADMAP.md                  # Feature-oversikt
```
