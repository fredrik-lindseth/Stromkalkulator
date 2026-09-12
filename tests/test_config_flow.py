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
import sys
from pathlib import Path
from unittest.mock import MagicMock

# voluptuous er ikke installert i testmiljøet, og config_flow.py importerer den.
# Uten stubben her besto filen bare når en annen testfil tilfeldigvis hadde
# lagt den i sys.modules først, og feilet når den ble kjørt alene.
if "voluptuous" not in sys.modules:
    _vol = MagicMock()
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    _vol.Required = lambda name, **kw: name
    _vol.Optional = lambda name, **kw: name
    sys.modules["voluptuous"] = _vol

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
            assert value >= self.MIN_STEP, f"step={value} at {location} is below HA minimum {self.MIN_STEP}"

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

    def test_alle_steg_finnes_i_begge_spraak(self):
        """Et nytt config-flow-steg uten oversettelse vises som en rå nøkkel.

        Sikring-steget avdekket at paritetstestene bare dekket sensor- og
        error-nøkler, aldri stegene. Samme halvdekning som drift-vakten hadde
        (incident 006, lærdom 1).
        """
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        for fil in ("en.json", "nb.json"):
            oversatt = self._load_json(COMPONENTS_DIR / "translations" / fil)
            for seksjon in ("config", "options"):
                if seksjon not in strings:
                    continue
                forventet = set(strings[seksjon]["step"])
                faktisk = set(oversatt[seksjon]["step"])
                assert not forventet - faktisk, f"{fil} mangler {seksjon}-steg: {forventet - faktisk}"

    def test_alle_issue_noekler_finnes_i_begge_spraak(self):
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        for fil in ("en.json", "nb.json"):
            oversatt = self._load_json(COMPONENTS_DIR / "translations" / fil)
            mangler = set(strings["issues"]) - set(oversatt.get("issues", {}))
            assert not mangler, f"{fil} mangler issue-nøkler: {mangler}"

    def test_translation_keys_i_koden_finnes_i_strings(self):
        """Hver translation_key= i integrasjonen må ha en tekst å vise."""
        strings = self._load_json(COMPONENTS_DIR / "strings.json")
        kjent = set(strings["issues"])
        brukt: set[str] = set()
        for fil in ("__init__.py", "coordinator.py", "config_flow.py"):
            kilde = (COMPONENTS_DIR / fil).read_text()
            brukt |= set(re.findall(r'translation_key="([a-z_]+)"', kilde))
        assert not brukt - kjent, f"translation_key uten tekst i strings.json: {brukt - kjent}"

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
            dso["name"] for key, dso in DSO_LIST.items() if dso.get("supported") and key != "custom"
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
        assert not missing, f"Config flow uses error keys without translations: {missing}"


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

        # All sensorlesing går gjennom inputadapteren nå, så det er der
        # float(state) står.
        source = (COMPONENTS_DIR / "inputadapter.py").read_text()
        for method_name in ("vurder_state",):
            pattern = rf"def {method_name}\(.*?(?=\ndef |\nclass |\Z)"
            match = re.search(pattern, source, re.DOTALL)
            assert match, f"Could not find {method_name} method"
            method_source = match.group(0)

            float_calls = re.findall(r"float\([^)]*state[^)]*\)", method_source)
            assert float_calls, f"Should find float() calls on sensor state in {method_name}"

            has_protection = "except (ValueError" in method_source or "except ValueError" in method_source
            assert has_protection, (
                f"Found {len(float_calls)} float(state) calls in {method_name} but no ValueError handler."
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

    def __init__(self, state: str, unit: str | None = None, state_class: str | None = None) -> None:
        self.state = state
        self.last_updated = None
        self.attributes: dict[str, str] = {}
        if unit is not None:
            self.attributes["unit_of_measurement"] = unit
        if state_class is not None:
            self.attributes["state_class"] = state_class


CONF_POWER_SENSOR = "power_sensor"
CONF_SPOT_PRICE_SENSOR = "spot_price_sensor"
CONF_ENERGY_SENSOR = "energy_sensor"


class TestValiderSensorfelt:
    """Adapteren fanger feil sensorvalg i oppsett, options og reconfigure.

    Regresjon for stromkalkulator-34qzbh: bruker hadde pekt spot_price_sensor
    mot en kr-totalsensor (~877 kr). Alle Elvia-derivater ble katastrofalt feil
    uten advarsel.

    Den gamle `_validate_spot_sensor` avviste der den burde regnet om: øre/kWh
    ble nektet, mens EUR/MWh slapp gjennom til å bli lest som kroner.
    """

    def _feil(self, felt, state, **andre):
        from stromkalkulator.config_flow import _valider_sensorfelt

        hass = MagicMock()
        states = {"sensor.rolle": state}
        states.update(andre)
        hass.states.get = MagicMock(side_effect=states.get)
        user_input = {felt: "sensor.rolle"}
        return _valider_sensorfelt(hass, user_input, paakrevd=set()).get(felt)

    def test_nord_pool_style_sensor_passes(self):
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("0.85", "NOK/kWh")) is None

    def test_ore_per_kwh_godtas_og_regnes_om(self):
        """Etter kontrakten regnes øre/kWh om i stedet for å avvises.

        Brukeren fikk før beskjed om å bygge en malsensor for noe adapteren kan
        gjøre selv.
        """
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("85.5", "øre/kWh")) is None
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("85.5", "ore/kWh")) is None

    def test_eur_per_mwh_avvises(self):
        """Vi har ingen valutakurs, og å lese euro som kroner er verre enn nei."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("65.4", "EUR/MWh")) == "enhet_feil_valuta"
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("0.065", "EUR/kWh")) == "enhet_feil_valuta"

    def test_nok_per_mwh_godtas(self):
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("850", "NOK/MWh")) is None

    def test_negative_spot_price_passes(self):
        """Spotprisen kan så vidt gå negativ, og det er en gyldig pris."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("-0.05", "NOK/kWh")) is None

    def test_kr_unit_rejected(self):
        """Brukeren pekte på en kr-totalsensor."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("877.50", "kr")) == "enhet_feil_dimensjon"

    def test_kwh_unit_rejected(self):
        """Brukeren pekte på en kWh-måler."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("1543.2", "kWh")) == "enhet_feil_dimensjon"

    def test_ukjent_enhet_avvises(self):
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("1.2", "bananer")) == "enhet_ukjent"

    def test_extreme_value_rejected_even_without_unit(self):
        """En sensor uten enhet med verdien 8772 er ingen spotpris."""
        assert (
            self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("8772.40", unit=None)) == "spot_value_unreasonable"
        )

    def test_dyr_time_i_nok_per_mwh_slipper_gjennom(self):
        """Grensen gjelder etter normalisering. 2500 NOK/MWh er 2,5 NOK/kWh."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("2500", "NOK/MWh")) is None

    def test_unavailable_sensor_accepted(self):
        """unavailable/unknown skal ikke blokkere lagring."""
        assert self._feil(CONF_SPOT_PRICE_SENSOR, _FakeState("unavailable", "NOK/kWh")) is None

    def test_effektsensor_i_kilowatt_godtas(self):
        assert self._feil(CONF_POWER_SENSOR, _FakeState("5.2", "kW")) is None

    def test_effektfelt_med_energisensor_avvises(self):
        assert self._feil(CONF_POWER_SENSOR, _FakeState("1543", "kWh")) == "enhet_feil_dimensjon"

    def test_energisensor_uten_state_class_avvises(self):
        state = _FakeState("1543", "kWh")
        assert self._feil(CONF_ENERGY_SENSOR, state) == "energi_ikke_kumulativ"

    def test_energisensor_med_measurement_avvises(self):
        """En øyeblikksverdi er ingen teller, uansett hva enheten sier."""
        state = _FakeState("1543", "kWh", state_class="measurement")
        assert self._feil(CONF_ENERGY_SENSOR, state) == "energi_ikke_kumulativ"

    def test_energisensor_med_total_godtas(self):
        for state_class in ("total", "total_increasing"):
            state = _FakeState("1543", "kWh", state_class=state_class)
            assert self._feil(CONF_ENERGY_SENSOR, state) is None

    def test_energisensor_i_wh_godtas(self):
        state = _FakeState("1543000", "Wh", state_class="total_increasing")
        assert self._feil(CONF_ENERGY_SENSOR, state) is None

    def test_slettet_entitet_gir_sensor_not_found(self):
        from stromkalkulator.config_flow import _valider_sensorfelt

        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        feil = _valider_sensorfelt(hass, {CONF_POWER_SENSOR: "sensor.borte"}, paakrevd={CONF_POWER_SENSOR})
        assert feil[CONF_POWER_SENSOR] == "sensor_not_found"

    def test_tomt_valgfritt_felt_gir_ingen_feil(self):
        from stromkalkulator.config_flow import _valider_sensorfelt

        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        assert _valider_sensorfelt(hass, {}, paakrevd=set()) == {}


# ---------------------------------------------------------------------------
# 9. Energiledd-feltet må si hva koden faktisk venter
# ---------------------------------------------------------------------------


class TestEnergileddMerking:
    """Labelen på energiledd-feltet skal aldri love «inkl. avgifter» igjen.

    Koden regner satsen som ren nettleie og legger forbruksavgift, Enova og mva
    på selv (compute_energiledd_inkl_mva). Fram til og med 1.16.0 sto feltet
    merket motsatt i nb og en, så alle som fulgte teksten tastet en sats med
    avgiftene alt inne, og de ble talt to ganger. Se
    docs/incidents/007-energiledd-label-inkl-avgifter.md.

    Tekstdriften mellom malen og oversettelsene vokter test_oversettelser.py.
    Denne vokter innholdet: en formulering som sier det motsatte av koden er en
    feil selv om alle tre filene er enige om den.
    """

    FILER = ("strings.json", "translations/nb.json", "translations/en.json")
    FORBUDT = ("inkl. avgifter", "incl. taxes", "including taxes", "inkludert avgifter")

    def _energiledd_tekster(self, fil: str) -> list[str]:
        data = json.loads((COMPONENTS_DIR / fil).read_text())
        tekster: list[str] = []

        def gaa(node, forelder: str | None) -> None:
            if isinstance(node, dict):
                for nokkel, verdi in node.items():
                    gaa(verdi, nokkel)
                return
            if forelder and forelder.startswith("energiledd"):
                tekster.append(str(node))

        gaa(data, None)
        # Steget for egendefinerte priser har sin egen forklaring i description.
        for sti in (("config", "step", "pricing", "description"),):
            node = data
            for ledd in sti:
                node = node[ledd]
            tekster.append(str(node))
        return tekster

    def test_ingen_lover_inkl_avgifter(self):
        for fil in self.FILER:
            for tekst in self._energiledd_tekster(fil):
                lav = tekst.lower()
                traff = [ord_ for ord_ in self.FORBUDT if ord_ in lav]
                assert not traff, f"{fil}: «{tekst}» lover {traff}, koden venter eks. mva og avgifter"

    def test_labelen_sier_eks_mva(self):
        """Uten forbeholdet i selve labelen må brukeren gjette."""
        for fil in self.FILER:
            data = json.loads((COMPONENTS_DIR / fil).read_text())
            label = data["config"]["step"]["pricing"]["data"]["energiledd_dag"]
            assert "eks. mva" in label or "excl. VAT" in label, f"{fil}: {label}"


class TestEgendefinertBekreftelse:
    """Nye egendefinerte oppsett skal ikke møte varselet om den gamle teksten.

    Varselet gjelder satser tastet etter en feilmerket label. Den som taster nå
    ser den rettede teksten, så config-flowen setter bekreftelsen med en gang.
    Source-guard fordi flowen ikke kan kjøres uten HA.
    """

    def test_pricing_steget_setter_flagget(self):
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        pricing = re.search(
            r"async def async_step_pricing\(.*?(?=\n    def |\n    async def |\nclass |\Z)",
            source,
            re.DOTALL,
        )
        assert pricing, "fant ikke async_step_pricing"
        assert "CONF_EGENDEFINERT_SATSER_BEKREFTET" in pricing.group(0)

    def test_bytte_til_egendefinert_setter_flagget(self):
        source = (COMPONENTS_DIR / "config_flow.py").read_text()
        derivasjon = re.search(r"def _apply_dso_derivation\(.*?(?=\ndef |\nclass |\Z)", source, re.DOTALL)
        assert derivasjon, "fant ikke _apply_dso_derivation"
        assert "CONF_EGENDEFINERT_SATSER_BEKREFTET" in derivasjon.group(0)
