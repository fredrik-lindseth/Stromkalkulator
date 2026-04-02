# Dagskostnad + Estimert månedskostnad — Implementasjonsplan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Legg til 2 nye sensorer (dagens kostnad, estimert månedskostnad) og 2 attributter (vektet snittpris, dag/natt-fordeling) på eksisterende sensorer.

**Architecture:** Coordinator utvides med daglig kostnadsakkumulering (`_daily_cost`). Nullstilles ved datobytte, persisteres i storage. Nye sensorer leser fra coordinator.data. Attributter beregnes direkte i eksisterende sensorer fra data som allerede finnes.

**Tech Stack:** Home Assistant DataUpdateCoordinator, SensorEntity, pytest

---

### Task 1: Attributt `dag_natt_fordeling_pct` på MaanedligForbrukTotalSensor

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py` — MaanedligForbrukTotalSensor.extra_state_attributes (~linje 1214)
- Test: `tests/test_monthly_sensors.py`

**Step 1: Write the failing test**

```python
def test_dag_natt_fordeling_pct(coordinator_with_data):
    """Dag/natt-fordeling vises som prosentattributt."""
    coordinator = coordinator_with_data
    # Sett opp: 750 kWh dag, 250 kWh natt = 75%/25%
    coordinator.data["monthly_consumption_dag_kwh"] = 750.0
    coordinator.data["monthly_consumption_natt_kwh"] = 250.0
    coordinator.data["monthly_consumption_total_kwh"] = 1000.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = MaanedligForbrukTotalSensor(coordinator, entry)
    attrs = sensor.extra_state_attributes

    assert attrs["dag_pct"] == 75.0
    assert attrs["natt_pct"] == 25.0


def test_dag_natt_fordeling_pct_zero_consumption(coordinator_with_data):
    """Ingen forbruk gir 0/0, ikke division by zero."""
    coordinator = coordinator_with_data
    coordinator.data["monthly_consumption_dag_kwh"] = 0.0
    coordinator.data["monthly_consumption_natt_kwh"] = 0.0
    coordinator.data["monthly_consumption_total_kwh"] = 0.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = MaanedligForbrukTotalSensor(coordinator, entry)
    attrs = sensor.extra_state_attributes

    assert attrs["dag_pct"] == 0.0
    assert attrs["natt_pct"] == 0.0
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "dag_natt_fordeling" -v`
Expected: FAIL — `dag_pct` not in attributes

**Step 3: Implement**

I `sensor.py`, MaanedligForbrukTotalSensor.extra_state_attributes (~linje 1214), legg til i return-dict:

```python
total = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
dag = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
natt = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
# ... eksisterende attributter ...
return {
    "dag_kwh": ...,
    "natt_kwh": ...,
    "dag_pct": round(dag / total * 100, 1) if total > 0 else 0.0,
    "natt_pct": round(natt / total * 100, 1) if total > 0 else 0.0,
}
```

**Step 4: Run test to verify it passes**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "dag_natt_fordeling" -v`
Expected: PASS

**Step 5: Commit**

```
git add custom_components/stromkalkulator/sensor.py tests/test_monthly_sensors.py
git commit -m "feat: attributt dag/natt-fordeling (%) på månedlig forbruk"
```

---

### Task 2: Attributt `vektet_snittpris` på MaanedligTotalSensor

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py` — MaanedligTotalSensor.extra_state_attributes (~linje 1424)
- Test: `tests/test_monthly_sensors.py`

**Step 1: Write the failing test**

```python
def test_vektet_snittpris_attributt(coordinator_with_data):
    """Vektet snittpris = total kostnad / total kWh."""
    coordinator = coordinator_with_data
    coordinator.data["monthly_consumption_dag_kwh"] = 500.0
    coordinator.data["monthly_consumption_natt_kwh"] = 200.0
    coordinator.data["monthly_consumption_total_kwh"] = 700.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = MaanedligTotalSensor(coordinator, entry)
    value = sensor.native_value  # total kostnad i kr
    attrs = sensor.extra_state_attributes

    assert attrs["vektet_snittpris_kr_per_kwh"] == round(value / 700.0, 4)


def test_vektet_snittpris_zero_consumption(coordinator_with_data):
    """Null forbruk gir None, ikke division by zero."""
    coordinator = coordinator_with_data
    coordinator.data["monthly_consumption_dag_kwh"] = 0.0
    coordinator.data["monthly_consumption_natt_kwh"] = 0.0
    coordinator.data["monthly_consumption_total_kwh"] = 0.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = MaanedligTotalSensor(coordinator, entry)
    attrs = sensor.extra_state_attributes

    assert attrs["vektet_snittpris_kr_per_kwh"] is None
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "vektet_snittpris" -v`
Expected: FAIL

**Step 3: Implement**

I MaanedligTotalSensor.extra_state_attributes (~linje 1443), legg til i return-dict:

```python
total_kostnad = nettleie + avgifter - stotte  # allerede beregnet
return {
    # ... eksisterende attributter ...
    "vektet_snittpris_kr_per_kwh": round(total_kostnad / total_kwh, 4) if total_kwh > 0 else None,
}
```

**Step 4: Run test to verify it passes**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "vektet_snittpris" -v`
Expected: PASS

**Step 5: Commit**

```
git add custom_components/stromkalkulator/sensor.py tests/test_monthly_sensors.py
git commit -m "feat: attributt vektet snittpris (kr/kWh) på månedlig total"
```

---

### Task 3: Daglig kostnadsakkumulering i coordinator

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py`
  - Ny instansvariabel `_daily_cost: float` (linje ~133)
  - Nullstill ved datobytte i `_async_update_data` (linje ~209)
  - Akkumuler etter energi-beregning (~linje 350)
  - Eksponere `daily_cost_kr` i return-dict (~linje 407)
  - Lagre/laste i `_save_stored_data`/`_load_stored_data`
- Test: `tests/test_coordinator_update.py`

**Step 1: Write the failing test**

```python
def test_daily_cost_accumulates(hass, coordinator):
    """Dagskostnad akkumuleres fra energi × pris."""
    # Sett opp coordinator med kjent energi og priser
    # Kjør _async_update_data to ganger
    # Verifiser at daily_cost_kr > 0 og øker for hver oppdatering
    data = await coordinator._async_update_data()
    assert "daily_cost_kr" in data


def test_daily_cost_resets_at_date_change(hass, coordinator):
    """Dagskostnad nullstilles ved datobytte."""
    # Kjør oppdatering for dag 1
    # Endre now til dag 2
    # Kjør oppdatering igjen
    # Verifiser at daily_cost_kr er tilbakestilt (nær 0)
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_coordinator_update.py -k "daily_cost" -v`
Expected: FAIL — `daily_cost_kr` not in data

**Step 3: Implement**

I coordinator.py:

1. Legg til instansvariabler (~linje 133):
```python
self._daily_cost = 0.0
self._current_date = dt_util.now().strftime("%Y-%m-%d")
```

2. Nullstill ved datobytte, etter `today_str` beregnes (~linje 210):
```python
if today_str != self._current_date:
    self._daily_cost = 0.0
    self._current_date = today_str
```

3. Akkumuler etter energi-beregning og prisberegning (~linje 350, etter `energy_kwh` og `total_price_inkl_avgifter` er kjent):
```python
if energy_kwh > 0:
    self._daily_cost += (total_price_inkl_avgifter - stromstotte) * energy_kwh
```

4. Eksponere i return-dict (~linje 407):
```python
"daily_cost_kr": round(self._daily_cost, 2),
```

5. Lagre i `_save_stored_data`:
```python
"daily_cost": self._daily_cost,
"current_date": self._current_date,
```

6. Laste i `_load_stored_data`:
```python
self._daily_cost = self._validate_float(data.get("daily_cost", 0.0))
self._current_date = data.get("current_date", dt_util.now().strftime("%Y-%m-%d"))
```

**Step 4: Run test to verify it passes**

Run: `pipx run pytest tests/test_coordinator_update.py -k "daily_cost" -v`
Expected: PASS

**Step 5: Commit**

```
git add custom_components/stromkalkulator/coordinator.py tests/test_coordinator_update.py
git commit -m "feat: akkumuler daglig kostnad i coordinator"
```

---

### Task 4: Sensor DagskostnadSensor

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py`
  - Ny klasse DagskostnadSensor (~etter MaanedligNorgesprisDifferanseSensor)
  - Registrer i async_setup_entry entity-listen
- Test: `tests/test_monthly_sensors.py`

**Step 1: Write the failing test**

```python
def test_dagskostnad_sensor(coordinator_with_data):
    """Dagskostnad-sensor leser daily_cost_kr."""
    coordinator = coordinator_with_data
    coordinator.data["daily_cost_kr"] = 42.50

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = DagskostnadSensor(coordinator, entry)
    assert sensor.native_value == 42.50
    assert sensor.native_unit_of_measurement == "kr"
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "dagskostnad" -v`
Expected: FAIL — ImportError

**Step 3: Implement**

```python
class DagskostnadSensor(MaanedligBaseSensor):
    """Sensor for today's accumulated cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:calendar-today"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "dagskostnad", "dagskostnad")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:calendar-today"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Return today's accumulated cost."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("daily_cost_kr"))
        return None
```

Registrer i async_setup_entry (~linje 98, under Månedlig-gruppen):
```python
DagskostnadSensor(coordinator, entry),
```

**Step 4: Run test to verify it passes**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "dagskostnad" -v`
Expected: PASS

**Step 5: Commit**

```
git add custom_components/stromkalkulator/sensor.py tests/test_monthly_sensors.py
git commit -m "feat: sensor for dagens kostnad"
```

---

### Task 5: Sensor EstimertMaanedskostnadSensor

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py`
  - Ny klasse EstimertMaanedskostnadSensor
  - Registrer i async_setup_entry
- Test: `tests/test_monthly_sensors.py`

**Step 1: Write the failing test**

```python
def test_estimert_maanedskostnad(coordinator_with_data):
    """Estimert månedskostnad projiserer fra hittil-data."""
    coordinator = coordinator_with_data
    # Simuler: 15 dager inn i en 30-dagers måned, 500 kr hittil
    coordinator.data["monthly_consumption_dag_kwh"] = 375.0
    coordinator.data["monthly_consumption_natt_kwh"] = 125.0
    coordinator.data["monthly_consumption_total_kwh"] = 500.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = EstimertMaanedskostnadSensor(coordinator, entry)
    value = sensor.native_value

    # Estimat skal være > 0 og > nåværende månedlig total
    assert value is not None
    assert value > 0


def test_estimert_maanedskostnad_first_day(coordinator_with_data):
    """Dag 1 av måneden: estimat basert på 1 dags data."""
    coordinator = coordinator_with_data
    coordinator.data["monthly_consumption_dag_kwh"] = 10.0
    coordinator.data["monthly_consumption_natt_kwh"] = 5.0
    coordinator.data["monthly_consumption_total_kwh"] = 15.0

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "alminnelig"}
    sensor = EstimertMaanedskostnadSensor(coordinator, entry)
    value = sensor.native_value
    assert value is not None
    assert value > 0
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "estimert" -v`
Expected: FAIL

**Step 3: Implement**

```python
class EstimertMaanedskostnadSensor(MaanedligBaseSensor):
    """Sensor for estimated total monthly cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_icon: str = "mdi:crystal-ball"
    _attr_suggested_display_precision: int = 0
    _avgiftssone: str

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "estimert_maanedskostnad", "estimert_maanedskostnad")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_icon = "mdi:crystal-ball"
        self._attr_suggested_display_precision = 0
        self._avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    @property
    def native_value(self) -> float | None:
        """Project current month cost to full month."""
        if not self.coordinator.data:
            return None

        now = dt_util.now()
        day_of_month = now.day
        days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1)).day if now.month < 12 else 31

        # Beregn nåværende månedlig total (samme logikk som MaanedligTotalSensor)
        dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
        natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
        total_kwh = dag_kwh + natt_kwh
        dag_pris = self.coordinator.data.get("energiledd_dag", 0)
        natt_pris = self.coordinator.data.get("energiledd_natt", 0)
        kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
        stromstotte = self.coordinator.data.get("stromstotte", 0)

        month = now.month
        forbruksavgift = get_forbruksavgift(self._avgiftssone, month)
        mva_sats = get_mva_sats(self._avgiftssone)

        nettleie = (dag_kwh * dag_pris) + (natt_kwh * natt_pris) + kapasitet
        avgifter = total_kwh * ((forbruksavgift + ENOVA_AVGIFT) * (1 + mva_sats))
        stotte = total_kwh * stromstotte
        current_cost = nettleie + avgifter - stotte

        if day_of_month == 0:
            return None

        # Projiser: (kostnad hittil / dager hittil) × dager i måneden
        # Kapasitetsledd er fast per måned, ikke projiser den
        variable_cost = current_cost - kapasitet
        estimated_variable = (variable_cost / day_of_month) * days_in_month
        return round(estimated_variable + kapasitet, 0)
```

Registrer i async_setup_entry:
```python
EstimertMaanedskostnadSensor(coordinator, entry),
```

**Step 4: Run test to verify it passes**

Run: `pipx run pytest tests/test_monthly_sensors.py -k "estimert" -v`
Expected: PASS

**Step 5: Commit**

```
git add custom_components/stromkalkulator/sensor.py tests/test_monthly_sensors.py
git commit -m "feat: sensor for estimert månedskostnad"
```

---

### Task 6: i18n — oversettelser

**Files:**
- Modify: `custom_components/stromkalkulator/strings.json`
- Modify: `custom_components/stromkalkulator/translations/nb.json`
- Modify: `custom_components/stromkalkulator/translations/en.json`

**Step 1:** Legg til oversettelser for `dagskostnad` og `estimert_maanedskostnad` i alle 3 filer. Følg eksisterende mønster for sensor-navn.

**Step 2:** Run lint: `pipx run ruff check custom_components/stromkalkulator/`

**Step 3: Commit**

```
git commit -m "i18n: oversettelser for dagskostnad og estimert månedskostnad"
```

---

### Task 7: Kjør full testsuite + deploy

**Step 1:** `pipx run pytest tests/ -v`
**Step 2:** `pipx run ruff check custom_components/stromkalkulator/ tests/`
**Step 3:** Commit eventuelle fikser
**Step 4:** Push til GitHub
**Step 5:** SCP til ha-ts og restart HA
**Step 6:** Sjekk HA-logger for feil
