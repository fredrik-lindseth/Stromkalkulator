# Nye sensorer: Margin, Norgespris-besparelse, Strømstøtte-tak

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Legg til margin til neste kapasitetstrinn (sensor + binary sensor), akkumulert Norgespris-besparelse, og 5000 kWh strømstøtte-tak.

**Architecture:** Tre uavhengige features som alle følger samme mønster: beregning i coordinator → data i return dict → sensor i sensor.py. Feature 3 endrer også eksisterende strømstøtte-beregning. Ny config-key for varsel-terskel i options flow.

**Tech Stack:** Python, Home Assistant DataUpdateCoordinator, pytest

---

### Task 1: Strømstøtte 5000 kWh-tak — tester

Starter med denne fordi den endrer eksisterende beregningslogikk.

**Files:**
- Create: `tests/test_stromstotte_tak.py`

**Step 1: Write the tests**

```python
"""Test 5000 kWh strømstøtte-tak."""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_MAX_KWH,
    STROMSTOTTE_RATE,
)


def calculate_stromstotte(
    spot_price: float,
    har_norgespris: bool,
    monthly_consumption_kwh: float,
) -> float:
    """Calculate strømstøtte with 5000 kWh cap."""
    if har_norgespris:
        return 0.0
    if monthly_consumption_kwh >= STROMSTOTTE_MAX_KWH:
        return 0.0
    if spot_price > STROMSTOTTE_LEVEL:
        return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
    return 0.0


def stromstotte_gjenstaaende(monthly_consumption_kwh: float) -> float:
    """Calculate remaining kWh before cap."""
    return max(0.0, STROMSTOTTE_MAX_KWH - monthly_consumption_kwh)


class TestStromstotteTak:
    """Test 5000 kWh monthly cap on strømstøtte."""

    def test_under_cap_gets_support(self) -> None:
        result = calculate_stromstotte(1.20, False, 3000.0)
        expected = (1.20 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        assert result == pytest.approx(expected, abs=0.001)

    def test_at_cap_gets_no_support(self) -> None:
        result = calculate_stromstotte(1.20, False, 5000.0)
        assert result == 0.0

    def test_over_cap_gets_no_support(self) -> None:
        result = calculate_stromstotte(1.20, False, 6000.0)
        assert result == 0.0

    def test_norgespris_always_zero(self) -> None:
        result = calculate_stromstotte(1.20, True, 1000.0)
        assert result == 0.0

    def test_under_threshold_no_support(self) -> None:
        result = calculate_stromstotte(0.50, False, 1000.0)
        assert result == 0.0

    def test_gjenstaaende_under_cap(self) -> None:
        assert stromstotte_gjenstaaende(3000.0) == 2000.0

    def test_gjenstaaende_at_cap(self) -> None:
        assert stromstotte_gjenstaaende(5000.0) == 0.0

    def test_gjenstaaende_over_cap(self) -> None:
        assert stromstotte_gjenstaaende(6000.0) == 0.0

    def test_gjenstaaende_zero_consumption(self) -> None:
        assert stromstotte_gjenstaaende(0.0) == 5000.0
```

**Step 2: Run tests to verify they pass** (the test file contains its own functions)

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/test_stromstotte_tak.py -v`

**Step 3: Commit**

```bash
git add tests/test_stromstotte_tak.py
git commit -m "test: strømstøtte 5000 kWh-tak"
```

---

### Task 2: Strømstøtte 5000 kWh-tak — implementering i coordinator

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py`

**Step 1: Add 5000 kWh cap check to strømstøtte-beregning**

In `_async_update_data()`, after line 173 where `avg_power` is calculated, the monthly total is already available. Modify the strømstøtte-beregning (lines 185-195) to check against the cap:

```python
        # Calculate strømstøtte
        monthly_total_kwh = self._monthly_consumption["dag"] + self._monthly_consumption["natt"]
        stromstotte: float
        if self.har_norgespris:
            stromstotte = 0.0
        elif monthly_total_kwh >= STROMSTOTTE_MAX_KWH:
            stromstotte = 0.0
        elif spot_price > STROMSTOTTE_LEVEL:
            stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        else:
            stromstotte = 0.0

        stromstotte_gjenstaaende = max(0.0, STROMSTOTTE_MAX_KWH - monthly_total_kwh)
```

Add `STROMSTOTTE_MAX_KWH` to the import from `.const`.

Add to the return dict:
```python
            "stromstotte_tak_naadd": monthly_total_kwh >= STROMSTOTTE_MAX_KWH,
            "stromstotte_gjenstaaende_kwh": round(stromstotte_gjenstaaende, 1),
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 3: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py
git commit -m "feat: strømstøtte 5000 kWh månedlig tak"
```

---

### Task 3: Strømstøtte-tak — nye sensorer

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py`

**Step 1: Add StromstotteGjenstaaendeSensor**

Add after `StromstotteKwhSensor` class (around line 950):

```python
class StromstotteGjenstaaendeSensor(NettleieBaseSensor):
    """Sensor for remaining kWh before strømstøtte cap."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:gauge"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte_gjenstaaende", "stromstotte_gjenstaaende")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return remaining kWh."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("stromstotte_gjenstaaende_kwh"))
        return None
```

**Step 2: Add `tak_naadd` attribute to existing StromstotteSensor**

In `StromstotteSensor.extra_state_attributes` (line 501-508), add:

```python
                "tak_naadd": self.coordinator.data.get("stromstotte_tak_naadd", False),
```

**Step 3: Register sensor in `async_setup_entry`**

Add to entities list (around line 81):

```python
        StromstotteGjenstaaendeSensor(coordinator, entry),
```

**Step 4: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/sensor.py
git commit -m "feat: sensor for gjenstående kWh før strømstøtte-tak"
```

---

### Task 4: Margin til neste kapasitetstrinn — tester

**Files:**
- Create: `tests/test_margin_neste_trinn.py`

**Step 1: Write the tests**

```python
"""Test margin til neste kapasitetstrinn."""

from __future__ import annotations

import pytest

BKK_KAPASITETSTRINN = [
    (2, 155),
    (5, 250),
    (10, 415),
    (15, 600),
    (20, 770),
    (25, 940),
    (50, 1800),
    (75, 2650),
    (100, 3500),
    (float("inf"), 6900),
]


def calculate_margin(
    avg_power: float,
    kapasitetstrinn: list[tuple[float, int]],
) -> tuple[float, int, int]:
    """Calculate margin to next capacity tier.

    Returns: (margin_kw, current_price, next_price)
    """
    current_price = kapasitetstrinn[-1][1]
    for i, (threshold, price) in enumerate(kapasitetstrinn):
        if avg_power <= threshold:
            current_price = price
            # Find next tier
            if i + 1 < len(kapasitetstrinn):
                next_threshold = kapasitetstrinn[i + 1][0]
                next_price = kapasitetstrinn[i + 1][1]
                margin = threshold - avg_power
                return margin, current_price, next_price
            # Already on highest tier
            return 0.0, current_price, current_price
    return 0.0, current_price, current_price


class TestMarginNesteTrinn:
    """Test margin calculation."""

    def test_low_consumption_tier1(self) -> None:
        margin, current, neste = calculate_margin(1.0, BKK_KAPASITETSTRINN)
        assert margin == 1.0  # 2.0 - 1.0
        assert current == 155
        assert neste == 250

    def test_at_boundary(self) -> None:
        margin, current, neste = calculate_margin(2.0, BKK_KAPASITETSTRINN)
        assert margin == 0.0  # exactly at boundary
        assert current == 155
        assert neste == 250

    def test_mid_tier(self) -> None:
        margin, current, neste = calculate_margin(7.5, BKK_KAPASITETSTRINN)
        assert margin == 2.5  # 10.0 - 7.5
        assert current == 415
        assert neste == 600

    def test_highest_tier(self) -> None:
        margin, current, neste = calculate_margin(150.0, BKK_KAPASITETSTRINN)
        assert margin == 0.0
        assert current == 6900
        assert neste == 6900  # no next tier

    def test_zero_consumption(self) -> None:
        margin, current, neste = calculate_margin(0.0, BKK_KAPASITETSTRINN)
        assert margin == 2.0
        assert current == 155
        assert neste == 250


class TestKapasitetVarsel:
    """Test binary sensor threshold logic."""

    def test_varsel_when_margin_under_threshold(self) -> None:
        margin, _, _ = calculate_margin(9.0, BKK_KAPASITETSTRINN)
        terskel = 2.0
        assert margin < terskel  # 1.0 < 2.0 → varsel

    def test_no_varsel_when_margin_over_threshold(self) -> None:
        margin, _, _ = calculate_margin(3.0, BKK_KAPASITETSTRINN)
        terskel = 2.0
        assert not (margin < terskel)  # 2.0 is not < 2.0

    def test_varsel_at_exact_threshold(self) -> None:
        margin, _, _ = calculate_margin(8.0, BKK_KAPASITETSTRINN)
        terskel = 2.0
        assert not (margin < terskel)  # 2.0 is not < 2.0, no varsel

    def test_highest_tier_always_warns(self) -> None:
        margin, _, _ = calculate_margin(150.0, BKK_KAPASITETSTRINN)
        terskel = 2.0
        assert margin < terskel  # 0.0 < 2.0 → varsel
```

**Step 2: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/test_margin_neste_trinn.py -v`

**Step 3: Commit**

```bash
git add tests/test_margin_neste_trinn.py
git commit -m "test: margin til neste kapasitetstrinn"
```

---

### Task 5: Margin til neste trinn — coordinator + config

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py`
- Modify: `custom_components/stromkalkulator/const.py`

**Step 1: Add config constant**

In `const.py`, add:

```python
CONF_KAPASITET_VARSEL_TERSKEL: Final[str] = "kapasitet_varsel_terskel"
DEFAULT_KAPASITET_VARSEL_TERSKEL: Final[float] = 2.0
```

**Step 2: Add margin calculation to coordinator**

In `coordinator.__init__()`, add after line 97:

```python
        self.kapasitet_varsel_terskel = float(
            entry.data.get(CONF_KAPASITET_VARSEL_TERSKEL, DEFAULT_KAPASITET_VARSEL_TERSKEL)
        )
```

Add imports for `CONF_KAPASITET_VARSEL_TERSKEL` and `DEFAULT_KAPASITET_VARSEL_TERSKEL`.

In `_async_update_data()`, after the capacity tier calculation (line 176), add:

```python
        # Calculate margin to next tier
        margin_neste_trinn = 0.0
        neste_trinn_pris = kapasitetsledd
        for i, (threshold, price) in enumerate(self.kapasitetstrinn):
            if avg_power <= threshold:
                if i + 1 < len(self.kapasitetstrinn):
                    margin_neste_trinn = round(threshold - avg_power, 2)
                    neste_trinn_pris = self.kapasitetstrinn[i + 1][1]
                break

        kapasitet_varsel = margin_neste_trinn < self.kapasitet_varsel_terskel
```

Add to the return dict:

```python
            "margin_neste_trinn_kw": margin_neste_trinn,
            "neste_trinn_pris": neste_trinn_pris,
            "kapasitet_varsel": kapasitet_varsel,
```

**Step 3: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py custom_components/stromkalkulator/const.py
git commit -m "feat: beregn margin til neste kapasitetstrinn"
```

---

### Task 6: Margin til neste trinn — sensorer

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py`

**Step 1: Add MarginNesteTrinnSensor**

Add in the Nettleie-Kapasitet section (after `KapasitetstrinnSensor`):

```python
class MarginNesteTrinnSensor(NettleieBaseSensor):
    """Sensor for margin to next capacity tier."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:arrow-up-bold"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "margin_neste_trinn", "margin_neste_trinn")
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:arrow-up-bold"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return margin in kW."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("margin_neste_trinn_kw"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "nåværende_trinn_pris": self.coordinator.data.get("kapasitetsledd"),
                "neste_trinn_pris": self.coordinator.data.get("neste_trinn_pris"),
            }
        return None
```

**Step 2: Add KapasitetVarselSensor (binary-like)**

```python
class KapasitetVarselSensor(NettleieBaseSensor):
    """Binary-like sensor that warns when close to next capacity tier."""

    _attr_icon: str = "mdi:alert"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitet_varsel", "kapasitet_varsel")
        self._attr_icon = "mdi:alert"

    @property
    def native_value(self) -> str | None:
        """Return 'on' or 'off'."""
        if self.coordinator.data:
            varsel = self.coordinator.data.get("kapasitet_varsel", False)
            return "on" if varsel else "off"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "margin_kw": self.coordinator.data.get("margin_neste_trinn_kw"),
                "terskel_kw": self.coordinator.entry.data.get("kapasitet_varsel_terskel", 2.0),
            }
        return None
```

**Step 3: Register in `async_setup_entry`**

Add to entities list after `KapasitetstrinnSensor`:

```python
        MarginNesteTrinnSensor(coordinator, entry),
        KapasitetVarselSensor(coordinator, entry),
```

**Step 4: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/sensor.py
git commit -m "feat: sensorer for margin til neste trinn + kapasitetsvarsel"
```

---

### Task 7: Margin til neste trinn — options flow

**Files:**
- Modify: `custom_components/stromkalkulator/config_flow.py`
- Modify: `custom_components/stromkalkulator/translations/nb.json`
- Modify: `custom_components/stromkalkulator/translations/en.json`

**Step 1: Add terskel to options flow**

In `config_flow.py`, import the new constants:

```python
from .const import (
    ...
    CONF_KAPASITET_VARSEL_TERSKEL,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
)
```

In `NettleieOptionsFlow.async_step_init()`, add to the schema (inside `options_schema`, after `CONF_ENERGILEDD_NATT`):

```python
                vol.Optional(
                    CONF_KAPASITET_VARSEL_TERSKEL,
                    default=current.get(CONF_KAPASITET_VARSEL_TERSKEL, DEFAULT_KAPASITET_VARSEL_TERSKEL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.5,
                        unit_of_measurement="kW",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
```

**Step 2: Add translations**

In `nb.json`, add to `options.step.init.data`:

```json
"kapasitet_varsel_terskel": "Kapasitetsvarsel-terskel (kW)"
```

In `nb.json`, add to `options.step.init.data_description`:

```json
"kapasitet_varsel_terskel": "Varsle når margin til neste kapasitetstrinn er under denne verdien. Standard: 2.0 kW."
```

Update `en.json` similarly with English text.

**Step 3: Run tests + lint**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v && ruff check custom_components/stromkalkulator/ tests/`

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/config_flow.py custom_components/stromkalkulator/translations/
git commit -m "feat: konfigurerbar terskel for kapasitetsvarsel"
```

---

### Task 8: Akkumulert Norgespris-besparelse — tester

**Files:**
- Create: `tests/test_norgespris_akkumulert.py`

**Step 1: Write the tests**

```python
"""Test akkumulert Norgespris-besparelse."""

from __future__ import annotations

import pytest


def accumulate_norgespris_diff(
    har_norgespris: bool,
    spot_total: float,
    norgespris_total: float,
    forbruk_kwh: float,
    existing_diff: float,
) -> float:
    """Accumulate kr saved/lost vs alternative.

    Positive = saving with current plan.
    """
    if har_norgespris:
        # User has Norgespris, compare with spot
        diff_per_kwh = spot_total - norgespris_total
    else:
        # User has spot, compare with Norgespris
        diff_per_kwh = norgespris_total - spot_total

    return existing_diff + diff_per_kwh * forbruk_kwh


class TestNorgesprisAkkumulert:
    """Test accumulated Norgespris comparison."""

    def test_spot_user_saves_vs_norgespris(self) -> None:
        """Spot at 0.30, Norgespris at 0.50 → saving."""
        result = accumulate_norgespris_diff(
            har_norgespris=False,
            spot_total=0.30,
            norgespris_total=0.50,
            forbruk_kwh=10.0,
            existing_diff=0.0,
        )
        assert result == pytest.approx(2.0)  # (0.50 - 0.30) * 10

    def test_spot_user_loses_vs_norgespris(self) -> None:
        """Spot at 0.80, Norgespris at 0.50 → losing."""
        result = accumulate_norgespris_diff(
            har_norgespris=False,
            spot_total=0.80,
            norgespris_total=0.50,
            forbruk_kwh=10.0,
            existing_diff=0.0,
        )
        assert result == pytest.approx(-3.0)  # (0.50 - 0.80) * 10

    def test_norgespris_user_saves_vs_spot(self) -> None:
        """Norgespris at 0.50, spot at 0.80 → saving."""
        result = accumulate_norgespris_diff(
            har_norgespris=True,
            spot_total=0.80,
            norgespris_total=0.50,
            forbruk_kwh=10.0,
            existing_diff=0.0,
        )
        assert result == pytest.approx(3.0)  # (0.80 - 0.50) * 10

    def test_accumulation_over_time(self) -> None:
        """Test that values accumulate correctly."""
        diff = 0.0
        diff = accumulate_norgespris_diff(False, 0.30, 0.50, 5.0, diff)
        assert diff == pytest.approx(1.0)
        diff = accumulate_norgespris_diff(False, 0.80, 0.50, 5.0, diff)
        assert diff == pytest.approx(-0.5)  # 1.0 + (-1.5)

    def test_zero_consumption_no_change(self) -> None:
        result = accumulate_norgespris_diff(False, 0.80, 0.50, 0.0, 5.0)
        assert result == pytest.approx(5.0)
```

**Step 2: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/test_norgespris_akkumulert.py -v`

**Step 3: Commit**

```bash
git add tests/test_norgespris_akkumulert.py
git commit -m "test: akkumulert Norgespris-besparelse"
```

---

### Task 9: Akkumulert Norgespris-besparelse — coordinator

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py`

**Step 1: Add accumulator to coordinator**

In `__init__()`, add after `_monthly_consumption` init (line 106):

```python
        self._monthly_norgespris_diff = 0.0
```

Add type annotation at class level:

```python
    _monthly_norgespris_diff: float
```

**Step 2: Accumulate diff in `_async_update_data()`**

After the consumption accumulation block (after line 157), add:

```python
        # Accumulate Norgespris diff
        if self._last_update is not None and current_power_kw > 0:
            # total_price and total_pris_norgespris are calculated later,
            # so we calculate inline here
            ...
```

Actually, the Norgespris diff calculation needs spot price and total prices which are calculated later. So place this AFTER line 244 (after `kroner_spart_per_kwh` calculation), using `energy_kwh` from the earlier block:

```python
        # Accumulate monthly Norgespris comparison
        if consumption_updated and energy_kwh > 0:
            if self.har_norgespris:
                diff_per_kwh = total_price_uten_stotte - total_pris_norgespris
            else:
                diff_per_kwh = total_pris_norgespris - total_price
            self._monthly_norgespris_diff += diff_per_kwh * energy_kwh
```

Note: need to hoist `energy_kwh` to be accessible outside the if block. Initialize `energy_kwh = 0.0` before the consumption block.

**Step 3: Reset at month change**

In the month-reset block (line 137-139), add:

```python
            self._monthly_norgespris_diff = 0.0
```

**Step 4: Add to return dict**

```python
            "monthly_norgespris_diff_kr": round(self._monthly_norgespris_diff, 2),
```

**Step 5: Add to save/load**

In `_save_stored_data()`, add to data dict:

```python
            "monthly_norgespris_diff": self._monthly_norgespris_diff,
```

In `_load_stored_data()`, add after monthly_consumption load:

```python
            self._monthly_norgespris_diff = data.get("monthly_norgespris_diff", 0.0)
```

Also clear on month mismatch (line 400-401 area):

```python
                self._monthly_norgespris_diff = 0.0
```

**Step 6: Run tests**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 7: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py
git commit -m "feat: akkumuler Norgespris-differanse per måned"
```

---

### Task 10: Akkumulert Norgespris-besparelse — sensor

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py`

**Step 1: Add MaanedligNorgesprisDifferanseSensor**

Add in the Månedlig section (after `MaanedligTotalSensor`):

```python
class MaanedligNorgesprisDifferanseSensor(NettleieBaseSensor):
    """Sensor for accumulated monthly Norgespris savings/loss."""

    _device_group: str = DEVICE_MAANEDLIG
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:scale-balance"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_norgespris_diff", "maanedlig_norgespris_diff")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:scale-balance"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Return accumulated diff in kr."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_norgespris_diff_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            har_norgespris = self.coordinator.data.get("har_norgespris", False)
            return {
                "sammenligner_med": "spotpris" if har_norgespris else "Norgespris",
                "positiv_betyr": "du sparer med nåværende avtale",
            }
        return None
```

**Step 2: Register in `async_setup_entry`**

Add to entities list after `MaanedligTotalSensor`:

```python
        MaanedligNorgesprisDifferanseSensor(coordinator, entry),
```

**Step 3: Run tests + lint**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v && ruff check custom_components/stromkalkulator/ tests/`

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/sensor.py
git commit -m "feat: sensor for akkumulert Norgespris-besparelse"
```

---

### Task 11: Translations for alle nye sensorer

**Files:**
- Modify: `custom_components/stromkalkulator/translations/nb.json`
- Modify: `custom_components/stromkalkulator/translations/en.json`

**Step 1: Check existing translation keys**

Look at how existing sensors reference translation keys — `sensor.py` uses `translation_key` parameter.

New keys needed:
- `margin_neste_trinn`
- `kapasitet_varsel`
- `stromstotte_gjenstaaende`
- `maanedlig_norgespris_diff`

**Step 2: Add to nb.json**

Add `entity` section if not present:

```json
{
  "entity": {
    "sensor": {
      "margin_neste_trinn": { "name": "Margin til neste trinn" },
      "kapasitet_varsel": { "name": "Kapasitetsvarsel" },
      "stromstotte_gjenstaaende": { "name": "Strømstøtte gjenstående" },
      "maanedlig_norgespris_diff": { "name": "Norgespris besparelse" }
    }
  }
}
```

**Step 3: Add to en.json similarly**

**Step 4: Run lint**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && ruff check custom_components/stromkalkulator/ tests/`

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/translations/
git commit -m "feat: oversettelser for nye sensorer"
```

---

### Task 12: Endelig verifikasjon

**Step 1: Run full test suite**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && python -m pytest tests/ -v`

**Step 2: Run linter**

Run: `cd /Users/fredrik/dev/hacs-strømkalkulator && ruff check custom_components/stromkalkulator/ tests/`

**Step 3: Review all changes**

Run: `git diff main --stat` to verify scope.

**Step 4: Bump version if appropriate**
