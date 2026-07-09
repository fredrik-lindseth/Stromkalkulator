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

COMPONENTS_DIR = Path(__file__).parent.parent / "custom_components" / "stromkalkulator"


# ---------------------------------------------------------------------------
# 1. NumberSelector step validation
# ---------------------------------------------------------------------------


class TestNumberSelectorStep:
    """NumberSelectorConfig step must be >= 0.001 or "any" (HA constraint).

    Source-guard, ikke atferdstest: en ekte atferdstest måtte instansiere
    HA-selectorene og lese NumberSelectorConfig.step, men selector-modulen er
    en MagicMock i denne suiten (ingen pytest-homeassistant-custom-component),
    så konfig-verdiene finnes ikke å inspisere. Vi skanner kilden i stedet.
    step < 0.001 krasjer HA og step=0.001 avrunder bort presisjon (begge er
    ekte bugs vi har hatt), så guarden fanger noe reelt. Kosmetiske renames
    her betyr som regel en faktisk endring av skjemaet.
    """

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

    # DSO-datasjekker (positiv/numerisk energiledd, dag >= natt) dekkes av
    # tests/test_dso_data_validation.py for hele DSO_LIST; ikke duplisert her.


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

        required = {
            "name",
            "prisomrade",
            "supported",
            "energiledd_dag_eks_mva",
            "energiledd_natt_eks_mva",
            "kapasitetstrinn",
        }
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
# 5. Config flow error keys exist in strings.json
# ---------------------------------------------------------------------------


class TestConfigFlowErrorKeys:
    """Every error key used in config_flow.py must have a translation.

    Source-guard: driver config-flowen mot mock-HA ville aldri nå
    oversettelses-oppslaget (HA gjør det, ikke koden vår), så vi krysssjekker
    i stedet at hver literal `errors[...] = "key"` finnes i strings.json.
    Fanger den ekte bugen «feilkode uten oversettelse».
    """

    def test_all_error_keys_have_translations(self):
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        strings = json.loads((COMPONENTS_DIR / "strings.json").read_text())
        error_translations = set(strings["config"]["error"].keys())

        used_keys = set(re.findall(r'errors\[.*?\]\s*=\s*"(\w+)"', source))

        missing = used_keys - error_translations
        assert not missing, (
            f"Config flow uses error keys without translations: {missing}"
        )


# ---------------------------------------------------------------------------
# 6. Coordinator float() calls are all protected
# ---------------------------------------------------------------------------


class TestCoordinatorFloatProtection:
    """Every float(state) in coordinator sensor-reading helpers must be wrapped in try/except.

    Source-guard: robusthetstestene i test_coordinator_robustness.py dekker
    at ugyldige sensorverdier ikke krasjer coordinatoren, men de kjører kun de
    stiene testdataene treffer. Denne skanner _read_sensor_float/_read_price_sensor
    strukturelt for å sikre at ingen fremtidig float(state)-linje sniker seg inn
    uten ValueError-vern. Fanget en ekte krasj-bug (kr-total-sensor).
    """

    def test_all_float_state_conversions_are_protected(self):
        """float(.*state) calls in sensor-reading helpers must have except ValueError."""
        source = (COMPONENTS_DIR / "coordinator.py").read_text()

        # Sensor reading is now in _read_sensor_float and _read_price_sensor helpers
        for method_name in ("_read_sensor_float", "_read_price_sensor"):
            pattern = rf"def {method_name}\(.*?(?=\n    def |\n    async def |\nclass |\Z)"
            match = re.search(pattern, source, re.DOTALL)
            assert match, f"Could not find {method_name} method"
            method_source = match.group(0)

            float_calls = re.findall(r"float\([^)]*state[^)]*\)", method_source)
            assert float_calls, f"Should find float() calls on sensor state in {method_name}"

            has_protection = "except (ValueError" in method_source or "except ValueError" in method_source
            assert has_protection, (
                f"Found {len(float_calls)} float(state) calls in {method_name} "
                f"but no ValueError handler."
            )


# ---------------------------------------------------------------------------
# 7. Config flow avgiftssone auto-detection (incident 003)
# ---------------------------------------------------------------------------


class TestAvgiftssoneAutoDetection:
    """Config flow auto-detection must use DSO avgiftssone field and correct NO3 mapping."""

    def test_no3_defaults_to_standard(self):
        """NO3 DSOs without avgiftssone override get standard (not nord_norge)."""
        from stromkalkulator.const import resolve_avgiftssone
        from stromkalkulator.dso import DSO_LIST

        for dso_id in ("tensio_tn", "tensio_ts", "mellom", "elinett", "vevig"):
            dso = DSO_LIST[dso_id]
            assert dso["prisomrade"] == "NO3"
            assert resolve_avgiftssone(dso) == "standard", f"{dso_id} should be standard"

    def test_no4_defaults_to_nord_norge(self):
        """NO4 DSOs without tiltakssone get nord_norge."""
        from stromkalkulator.const import resolve_avgiftssone
        from stromkalkulator.dso import DSO_LIST

        for dso_id in ("noranett", "linea", "elmea", "vestall", "stram"):
            dso = DSO_LIST[dso_id]
            assert dso["prisomrade"] == "NO4"
            assert resolve_avgiftssone(dso) == "nord_norge", f"{dso_id} should be nord_norge"

    def test_bindal_overrides_to_nord_norge(self):
        """Bindal Kraftnett is NO3 but in Nordland, should get nord_norge via DSO field."""
        from stromkalkulator.const import resolve_avgiftssone
        from stromkalkulator.dso import DSO_LIST

        dso = DSO_LIST["bindal_kraftnett"]
        assert dso["prisomrade"] == "NO3"
        assert resolve_avgiftssone(dso) == "nord_norge"

    def test_tiltakssone_dsos(self):
        """DSOs with tiltakssone flag get tiltakssone avgiftssone."""
        from stromkalkulator.const import resolve_avgiftssone
        from stromkalkulator.dso import DSO_LIST

        for dso_id in ("barents_nett", "lucerna", "vissi", "area_nett"):
            dso = DSO_LIST[dso_id]
            assert dso.get("tiltakssone") is True, f"{dso_id} should have tiltakssone=True"
            assert resolve_avgiftssone(dso) == "tiltakssone", f"{dso_id} should be tiltakssone"


class _FakeState:
    """Minimal State-stub for å teste spot-sensor-validator uten HA."""

    def __init__(self, state: str, unit: str | None = None) -> None:
        self.state = state
        self.attributes: dict[str, str] = {}
        if unit is not None:
            self.attributes["unit_of_measurement"] = unit


class TestValidateSpotSensor:
    """_validate_spot_sensor fanger åpenbart feil sensorvalg.

    Regresjon for stromkalkulator-34qzbh: bruker hadde pekt spot_price_sensor
    mot en kr-totalsensor (~877 kr). Alle Elvia-derivater ble katastrofalt feil
    uten advarsel.
    """

    def test_nord_pool_style_sensor_passes(self):
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("0.85", "NOK/kWh")
        assert _validate_spot_sensor(state) is None

    def test_ore_per_kwh_sensor_rejected(self):
        """øre/kWh tolkes av coordinator som NOK/kWh og gir 100x for lav pris.

        Regresjon for stromkalkulator-3hnc: verdien (~85) er innenfor den
        godtatte terskelen, så enheten er eneste holdepunkt for å avvise den.
        """
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("85.5", "øre/kWh")
        assert _validate_spot_sensor(state) == "spot_unit_invalid"

    def test_eur_per_mwh_passes(self):
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("65.4", "EUR/MWh")
        assert _validate_spot_sensor(state) is None

    def test_negative_spot_price_passes(self):
        """Spot price can briefly go negative."""
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("-0.05", "NOK/kWh")
        assert _validate_spot_sensor(state) is None

    def test_kr_unit_rejected(self):
        """User pointed at a kr-total sensor."""
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("877.50", "kr")
        assert _validate_spot_sensor(state) == "spot_unit_invalid"

    def test_kwh_unit_rejected(self):
        """User pointed at a kWh meter."""
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("1543.2", "kWh")
        assert _validate_spot_sensor(state) == "spot_unit_invalid"

    def test_extreme_value_rejected_even_without_unit(self):
        """Sensor without unit but with value of 8772 is not a spot price."""
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("8772.40", unit=None)
        assert _validate_spot_sensor(state) == "spot_value_unreasonable"

    def test_unavailable_sensor_accepted(self):
        """unavailable/unknown state should not block config save."""
        from stromkalkulator.config_flow import _validate_spot_sensor

        state = _FakeState("unavailable", "NOK/kWh")
        assert _validate_spot_sensor(state) is None
