"""Tariffmodus: hvor energiledd-satsen kommer fra, og varselet som spør.

Til og med 1.16.0 vant en sats lagret på config entryet over `dso.py`, og
oppsettsflyten lagret katalogens sats på hvert eneste oppsett. En tariffendring
i katalogen nådde derfor aldri fram til noen som allerede hadde satt opp
anlegget sitt. Sju nettselskap fikk nye satser i august og september 2026, og av
dem slo bare Sør Aurdal gjennom, fordi den har sesongperioder.

Kontrakt §6 og §8 i docs/kontrakter/input-og-konfig.md. Hver påstand her har en
negativ prøve ved siden av seg: et varsel som bare er testet i den retningen det
skal komme, er ikke testet.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _make_entry

if "voluptuous" not in sys.modules:
    # Samme stub som i test_repairs_egendefinert.py; repairs.py bruker bare
    # vol.Schema({}) og menyvalg.
    _vol = MagicMock()
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    sys.modules["voluptuous"] = _vol


def _installer_repairs_stub() -> None:
    """Gi repairs.py ekte basisklasser å arve fra.

    conftest bytter ut hele homeassistant-pakken med MagicMock, og man kan ikke
    arve fra en MagicMock. Stubben må ligge i sys.modules før
    stromkalkulator.repairs importeres, og må ha de FlowHandler-metodene flowen
    vår kaller, inkludert async_show_menu.
    """
    modul = sys.modules.get("homeassistant.components.repairs")
    if modul is not None and hasattr(modul.RepairsFlow, "async_show_menu"):
        return

    modul = ModuleType("homeassistant.components.repairs")

    class RepairsFlow:
        """Minimal FlowHandler-stub."""

        hass: MagicMock

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    class ConfirmRepairFlow(RepairsFlow):
        """Stub for HA-helperen som bare viser et bekreftelsessteg."""

    modul.RepairsFlow = RepairsFlow
    modul.ConfirmRepairFlow = ConfirmRepairFlow
    sys.modules.setdefault("homeassistant.components", MagicMock())
    sys.modules["homeassistant.components.repairs"] = modul


_installer_repairs_stub()

from stromkalkulator.const import (  # noqa: E402
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_TARIFFMODUS,
    DSO_LIST,
    TARIFF_AVVIK_TERSKEL,
    TARIFF_ISSUE_PREFIX,
    compute_energiledd_inkl_mva,
    energiledd_avviker,
    les_tariffmodus,
)

BKK = DSO_LIST["bkk"]
# Sør Aurdal er sesong-DSO-en fra kontrakten: den som slo gjennom fordi
# periodene alltid har ignorert en lagret fast sats.
SESONG_ID = next(
    dso_id for dso_id, dso in DSO_LIST.items() if dso.get("energiledd_perioder") and dso.get("supported")
)
SESONG = DSO_LIST[SESONG_ID]


@pytest.fixture
def init_module():
    """Last __init__ og coordinator på nytt, med Store byttet ut."""
    import stromkalkulator.__init__ as init_mod
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    importlib.reload(init_mod)
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


def _ore_inkl(eks_mva: float, sone: str = "standard") -> str:
    """Satsen slik varselet skriver den: øre/kWh inkl. avgifter og mva."""
    return f"{compute_energiledd_inkl_mva(eks_mva, sone) * 100:.2f}".replace(".", ",")


def _reist(mock_ir: MagicMock, issue_id: str) -> MagicMock | None:
    for call in mock_ir.async_create_issue.call_args_list:
        if call.args[2] == issue_id:
            return call
    return None


# ===========================================================================
# Rate-oppløsningen i coordinatoren
# ===========================================================================


class TestRateOpplosning:
    """Katalogen skal vinne med mindre brukeren uttrykkelig har valgt noe annet."""

    def test_catalog_ignorerer_lagret_sats(self, coord_module):
        """Selve feilen: en lagret sats skal ikke lenger slå dso.py.

        0,40 er hverken BKKs gamle eller nye sats. Står den igjen i regnestykket,
        er katalogen fortsatt overkjørt.
        """
        entry = _make_entry(
            extra_data={
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_ENERGILEDD_NATT: 0.30,
                CONF_TARIFFMODUS: "catalog",
            }
        )
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]
        assert coordinator.energiledd_natt_eks_mva == BKK["energiledd_natt_eks_mva"]

    def test_legacy_unconfirmed_regner_med_katalogen(self, coord_module):
        """Den som ikke har svart på varselet skal ikke bli stående på gammel sats."""
        entry = _make_entry(
            extra_data={
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_TARIFFMODUS: "legacy_unconfirmed",
            }
        )
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]

    def test_manual_beholder_brukerens_sats(self, coord_module):
        """Et bevisst valg skal ikke overskrives av katalogen."""
        entry = _make_entry(
            extra_data={
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_ENERGILEDD_NATT: 0.30,
                CONF_TARIFFMODUS: "manual",
            }
        )
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.energiledd_dag_eks_mva == 0.40
        assert coordinator.energiledd_natt_eks_mva == 0.30

    def test_manual_uten_egen_sats_faller_til_katalogen(self, coord_module):
        """Manual uten tall er ikke null; da er katalogen det beste vi har."""
        entry = _make_entry(extra_data={CONF_TARIFFMODUS: "manual"})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]

    def test_entry_uten_modus_bruker_katalogen(self, coord_module):
        """En entry som ikke har rukket migreringen skal følge prislisten."""
        entry = _make_entry(extra_data={CONF_ENERGILEDD_DAG: 0.40})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.tariffmodus == "catalog"
        assert coordinator.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]

    def test_egendefinert_uten_modus_er_manual(self, coord_module):
        """Egendefinert har ingen katalog å falle tilbake på."""
        entry = _make_entry(dso_id="custom", extra_data={CONF_ENERGILEDD_DAG: 0.40})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.tariffmodus == "manual"
        assert coordinator.energiledd_dag_eks_mva == 0.40


class TestSesongDso:
    """Periodene styrer hele året, også for manual, og det skal være synlig."""

    def test_manual_ignoreres_paa_sesong_dso(self, coord_module):
        entry = _make_entry(
            dso_id=SESONG_ID,
            extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "manual"},
        )
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.manual_ignorert is True
        assert coordinator.energiledd_dag_eks_mva == SESONG["energiledd_dag_eks_mva"]

    def test_attributtet_staar_i_tarifforigin(self, coord_module):
        entry = _make_entry(
            dso_id=SESONG_ID,
            extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "manual"},
        )
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)
        naa = coord_module.dt_util.now()

        opprinnelse = coordinator._tarifforigin(naa, 0.5, 0.4)

        assert opprinnelse["manual_ignorert"] is True
        assert opprinnelse["sesongperioder_styrer"] is True
        assert opprinnelse["modus"] == "manual"

    def test_katalogmodus_paa_sesong_dso_flagger_ingenting(self, coord_module):
        """Negativ prøve: uten manual er det ingenting som blir ignorert."""
        entry = _make_entry(dso_id=SESONG_ID, extra_data={CONF_TARIFFMODUS: "catalog"})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)
        naa = coord_module.dt_util.now()

        assert coordinator.manual_ignorert is False
        assert coordinator._tarifforigin(naa, 0.5, 0.4)["manual_ignorert"] is False

    def test_manual_paa_vanlig_dso_flagger_ingenting(self, coord_module):
        """Negativ prøve: uten perioder gjelder manual-satsen som den skal."""
        entry = _make_entry(extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "manual"})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)

        assert coordinator.manual_ignorert is False


class TestTarifforiginForD2:
    """Diagnostikken skal se hvilke satser som faktisk ble brukt."""

    def test_satsene_er_de_aktive(self, coord_module):
        entry = _make_entry(extra_data={CONF_TARIFFMODUS: "catalog"})
        coordinator = coord_module.NettleieCoordinator(MagicMock(), entry)
        naa = coord_module.dt_util.now()

        opprinnelse = coordinator._tarifforigin(naa, 0.46125, 0.23288)

        assert opprinnelse["dso"] == "bkk"
        assert opprinnelse["energiledd_dag_eks_mva"] == pytest.approx(BKK["energiledd_dag_eks_mva"], abs=1e-5)
        assert opprinnelse["energiledd_dag_inkl_mva"] == pytest.approx(0.46125, abs=1e-5)

    def test_staar_i_coordinator_data(self, coord_module):
        from tests.conftest import _make_hass, _run_update

        coordinator = coord_module.NettleieCoordinator(_make_hass(), _make_entry())
        data = _run_update(coord_module, coordinator)

        assert data["tarifforigin"]["modus"] == "catalog"


# ===========================================================================
# Terskelen for hva som er et avvik
# ===========================================================================


class TestAvviksterskel:
    """Terskelen skiller v1-migreringens avrundingsstøy fra en ekte endring."""

    def test_avrundingsstoy_er_ikke_avvik(self):
        """Fredriks egen BKK-entry: 0,28774 lagret mot 0,2877 i katalogen.

        Verdien kommer fra v1-migreringen, som regnet 46,13 øre inkl. mva
        tilbake til eks. mva og rundet til fem desimaler. Forskjellen er 0,005
        øre/kWh, usynlig på alle sensorer, og skal ikke vekke noen.
        """
        assert energiledd_avviker({CONF_ENERGILEDD_DAG: 0.28774}, BKK, "standard") is False

    def test_ett_prislistesteg_er_avvik(self):
        """0,01 øre/kWh inkl. mva er minste kvantum på en norsk prisliste."""
        ett_steg = BKK["energiledd_dag_eks_mva"] + 0.0001 / 1.25
        assert energiledd_avviker({CONF_ENERGILEDD_DAG: ett_steg}, BKK, "standard") is True

    def test_ekte_elvia_endring_er_avvik(self):
        """Den minste ekte endringen i dso.py-historikken: 0,2915 -> 0,2899."""
        elvia = DSO_LIST["elvia"]
        assert energiledd_avviker({CONF_ENERGILEDD_DAG: 0.2915}, elvia, "standard") is True

    def test_identisk_sats_er_ikke_avvik(self):
        assert (
            energiledd_avviker(
                {
                    CONF_ENERGILEDD_DAG: BKK["energiledd_dag_eks_mva"],
                    CONF_ENERGILEDD_NATT: BKK["energiledd_natt_eks_mva"],
                },
                BKK,
                "standard",
            )
            is False
        )

    def test_bare_natt_avviker_er_nok(self):
        assert (
            energiledd_avviker(
                {
                    CONF_ENERGILEDD_DAG: BKK["energiledd_dag_eks_mva"],
                    CONF_ENERGILEDD_NATT: BKK["energiledd_natt_eks_mva"] + 0.01,
                },
                BKK,
                "standard",
            )
            is True
        )

    def test_uten_lagret_sats_er_det_ingenting_aa_avvike_fra(self):
        assert energiledd_avviker({}, BKK, "standard") is False

    def test_uleselig_sats_teller_ikke_som_avvik(self):
        """En overstyring som ikke er et tall er ikke en sats brukeren kan velge."""
        assert energiledd_avviker({CONF_ENERGILEDD_DAG: "høy"}, BKK, "standard") is False

    def test_terskelen_ligger_mellom_de_to_tallene(self):
        """Vakt på selve konstanten, ikke bare på bruken av den."""
        stoy = abs(
            compute_energiledd_inkl_mva(0.28774, "standard")
            - compute_energiledd_inkl_mva(BKK["energiledd_dag_eks_mva"], "standard")
        )
        assert stoy < TARIFF_AVVIK_TERSKEL < 0.0001

    def test_mva_fri_sone_bruker_sin_egen_sats(self):
        """Sammenligningen skal skje på tallet brukeren ser, med entryets sone."""
        arva = DSO_LIST["arva"]
        knapt_over = arva["energiledd_dag_eks_mva"] + TARIFF_AVVIK_TERSKEL * 1.1
        assert energiledd_avviker({CONF_ENERGILEDD_DAG: knapt_over}, arva, "tiltakssone") is True


class TestLesTariffmodus:
    def test_ukjent_verdi_faller_til_katalog(self):
        assert les_tariffmodus({"tso": "bkk", CONF_TARIFFMODUS: "noe_annet"}) == "catalog"

    def test_kjent_verdi_beholdes(self):
        assert les_tariffmodus({"tso": "bkk", CONF_TARIFFMODUS: "manual"}) == "manual"


# ===========================================================================
# Repair-varselet
# ===========================================================================


class TestTariffvarselet:
    """Varselet skal komme der satsene spriker, og bare der."""

    def _sjekk(self, init_module, entry):
        mock_ir = _mock_ir()
        with patch.object(init_module, "ir", mock_ir):
            init_module._check_tariffmodus(MagicMock(), entry)
        return mock_ir

    def test_legacy_med_avvik_gir_varsel(self, init_module):
        entry = _make_entry(
            entry_id="abc",
            extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "legacy_unconfirmed"},
        )
        mock_ir = self._sjekk(init_module, entry)

        call = _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc")
        assert call is not None
        assert call.kwargs["is_fixable"] is True
        assert call.kwargs["data"] == {"entry_id": "abc"}
        plassholdere = call.kwargs["translation_placeholders"]
        assert plassholdere["dso"] == BKK["name"]
        # Tallene vises inkl. avgifter og mva, som på fakturaen.
        assert plassholdere["lagret_dag"] == _ore_inkl(0.40)
        assert plassholdere["katalog_dag"] == _ore_inkl(BKK["energiledd_dag_eks_mva"])
        assert plassholdere["lagret_dag"] != plassholdere["katalog_dag"]

    def test_catalog_gir_ikke_varsel(self, init_module):
        """Den som allerede følger prislisten skal ikke merke at modusen finnes."""
        entry = _make_entry(entry_id="abc", extra_data={CONF_TARIFFMODUS: "catalog"})
        mock_ir = self._sjekk(init_module, entry)

        assert _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc") is None
        mock_ir.async_delete_issue.assert_called_once()

    def test_manual_gir_ikke_varsel(self, init_module):
        """Et bevisst valg er alt avklart."""
        entry = _make_entry(
            entry_id="abc",
            extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "manual"},
        )
        mock_ir = self._sjekk(init_module, entry)

        assert _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc") is None

    def test_legacy_uten_avvik_gir_ikke_varsel(self, init_module):
        """Avrundingsstøyen fra v1-migreringen skal ikke vekke noen.

        Dette er den falske positiven som ville truffet rundt to tredjedeler av
        brukerne om terskelen sto på null.
        """
        entry = _make_entry(
            entry_id="abc",
            extra_data={
                CONF_ENERGILEDD_DAG: 0.28774,
                CONF_TARIFFMODUS: "legacy_unconfirmed",
            },
        )
        mock_ir = self._sjekk(init_module, entry)

        assert _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc") is None

    def test_sesong_dso_gir_ikke_varsel(self, init_module):
        """Periodene styrte alt fra før, så tallene endrer seg ikke."""
        entry = _make_entry(
            entry_id="abc",
            dso_id=SESONG_ID,
            extra_data={CONF_ENERGILEDD_DAG: 0.40, CONF_TARIFFMODUS: "legacy_unconfirmed"},
        )
        mock_ir = self._sjekk(init_module, entry)

        assert _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc") is None

    def test_varselet_forsvinner_naar_katalogen_tar_igjen(self, init_module):
        """Sjekken kjøres ved hver oppstart, ikke bare i migreringen.

        Blir dso.py oppdatert til det entryet alt har lagret, er det ingenting
        å velge mellom lenger.
        """
        entry = _make_entry(
            entry_id="abc",
            extra_data={
                CONF_ENERGILEDD_DAG: BKK["energiledd_dag_eks_mva"],
                CONF_ENERGILEDD_NATT: BKK["energiledd_natt_eks_mva"],
                CONF_TARIFFMODUS: "legacy_unconfirmed",
            },
        )
        mock_ir = self._sjekk(init_module, entry)

        assert _reist(mock_ir, f"{TARIFF_ISSUE_PREFIX}abc") is None
        mock_ir.async_delete_issue.assert_called_once()


class TestTariffFixFlow:
    """Begge svarene skal skrive en modus, og begge lukker varselet."""

    def _flow(self, repairs_module, entry):
        flow = repairs_module.TariffmodusRepairFlow(f"{TARIFF_ISSUE_PREFIX}abc", "abc")
        flow.hass = MagicMock()
        flow.hass.config_entries.async_get_entry.return_value = entry
        return flow

    def _entry(self):
        entry = MagicMock()
        entry.entry_id = "abc"
        entry.data = {
            "tso": "bkk",
            CONF_ENERGILEDD_DAG: 0.40,
            CONF_ENERGILEDD_NATT: 0.30,
            CONF_TARIFFMODUS: "legacy_unconfirmed",
        }
        return entry

    def test_menyen_har_begge_valgene(self, repairs_module):
        import asyncio

        flow = self._flow(repairs_module, self._entry())
        resultat = asyncio.run(flow.async_step_init())

        assert resultat["type"] == "menu"
        assert resultat["menu_options"] == ["folg_katalog", "behold_manual"]

    def test_folg_katalog_fjerner_satsen(self, repairs_module):
        import asyncio

        entry = self._entry()
        flow = self._flow(repairs_module, entry)

        asyncio.run(flow.async_step_folg_katalog())

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert data[CONF_TARIFFMODUS] == "catalog"
        assert CONF_ENERGILEDD_DAG not in data
        assert CONF_ENERGILEDD_NATT not in data

    def test_behold_manual_beholder_satsen(self, repairs_module):
        import asyncio

        entry = self._entry()
        flow = self._flow(repairs_module, entry)

        asyncio.run(flow.async_step_behold_manual())

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert data[CONF_TARIFFMODUS] == "manual"
        assert data[CONF_ENERGILEDD_DAG] == 0.40
        assert data[CONF_ENERGILEDD_NATT] == 0.30

    def test_slettet_entry_kaster_ikke(self, repairs_module):
        import asyncio

        flow = self._flow(repairs_module, None)

        asyncio.run(flow.async_step_folg_katalog())

        flow.hass.config_entries.async_update_entry.assert_not_called()

    def test_riktig_flow_velges_av_issue_id(self, repairs_module):
        import asyncio

        flow = asyncio.run(
            repairs_module.async_create_fix_flow(
                MagicMock(), f"{TARIFF_ISSUE_PREFIX}abc", {"entry_id": "abc"}
            )
        )

        assert isinstance(flow, repairs_module.TariffmodusRepairFlow)
