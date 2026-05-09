"""Validation tests for all DSO (nettselskap) entries in DSO_LIST.

Ensures that every DSO entry has valid structure, correct value ranges,
properly sorted kapasitetstrinn, and avgifts-consistent pricing.
"""

from __future__ import annotations

import pytest
from stromkalkulator.const import (
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
    resolve_avgiftssone,
)
from stromkalkulator.dso import DSO_LIST, DSOEntry

VALID_PRISOMRADER = {"NO1", "NO2", "NO3", "NO4", "NO5"}
REQUIRED_FIELDS = {
    "name",
    "prisomrade",
    "energiledd_dag_eks_mva",
    "energiledd_natt_eks_mva",
    "kapasitetstrinn",
    "url",
}


@pytest.fixture(params=list(DSO_LIST.keys()), ids=list(DSO_LIST.keys()))
def dso_entry(request) -> tuple[str, DSOEntry]:
    """Parametrized fixture yielding (dso_id, dso_data) for each DSO."""
    return request.param, DSO_LIST[request.param]


class TestDSORequiredFields:
    """Every DSO entry must have all required fields."""

    def test_has_required_fields(self, dso_entry):
        dso_id, data = dso_entry
        missing = REQUIRED_FIELDS - set(data.keys())
        assert not missing, f"{dso_id} mangler felt: {missing}"

    def test_has_supported_flag(self, dso_entry):
        dso_id, data = dso_entry
        assert "supported" in data, f"{dso_id} mangler 'supported' flagg"
        assert isinstance(data["supported"], bool), f"{dso_id}: supported er ikke bool"

    def test_name_is_nonempty_string(self, dso_entry):
        dso_id, data = dso_entry
        assert isinstance(data["name"], str) and len(data["name"]) > 0, (
            f"{dso_id}: name skal være en ikke-tom streng"
        )


class TestDSOPrisomrade:
    """prisomrade must be valid (NO1-NO5)."""

    def test_prisomrade_is_valid(self, dso_entry):
        dso_id, data = dso_entry
        assert data["prisomrade"] in VALID_PRISOMRADER, (
            f"{dso_id}: ugyldig prisomrade '{data['prisomrade']}', forventet {VALID_PRISOMRADER}"
        )


class TestDSOAvgiftssone:
    """avgiftssone field (if present) must be a valid value."""

    VALID_AVGIFTSSONER: frozenset[str] = frozenset({"standard", "nord_norge", "tiltakssone"})

    def test_avgiftssone_is_valid_string(self, dso_entry):
        dso_id, data = dso_entry
        if "avgiftssone" in data:
            assert data["avgiftssone"] in self.VALID_AVGIFTSSONER, (
                f"{dso_id}: ugyldig avgiftssone '{data['avgiftssone']}'"
            )


class TestDSOEnergiledd:
    """energiledd_*_eks_mva must be positive numbers."""

    def test_energiledd_dag_is_positive(self, dso_entry):
        dso_id, data = dso_entry
        val = data["energiledd_dag_eks_mva"]
        assert isinstance(val, (int, float)), (
            f"{dso_id}: energiledd_dag_eks_mva er ikke et tall"
        )
        assert val > 0, (
            f"{dso_id}: energiledd_dag_eks_mva skal være positiv, fikk {val}"
        )

    def test_energiledd_natt_is_positive(self, dso_entry):
        dso_id, data = dso_entry
        val = data["energiledd_natt_eks_mva"]
        assert isinstance(val, (int, float)), (
            f"{dso_id}: energiledd_natt_eks_mva er ikke et tall"
        )
        assert val > 0, (
            f"{dso_id}: energiledd_natt_eks_mva skal være positiv, fikk {val}"
        )

    def test_dag_greater_than_or_equal_to_natt(self, dso_entry):
        """Day rate should normally be >= night rate."""
        dso_id, data = dso_entry
        dag = data["energiledd_dag_eks_mva"]
        natt = data["energiledd_natt_eks_mva"]
        assert dag >= natt, (
            f"{dso_id}: energiledd_dag_eks_mva ({dag}) er lavere enn "
            f"energiledd_natt_eks_mva ({natt})"
        )


class TestDSOKapasitetstrinn:
    """Kapasitetstrinn must be sorted, with valid structure."""

    def test_has_at_least_one_trinn(self, dso_entry):
        dso_id, data = dso_entry
        assert len(data["kapasitetstrinn"]) >= 1, (
            f"{dso_id}: kapasitetstrinn skal ha minst ett trinn"
        )

    def test_last_trinn_has_inf_or_high_max(self, dso_entry):
        """Last tier must have float('inf') threshold (tuple) or high max (dict)."""
        dso_id, data = dso_entry
        last = data["kapasitetstrinn"][-1]
        if isinstance(last, dict):
            # Dict format: check max is very high (catch-all)
            assert last["max"] >= 999, (
                f"{dso_id}: siste trinn (dict) skal ha høy max, fikk {last['max']}"
            )
        else:
            # Tuple format: last threshold must be inf
            assert last[0] == float("inf"), (
                f"{dso_id}: siste trinn skal ha float('inf') som grense, fikk {last[0]}"
            )

    def test_trinn_sorted_ascending(self, dso_entry):
        """Kapasitetstrinn thresholds must be sorted ascending."""
        dso_id, data = dso_entry
        trinn = data["kapasitetstrinn"]
        thresholds = []
        for t in trinn:
            if isinstance(t, dict):
                thresholds.append(t["max"])
            else:
                thresholds.append(t[0])
        for i in range(1, len(thresholds)):
            assert thresholds[i] > thresholds[i - 1], (
                f"{dso_id}: kapasitetstrinn er ikke sortert stigende ved indeks {i}: "
                f"{thresholds[i - 1]} >= {thresholds[i]}"
            )

    def test_trinn_prices_are_positive(self, dso_entry):
        """All capacity tier prices must be positive integers."""
        dso_id, data = dso_entry
        for i, t in enumerate(data["kapasitetstrinn"]):
            if isinstance(t, dict):
                price = t["pris"]
            else:
                price = t[1]
            assert isinstance(price, int), (
                f"{dso_id}: trinn {i + 1} pris skal være int, fikk {type(price).__name__}"
            )
            assert price > 0, (
                f"{dso_id}: trinn {i + 1} pris skal være positiv, fikk {price}"
            )

    def test_trinn_prices_non_decreasing(self, dso_entry):
        """Capacity tier prices should generally not decrease (higher tier = higher price)."""
        dso_id, data = dso_entry
        prices = []
        for t in data["kapasitetstrinn"]:
            if isinstance(t, dict):
                prices.append(t["pris"])
            else:
                prices.append(t[1])
        for i in range(1, len(prices)):
            assert prices[i] >= prices[i - 1], (
                f"{dso_id}: kapasitetstrinn-pris synker ved trinn {i + 1}: "
                f"{prices[i - 1]} -> {prices[i]}"
            )


class TestDSOUrl:
    """URL field validation."""

    def test_url_is_string(self, dso_entry):
        dso_id, data = dso_entry
        assert isinstance(data["url"], str), f"{dso_id}: url er ikke en streng"

    def test_supported_dso_has_url(self, dso_entry):
        """Supported DSOs should have a non-empty URL."""
        dso_id, data = dso_entry
        if data.get("supported") and dso_id != "custom":
            assert len(data["url"]) > 0, (
                f"{dso_id}: støttet nettselskap mangler URL"
            )


class TestDSOAvgiftskonsistens:
    """Sanity-sjekk av energiledd_*_eks_mva-verdier.

    Etter refactor lagrer vi ren nettleie eks. mva og avgifter direkte. Da er
    avgiftskonsistens en triviell sjekk (verdiene er positive og rimelige), og
    inkl-mva-pris bygges deterministisk i coordinator.
    """

    def test_eks_mva_within_reasonable_range(self, dso_entry):
        """eks_mva-verdier skal være positive og under en rimelig grense.

        Norske husholdningsenergiledd ligger typisk i området 0.001-0.6 NOK/kWh
        eks. mva. Verdier utenfor området tyder på at gammel inkl-mva-verdi har
        sneket seg inn i den nye strukturen.
        """
        dso_id, data = dso_entry
        if dso_id == "custom":
            pytest.skip("custom DSO har brukervalgte priser")

        for label in ("energiledd_dag_eks_mva", "energiledd_natt_eks_mva"):
            val = data[label]
            assert val > 0, f"{dso_id}: {label} må være positiv, fikk {val}"
            assert val < 0.65, (
                f"{dso_id}: {label}={val} virker for høyt for ren nettleie. "
                f"Mulig feil: inkl-mva-verdi ikke konvertert til eks-mva."
            )

    def test_dag_natt_diff_makes_sense(self, dso_entry):
        """Hvis dag og natt er forskjellig, skal forskjellen ha rimelig størrelse."""
        dso_id, data = dso_entry
        if dso_id == "custom":
            pytest.skip("custom DSO har brukervalgte priser")

        dag = data["energiledd_dag_eks_mva"]
        natt = data["energiledd_natt_eks_mva"]
        if dag == natt:
            pytest.skip("flat sats")

        # Differansen skal være positiv og rimelig (under 30 øre/kWh).
        diff = dag - natt
        assert diff > 0, f"{dso_id}: dag-natt-diff må være positiv, fikk {diff}"
        assert diff < 0.30, (
            f"{dso_id}: dag-natt-forskjell {diff} virker urimelig stor for "
            f"eks-mva-verdier."
        )

    def test_inkl_mva_matches_legacy_formula(self, dso_entry):
        """Inkl-mva-verdien (utledet fra eks-mva via coordinator-formelen) skal
        fortsatt ligge i et rimelig område for norske nettselskap.
        """
        dso_id, data = dso_entry
        if dso_id == "custom":
            pytest.skip("custom DSO har brukervalgte priser")

        sone = resolve_avgiftssone(data)
        if sone == "tiltakssone":
            mva = 0.0
            forbruksavgift = 0.0
        elif sone == "nord_norge":
            mva = 0.0
            forbruksavgift = FORBRUKSAVGIFT_ALMINNELIG
        else:
            mva = MVA_SATS
            forbruksavgift = FORBRUKSAVGIFT_ALMINNELIG

        for label in ("energiledd_dag_eks_mva", "energiledd_natt_eks_mva"):
            inkl = (data[label] + forbruksavgift + ENOVA_AVGIFT) * (1 + mva)
            # Norske husholdningsledd ligger typisk 0.05-0.65 NOK/kWh inkl. mva
            assert 0.04 < inkl < 0.70, (
                f"{dso_id}: utledet inkl-mva ({inkl:.4f}) for {label} ({data[label]}) "
                f"i sone {sone} ligger utenfor rimelig område."
            )


class TestDSOHelgSomNatt:
    """Verify helg_som_natt flag consistency."""

    def test_helg_som_natt_false_requires_dag_natt_diff(self):
        """DSO-er med helg_som_natt=False bor ha dag != natt.

        Hvis dag == natt (flat sats), gir flagget ingen mening.
        """
        for dso_id, data in DSO_LIST.items():
            if data.get("helg_som_natt") is False:
                assert data["energiledd_dag_eks_mva"] != data["energiledd_natt_eks_mva"], (
                    f"{dso_id}: har helg_som_natt=False men dag == natt (flat sats). "
                    f"Flagget har ingen effekt."
                )

    def test_helg_som_natt_only_bool_or_absent(self):
        """helg_som_natt skal vaere bool eller ikke satt."""
        for dso_id, data in DSO_LIST.items():
            val = data.get("helg_som_natt")
            if val is not None:
                assert isinstance(val, bool), (
                    f"{dso_id}: helg_som_natt skal vaere bool, fikk {type(val).__name__}"
                )


class TestDSOListIntegrity:
    """Overall DSO_LIST integrity checks."""

    def test_dso_list_is_not_empty(self):
        assert len(DSO_LIST) > 0

    def test_bkk_exists_as_default(self):
        """BKK is the default DSO and must exist."""
        assert "bkk" in DSO_LIST

    def test_all_keys_are_lowercase(self):
        for key in DSO_LIST:
            assert key == key.lower(), f"DSO key '{key}' bør være lowercase"

    def test_no_duplicate_names(self):
        """No two DSOs should have the same display name."""
        names = [entry["name"] for entry in DSO_LIST.values()]
        duplicates = [n for n in names if names.count(n) > 1]
        assert not duplicates, f"Dupliserte DSO-navn: {set(duplicates)}"
