# Plan: Strømkalkulator + Utility Meter

## Oversikt

Denne planen beskriver hvordan sluttbrukere kan kombinere Strømkalkulator-integrasjonen med Home Assistants `utility_meter` for å få:

1. **Nøyaktig kostnadssporing** - Faktiske strømkostnader med riktig tariff (dag/natt)
2. **Månedlig/daglig forbruksoversikt** - Automatisk nullstilling
3. **Sparing vs. Norgespris** - Se hvor mye du sparer/taper
4. **Strømstøtte-sporing** - Hvor mye strømstøtte du har mottatt
5. **Energy Dashboard-integrasjon** - Full integrasjon med HA Energy Dashboard

---

## Del 1: Hva vi allerede har

Strømkalkulator gir disse sensorene som er relevante for utility_meter:

| Sensor | Enhet | Beskrivelse |
|--------|-------|-------------|
| `sensor.stromkalkulator_total_strompris_etter_stotte` | NOK/kWh | Din faktiske pris etter strømstøtte |
| `sensor.stromkalkulator_total_strompris_for_stotte` | NOK/kWh | Pris før strømstøtte |
| `sensor.stromkalkulator_stromstotte` | NOK/kWh | Strømstøtte per kWh |
| `sensor.stromkalkulator_energiledd` | NOK/kWh | Nettleie energiledd (dag/natt) |
| `sensor.stromkalkulator_total_strompris_norgespris` | NOK/kWh | Pris med Norgespris (50 øre/kWh) |

**Mangler for utility_meter:**
- Tariff-sensor som angir dag/natt for automatisk bytte
- Forbrukssensor i kWh (Riemann sum av effektsensor)

---

## Del 2: Ny funksjonalitet

### 2.1 Tariff-sensor (ny sensor i integrasjonen)

Lag en ny sensor som returnerer gjeldende tariff-periode:

```python
class TariffSensor(NettleieBaseSensor):
    """Sensor for current tariff period (dag/natt)."""
    
    @property
    def native_value(self):
        """Return current tariff: 'dag' or 'natt'."""
        if self.coordinator.data:
            is_day = self.coordinator.data.get("is_day_rate")
            return "dag" if is_day else "natt"
        return None
```

**Output:**
- `dag` - Hverdager 06:00-22:00 (ikke helligdager)
- `natt` - 22:00-06:00, helger, helligdager

### 2.2 Riemann-sum helper for forbruk

Brukere som kun har effekt-sensor (W) trenger å konvertere til energi (kWh).

**Dokumenter i README:**
```yaml
# configuration.yaml
sensor:
  - platform: integration
    source: sensor.power_consumption  # Din effektsensor i W
    name: "Energiforbruk"
    unit_prefix: k  # Konverter til kWh
    round: 2
    method: left
```

---

## Del 3: Bruker-konfigurasjon

### 3.1 Utility Meter med dag/natt-tariffer

```yaml
# configuration.yaml
utility_meter:
  # Daglig forbruk per tariff
  daglig_strom:
    source: sensor.energiforbruk
    name: "Daglig strømforbruk"
    cycle: daily
    tariffs:
      - dag
      - natt
  
  # Månedlig forbruk per tariff
  manedlig_strom:
    source: sensor.energiforbruk
    name: "Månedlig strømforbruk"
    cycle: monthly
    tariffs:
      - dag
      - natt
```

**Resulterende sensorer:**
- `sensor.daglig_strom_dag` - Forbruk på dagtariff (kWh)
- `sensor.daglig_strom_natt` - Forbruk på nattariff (kWh)
- `sensor.manedlig_strom_dag` - Månedlig dagforbruk
- `sensor.manedlig_strom_natt` - Månedlig nattforbruk
- `select.daglig_strom` - Gjeldende tariff (dag/natt)
- `select.manedlig_strom` - Gjeldende tariff

### 3.2 Automasjon for tariff-bytte

```yaml
# automations.yaml
automation:
  - alias: "Oppdater strøm-tariff"
    trigger:
      - platform: state
        entity_id: sensor.stromkalkulator_tariff
        not_to:
          - unavailable
          - unknown
    action:
      - service: select.select_option
        target:
          entity_id:
            - select.daglig_strom
            - select.manedlig_strom
        data:
          option: "{{ trigger.to_state.state }}"
```

### 3.3 Prissensorer for Energy Dashboard

Lag input_number for dag- og natt-priser:

```yaml
# configuration.yaml
input_number:
  energiledd_dag:
    name: "Energiledd dag"
    min: 0
    max: 2
    step: 0.01
    unit_of_measurement: "NOK/kWh"
    icon: mdi:currency-usd
  
  energiledd_natt:
    name: "Energiledd natt"
    min: 0
    max: 2
    step: 0.01
    unit_of_measurement: "NOK/kWh"
    icon: mdi:currency-usd
```

**Alternativ:** Bruk sensorene fra Strømkalkulator direkte:
- `sensor.stromkalkulator_total_strompris_etter_stotte` som prissensor

---

## Del 4: Energy Dashboard-oppsett

### 4.1 Legg til forbrukssensorer

I **Settings > Dashboards > Energy**:

1. **Grid consumption:**
   - `sensor.manedlig_strom_dag` med pris `sensor.stromkalkulator_energiledd` (attributt `energiledd_dag`)
   - `sensor.manedlig_strom_natt` med pris fra attributt `energiledd_natt`

2. **Eller enklere:**
   - `sensor.energiforbruk` med pris `sensor.stromkalkulator_total_strompris_etter_stotte`

### 4.2 Visualisering i dashboard

Energy Dashboard vil vise:
- Forbruk i dag/natt-kolonner med ulike farger
- Kostnader basert på valgt prissensor
- Graf over tid

---

## Del 5: Avanserte template-sensorer

### 5.1 Total månedskostnad

```yaml
template:
  - sensor:
      - name: "Månedlig strømkostnad"
        unique_id: monthly_electricity_cost
        unit_of_measurement: "NOK"
        device_class: monetary
        state: >
          {% set dag_kwh = states('sensor.manedlig_strom_dag') | float(0) %}
          {% set natt_kwh = states('sensor.manedlig_strom_natt') | float(0) %}
          {% set dag_pris = state_attr('sensor.stromkalkulator_energiledd', 'energiledd_dag') | float(0.46) %}
          {% set natt_pris = state_attr('sensor.stromkalkulator_energiledd', 'energiledd_natt') | float(0.23) %}
          {% set kapasitet = states('sensor.stromkalkulator_kapasitetstrinn') | float(0) %}
          {{ ((dag_kwh * dag_pris) + (natt_kwh * natt_pris) + kapasitet) | round(2) }}
```

### 5.2 Besparelse vs. Norgespris

```yaml
template:
  - sensor:
      - name: "Besparelse vs Norgespris"
        unique_id: savings_vs_norgespris
        unit_of_measurement: "NOK"
        device_class: monetary
        state: >
          {% set forbruk = states('sensor.manedlig_strom_dag') | float(0) + states('sensor.manedlig_strom_natt') | float(0) %}
          {% set diff_per_kwh = states('sensor.stromkalkulator_prisforskjell_norgespris') | float(0) %}
          {{ (forbruk * diff_per_kwh * -1) | round(2) }}
        attributes:
          note: "Positiv = du sparer, Negativ = du taper"
```

### 5.3 Akkumulert strømstøtte

```yaml
template:
  - sensor:
      - name: "Akkumulert strømstøtte månedlig"
        unique_id: accumulated_stromstotte_monthly
        unit_of_measurement: "NOK"
        device_class: monetary
        state: >
          {% set forbruk = states('sensor.manedlig_strom_dag') | float(0) + states('sensor.manedlig_strom_natt') | float(0) %}
          {% set stotte_rate = states('sensor.stromkalkulator_stromstotte') | float(0) %}
          {# Forenklet - bruker gjeldende støtte-rate på alt forbruk #}
          {# For nøyaktig beregning trengs historikk-sporing #}
          {{ (forbruk * stotte_rate) | round(2) }}
```

---

## Del 6: Implementeringsplan

### Fase 1: Ny Tariff-sensor (integrasjonen)

**Filer å endre:**
- `sensor.py` - Legg til `TariffSensor`
- Legg til tariff i `coordinator.py` data

**Estimert arbeid:** 1-2 timer

### Fase 2: Dokumentasjon

**Nye filer:**
- `docs/utility_meter_setup.md` - Komplett oppsettguide
- Oppdater `README.md` med link

**Innhold:**
1. Steg-for-steg oppsett
2. Eksempel-konfigurasjoner (kopier-lim)
3. Energy Dashboard-oppsett
4. Feilsøking

**Estimert arbeid:** 2-3 timer

### Fase 3: Ferdigpakkede YAML-pakker (valgfritt)

Lag ferdigpakkede "packages" som brukere kan inkludere:

```yaml
# packages/stromkalkulator_utility.yaml
utility_meter:
  ...
  
automation:
  ...
  
template:
  ...
```

**Estimert arbeid:** 1-2 timer

### Fase 4: UI-integrasjon (fremtidig)

Fremtidig mulighet: La integrasjonen automatisk opprette utility_meters via config_flow.

**Estimert arbeid:** 4-6 timer

---

## Del 7: Brukerfordeler

### Før (uten utility_meter)

- Sanntidspriser uten historikk
- Manuell beregning av månedskostnad
- Ingen oversikt over dag/natt-fordeling

### Etter (med utility_meter)

| Funksjon | Fordel |
|----------|--------|
| Automatisk tariff-bytte | Riktig pris alltid |
| Daglig/månedlig oversikt | Se forbruk over tid |
| Energy Dashboard | Vakker visualisering |
| Kostnadsberegning | Nøyaktige månedskostnader |
| Norgespris-sammenligning | Vit om du bør bytte |
| Strømstøtte-sporing | Se hvor mye du får i støtte |

---

## Del 8: Eksempel på komplett oppsett

### configuration.yaml

```yaml
# Strømkalkulator er allerede satt opp via UI

# Konverter effekt til energi (hvis du ikke har kWh-sensor)
sensor:
  - platform: integration
    source: sensor.power_meter
    name: "Energiforbruk"
    unit_prefix: k
    round: 2
    method: left

# Utility meter for forbrukssporing
utility_meter:
  daglig_strom:
    source: sensor.energiforbruk
    cycle: daily
    tariffs:
      - dag
      - natt
  
  manedlig_strom:
    source: sensor.energiforbruk
    cycle: monthly
    tariffs:
      - dag
      - natt

# Template-sensorer for kostnader
template:
  - sensor:
      - name: "Månedlig strømkostnad"
        unique_id: monthly_electricity_cost
        unit_of_measurement: "NOK"
        device_class: monetary
        state: >
          {% set dag = states('sensor.manedlig_strom_dag') | float(0) %}
          {% set natt = states('sensor.manedlig_strom_natt') | float(0) %}
          {% set dag_pris = state_attr('sensor.stromkalkulator_energiledd', 'energiledd_dag') | float(0.46) %}
          {% set natt_pris = state_attr('sensor.stromkalkulator_energiledd', 'energiledd_natt') | float(0.23) %}
          {% set kap = states('sensor.stromkalkulator_kapasitetstrinn') | float(0) %}
          {{ ((dag * dag_pris) + (natt * natt_pris) + kap) | round(2) }}
```

### automations.yaml

```yaml
- alias: "Oppdater strøm-tariff"
  trigger:
    - platform: state
      entity_id: sensor.stromkalkulator_tariff
      not_to:
        - unavailable
        - unknown
  action:
    - service: select.select_option
      target:
        entity_id:
          - select.daglig_strom
          - select.manedlig_strom
      data:
        option: "{{ trigger.to_state.state }}"
```

---

## Del 9: Neste steg

1. **Prioritet 1:** Implementer `TariffSensor` i integrasjonen
2. **Prioritet 2:** Skriv dokumentasjon med eksempler
3. **Prioritet 3:** Lag ferdigpakkede YAML-pakker
4. **Fremtidig:** Vurder automatisk oppsett via config_flow

---

## Referanser

- [Home Assistant Utility Meter](https://www.home-assistant.io/integrations/utility_meter/)
- [Multi-tariff guide](https://community.home-assistant.io/t/quick-tldr-on-how-to-create-multi-tariff-energy-meters/585379)
- [Energy Dashboard](https://www.home-assistant.io/docs/energy/)
