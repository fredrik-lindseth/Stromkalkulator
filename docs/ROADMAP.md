# Roadmap og Feature-oversikt

Dette dokumentet holder oversikt over features, hva som er implementert, og hva som er planlagt.

## Versjonsoversikt

| Versjon | Status   | Hovedfunksjoner                          |
|---------|----------|------------------------------------------|
| v0.20.0 | Ferdig   | Dokumentasjonsoppdatering, ÆØÅ-fiks      |
| v0.21.0 | Planlagt | Automatisk utility meter via config flow |

---

## Implementerte features

### Kjerneberegninger
- [x] **Spotpris-integrasjon** - Leser fra Nord Pool/Tibber-sensor
- [x] **Energiledd dag/natt** - Automatisk tariff basert på tid og helligdager
- [x] **Kapasitetsledd** - Topp-3 effektdager med persistens
- [x] **Offentlige avgifter** - Forbruksavgift + Enova med avgiftssoner
- [x] **Strømstøtte** - 90% over terskel (96,25 øre 2026)
- [x] **Norgespris** - Fast pris med geografisk differensiering

### Nettselskaper
- [x] **30+ TSO-er** - BKK, Elvia, Tensio, Glitre, etc.
- [x] **Egendefinert TSO** - Brukeren kan legge inn egne satser
- [x] **Avgiftssoner** - Standard, Nord-Norge, Tiltakssonen

### Sensorer (22 stk)
- [x] `total_strompris_etter_stotte` - Hovedsensor for Energy Dashboard
- [x] `strømstøtte` - Støtte per kWh
- [x] `kapasitetstrinn` - Månedlig kostnad i kr
- [x] `energiledd` / `energiledd_dag` / `energiledd_natt`
- [x] `tariff` - "dag" eller "natt"
- [x] `toppforbruk_1/2/3` / `snitt_toppforbruk`
- [x] `forbruksavgift` / `enovaavgift` / `offentlige_avgifter`
- [x] `prisforskjell_norgespris`

### Konfigurasjon
- [x] **Config flow** - UI-basert oppsett
- [x] **Options flow** - Endre innstillinger etter oppsett
- [x] **Har Norgespris** - Checkbox i konfigurasjon

### Dokumentasjon
- [x] README med installasjon og bruk
- [x] beregninger.md med formler
- [x] ARCHITECTURE.md med design
- [x] CONTRIBUTING.md for nye TSO-er
- [x] TESTING.md for validering

---

## Planlagte features

### v0.20.0: Faktura-verifisering (FERDIG)

**Mål:** Brukeren skal kunne sammenligne Strømkalkulator med nettleiefakturaen.

**Løsning:** Utvidet `packages/stromkalkulator_utility.yaml` med template-sensorer som
bruker Home Assistants innebygde `utility_meter` og `integration`-sensorer.

#### Sensorer i packages/stromkalkulator_utility.yaml

| Sensor                            | Beskrivelse              | Matcher faktura-post      |
|-----------------------------------|--------------------------|---------------------------|
| `strom_maanedlig_dag`             | kWh på dag-tariff        | Energiledd dag (forbruk)  |
| `strom_maanedlig_natt`            | kWh på natt-tariff       | Energiledd natt (forbruk) |
| `maanedlig_energiledd_dag`        | Sum energiledd dag (kr)  | Energiledd dag            |
| `maanedlig_energiledd_natt`       | Sum energiledd natt (kr) | Energiledd natt/helg      |
| `maanedlig_forbruksavgift`        | Sum forbruksavgift (kr)  | Forbruksavgift            |
| `maanedlig_enovaavgift`           | Sum Enova-avgift (kr)    | Enovaavgift               |
| `maanedlig_stromstotte`           | Sum strømstøtte (kr)     | Midlert. strømstønad      |
| `maanedlig_nettleie_etter_stotte` | Totalt å betale (kr)     | Å betale                  |
| `kapasitetstrinn`                 | Kapasitetsledd (kr)      | Kapasitetsledd            |

#### Oppsett

Se README.md > "Verifisere mot faktura" for komplett guide.

### v0.21.0: Automatisk utility meter

**Mål:** Sette opp dag/natt-splitting via config flow i stedet for manuell YAML.

- [ ] Opprette utility_meter via config flow
- [ ] Fjerne behovet for packages/stromkalkulator_utility.yaml
- [ ] Automatisk kobling til tariff-sensor

### HACS-publisering

**Status:** Pågår - se [HACS_PUBLISERING.md](HACS_PUBLISERING.md) for detaljer

- [x] Brand-bilder (icon/logo) med riktige størrelser
- [x] PR til home-assistant/brands: https://github.com/home-assistant/brands/pull/9262
- [ ] Vente på merge av brands PR
- [ ] PR til hacs/default
- [ ] Vente på merge av HACS PR

### Fremtidige ideer

| Feature                                   | Kompleksitet |
|-------------------------------------------|--------------|
| Custom dashboard-kort                     | Høy          |
| Varsel når kapasitetstrinn øker           | Lav          |
| Historikk-graf for strømstøtte            | Medium       |
| Faktura-import (PDF/CSV)                  | Høy          |
| Støtte for fritidsbolig (1000 kWh grense) | Medium       |
| Støtte for næring                         | Medium       |

---

Se [README.md](../README.md#begrensninger) for kjente begrensninger.
