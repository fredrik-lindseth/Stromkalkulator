"""Tester for spotpris_inkl_mva-flagget (incident 004).

Verifiserer at coordinator normaliserer spotpris til inkl. mva basert på
avgiftssone og spotpris_inkl_mva-flagget. Default-konfig (False) skal multiplisere
spotpris fra sensor med (1 + mva_sats); migrert konfig (True) skal beholde
verdien som den er.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry as _base_make_entry
from tests.conftest import _make_hass as _base_make_hass


def _make_entry(
    spotpris_inkl_mva: bool,
    avgiftssone: str = "standard",
    har_norgespris: bool = False,
):
    """Bruker delt _make_entry-fabrikk med spotpris_inkl_mva som første-felt-fokus."""
    return _base_make_entry(
        entry_id="test_entry",
        dso_id="bkk",
        spotpris_inkl_mva=spotpris_inkl_mva,
        avgiftssone=avgiftssone,
        har_norgespris=har_norgespris,
    )


def _make_hass(spot_price: float):
    """Lokal wrapper: power=0 og angitt spot_price (via delt fabrikk)."""
    return _base_make_hass(power_w=0, spot_price=spot_price)


def _run_update(coord):
    """Lokal forenklet variant uten now-override (kun denne filen bruker den)."""
    return asyncio.run(coord._async_update_data())


class TestSpotprisNormalisering:
    """Spotpris fra sensor skal normaliseres til inkl. mva i interne beregninger."""

    def test_eks_mva_sone_standard_legger_paa_25_prosent(self, coord_module):
        """Sør-Norge + spotpris_inkl_mva=False skal gi spot * 1.25."""
        entry = _make_entry(spotpris_inkl_mva=False, avgiftssone="standard")
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        assert result["spot_price"] == pytest.approx(1.50, abs=1e-9)

    def test_inkl_mva_passthrough_uten_endring(self, coord_module):
        """spotpris_inkl_mva=True skal beholde verdien som den er."""
        entry = _make_entry(spotpris_inkl_mva=True, avgiftssone="standard")
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        assert result["spot_price"] == pytest.approx(1.20, abs=1e-9)

    def test_nord_norge_legger_ikke_paa_mva(self, coord_module):
        """Nord-Norge har 0% mva, så normaliseringen skal være no-op."""
        entry = _make_entry(spotpris_inkl_mva=False, avgiftssone="nord_norge")
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        assert result["spot_price"] == pytest.approx(1.20, abs=1e-9)

    def test_tiltakssone_legger_ikke_paa_mva(self, coord_module):
        """Tiltakssonen har 0% mva, så normaliseringen skal være no-op."""
        entry = _make_entry(spotpris_inkl_mva=False, avgiftssone="tiltakssone")
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        assert result["spot_price"] == pytest.approx(1.20, abs=1e-9)

    def test_default_uten_flagg_antar_eks_mva(self, coord_module):
        """Manglende spotpris_inkl_mva-felt skal default til False (eks. mva)."""
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            "tso": "bkk",
            "power_sensor": "sensor.power",
            "spot_price_sensor": "sensor.spot_price",
            "har_norgespris": False,
            "avgiftssone": "standard",
        }
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        assert result["spot_price"] == pytest.approx(1.50, abs=1e-9)


class TestStromstotteMedNormalisering:
    """Strømstøtte trigges ved riktig terskel etter normalisering."""

    def test_spot_under_terskel_eks_mva_men_over_inkl_mva_gir_stotte(self, coord_module):
        """Spot 0.80 eks. mva = 1.00 inkl. mva, som er over terskel 0.9625."""
        entry = _make_entry(spotpris_inkl_mva=False, avgiftssone="standard")
        hass = _make_hass(spot_price=0.80)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        # 0.80 * 1.25 = 1.00 inkl mva. Stromstotte = (1.00 - 0.9625) * 0.90 = 0.03375
        assert result["stromstotte"] == pytest.approx(0.03375, abs=1e-4)

    def test_samme_eks_mva_verdi_uten_konvertering_gir_ingen_stotte(self, coord_module):
        """Hvis vi feilaktig hadde spotpris_inkl_mva=True på en eks-mva-sensor."""
        entry = _make_entry(spotpris_inkl_mva=True, avgiftssone="standard")
        hass = _make_hass(spot_price=0.80)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        # 0.80 < 0.9625, ingen stotte (det er bug-oppførselen vi unngår med default False).
        assert result["stromstotte"] == 0.0


class TestNorgesprisDiffMedNormalisering:
    """Norgespris-besparelse beregnes med inkl-mva-spotpris."""

    def test_besparelse_bruker_normalisert_spot(self, coord_module):
        """Spot 1.20 eks. mva → 1.50 inkl. mva. Sammenligner med spot-etter-stotte.

        Reelt alternativ uten Norgespris: spot 1.50 minus strømstøtte 0.4838 = 1.0162
        Norgespris: 0.50
        Diff = 1.0162 - 0.50 = 0.5162 kr/kWh
        """
        entry = _make_entry(spotpris_inkl_mva=False, avgiftssone="standard", har_norgespris=True)
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        # spot_inkl_mva = 1.50, stromstotte = (1.50 - 0.9625) * 0.90 = 0.4838
        # spot_total_etter_stotte = 1.50 - 0.4838 + ledd
        # total_price = 0.50 + ledd
        # Diff = 1.0162 - 0.50 = 0.5162
        assert result["kroner_spart_per_kwh"] == pytest.approx(0.5162, abs=1e-3)

    def test_besparelse_uten_normalisering_undervurderer_kraftig(self, coord_module):
        """Demonstrerer bug-en: spotpris_inkl_mva=True på eks-mva-sensor gir feil."""
        entry = _make_entry(spotpris_inkl_mva=True, avgiftssone="standard", har_norgespris=True)
        hass = _make_hass(spot_price=1.20)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True

        result = _run_update(coord)

        # Spot brukes som 1.20 inkl mva (feil). Stromstotte = (1.20 - 0.9625) * 0.90 = 0.2138
        # spot_total_etter_stotte = 0.9863
        # total_price = 0.50
        # Diff = 0.9863 - 0.50 = 0.4863 — undervurderer 0.5162 (riktig) med ~6%
        assert result["kroner_spart_per_kwh"] == pytest.approx(0.4863, abs=1e-3)
