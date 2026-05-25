"""Tester for sesong-styrte energiledd-perioder.

Verifiserer:
- `finn_aktiv_periode` slår opp riktig periode på MM-DD.
- Coordinator returnerer riktige (dag, natt)-satser ut fra dato.
- Periode som krysser nyttår (fra > til) behandles som union.
- Fallback til DSO-default når ingen periode treffer.
"""

from __future__ import annotations

from datetime import datetime

import pytest

# Conftest legger custom_components på sys.path, så stromkalkulator-pakken
# importeres uten "custom_components."-prefix. Coordinator-fixturen bruker
# samme path, slik at vi patcher samme DSO_LIST-objekt.
from stromkalkulator.dso import (
    DSO_LIST,
    finn_aktiv_periode,
)

from tests.conftest import _make_entry, _make_hass, _run_update


class TestFinnAktivPeriode:
    """Unit-tester for periode-oppslag."""

    def test_treffer_innen_normal_periode(self):
        perioder = [
            {"fra": "01-01", "til": "06-30", "dag_eks_mva": 0.25, "natt_eks_mva": 0.13},
            {"fra": "07-01", "til": "12-31", "dag_eks_mva": 0.21, "natt_eks_mva": 0.10},
        ]
        treff = finn_aktiv_periode(perioder, "03-15")
        assert treff is not None
        assert treff["dag_eks_mva"] == 0.25

    def test_treffer_periode_som_krysser_nyttar(self):
        perioder = [
            {"fra": "11-01", "til": "03-31", "dag_eks_mva": 0.30, "natt_eks_mva": 0.15},
            {"fra": "04-01", "til": "10-31", "dag_eks_mva": 0.20, "natt_eks_mva": 0.10},
        ]
        # Januar — vinter-perioden krysser nyttår
        treff = finn_aktiv_periode(perioder, "01-15")
        assert treff is not None
        assert treff["dag_eks_mva"] == 0.30
        # Desember — fortsatt vinter
        treff = finn_aktiv_periode(perioder, "12-15")
        assert treff is not None
        assert treff["dag_eks_mva"] == 0.30
        # Juli — sommer
        treff = finn_aktiv_periode(perioder, "07-15")
        assert treff is not None
        assert treff["dag_eks_mva"] == 0.20

    def test_grenseverdier_inkluderes(self):
        perioder = [
            {"fra": "07-01", "til": "12-31", "dag_eks_mva": 0.21, "natt_eks_mva": 0.10},
        ]
        # Første dag
        assert finn_aktiv_periode(perioder, "07-01") is not None
        # Siste dag
        assert finn_aktiv_periode(perioder, "12-31") is not None
        # Utenfor
        assert finn_aktiv_periode(perioder, "06-30") is None

    def test_ingen_treff_returnerer_none(self):
        perioder = [
            {"fra": "04-01", "til": "06-30", "dag_eks_mva": 0.21, "natt_eks_mva": 0.10},
        ]
        assert finn_aktiv_periode(perioder, "01-15") is None


class TestCoordinatorSesongBytte:
    """Verifiserer at coordinator bruker aktiv sesongperiode."""

    @pytest.fixture
    def patch_tensio_tn_med_perioder(self, monkeypatch):
        """Patch tensio_tn med sesongperioder for testing.

        Bruker fiktive tall så vi tester mekanismen, ikke faktisk faktura.
        """
        original = DSO_LIST["tensio_tn"].copy()
        original["energiledd_perioder"] = [
            {"fra": "01-01", "til": "06-30", "dag_eks_mva": 0.30, "natt_eks_mva": 0.20},
            {"fra": "07-01", "til": "12-31", "dag_eks_mva": 0.20, "natt_eks_mva": 0.10},
        ]
        monkeypatch.setitem(DSO_LIST, "tensio_tn", original)
        return original

    def test_vinter_periode_brukes_i_januar(self, coord_module, patch_tensio_tn_med_perioder):
        januar_dag = datetime(2026, 1, 15, 12, 0)  # midt på dagen, virkedag
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_tn")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator, now=januar_dag)
        # Standard NO3 har 25% mva, så 0.30 + 0.0713 + 0.01 = 0.3813 -> *1.25 = 0.4766
        assert result["energiledd_dag"] == pytest.approx(0.4766, abs=0.001)
        assert result["aktiv_energiledd_periode"] == "01-01 til 06-30"

    def test_sommer_periode_brukes_i_juli(self, coord_module, patch_tensio_tn_med_perioder):
        juli_dag = datetime(2026, 7, 15, 12, 0)
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_tn")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator, now=juli_dag)
        # 0.20 + 0.0713 + 0.01 = 0.2813 -> *1.25 = 0.3516
        assert result["energiledd_dag"] == pytest.approx(0.3516, abs=0.001)
        assert result["aktiv_energiledd_periode"] == "07-01 til 12-31"

    def test_natt_sats_byttes_ogsa(self, coord_module, patch_tensio_tn_med_perioder):
        """Tensio TN har helg_som_natt=False, så kveld er natt-sats."""
        juli_natt = datetime(2026, 7, 15, 23, 0)
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_tn")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator, now=juli_natt)
        # Sommer-natt: 0.10 + 0.0713 + 0.01 = 0.1813 -> *1.25 = 0.2266
        assert result["energiledd_natt"] == pytest.approx(0.2266, abs=0.001)
        assert result["energiledd"] == pytest.approx(0.2266, abs=0.001)

    def test_perioder_eksponert_i_data(self, coord_module, patch_tensio_tn_med_perioder):
        januar_dag = datetime(2026, 1, 15, 12, 0)
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_tn")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator, now=januar_dag)
        perioder = result["energiledd_perioder"]
        assert perioder is not None
        assert len(perioder) == 2
        assert perioder[0]["fra"] == "01-01"
        assert perioder[1]["fra"] == "07-01"

    def test_dso_uten_perioder_har_ingen_aktiv_periode(self, coord_module):
        januar_dag = datetime(2026, 1, 15, 12, 0)
        hass = _make_hass()
        entry = _make_entry(dso_id="bkk")  # ingen sesongprising
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator, now=januar_dag)
        assert result["aktiv_energiledd_periode"] is None
        assert result["energiledd_perioder"] is None
