"""Varselet om den feilmerkede energiledd-satsen for egendefinert nettselskap.

Til og med 1.16.0 sto feltet merket «inkl. avgifter» i nb og «incl. taxes» i en,
mens koden regner satsen som ren nettleie og legger forbruksavgift, Enova og mva
på selv. Fulgte brukeren teksten, telles avgiftene to ganger. Vi kan ikke se hvem
som tastet hva, så varselet ber om en sjekk, og bekreftelsen lagres på entryet
slik at det ikke kommer tilbake ved neste omstart.

Testene dekker begge sidene av akseptansen: varselet reises for en entry med
egendefinerte satser og ikke for andre, og det lar seg lukke.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import _make_entry

if "voluptuous" not in sys.modules:
    # voluptuous er ikke installert i testmiljøet. Samme stub som i
    # test_config_flow_options.py; repairs.py bruker bare vol.Schema({}).
    _vol = MagicMock()
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    sys.modules["voluptuous"] = _vol


def _installer_repairs_stub() -> None:
    """Gi repairs.py ekte basisklasser å arve fra.

    conftest bytter ut hele homeassistant-pakken med MagicMock, og man kan ikke
    arve fra en MagicMock. Stubben må derfor ligge i sys.modules før
    stromkalkulator.repairs importeres, og den må ha de FlowHandler-metodene
    flowen vår kaller.
    """
    if "homeassistant.components.repairs" in sys.modules:
        return

    modul = ModuleType("homeassistant.components.repairs")

    class RepairsFlow:
        """Minimal FlowHandler-stub."""

        hass: MagicMock

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    class ConfirmRepairFlow(RepairsFlow):
        """Stub for HA-helperen som bare viser et bekreftelsessteg."""

    modul.RepairsFlow = RepairsFlow
    modul.ConfirmRepairFlow = ConfirmRepairFlow
    sys.modules.setdefault("homeassistant.components", MagicMock())
    sys.modules["homeassistant.components.repairs"] = modul


_installer_repairs_stub()


@pytest.fixture
def init_module():
    """Last __init__ og coordinator på nytt, med Store byttet ut."""
    import stromkalkulator.__init__ as init_mod
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    importlib.reload(init_mod)

    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return init_mod


@pytest.fixture
def repairs_module():
    """Last repairs.py med stubbede HA-basisklasser."""
    import stromkalkulator.repairs as repairs_mod

    return importlib.reload(repairs_mod)


def _mock_ir() -> MagicMock:
    mock = MagicMock()
    mock.IssueSeverity.WARNING = "warning"
    return mock


def _reist(mock_ir: MagicMock, issue_id: str) -> MagicMock | None:
    for call in mock_ir.async_create_issue.call_args_list:
        if call.args[2] == issue_id:
            return call
    return None


class TestVarseletReises:
    """Hvem som får varselet, og hvem som slipper."""

    def test_egendefinert_dso_far_varselet(self, init_module):
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        call = _reist(mock_ir, "egendefinert_energiledd_abc")
        assert call is not None
        assert call.kwargs["is_fixable"] is True
        assert call.kwargs["translation_key"] == "egendefinert_energiledd"

    def test_kjent_dso_far_det_ikke(self, init_module):
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="bkk")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once_with(
            hass, init_module.DOMAIN, "egendefinert_energiledd_abc"
        )

    def test_bekreftet_entry_far_det_ikke_igjen(self, init_module):
        """Bekreftelsen er det eneste som skiller en sjekket sats fra en usjekket."""
        hass = MagicMock()
        entry = _make_entry(
            entry_id="abc",
            dso_id="custom",
            extra_data={"egendefinert_satser_bekreftet": True},
        )
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once()

    def test_teksten_far_brukerens_egne_tall(self, init_module):
        """Uten satsene i teksten har brukeren ingenting å kjenne igjen."""
        hass = MagicMock()
        entry = _make_entry(
            entry_id="abc",
            dso_id="custom",
            extra_data={"energiledd_dag": 0.2099, "energiledd_natt": 0.105},
        )
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        plassholdere = _reist(mock_ir, "egendefinert_energiledd_abc").kwargs["translation_placeholders"]
        assert plassholdere["avgifter"] == "8,13"
        assert plassholdere["dag"] == "20,99"
        assert plassholdere["natt"] == "10,50"

    def test_tiltakssonen_har_bare_enova(self, init_module):
        """Forbruksavgiften er fritatt der, så dobbelttellingen er mindre."""
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom", avgiftssone="tiltakssone")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        plassholdere = _reist(mock_ir, "egendefinert_energiledd_abc").kwargs["translation_placeholders"]
        assert plassholdere["avgifter"] == "1,00"

    def test_sats_som_mangler_gir_ikke_krasj(self, init_module):
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom")
        entry.data.pop("energiledd_dag", None)
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinerte_satser(hass, entry)

        plassholdere = _reist(mock_ir, "egendefinert_energiledd_abc").kwargs["translation_placeholders"]
        assert plassholdere["dag"] == "?"


class TestVarseletLarSegLukke:
    """Et varsel som ikke kan lukkes er støy. Fix-flowen må huske bekreftelsen."""

    def test_egen_flow_for_energiledd_varselet(self, repairs_module):
        flow = asyncio.run(
            repairs_module.async_create_fix_flow(MagicMock(), "egendefinert_energiledd_abc", None)
        )
        assert isinstance(flow, repairs_module.EgendefinertSatserRepairFlow)
        assert flow._entry_id == "abc"

    def test_andre_issues_far_confirm_flowen(self, repairs_module):
        flow = asyncio.run(repairs_module.async_create_fix_flow(MagicMock(), "dso_migration_a_b", None))
        assert not isinstance(flow, repairs_module.EgendefinertSatserRepairFlow)

    def test_bekreftelse_skrives_pa_entryet(self, repairs_module):
        entry = _make_entry(entry_id="abc", dso_id="custom")
        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = entry

        flow = repairs_module.EgendefinertSatserRepairFlow("egendefinert_energiledd_abc", "abc")
        flow.hass = hass
        resultat = asyncio.run(flow.async_step_confirm({}))

        assert resultat["type"] == "create_entry"
        hass.config_entries.async_update_entry.assert_called_once()
        ny_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert ny_data["egendefinert_satser_bekreftet"] is True

    def test_bekreftet_entry_skrives_ikke_pa_nytt(self, repairs_module):
        entry = _make_entry(
            entry_id="abc",
            dso_id="custom",
            extra_data={"egendefinert_satser_bekreftet": True},
        )
        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = entry

        flow = repairs_module.EgendefinertSatserRepairFlow("egendefinert_energiledd_abc", "abc")
        flow.hass = hass
        asyncio.run(flow.async_step_confirm({}))

        hass.config_entries.async_update_entry.assert_not_called()

    def test_slettet_entry_gir_ikke_krasj(self, repairs_module):
        """Entryet kan være borte mellom at varselet ble reist og bekreftet."""
        hass = MagicMock()
        hass.config_entries.async_get_entry.return_value = None

        flow = repairs_module.EgendefinertSatserRepairFlow("egendefinert_energiledd_abc", "abc")
        flow.hass = hass
        resultat = asyncio.run(flow.async_step_confirm({}))

        assert resultat["type"] == "create_entry"
        hass.config_entries.async_update_entry.assert_not_called()

    def test_forste_visning_har_satsene_i_teksten(self, repairs_module):
        issue = MagicMock()
        issue.translation_placeholders = {"avgifter": "8,13", "dag": "20,99", "natt": "10,50"}
        hass = MagicMock()

        flow = repairs_module.EgendefinertSatserRepairFlow("egendefinert_energiledd_abc", "abc")
        flow.hass = hass

        with patch.object(repairs_module, "ir") as mock_ir:
            mock_ir.async_get.return_value.async_get_issue.return_value = issue
            resultat = asyncio.run(flow.async_step_init())

        assert resultat["type"] == "form"
        assert resultat["description_placeholders"]["dag"] == "20,99"

    def test_ukjent_issue_gir_tomme_plassholdere(self, repairs_module):
        flow = repairs_module.EgendefinertSatserRepairFlow("egendefinert_energiledd_abc", "abc")
        flow.hass = MagicMock()

        with patch.object(repairs_module, "ir") as mock_ir:
            mock_ir.async_get.return_value.async_get_issue.return_value = None
            resultat = asyncio.run(flow.async_step_confirm())

        assert resultat["description_placeholders"] is None


class TestFastleddVarselet:
    """Varselet om de fjernede kapasitetstrinnene (kontrakt §9).

    Egendefinert hadde ti innebygde trinn til og med 1.16.0. De var en mal uten
    prisliste bak seg, og bare brukeren vet hva nettselskapet hans tar. Varselet
    ber om tabellen, og er ikke fiksbart: det finnes ingen bekreftelse vi kan ta
    imot i stedet for tallene, akkurat som for sikringsstørrelse.
    """

    def test_egendefinert_uten_tabell_far_varselet(self, init_module):
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinert_fastledd(hass, entry)

        call = _reist(mock_ir, "egendefinert_fastledd_abc")
        assert call is not None
        assert call.kwargs["is_fixable"] is False
        assert call.kwargs["translation_key"] == "egendefinert_fastledd"

    def test_egendefinert_med_tabell_far_det_ikke(self, init_module):
        hass = MagicMock()
        entry = _make_entry(
            entry_id="abc",
            dso_id="custom",
            extra_data={"egendefinert_kapasitetstrinn": "2:155,5:250,10:415"},
        )
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinert_fastledd(hass, entry)

        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once_with(
            hass, init_module.DOMAIN, "egendefinert_fastledd_abc"
        )

    def test_kjent_dso_far_det_ikke(self, init_module):
        """Falske positiver varsler hos alle. BKK har trinn med kilde."""
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="bkk")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinert_fastledd(hass, entry)

        mock_ir.async_create_issue.assert_not_called()
        mock_ir.async_delete_issue.assert_called_once()

    def test_varselet_forsvinner_nar_tabellen_kommer(self, init_module):
        """Sjekken kjører ved hver oppstart, så et fylt felt lukker varselet."""
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom")
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinert_fastledd(hass, entry)
            entry.data["egendefinert_kapasitetstrinn"] = "2:155"
            init_module._check_egendefinert_fastledd(hass, entry)

        assert _reist(mock_ir, "egendefinert_fastledd_abc") is not None
        mock_ir.async_delete_issue.assert_called_once_with(
            hass, init_module.DOMAIN, "egendefinert_fastledd_abc"
        )

    def test_tom_tabell_teller_som_manglende(self, init_module):
        hass = MagicMock()
        entry = _make_entry(entry_id="abc", dso_id="custom", extra_data={"egendefinert_kapasitetstrinn": ""})
        mock_ir = _mock_ir()

        with patch.object(init_module, "ir", mock_ir):
            init_module._check_egendefinert_fastledd(hass, entry)

        assert _reist(mock_ir, "egendefinert_fastledd_abc") is not None
