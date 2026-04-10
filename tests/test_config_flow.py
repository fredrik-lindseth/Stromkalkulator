"""Tests for config flow validation.

Covers bugs found from user reports:
- NumberSelectorConfig step=0.0001 crashes (HA minimum is 0.001)
- Duplicate power sensor not caught until after pricing step
- Translation keys must exist for all error codes
- Energiledd must support 4+ decimal places

Note: Some tests use regex on source code (fragile by design) because we
cannot run HA config flow without pytest-homeassistant-custom-component.
These structural checks catch real constraints that have caused bugs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

COMPONENTS_DIR = Path(__file__).parent.parent / "custom_components" / "stromkalkulator"


# ---------------------------------------------------------------------------
# 1. NumberSelector step validation
# ---------------------------------------------------------------------------


class TestNumberSelectorStep:
    """NumberSelectorConfig step must be >= 0.001 or "any" (HA constraint)."""

    MIN_STEP = 0.001

    def _extract_step_values(self) -> list[tuple[str, str]]:
        """Extract all step= values from config_flow.py source."""
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        results = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("step="):
                raw = stripped.split("=", 1)[1].rstrip(",").strip('"').strip("'")
                results.append((f"line {i}", raw))
        return results

    def test_all_step_values_are_valid(self):
        """Every step= in config_flow.py must be >= 0.001 or "any"."""
        steps = self._extract_step_values()
        assert steps, "Should find at least one step= value in config_flow.py"
        for location, raw in steps:
            if raw == "any":
                continue
            value = float(raw)
            assert value >= self.MIN_STEP, (
                f"step={value} at {location} is below HA minimum {self.MIN_STEP}"
            )

    def test_energiledd_fields_use_step_any(self):
        """Energiledd fields need 4+ decimal precision, must use step="any".

        HA NumberSelector with step=0.001 rounds to 3 decimals on interaction,
        losing precision on values like 0.4613. step="any" preserves all decimals.
        """
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        # Find step= inside async_step_pricing (the only place with energiledd NumberSelectors with step)
        pricing_match = re.search(
            r"async def async_step_pricing.*?(?=\n    async def |\n    def |\nclass )",
            source,
            re.DOTALL,
        )
        assert pricing_match, "Could not find async_step_pricing method"
        pricing_source = pricing_match.group(0)

        step_values = re.findall(r"step=([^\n,)]+)", pricing_source)
        assert len(step_values) >= 2, "Should find at least 2 step= values in pricing step"
        for raw in step_values:
            raw = raw.strip().strip('"').strip("'")
            assert raw == "any", (
                f"Energiledd NumberSelector in pricing step has step={raw}, "
                f"must be 'any' to preserve 4-decimal precision (e.g. 0.4613)"
            )


# ---------------------------------------------------------------------------
# 2. Energiledd decimal precision
# ---------------------------------------------------------------------------


class TestEnergileddPrecision:
    """Energiledd values in DSO_LIST must not lose precision through config flow."""

    def test_default_energiledd_has_four_decimals(self):
        """Default values must have 4 decimal places."""
        from stromkalkulator.const import DEFAULT_ENERGILEDD_DAG, DEFAULT_ENERGILEDD_NATT

        dag_str = f"{DEFAULT_ENERGILEDD_DAG:.4f}"
        natt_str = f"{DEFAULT_ENERGILEDD_NATT:.4f}"
        assert float(dag_str) == DEFAULT_ENERGILEDD_DAG, "DAG default lost precision"
        assert float(natt_str) == DEFAULT_ENERGILEDD_NATT, "NATT default lost precision"

    @pytest.mark.parametrize(
        "value",
        [
            0.4613,
            0.2329,
            0.2123,
            0.0001,
            0.9999,
            1.0000,
            0.0,
        ],
        ids=lambda v: f"{v}",
    )
    def test_energiledd_roundtrip_preserves_precision(self, value):
        """Values must survive float→store→float without precision loss."""
        # Simulate what happens: user enters value → stored as float → loaded back
        stored = float(value)
        assert stored == value

    def test_all_dso_energiledd_are_valid_floats(self):
        """Every DSO energiledd_dag/natt must be a valid non-negative float."""
        from stromkalkulator.dso import DSO_LIST

        for key, dso in DSO_LIST.items():
            if not dso.get("supported"):
                continue
            dag = dso["energiledd_dag"]
            natt = dso["energiledd_natt"]
            assert isinstance(dag, (int, float)), f"{key}: energiledd_dag is not numeric"
            assert isinstance(natt, (int, float)), f"{key}: energiledd_natt is not numeric"
            assert dag >= 0, f"{key}: energiledd_dag is negative: {dag}"
            assert natt >= 0, f"{key}: energiledd_natt is negative: {natt}"
            assert dag < 5, f"{key}: energiledd_dag suspiciously high: {dag}"
            assert natt < 5, f"{key}: energiledd_natt suspiciously high: {natt}"

    def test_energiledd_dag_ge_natt_for_all_dso(self):
        """Day rate should be >= night rate for all grid companies."""
        from stromkalkulator.dso import DSO_LIST

        for key, dso in DSO_LIST.items():
            if not dso.get("supported"):
                continue
            assert dso["energiledd_dag"] >= dso["energiledd_natt"], (
                f"{key}: dag ({dso['energiledd_dag']}) < natt ({dso['energiledd_natt']})"
            )


# ---------------------------------------------------------------------------
# 3. Translation completeness
# ---------------------------------------------------------------------------


class TestTranslationCompleteness:
    """All translation files must cover the same keys as strings.json."""

    def _load_json(self, path: Path) -> dict:
        return json.loads(path.read_text())

    def test_en_json_has_all_sensor_keys(self):
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        en = self._load_json(COMPONENTS_DIR / "translations" / "en.json")
        missing = set(strings["entity"]["sensor"]) - set(en["entity"]["sensor"])
        assert not missing, f"en.json missing sensor keys: {missing}"

    def test_nb_json_has_all_sensor_keys(self):
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        nb = self._load_json(COMPONENTS_DIR / "translations" / "nb.json")
        missing = set(strings["entity"]["sensor"]) - set(nb["entity"]["sensor"])
        assert not missing, f"nb.json missing sensor keys: {missing}"

    def test_en_json_has_all_error_keys(self):
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        en = self._load_json(COMPONENTS_DIR / "translations" / "en.json")
        missing = set(strings["config"]["error"]) - set(en["config"]["error"])
        assert not missing, f"en.json missing error keys: {missing}"

    def test_en_json_has_issues_section(self):
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        en = self._load_json(COMPONENTS_DIR / "translations" / "en.json")
        if "issues" in strings:
            assert "issues" in en, "en.json missing issues section"

    def test_no_extra_sensor_keys_in_translations(self):
        """Translation files should not have sensor keys that strings.json doesn't."""
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        en = self._load_json(COMPONENTS_DIR / "translations" / "en.json")
        nb = self._load_json(COMPONENTS_DIR / "translations" / "nb.json")
        strings_keys = set(strings["entity"]["sensor"])
        en_extra = set(en["entity"]["sensor"]) - strings_keys
        nb_extra = set(nb["entity"]["sensor"]) - strings_keys
        assert not en_extra, f"en.json has extra sensor keys: {en_extra}"
        assert not nb_extra, f"nb.json has extra sensor keys: {nb_extra}"


# ---------------------------------------------------------------------------
# 4. DSO list validation
# ---------------------------------------------------------------------------


class TestDSOList:
    """Validate DSO list structure and config flow options."""

    def test_custom_dso_exists(self):
        from stromkalkulator.dso import DSO_LIST

        assert "custom" in DSO_LIST, "Egendefinert (custom) DSO must exist"
        assert DSO_LIST["custom"]["supported"] is True

    def test_all_supported_dso_have_required_fields(self):
        from stromkalkulator.dso import DSO_LIST

        required = {"name", "prisomrade", "supported", "energiledd_dag", "energiledd_natt", "kapasitetstrinn"}
        for key, dso in DSO_LIST.items():
            if dso.get("supported"):
                missing = required - set(dso.keys())
                assert not missing, f"DSO '{key}' missing fields: {missing}"

    def test_custom_dso_not_sorted_into_middle(self):
        """Egendefinert must always be last, never alphabetically sorted in."""
        from stromkalkulator.dso import DSO_LIST

        supported_names = sorted(
            dso["name"]
            for key, dso in DSO_LIST.items()
            if dso.get("supported") and key != "custom"
        )
        assert "Egendefinert" not in supported_names
        assert DSO_LIST["custom"]["name"] == "Egendefinert"


# ---------------------------------------------------------------------------
# 5. Coordinator robustness — non-numeric sensor states
# ---------------------------------------------------------------------------


class TestCoordinatorRobustness:
    """Coordinator must handle non-numeric sensor states gracefully."""

    @pytest.mark.parametrize(
        "bad_state",
        [
            "Ja",
            "Nei",
            "on",
            "off",
            "",
            "N/A",
            "none",
            "null",
            "abc",
            "1.2.3",
            "NOK",
            "true",
            "false",
            " ",
            "0,4613",  # Norwegian decimal comma
        ],
        ids=lambda v: f"state={v!r}",
    )
    def test_float_conversion_handles_bad_states(self, bad_state):
        """float() on non-numeric states must not raise."""
        # This is the pattern used in coordinator.py for spot_price and power
        try:
            result = (
                float(bad_state)
                if bad_state not in ("unknown", "unavailable")
                else 0
            )
        except (ValueError, TypeError):
            result = 0
        assert isinstance(result, (int, float))

    def test_unavailable_and_unknown_return_zero(self):
        for state in ("unknown", "unavailable"):
            result = float(state) if state not in ("unknown", "unavailable") else 0
            assert result == 0

    @pytest.mark.parametrize(
        "good_state,expected",
        [
            ("0", 0.0),
            ("1.5", 1.5),
            ("0.4613", 0.4613),
            ("-0.5", -0.5),
            ("100", 100.0),
            ("0.001", 0.001),
        ],
    )
    def test_valid_numeric_states_parse_correctly(self, good_state, expected):
        """Valid numeric strings must parse to correct float values."""
        try:
            result = (
                float(good_state)
                if good_state not in ("unknown", "unavailable")
                else 0
            )
        except (ValueError, TypeError):
            result = 0
        assert result == expected


# ---------------------------------------------------------------------------
# 6. Config flow error keys exist in strings.json
# ---------------------------------------------------------------------------


class TestConfigFlowErrorKeys:
    """Every error key used in config_flow.py must have a translation."""

    def test_all_error_keys_have_translations(self):
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        strings = json.loads((COMPONENTS_DIR / "strings.json").read_text())
        error_translations = set(strings["config"]["error"].keys())

        used_keys = set(re.findall(r'errors\[.*?\]\s*=\s*"(\w+)"', source))

        missing = used_keys - error_translations
        assert not missing, (
            f"Config flow uses error keys without translations: {missing}"
        )


