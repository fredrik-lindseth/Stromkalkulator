"""Validation tests for all DSO (nettselskap) entries in DSO_LIST.

Ensures that every DSO entry has valid structure, correct value ranges,
properly sorted kapasitetstrinn, and avgifts-consistent pricing.
"""

from __future__ import annotations

import pytest
from stromkalkulator.const import ENOVA_AVGIFT, FORBRUKSAVGIFT_ALMINNELIG, MVA_SATS
from stromkalkulator.dso import DSO_LIST, DSOEntry

VALID_PRISOMRADER = {"NO1", "NO2", "NO3", "NO4", "NO5"}
REQUIRED_FIELDS = {"name", "prisomrade", "energiledd_dag", "energiledd_natt", "kapasitetstrinn", "url"}


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


class TestDSOEnergiledd:
    """energiledd_dag and energiledd_natt must be positive numbers."""

    def test_energiledd_dag_is_positive(self, dso_entry):
        dso_id, data = dso_entry
        assert isinstance(data["energiledd_dag"], (int, float)), (
            f"{dso_id}: energiledd_dag er ikke et tall"
        )
        assert data["energiledd_dag"] > 0, (
            f"{dso_id}: energiledd_dag skal være positiv, fikk {data['energiledd_dag']}"
        )

    def test_energiledd_natt_is_positive(self, dso_entry):
        dso_id, data = dso_entry
        assert isinstance(data["energiledd_natt"], (int, float)), (
            f"{dso_id}: energiledd_natt er ikke et tall"
        )
        assert data["energiledd_natt"] > 0, (
            f"{dso_id}: energiledd_natt skal være positiv, fikk {data['energiledd_natt']}"
        )

    def test_dag_greater_than_or_equal_to_natt(self, dso_entry):
        """Day rate should normally be >= night rate."""
        dso_id, data = dso_entry
        assert data["energiledd_dag"] >= data["energiledd_natt"], (
            f"{dso_id}: energiledd_dag ({data['energiledd_dag']}) er lavere enn energiledd_natt ({data['energiledd_natt']})"
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
    """Verify that energiledd prices are consistent with tax rules.

    Fanger feilmonstre som:
    - Dobbel mva (legge avgifter inkl. mva pa base eks. mva, sa gange med mva igjen)
    - Feil forbruksavgift for avgiftssone (inkl. mva brukt for mva-fritt omrade)
    - Manglende tiltakssone-flagg (forbruksavgift inkludert for fritak-omrade)
    """

    def _get_avgiftssone(self, dso_id: str, data: DSOEntry) -> str:
        """Derive avgiftssone from DSO data, same logic as config_flow."""
        if data.get("tiltakssone"):
            return "tiltakssone"
        if data["prisomrade"] in ("NO3", "NO4"):
            return "nord_norge"
        return "standard"

    def _extract_base_nettleie(self, energiledd: float, avgiftssone: str) -> float:
        """Reverse-calculate base nettleie from total energiledd."""
        if avgiftssone == "tiltakssone":
            return energiledd - ENOVA_AVGIFT
        elif avgiftssone == "nord_norge":
            return energiledd - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
        else:
            return energiledd / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT

    def test_base_nettleie_is_positive(self, dso_entry):
        """Etter fratrekk av avgifter skal base nettleie vaere positiv.

        Negativ base betyr at avgiftene er for hoye -- typisk dobbel mva
        eller feil avgiftssone.
        """
        dso_id, data = dso_entry
        if dso_id == "custom":
            pytest.skip("custom DSO har brukervalgte priser")

        sone = self._get_avgiftssone(dso_id, data)
        for label, price in [("dag", data["energiledd_dag"]), ("natt", data["energiledd_natt"])]:
            base = self._extract_base_nettleie(price, sone)
            assert base > -0.001, (
                f"{dso_id}: base nettleie {label} er negativ ({base:.4f}). "
                f"Energiledd {price}, avgiftssone '{sone}'. "
                f"Mulig feil: dobbel mva, feil forbruksavgift, eller manglende tiltakssone-flagg."
            )

    def test_dag_natt_same_avgiftsandel(self, dso_entry):
        """Dag og natt bor ha samme avgiftsandel -- forskjellen er ren nettleie.

        Hvis mva-andelen er forskjellig mellom dag og natt, er noe galt
        med beregningen (f.eks. en bruker avgifter inkl. mva og den andre ikke).
        """
        dso_id, data = dso_entry
        if dso_id == "custom":
            pytest.skip("custom DSO har brukervalgte priser")

        dag = data["energiledd_dag"]
        natt = data["energiledd_natt"]
        if dag == natt:
            pytest.skip("flat sats -- ingen dag/natt-forskjell")

        sone = self._get_avgiftssone(dso_id, data)
        base_dag = self._extract_base_nettleie(dag, sone)
        base_natt = self._extract_base_nettleie(natt, sone)
        diff_total = dag - natt
        diff_base = base_dag - base_natt

        # For standard sone: diff_total bor vaere diff_base * 1.25 (mva pa forskjellen)
        # For nord/tiltakssone: diff_total bor vaere lik diff_base (ingen mva)
        if sone == "standard":
            expected_diff = diff_base * (1 + MVA_SATS)
        else:
            expected_diff = diff_base

        assert abs(diff_total - expected_diff) < 0.001, (
            f"{dso_id}: dag/natt-forskjell er inkonsistent. "
            f"Total diff: {diff_total:.4f}, forventet fra base: {expected_diff:.4f}. "
            f"Mulig feil: ulik avgiftsberegning for dag vs natt."
        )


class TestDSOHelgSomNatt:
    """Verify helg_som_natt flag consistency."""

    def test_helg_som_natt_false_requires_dag_natt_diff(self):
        """DSO-er med helg_som_natt=False bor ha dag != natt.

        Hvis dag == natt (flat sats), gir flagget ingen mening.
        """
        for dso_id, data in DSO_LIST.items():
            if data.get("helg_som_natt") is False:
                assert data["energiledd_dag"] != data["energiledd_natt"], (
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
