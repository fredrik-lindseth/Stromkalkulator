# Roadmap og Feature-oversikt

Dette dokumentet holder oversikt over features, hva som er implementert, og hva som er planlagt.

## Versjonsoversikt

| Versjon | Status | Hovedfunksjoner |
|---------|--------|-----------------|
| v0.19.0 | Ferdig | Stromstotte 2026, Norgespris-stotte |
| v0.20.0 | Planlagt | Faktura-verifisering med akkumulerte kostnader |
| v0.21.0 | Planlagt | Automatisk utility meter via config flow |

---

## Implementerte features

### Kjerneberegninger
- [x] **Spotpris-integrasjon** - Leser fra Nord Pool/Tibber-sensor
- [x] **Energiledd dag/natt** - Automatisk tariff basert pa tid og helligdager
- [x] **Kapasitetsledd** - Topp-3 effektdager med persistens
- [x] **Offentlige avgifter** - Forbruksavgift + Enova med avgiftssoner
- [x] **Stromstotte** - 90% over terskel (96,25 ore 2026)
- [x] **Norgespris** - Fast pris med geografisk differensiering

### Nettselskaper
- [x] **30+ TSO-er** - BKK, Elvia, Tensio, Glitre, etc.
- [x] **Egendefinert TSO** - Brukeren kan legge inn egne satser
- [x] **Avgiftssoner** - Standard, Nord-Norge, Tiltakssonen

### Sensorer (22 stk)
- [x] `total_strompris_etter_stotte` - Hovedsensor for Energy Dashboard
- [x] `stromstotte` - Stotte per kWh
- [x] `kapasitetstrinn` - Manedlig kostnad i kr
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

**Mal:** Brukeren skal kunne sammenligne Stromkalkulator med nettleiefakturaen.

**Losning:** Utvidet `packages/stromkalkulator_utility.yaml` med template-sensorer som
bruker Home Assistants innebygde `utility_meter` og `integration`-sensorer.

#### Sensorer i packages/stromkalkulator_utility.yaml

| Sensor | Beskrivelse | Matcher faktura-post |
|--------|-------------|---------------------|
| `strom_maanedlig_dag` | kWh pa dag-tariff | Energiledd dag (forbruk) |
| `strom_maanedlig_natt` | kWh pa natt-tariff | Energiledd natt (forbruk) |
| `maanedlig_energiledd_dag` | Sum energiledd dag (kr) | Energiledd dag |
| `maanedlig_energiledd_natt` | Sum energiledd natt (kr) | Energiledd natt/helg |
| `maanedlig_forbruksavgift` | Sum forbruksavgift (kr) | Forbruksavgift |
| `maanedlig_enovaavgift` | Sum Enova-avgift (kr) | Enovaavgift |
| `maanedlig_stromstotte` | Sum stromstotte (kr) | Midlert. stromstønad |
| `maanedlig_nettleie_etter_stotte` | Totalt a betale (kr) | A betale |
| `kapasitetstrinn` | Kapasitetsledd (kr) | Kapasitetsledd |

#### Oppsett

Se README.md > "Verifisere mot faktura" for komplett guide.

### v0.21.0: Automatisk utility meter

**Mal:** Sette opp dag/natt-splitting via config flow i stedet for manuell YAML.

- [ ] Opprette utility_meter via config flow
- [ ] Fjerne behovet for packages/stromkalkulator_utility.yaml
- [ ] Automatisk kobling til tariff-sensor

### Fremtidige ideer

| Feature | Prioritet | Kompleksitet |
|---------|-----------|--------------|
| Custom dashboard-kort | Lav | Hoy |
| Varsel nar kapasitetstrinn oker | Medium | Lav |
| Historikk-graf for stromstotte | Lav | Medium |
| Faktura-import (PDF/CSV) | Lav | Hoy |
| Stotte for fritidsbolig (1000 kWh grense) | Lav | Medium |
| Stotte for naring | Lav | Medium |

---

## Kjente begrensninger

### Forenklet stromstotte-modell
- **5000 kWh/mnd grense** - Ikke implementert. Beregner stotte pa alt forbruk.
- **Arsak:** De aller fleste husholdninger bruker under 5000 kWh/mnd.
- **Konsekvens:** Brukere med ekstremt hoyt forbruk vil se for mye stotte.

### Strømstotte-beregning pa faktura
- **Faktura viser vektet snitt** - Stromstotte per kWh varierer time for time
- **Vi beregner sanntid** - Sensor viser oyeblikksverdi, ikke manedssnitt
- **Konsekvens:** Akkumulert stromstotte_kr vil matche, men ore/kWh-verdi er annerledes

### Kun privatbolig
- Fritidsbolig, naring, fjernvarme, borettslag er ikke stottet

---

## Endringslogg

### v0.19.0 (2026-01-24)
- Oppdatert stromstotte-terskel til 2026 (77 ore eks. mva = 96,25 ore inkl. mva)
- Lagt til Norgespris-stotte med config-valg
- Norgespris med geografisk prising (50 ore Sor-Norge, 40 ore Nord-Norge)
- Dokumentert begrensninger

### v0.18.x og tidligere
- Se git log for historikk
