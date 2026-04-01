# Strømpris per kWh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two sensors showing electricity price per kWh without estimated capacity fee (kapasitetsledd).

**Architecture:** Two new coordinator data keys + two sensor classes following existing patterns. No changes to existing sensors.

**Tech Stack:** Python, Home Assistant sensor platform, pytest

---

### Task 1: Add coordinator calculations

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py:246-257` (price calculation block)
- Modify: `custom_components/stromkalkulator/coordinator.py:297-326` (return dict)

**Step 1: Add calculations after existing total_price block (line 257)**

After the `total_pris_norgespris` line, add:

```python
        # Strømpris per kWh (uten kapasitetsledd)
        if self.har_norgespris:
            strompris_per_kwh = norgespris + energiledd
            strompris_per_kwh_etter_stotte = norgespris + energiledd
        else:
            strompris_per_kwh = spot_price + energiledd
            strompris_per_kwh_etter_stotte = spot_price - stromstotte + energiledd
```

**Step 2: Add to return dict (after `total_price_inkl_avgifter`)**

```python
            "strompris_per_kwh": round(strompris_per_kwh, 4),
            "strompris_per_kwh_etter_stotte": round(strompris_per_kwh_etter_stotte, 4),
```

**Step 3: Run existing tests to verify nothing breaks**

Run: `pipx run pytest tests/ -v`
Expected: All existing tests PASS

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py
git commit -m "feat: beregn strømpris per kWh uten kapasitetsledd"
```

---

### Task 2: Write tests for new calculations

**Files:**
- Create: `tests/test_strompris_per_kwh.py`

**Step 1: Write test file**

```python
"""Test strømpris per kWh (uten kapasitetsledd).

Tester at de nye sensorene korrekt beregner strømpris + energiledd
uten å inkludere estimert kapasitetsledd per kWh.
"""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE


def calculate_strompris_per_kwh(
    spot_price: float,
    energiledd: float,
    har_norgespris: bool = False,
    norgespris: float = 0.50,
) -> float:
    """Strømpris per kWh uten kapasitetsledd (før støtte)."""
    if har_norgespris:
        return round(spot_price, 4)  # norgespris + energiledd passed as spot_price
    return round(spot_price + energiledd, 4)


def calculate_strompris_per_kwh_etter_stotte(
    spot_price: float,
    energiledd: float,
    stromstotte: float = 0.0,
    har_norgespris: bool = False,
    norgespris: float = 0.50,
) -> float:
    """Strømpris per kWh uten kapasitetsledd (etter støtte)."""
    if har_norgespris:
        return round(norgespris + energiledd, 4)
    return round(spot_price - stromstotte + energiledd, 4)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def energiledd_dag() -> float:
    """BKK energiledd dag 2026."""
    return 0.4613


@pytest.fixture
def energiledd_natt() -> float:
    """BKK energiledd natt 2026."""
    return 0.2329


# =============================================================================
# Før støtte — standard spotpris
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd", "expected"),
    [
        (0.50, 0.4613, 0.9613),   # Lav spotpris + dag-energiledd
        (1.20, 0.4613, 1.6613),   # Middels spotpris + dag-energiledd
        (2.00, 0.2329, 2.2329),   # Høy spotpris + natt-energiledd
        (0.00, 0.4613, 0.4613),   # Null spotpris
        (-0.10, 0.4613, 0.3613),  # Negativ spotpris
    ],
    ids=["lav_dag", "middels_dag", "hoy_natt", "null_pris", "negativ_pris"],
)
def test_strompris_per_kwh_standard(
    spot_price: float, energiledd: float, expected: float
) -> None:
    """Strømpris per kWh = spotpris + energiledd, uten kapasitetsledd."""
    result = calculate_strompris_per_kwh_etter_stotte(
        spot_price=spot_price, energiledd=energiledd
    )
    assert result == expected


# =============================================================================
# Etter støtte — spotpris over terskel
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd"),
    [
        (1.20, 0.4613),
        (2.00, 0.4613),
        (5.00, 0.2329),
    ],
    ids=["middels", "hoy", "ekstrem"],
)
def test_strompris_per_kwh_etter_stotte(
    spot_price: float, energiledd: float
) -> None:
    """Etter støtte = (spotpris - støtte) + energiledd."""
    stromstotte = round((spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    expected = round(spot_price - stromstotte + energiledd, 4)
    result = calculate_strompris_per_kwh_etter_stotte(
        spot_price=spot_price, energiledd=energiledd, stromstotte=stromstotte
    )
    assert result == expected


def test_strompris_per_kwh_under_terskel(energiledd_dag: float) -> None:
    """Under terskel: før og etter støtte er like."""
    spot = 0.50
    before = calculate_strompris_per_kwh(spot, energiledd_dag)
    after = calculate_strompris_per_kwh_etter_stotte(spot, energiledd_dag, stromstotte=0.0)
    assert before == after


# =============================================================================
# Norgespris
# =============================================================================


def test_strompris_per_kwh_norgespris(energiledd_dag: float) -> None:
    """Norgespris: bruker fast pris, ingen strømstøtte."""
    norgespris = 0.50
    result = calculate_strompris_per_kwh_etter_stotte(
        spot_price=1.50,  # ignorert
        energiledd=energiledd_dag,
        har_norgespris=True,
        norgespris=norgespris,
    )
    assert result == round(norgespris + energiledd_dag, 4)


def test_norgespris_for_og_etter_stotte_er_like(energiledd_dag: float) -> None:
    """Med Norgespris er før og etter støtte identiske."""
    norgespris = 0.50
    etter = calculate_strompris_per_kwh_etter_stotte(
        spot_price=1.50, energiledd=energiledd_dag,
        har_norgespris=True, norgespris=norgespris,
    )
    assert etter == round(norgespris + energiledd_dag, 4)


# =============================================================================
# Sammenligning med totalpris (med kapasitetsledd)
# =============================================================================


def test_strompris_alltid_lavere_enn_totalpris() -> None:
    """Strømpris per kWh skal alltid være lavere enn totalpris (som inkluderer kapasitetsledd)."""
    spot = 1.20
    energiledd = 0.4613
    kapasitetsledd_per_kwh = 0.0347  # Typisk verdi

    strompris = spot + energiledd
    totalpris = spot + energiledd + kapasitetsledd_per_kwh

    assert strompris < totalpris
```

**Step 2: Run tests**

Run: `pipx run pytest tests/test_strompris_per_kwh.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_strompris_per_kwh.py
git commit -m "test: tester for strømpris per kWh uten kapasitetsledd"
```

---

### Task 3: Add sensor classes

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py:76-77` (entity list)
- Modify: `custom_components/stromkalkulator/sensor.py` (new classes, after TotalPriceSensor ~line 329)

**Step 1: Add StromprisPerKwhSensor class after TotalPriceSensor (line 329)**

```python
class StromprisPerKwhSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh (without capacity fee)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:flash"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_per_kwh", "strompris_per_kwh")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("strompris_per_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spot_price": self.coordinator.data.get("spot_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
            }
        return None
```

**Step 2: Add StromprisPerKwhEtterStotteSensor after the class above**

```python
class StromprisPerKwhEtterStotteSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh after subsidy (without capacity fee)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:flash-outline"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_per_kwh_etter_stotte", "strompris_per_kwh_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash-outline"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("strompris_per_kwh_etter_stotte"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
            }
        return None
```

**Step 3: Register sensors in entity list (~line 76-77)**

Add after `ElectricityCompanyTotalSensor(coordinator, entry),`:

```python
        StromprisPerKwhSensor(coordinator, entry),
```

Add after `StromstotteGjenstaaendeSensor(coordinator, entry),` (in Strømstøtte section):

```python
        StromprisPerKwhEtterStotteSensor(coordinator, entry),
```

**Step 4: Run all tests**

Run: `pipx run pytest tests/ -v`
Expected: All PASS

**Step 5: Run linter**

Run: `pipx run ruff check custom_components/stromkalkulator/ tests/`
Expected: No errors

**Step 6: Commit**

```bash
git add custom_components/stromkalkulator/sensor.py
git commit -m "feat: sensorer for strømpris per kWh uten kapasitetsledd"
```

---

### Task 4: Add translations

**Files:**
- Modify: `custom_components/stromkalkulator/strings.json`
- Modify: `custom_components/stromkalkulator/translations/en.json`
- Modify: `custom_components/stromkalkulator/translations/nb.json`

**Step 1: Add to strings.json entity.sensor block (after `total_price` entry)**

```json
      "strompris_per_kwh": {
        "name": "Strømpris per kWh"
      },
```

And in the strømstøtte section (after `total_pris_inkl_avgifter`):

```json
      "strompris_per_kwh_etter_stotte": {
        "name": "Strømpris per kWh (etter støtte)"
      },
```

**Step 2: Add to translations/en.json entity.sensor block**

After `"total_price"`:
```json
      "strompris_per_kwh": { "name": "Electricity price per kWh" },
```

After `"total_pris_inkl_avgifter"`:
```json
      "strompris_per_kwh_etter_stotte": { "name": "Electricity price per kWh (after subsidy)" },
```

**Step 3: Add to translations/nb.json entity.sensor block**

After `"total_price"`:
```json
      "strompris_per_kwh": { "name": "Strømpris per kWh" },
```

After `"total_pris_inkl_avgifter"`:
```json
      "strompris_per_kwh_etter_stotte": { "name": "Strømpris per kWh (etter støtte)" },
```

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/strings.json custom_components/stromkalkulator/translations/
git commit -m "i18n: oversettelser for strømpris per kWh-sensorer"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `docs/SENSORS.md`
- Modify: `docs/beregninger.md`

**Step 1: Add to SENSORS.md — Nettleie section, Strømpris table (after line 51)**

Add row:
```
| Strømpris per kWh             | kr/kWh | Spotpris + energiledd (uten kapasitetsledd)     |
```

**Step 2: Add to SENSORS.md — Strømstøtte section table (after line 74)**

Add row:
```
| Strømpris per kWh (etter støtte) | kr/kWh | Spotpris + energiledd - strømstøtte (uten kapasitetsledd) |
```

**Step 3: Update sensor count in SENSORS.md overview (line 7)**

Change total from 36 to 38. Update Nettleie from 16 to 17, Strømstøtte from 5 to 6.

**Step 4: Add to beregninger.md — Total strømpris section (after line 235)**

```markdown
### Strømpris per kWh (uten kapasitetsledd)

Viser den faktiske variable kWh-prisen uten estimert kapasitetsledd.

```
strompris_per_kwh = spotpris + energiledd
strompris_per_kwh_etter_stotte = (spotpris - strømstøtte) + energiledd
```
```

**Step 5: Commit**

```bash
git add docs/SENSORS.md docs/beregninger.md
git commit -m "docs: dokumenter strømpris per kWh-sensorer"
```

---

### Task 6: Bump version

**Files:**
- Modify: `custom_components/stromkalkulator/manifest.json`

**Step 1: Bump version from 1.3.0 to 1.4.0**

Change `"version": "1.3.0"` to `"version": "1.4.0"`

**Step 2: Run full test suite + lint**

Run: `pipx run pytest tests/ -v && pipx run ruff check custom_components/stromkalkulator/ tests/`
Expected: All PASS, no lint errors

**Step 3: Commit**

```bash
git add custom_components/stromkalkulator/manifest.json
git commit -m "chore: bump versjon til 1.4.0"
```
