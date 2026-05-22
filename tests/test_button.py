"""Tester for FakturaRapportButton i button.py."""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import MagicMock, patch

# Conftest mocker HA-moduler som MagicMock, men subklassing av to MagicMock-
# baser gir metaclass-konflikt. Bytt ut med minimal-klasser før import.
_button_mod = sys.modules.setdefault("homeassistant.components.button", MagicMock())
_button_mod.ButtonEntity = type("ButtonEntity", (), {})
sys.modules.setdefault("homeassistant.components.persistent_notification", MagicMock())


class _FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = (
    _FakeCoordinatorEntity)
_dev = sys.modules.setdefault("homeassistant.helpers.device_registry", MagicMock())
_dev.DeviceInfo = lambda **kw: kw

import stromkalkulator.button as button_mod  # noqa: E402

importlib.reload(button_mod)
from stromkalkulator.button import FakturaRapportButton  # noqa: E402


def _make_entry(entry_id="entry-abc", dso_id="bkk", har_norgespris=False,
                avgiftssone="standard", spotpris_inkl_mva=False):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id, "har_norgespris": har_norgespris,
        "avgiftssone": avgiftssone, "spotpris_inkl_mva": spotpris_inkl_mva,
    }
    return entry


def _make_coord(data=None):
    coord = MagicMock()
    coord.data = data
    return coord


_FULL = {
    "previous_month_name": "april 2026",
    "previous_month_consumption_dag_kwh": 612.456,
    "previous_month_consumption_natt_kwh": 388.123,
    "previous_month_consumption_total_kwh": 1000.579,
    "previous_month_kapasitetsledd": 415,
    "previous_month_kapasitetstrinn": "5-10 kW",
    "previous_month_avg_top_3_kw": 7.42,
    "previous_month_norgespris_diff_kr": 312.55,
    "previous_month_norgespris_compensation_kr": 98.20,
    "previous_month_energiledd_dag": 0.4613,
    "previous_month_energiledd_natt": 0.2328,
}


class TestInitOgDeviceInfo:
    def test_unique_id(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(entry_id="abc"))
        assert btn._attr_unique_id == "abc_lag_fakturarapport"

    def test_dso_settes(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(dso_id="bkk"))
        assert btn._dso["name"] == "BKK"
        assert btn._dso["prisomrade"] == "NO5"

    def test_dso_fallback_ved_ukjent_id(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(dso_id="nope"))
        assert btn._dso["name"] == "BKK"

    def test_device_info(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(entry_id="xyz"))
        info = btn.device_info
        assert ("stromkalkulator", "xyz_forrige_maaned") in info["identifiers"]
        assert info["name"] == "Forrige måned"


def _report(coord_data, **entry_kw):
    return FakturaRapportButton(
        _make_coord(coord_data), _make_entry(**entry_kw))._build_report()


class TestBuildReportNorgespris:
    """Full Norgespris-rapport: fence, seksjoner, tall og personvern."""

    def setup_method(self):
        self.r = _report(_FULL, har_norgespris=True)

    def test_markdown_fence(self):
        assert "~~~markdown" in self.r
        assert self.r.rstrip().endswith("~~~")

    def test_alle_seksjoner(self):
        for h in ("## Oppsett", "## Forbruk", "## Faktura (fyll inn)",
                  "## Konklusjon", "## Kreditt"):
            assert h in self.r

    def test_avtale_og_periode(self):
        assert "Norgespris" in self.r
        assert "Spotpris + strømstøtte" not in self.r
        assert "april 2026" in self.r

    def test_personvern(self):
        assert "Personvern" in self.r and "kundenummer" in self.r

    def test_forbruk_og_norgespris_tall(self):
        for n in ("612.456", "388.123", "1000.579", "312.55", "98.20"):
            assert n in self.r

    def test_kapasitetstrinn(self):
        assert "5-10 kW" in self.r and "415" in self.r

    def test_faktura_tabell_tomme_celler(self):
        assert "| Energiledd dag | | |" in self.r
        assert "| **Sum nettleie** | | |" in self.r


class TestBuildReportSpot:
    def test_spot_inkl_mva(self):
        r = _report(_FULL, har_norgespris=False, spotpris_inkl_mva=True)
        assert "Spotpris + strømstøtte" in r
        assert "inkl. mva" in r

    def test_spot_eks_mva(self):
        assert "eks. mva" in _report(_FULL, har_norgespris=False, spotpris_inkl_mva=False)


class TestBuildReportNordNorge:
    def test_norgespris_nord_norge(self):
        r = _report(_FULL, har_norgespris=True, avgiftssone="nord_norge")
        assert "nord_norge" in r and "Norgespris" in r

    def test_spot_nord_norge(self):
        r = _report(_FULL, har_norgespris=False, avgiftssone="nord_norge")
        assert "nord_norge" in r and "Spotpris + strømstøtte" in r


class TestBuildReportTomData:
    def test_tom_dict(self):
        r = _report({})
        assert "(forrige måned ikke tilgjengelig)" in r
        assert "0.000" in r

    def test_none_data(self):
        assert "(forrige måned ikke tilgjengelig)" in _report(None)

    def test_manglende_kapasitetstrinn(self):
        r = _report(dict(_FULL, previous_month_kapasitetstrinn=None))
        assert "(ikke tilgjengelig)" in r


class TestAsyncPress:
    def test_kaller_async_create_med_riktig_args(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(entry_id="press-1"))
        btn.hass = MagicMock()
        with patch.object(button_mod, "async_create") as create:
            asyncio.run(btn.async_press())
        assert create.call_count == 1
        args, kwargs = create.call_args
        assert args[0] is btn.hass
        assert "~~~markdown" in args[1]
        assert kwargs["title"] == "Fakturaverifiserings-rapport"
        assert kwargs["notification_id"] == "stromkalkulator_fakturarapport_press-1"

    def test_notification_id_unik_per_entry(self):
        btn = FakturaRapportButton(_make_coord(_FULL), _make_entry(entry_id="annet-id"))
        btn.hass = MagicMock()
        with patch.object(button_mod, "async_create") as create:
            asyncio.run(btn.async_press())
        assert "annet-id" in create.call_args.kwargs["notification_id"]


class TestManifestVersionOgSetup:
    def test_version_er_string(self):
        assert isinstance(button_mod._MANIFEST_VERSION, str)
        assert button_mod._MANIFEST_VERSION != ""

    def test_version_med_i_rapport(self):
        assert button_mod._MANIFEST_VERSION in _report(_FULL)

    def test_les_manifest_ukjent_ved_feil(self, tmp_path, monkeypatch):
        monkeypatch.setattr(button_mod, "__file__", str(tmp_path / "x" / "button.py"))
        assert button_mod._read_manifest_version() == "ukjent"

    def test_setup_entry_legger_til_knappen(self):
        entry = _make_entry()
        entry.runtime_data = _make_coord(_FULL)
        add = MagicMock()
        asyncio.run(button_mod.async_setup_entry(MagicMock(), entry, add))
        entities = add.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], FakturaRapportButton)
