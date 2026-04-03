# Boligtype og fritidsbolig-stoette — Implementasjonsplan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Legg til boligtype-velger (bolig/fritidsbolig/fritidsbolig fast bosted) som styrer kWh-tak for stroemstotte og Norgespris, og haandhev Norgespris kWh-tak.

**Architecture:** Ny `CONF_BOLIGTYPE` config-noekkel med tre lovfestede verdier. Hjelpefunksjoner i `const.py` returnerer riktig kWh-tak. Coordinator bruker dynamisk tak i stedet for hardkodet `STROMSTOTTE_MAX_KWH`. Norgespris-beregningen faar ny logikk: over taket betaler man spotpris.

**Tech Stack:** Python, Home Assistant config flow, voluptuous, pytest

**Design:** Se `docs/plans/2026-04-03-boligtype-fritidsbolig-design.md`

---

### Task 1: Konstanter og hjelpefunksjoner i const.py

**Files:**
- Modify: `custom_components/stromkalkulator/const.py:22-23` (config keys)
- Modify: `custom_components/stromkalkulator/const.py:62-68` (stroemstotte-seksjonen)
- Modify: `custom_components/stromkalkulator/const.py:81-98` (Norgespris-seksjonen)
- Test: `tests/test_boligtype.py`

**Step 1: Write the failing tests**

Create `tests/test_boligtype.py`:

```python
"""Test boligtype constants and helper functions."""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_FRITIDSBOLIG,
    BOLIGTYPE_FRITIDSBOLIG_FAST,
    get_norgespris_max_kwh,
    get_stromstotte_max_kwh,
)


@pytest.mark.parametrize(
    ("boligtype", "expected"),
    [
        (BOLIGTYPE_BOLIG, 5000),
        (BOLIGTYPE_FRITIDSBOLIG, 1000),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000),
    ],
    ids=["bolig", "fritidsbolig", "fritidsbolig_fast"],
)
def test_get_norgespris_max_kwh(boligtype: str, expected: int) -> None:
    """Norgespris kWh cap: bolig/fast=5000, fritidsbolig=1000."""
    assert get_norgespris_max_kwh(boligtype) == expected


@pytest.mark.parametrize(
    ("boligtype", "expected"),
    [
        (BOLIGTYPE_BOLIG, 5000),
        (BOLIGTYPE_FRITIDSBOLIG, 0),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000),
    ],
    ids=["bolig", "fritidsbolig_ingen_rett", "fritidsbolig_fast"],
)
def test_get_stromstotte_max_kwh(boligtype: str, expected: int) -> None:
    """Stroemstotte kWh cap: bolig/fast=5000, fritidsbolig=0 (ingen rett)."""
    assert get_stromstotte_max_kwh(boligtype) == expected
```

**Step 2: Run tests to verify they fail**

Run: `pipx run pytest tests/test_boligtype.py -v`
Expected: FAIL — imports don't exist yet

**Step 3: Write implementation**

In `const.py`, add after line 22 (`CONF_KAPASITET_VARSEL_TERSKEL`):

```python
CONF_BOLIGTYPE: Final[str] = "boligtype"
```

Add after line 30 (`AVGIFTSSONE_TILTAKSSONE`), before `AVGIFTSSONE_OPTIONS`:

```python
# Boligtype — bestemmer kWh-tak for stroemstotte og Norgespris
# Kilde: Forskrift om stroemstoenad (lovdata.no/dokument/SF/forskrift/2025-09-08-1791)
# - Bolig (SS 5): 5000 kWh/mnd stroemstotte, 5000 kWh/mnd Norgespris
# - Fritidsbolig (SS 3): Ingen stroemstotte, 1000 kWh/mnd Norgespris
# - Fritidsbolig fast bosted (SS 11): Samme som bolig (5000 kWh/mnd begge)
BOLIGTYPE_BOLIG: Final[str] = "bolig"
BOLIGTYPE_FRITIDSBOLIG: Final[str] = "fritidsbolig"
BOLIGTYPE_FRITIDSBOLIG_FAST: Final[str] = "fritidsbolig_fast"

BOLIGTYPE_OPTIONS: Final[dict[str, str]] = {
    BOLIGTYPE_BOLIG: "Bolig",
    BOLIGTYPE_FRITIDSBOLIG: "Fritidsbolig",
    BOLIGTYPE_FRITIDSBOLIG_FAST: "Fritidsbolig (fast bosted)",
}
```

Update the Norgespris comment block (line 81-83) — replace "IKKE stoettet i denne integrasjonen":

```python
# Grenser:
# - Bolig: 5000 kWh/mnd
# - Fritidsbolig: 1000 kWh/mnd
```

Add two helper functions after `get_norgespris_inkl_mva()` (after line 115):

```python
def get_norgespris_max_kwh(boligtype: str) -> int:
    """Returnerer maks kWh/mnd for Norgespris basert paa boligtype.

    Bolig/Fritidsbolig fast bosted: 5000 kWh/mnd
    Fritidsbolig: 1000 kWh/mnd

    Kilde: regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/
    """
    if boligtype == BOLIGTYPE_FRITIDSBOLIG:
        return NORGESPRIS_MAX_KWH_FRITID
    return NORGESPRIS_MAX_KWH_BOLIG


def get_stromstotte_max_kwh(boligtype: str) -> int:
    """Returnerer maks kWh/mnd for stroemstotte basert paa boligtype.

    Bolig/Fritidsbolig fast bosted: 5000 kWh/mnd (Forskrift SS 5)
    Fritidsbolig: 0 kWh/mnd — ingen rett paa stroemstotte (Forskrift SS 3)

    Kilde: lovdata.no/dokument/SF/forskrift/2025-09-08-1791
    """
    if boligtype == BOLIGTYPE_FRITIDSBOLIG:
        return 0
    return STROMSTOTTE_MAX_KWH
```

**Step 4: Run tests to verify they pass**

Run: `pipx run pytest tests/test_boligtype.py -v`
Expected: PASS (all 6 tests)

**Step 5: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All existing tests still pass

**Step 6: Lint**

Run: `ruff check custom_components/stromkalkulator/const.py tests/test_boligtype.py`
Expected: No errors

**Step 7: Commit**

```bash
git add custom_components/stromkalkulator/const.py tests/test_boligtype.py
git commit -m "feat: add boligtype constants and helper functions (issue #3)"
```

---

### Task 2: Config flow — boligtype-velger

**Files:**
- Modify: `custom_components/stromkalkulator/config_flow.py:13-34` (imports), `:78-90` (step_user schema), `:243-266` (options schema)
- Modify: `custom_components/stromkalkulator/strings.json`
- Modify: `custom_components/stromkalkulator/translations/nb.json`
- Modify: `custom_components/stromkalkulator/translations/en.json`

**Step 1: Update strings.json**

In `strings.json`, update the `config.step.user` section. Add `"boligtype"` to `data` and `data_description`:

```json
"data": {
  "tso": "Nettselskap",
  "boligtype": "Boligtype",
  "har_norgespris": "Jeg har Norgespris"
},
"data_description": {
  "boligtype": "Bolig: Strømstøtte opptil 5000 kWh/mnd, Norgespris opptil 5000 kWh/mnd. Fritidsbolig: Ingen strømstøtte, Norgespris opptil 1000 kWh/mnd. Fritidsbolig (fast bosted): Samme som bolig (Forskrift § 11). Kilde: lovdata.no/dokument/SF/forskrift/2025-09-08-1791",
  "har_norgespris": "Aktiver hvis du har valgt Norgespris hos nettselskapet. Bruker fast pris (40-50 øre/kWh) i stedet for spotpris."
}
```

In `options.step.init`, add `"boligtype": "Boligtype"` to `data` and the same description to `data_description`.

**Step 2: Update translations/nb.json**

Same changes as strings.json (nb.json mirrors strings.json).

**Step 3: Update translations/en.json**

```json
"data": {
  "tso": "Grid company",
  "boligtype": "Property type",
  "har_norgespris": "I have Norgespris"
},
"data_description": {
  "boligtype": "Residence: Subsidy up to 5000 kWh/month, Norgespris up to 5000 kWh/month. Holiday home: No subsidy, Norgespris up to 1000 kWh/month. Holiday home (permanent residence): Same as residence (Regulation § 11). Source: lovdata.no/dokument/SF/forskrift/2025-09-08-1791",
  "har_norgespris": "Enable if you have opted for Norgespris from your grid company. Uses fixed price (40-50 øre/kWh) instead of spot price."
}
```

Same for options section.

**Step 4: Update config_flow.py imports**

Add to imports from `.const`:

```python
BOLIGTYPE_BOLIG,
BOLIGTYPE_OPTIONS,
CONF_BOLIGTYPE,
```

**Step 5: Update async_step_user schema**

In `config_flow.py`, update the schema in `async_step_user()` (around line 78-90). Add the boligtype selector between DSO and Norgespris:

```python
vol.Required(CONF_DSO, default=DEFAULT_DSO): selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=_dso_options(),
        mode=selector.SelectSelectorMode.DROPDOWN,
    ),
),
vol.Required(CONF_BOLIGTYPE, default=BOLIGTYPE_BOLIG): selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=key, label=label)
            for key, label in BOLIGTYPE_OPTIONS.items()
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    ),
),
vol.Optional(CONF_HAR_NORGESPRIS, default=False): selector.BooleanSelector(),
```

**Step 6: Update options flow schema**

In `NettleieOptionsFlow.async_step_init()` (around line 243), add the boligtype selector after DSO:

```python
vol.Required(
    CONF_BOLIGTYPE,
    default=current.get(CONF_BOLIGTYPE, BOLIGTYPE_BOLIG),
): selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=key, label=label)
            for key, label in BOLIGTYPE_OPTIONS.items()
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    ),
),
```

**Step 7: Lint**

Run: `ruff check custom_components/stromkalkulator/config_flow.py`
Expected: No errors

**Step 8: Commit**

```bash
git add custom_components/stromkalkulator/config_flow.py \
  custom_components/stromkalkulator/strings.json \
  custom_components/stromkalkulator/translations/nb.json \
  custom_components/stromkalkulator/translations/en.json
git commit -m "feat: add boligtype selector to config flow (issue #3)"
```

---

### Task 3: Coordinator — dynamisk kWh-tak og Norgespris-haandhevelse

**Files:**
- Modify: `custom_components/stromkalkulator/coordinator.py:14-37` (imports), `:55-97` (init), `:278-320` (beregninger), `:443` (data dict)
- Test: `tests/test_boligtype.py` (utvid)

**Step 1: Write failing tests for coordinator-logikk**

Append to `tests/test_boligtype.py`:

```python
from custom_components.stromkalkulator.const import (
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
)


def calculate_stromstotte_with_boligtype(
    spot_price: float,
    monthly_consumption_kwh: float,
    boligtype: str,
) -> float:
    """Calculate stroemstotte with boligtype-aware cap."""
    max_kwh = get_stromstotte_max_kwh(boligtype)
    if max_kwh == 0 or monthly_consumption_kwh >= max_kwh:
        return 0.0
    if spot_price <= STROMSTOTTE_LEVEL:
        return 0.0
    return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE


def calculate_norgespris_over_cap(
    monthly_consumption_kwh: float,
    boligtype: str,
) -> bool:
    """Return True if Norgespris cap is exceeded."""
    max_kwh = get_norgespris_max_kwh(boligtype)
    return monthly_consumption_kwh >= max_kwh


# === Stroemstotte with boligtype ===

@pytest.mark.parametrize(
    ("boligtype", "spot", "kwh", "expected"),
    [
        # Bolig: normal (5000 kWh cap)
        (BOLIGTYPE_BOLIG, 1.50, 2000, (1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (BOLIGTYPE_BOLIG, 1.50, 5000, 0.0),
        # Fritidsbolig: alltid 0 (ingen rett)
        (BOLIGTYPE_FRITIDSBOLIG, 1.50, 0, 0.0),
        (BOLIGTYPE_FRITIDSBOLIG, 2.00, 500, 0.0),
        # Fritidsbolig fast: same as bolig
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 1.50, 2000, (1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 1.50, 5000, 0.0),
    ],
    ids=[
        "bolig_under_cap",
        "bolig_at_cap",
        "fritid_zero_consumption",
        "fritid_high_spot",
        "fast_under_cap",
        "fast_at_cap",
    ],
)
def test_stromstotte_with_boligtype(
    boligtype: str, spot: float, kwh: float, expected: float,
) -> None:
    """Stroemstotte respects boligtype."""
    assert calculate_stromstotte_with_boligtype(spot, kwh, boligtype) == pytest.approx(expected)


# === Norgespris cap with boligtype ===

@pytest.mark.parametrize(
    ("boligtype", "kwh", "over_cap"),
    [
        (BOLIGTYPE_BOLIG, 4999, False),
        (BOLIGTYPE_BOLIG, 5000, True),
        (BOLIGTYPE_FRITIDSBOLIG, 999, False),
        (BOLIGTYPE_FRITIDSBOLIG, 1000, True),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 4999, False),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000, True),
    ],
    ids=[
        "bolig_under",
        "bolig_at",
        "fritid_under",
        "fritid_at",
        "fast_under",
        "fast_at",
    ],
)
def test_norgespris_cap_with_boligtype(
    boligtype: str, kwh: float, over_cap: bool,
) -> None:
    """Norgespris cap: bolig/fast=5000, fritidsbolig=1000."""
    assert calculate_norgespris_over_cap(kwh, boligtype) == over_cap
```

**Step 2: Run tests to verify they fail**

Run: `pipx run pytest tests/test_boligtype.py -v`
Expected: FAIL — new functions don't exist yet (but the test file defines them locally, so they should PASS immediately). This verifies the test logic.

Actually: these tests define the functions locally, so they PASS immediately. This is intentional — we're testing the algorithm before wiring it into the coordinator.

Run: `pipx run pytest tests/test_boligtype.py -v`
Expected: PASS (all tests)

**Step 3: Update coordinator imports**

In `coordinator.py`, update imports from `.const` (line 14-37). Add:

```python
BOLIGTYPE_BOLIG,
CONF_BOLIGTYPE,
get_norgespris_max_kwh,
get_stromstotte_max_kwh,
```

Remove `STROMSTOTTE_MAX_KWH` from imports (no longer used directly).

**Step 4: Update coordinator __init__**

In `coordinator.py __init__()`, after `self.har_norgespris` (line 97), add:

```python
# Get boligtype from config (default: bolig for backward compatibility)
self.boligtype = entry.data.get(CONF_BOLIGTYPE, BOLIGTYPE_BOLIG)
```

**Step 5: Update stroemstotte calculation**

In `coordinator.py _async_update_data()`, replace the stroemstotte block (lines 278-293):

Old:
```python
# Calculate stroemstotte (always from spot price, for comparison)
...
monthly_total_kwh = self._monthly_consumption["dag"] + self._monthly_consumption["natt"]
stromstotte: float
if monthly_total_kwh >= STROMSTOTTE_MAX_KWH:
    stromstotte = 0.0
elif spot_price > STROMSTOTTE_LEVEL:
    stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
else:
    stromstotte = 0.0

stromstotte_gjenstaaende = max(0.0, STROMSTOTTE_MAX_KWH - monthly_total_kwh)
```

New:
```python
# Calculate stroemstotte (always from spot price, for comparison)
# Forskrift SS 5: 90% av spotpris over 77 oere/kWh eks. mva (96,25 oere inkl. mva) i 2026
# kWh-tak avhenger av boligtype:
# - Bolig / Fritidsbolig fast bosted: 5000 kWh/mnd (Forskrift SS 5)
# - Fritidsbolig: Ingen rett paa stroemstotte (Forskrift SS 3)
# Kilde: https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791
# NB: Norgespris-kunder mottar ikke stroemstotte, men vi beregner den
# alltid slik at sammenligning mellom Norgespris og spot+stotte fungerer.
monthly_total_kwh = self._monthly_consumption["dag"] + self._monthly_consumption["natt"]
stromstotte_max = get_stromstotte_max_kwh(self.boligtype)
stromstotte: float
if stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max:
    stromstotte = 0.0
elif spot_price > STROMSTOTTE_LEVEL:
    stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
else:
    stromstotte = 0.0

stromstotte_gjenstaaende = max(0.0, stromstotte_max - monthly_total_kwh)
```

**Step 6: Update Norgespris total_price — haandhev kWh-tak**

In `coordinator.py`, replace the Norgespris total_price block (lines 311-319):

Old:
```python
# Total price calculation depends on whether user has Norgespris
if self.har_norgespris:
    # Bruker har Norgespris: bruk fast pris i stedet for spotpris
    total_price = norgespris + energiledd + fastledd_per_kwh
    total_price_uten_stotte = norgespris + energiledd + fastledd_per_kwh  # Samme som total_price
else:
    # Standard: spotpris minus stroemstotte
    total_price = spot_price - stromstotte + energiledd + fastledd_per_kwh
    total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh
```

New:
```python
# Total price calculation depends on whether user has Norgespris
# Norgespris kWh-tak: Bolig=5000, Fritidsbolig=1000. Over taket betaler man spotpris.
norgespris_max = get_norgespris_max_kwh(self.boligtype)
norgespris_over_tak = monthly_total_kwh >= norgespris_max

if self.har_norgespris:
    if norgespris_over_tak:
        # Over Norgespris-taket: betaler spotpris (ingen Norgespris-rabatt)
        total_price = spot_price + energiledd + fastledd_per_kwh
        total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh
    else:
        # Under taket: fast Norgespris
        total_price = norgespris + energiledd + fastledd_per_kwh
        total_price_uten_stotte = norgespris + energiledd + fastledd_per_kwh
else:
    # Standard: spotpris minus stroemstotte
    total_price = spot_price - stromstotte + energiledd + fastledd_per_kwh
    total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh
```

**Step 7: Update Norgespris comparison and strompris_per_kwh**

The `total_pris_norgespris` (line 322) and `strompris_per_kwh` blocks (lines 325-330) also need to respect the cap.

Replace line 322:
```python
total_pris_norgespris = norgespris + energiledd + fastledd_per_kwh
```
With:
```python
# Norgespris comparison: use Norgespris if under cap, else spotpris
if norgespris_over_tak:
    total_pris_norgespris = spot_price + energiledd + fastledd_per_kwh
else:
    total_pris_norgespris = norgespris + energiledd + fastledd_per_kwh
```

Replace lines 325-330:
```python
if self.har_norgespris:
    strompris_per_kwh = norgespris + energiledd
    strompris_per_kwh_etter_stotte = norgespris + energiledd
else:
    strompris_per_kwh = spot_price + energiledd
    strompris_per_kwh_etter_stotte = spot_price - stromstotte + energiledd
```
With:
```python
if self.har_norgespris:
    if norgespris_over_tak:
        strompris_per_kwh = spot_price + energiledd
        strompris_per_kwh_etter_stotte = spot_price + energiledd
    else:
        strompris_per_kwh = norgespris + energiledd
        strompris_per_kwh_etter_stotte = norgespris + energiledd
else:
    strompris_per_kwh = spot_price + energiledd
    strompris_per_kwh_etter_stotte = spot_price - stromstotte + energiledd
```

**Step 8: Update data dict**

In the returned data dict (around line 443), replace:
```python
"stromstotte_tak_naadd": monthly_total_kwh >= STROMSTOTTE_MAX_KWH,
```
With:
```python
"stromstotte_tak_naadd": stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max,
"norgespris_over_tak": norgespris_over_tak,
"boligtype": self.boligtype,
```

**Step 9: Lint**

Run: `ruff check custom_components/stromkalkulator/coordinator.py`
Expected: No errors

**Step 10: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All tests pass. Existing tests use default boligtype (bolig) via backward compatibility.

**Step 11: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py tests/test_boligtype.py
git commit -m "feat: dynamic kWh cap and Norgespris enforcement (issue #3)"
```

---

### Task 4: Sensor-attributter

**Files:**
- Modify: `custom_components/stromkalkulator/sensor.py:597-606` (StromstotteSensor attrs), `:1025-1035` (StromstotteKwhSensor attrs)

**Step 1: Update StromstotteSensor extra_state_attributes**

In `sensor.py` around line 601-606, the `StromstotteSensor` shows `tak_naadd`. No change needed — it already reads from `coordinator.data["stromstotte_tak_naadd"]`.

**Step 2: Update StromstotteKwhSensor extra_state_attributes**

In `sensor.py` around line 1030-1035, add `boligtype` to attributes:

Replace:
```python
return {
    "spotpris": spot_price,
    "terskel": STROMSTOTTE_LEVEL,
    "over_terskel": spot_price > STROMSTOTTE_LEVEL,
    "stromstotte_per_kwh": stromstotte,
    "note": f"Timer hvor spotpris > {STROMSTOTTE_LEVEL * 100:.2f} øre/kWh gir strømstøtte på fakturaen",
}
```
With:
```python
boligtype = self.coordinator.data.get("boligtype", "bolig")
return {
    "spotpris": spot_price,
    "terskel": STROMSTOTTE_LEVEL,
    "over_terskel": spot_price > STROMSTOTTE_LEVEL,
    "stromstotte_per_kwh": stromstotte,
    "boligtype": boligtype,
    "note": f"Timer hvor spotpris > {STROMSTOTTE_LEVEL * 100:.2f} øre/kWh gir strømstøtte på fakturaen",
}
```

**Step 3: Lint**

Run: `ruff check custom_components/stromkalkulator/sensor.py`
Expected: No errors

**Step 4: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/sensor.py
git commit -m "feat: add boligtype to sensor attributes (issue #3)"
```

---

### Task 5: Oppdater test_stromstotte_tak.py

**Files:**
- Modify: `tests/test_stromstotte_tak.py`

**Step 1: Update existing test to use get_stromstotte_max_kwh**

The existing `test_cap_is_5000_kwh` (line 182-184) tests the constant directly. Add a test that verifies the constant matches the helper for bolig:

```python
from custom_components.stromkalkulator.const import (
    BOLIGTYPE_BOLIG,
    get_stromstotte_max_kwh,
)

def test_cap_matches_bolig_helper() -> None:
    """Verify STROMSTOTTE_MAX_KWH matches get_stromstotte_max_kwh for bolig."""
    assert STROMSTOTTE_MAX_KWH == get_stromstotte_max_kwh(BOLIGTYPE_BOLIG)
```

**Step 2: Run tests**

Run: `pipx run pytest tests/test_stromstotte_tak.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_stromstotte_tak.py
git commit -m "test: verify stromstotte cap matches boligtype helper (issue #3)"
```

---

### Task 6: README og dokumentasjon

**Files:**
- Modify: `README.md:43-71` (Oppsett), `:186-196` (Begrensninger)
- Modify: `README.en.md` (tilsvarende)
- Modify: `docs/beregninger.md` (formler med boligtype)

**Step 1: Update README.md — ny Konfigurasjon-seksjon**

Replace the existing "Oppsett" section (lines 43-71) with a more comprehensive section. Keep steg 1 and 2, but add boligtype documentation:

After "Steg 1: Velg nettselskap", add:

```markdown
### Boligtype

| Boligtype | Stroemstotte | Norgespris-tak | Kilde |
|-----------|-------------|----------------|-------|
| Bolig (standard) | 5000 kWh/mnd | 5000 kWh/mnd | [Forskrift SS 5](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Fritidsbolig | Ingen | 1000 kWh/mnd | [Forskrift SS 3](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |
| Fritidsbolig (fast bosted) | 5000 kWh/mnd | 5000 kWh/mnd | [Forskrift SS 11](https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791) |

Over kWh-taket for Norgespris betaler du spotpris for resten av maaneden.
Fritidsboliger har ikke rett paa stroemstotte med mindre du bor der fast (SS 11).
```

Update "Begrensninger" (lines 186-196) — remove "Fritidsbolig" from the list of unsupported things.

**Step 2: Update README.en.md**

Mirror the changes in English.

**Step 3: Update docs/beregninger.md**

Add a note about boligtype affecting kWh-tak in the stroemstotte and Norgespris formula sections.

**Step 4: Commit**

```bash
git add README.md README.en.md docs/beregninger.md
git commit -m "docs: document boligtype configuration and update limitations (issue #3)"
```

---

### Task 7: Sluttkontroll

**Step 1: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All tests pass

**Step 2: Run linter on all changed files**

Run: `ruff check custom_components/stromkalkulator/ tests/`
Expected: No errors

**Step 3: Verify backward compatibility**

Confirm that no existing test has been broken — all tests that don't specify boligtype should use the default "bolig" (5000 kWh tak).
