"""Tester for async_migrate_entry (v1→v2→v3→v4 config entry-migrering).

Migrering kjører på alle eksisterende brukere ved oppgradering. Ufanget
exception stopper integrasjonen kald, så denne funksjonen MÅ være dekket.
Se docs/research/test-strategi-vurdering.md (anbefaling 1, P0).

v1 → v2: Energiledd-overrides konverteres fra inkl-mva til eks-mva.
v2 → v3: Setter spotpris_inkl_mva = False og lager repair-issue for Sør-Norge.
v3 → v4: Setter entry unique_id = entry_id (stabil, uavhengig av power-sensor).
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def init_module():
    """Last __init__-modulen på nytt slik at vi får ren state per test."""
    import stromkalkulator.__init__ as init_mod

    importlib.reload(init_mod)
    return init_mod


def _make_entry(
    version: int, data: dict, entry_id: str = "abc123", unique_id: str | None = None
) -> MagicMock:
    """Lag en mock config entry med oppgitt versjon og data.

    Mocker entry slik at hass.config_entries.async_update_entry kan oppdatere
    `.data`, `.version` og `.unique_id` in-place, slik at kjedet migrering
    virker. `unique_id` defaulter til det gamle power-sensor-baserte skjemaet
    for å speile en ekte pre-v4-entry.
    """
    entry = MagicMock()
    entry.version = version
    entry.data = dict(data)
    entry.entry_id = entry_id
    entry.unique_id = unique_id if unique_id is not None else "stromkalkulator_sensor.gammel"
    return entry


def _make_hass(entry: MagicMock) -> MagicMock:
    """HA-mock der async_update_entry oppdaterer entry-felter in-place.

    Det matcher hvordan ekte HA oppfører seg, slik at kjedet v1→v2→v3→v4-
    migrering kan testes uten å hoppe over mellomliggende grener.
    """
    hass = MagicMock()

    def update_entry(target, **kwargs):
        if "data" in kwargs:
            target.data = kwargs["data"]
        if "version" in kwargs:
            target.version = kwargs["version"]
        if "unique_id" in kwargs:
            target.unique_id = kwargs["unique_id"]

    hass.config_entries.async_update_entry = MagicMock(side_effect=update_entry)
    return hass


def _migrate(init_module, hass, entry) -> bool:
    return asyncio.run(init_module.async_migrate_entry(hass, entry))


class TestV1ToV2Migration:
    """v1 → v2: Energiledd-overrides konverteres fra inkl-mva til eks-mva.

    Formel ved v1 (gammel): inkl = (eks + forbruksavgift + Enova) * (1 + mva)
    Migrering: eks = inkl / (1 + mva) - forbruksavgift - Enova
    """

    def test_converts_energiledd_dag_inkl_to_eks(self, init_module):
        """Standard-sone: 0.50 inkl skal bli omtrent 0.3187 eks."""
        # 0.50 / 1.25 - 0.0713 - 0.01 = 0.3187
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": 0.50,
            },
        )
        hass = _make_hass(entry)

        result = _migrate(init_module, hass, entry)

        assert result is True
        assert entry.version == 4  # kjedet helt fram via v2- og v3-grenene
        assert entry.data["energiledd_dag"] == pytest.approx(0.31870, abs=1e-5)

    def test_converts_energiledd_natt_inkl_to_eks(self, init_module):
        """Standard-sone: 0.30 inkl skal bli omtrent 0.15870 eks."""
        # 0.30 / 1.25 - 0.0713 - 0.01 = 0.15870
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_natt": 0.30,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_natt"] == pytest.approx(0.15870, abs=1e-5)

    def test_converts_both_dag_and_natt(self, init_module):
        """Begge energiledd-feltene konverteres samtidig."""
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": 0.50,
                "energiledd_natt": 0.30,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_dag"] == pytest.approx(0.31870, abs=1e-5)
        assert entry.data["energiledd_natt"] == pytest.approx(0.15870, abs=1e-5)

    def test_no_energiledd_overrides_no_change(self, init_module):
        """Brukere uten energiledd-override: ingen energiledd-felt skrives."""
        entry = _make_entry(
            version=1,
            data={"tso": "bkk", "avgiftssone": "standard"},
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert "energiledd_dag" not in entry.data
        assert "energiledd_natt" not in entry.data
        assert entry.version == 4

    def test_nord_norge_no_mva_no_forbruksavgift_reduction(self, init_module):
        """Nord-Norge: mva-fritak, men full forbruksavgift fra 2026."""
        # 0.20 / 1.0 - 0.0713 - 0.01 = 0.1187
        entry = _make_entry(
            version=1,
            data={
                "tso": "noranett",
                "avgiftssone": "nord_norge",
                "energiledd_dag": 0.20,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_dag"] == pytest.approx(0.1187, abs=1e-5)

    def test_tiltakssone_no_forbruksavgift(self, init_module):
        """Tiltakssonen: ingen mva, ingen forbruksavgift, kun Enova trekkes fra."""
        # 0.15 / 1.0 - 0.0 - 0.01 = 0.14
        entry = _make_entry(
            version=1,
            data={
                "tso": "area_nett",
                "avgiftssone": "tiltakssone",
                "energiledd_dag": 0.15,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_dag"] == pytest.approx(0.14, abs=1e-5)

    def test_invalid_string_value_drops_field(self, init_module):
        """Ugyldig verdi (ikke-numerisk streng) skal fjerne overstyringen."""
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": "ikke et tall",
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert "energiledd_dag" not in entry.data

    def test_negative_result_drops_field(self, init_module):
        """Hvis konvertert verdi blir <= 0, fjernes feltet (sannsynlig korrupt)."""
        # 0.05 / 1.25 - 0.0713 - 0.01 = -0.0413 → dropp
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": 0.05,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert "energiledd_dag" not in entry.data

    def test_missing_avgiftssone_resolves_from_dso(self, init_module):
        """Eldre entries uten avgiftssone: skal slå opp fra DSO."""
        # BKK er NO5 (Sør-Norge) → standard. 0.50 / 1.25 - 0.0713 - 0.01 = 0.3187
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "energiledd_dag": 0.50,
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_dag"] == pytest.approx(0.31870, abs=1e-5)

    def test_preserves_other_fields(self, init_module):
        """Ukjente / ekstra felter skal beholdes uendret."""
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "power_sensor": "sensor.power",
                "spot_price_sensor": "sensor.spot",
                "har_norgespris": True,
                "energiledd_dag": 0.50,
                "et_fremmed_felt": "behold meg",
            },
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data["power_sensor"] == "sensor.power"
        assert entry.data["spot_price_sensor"] == "sensor.spot"
        assert entry.data["har_norgespris"] is True
        assert entry.data["et_fremmed_felt"] == "behold meg"


class TestV2ToV3Migration:
    """v2 → v3: Setter spotpris_inkl_mva = False og lager repair-issue for Sør-Norge."""

    def test_sets_spotpris_inkl_mva_false(self, init_module):
        """Alle v2-entries skal få spotpris_inkl_mva = False (incident 004)."""
        entry = _make_entry(
            version=2,
            data={"tso": "bkk", "avgiftssone": "standard"},
        )
        hass = _make_hass(entry)

        result = _migrate(init_module, hass, entry)

        assert result is True
        assert entry.data["spotpris_inkl_mva"] is False
        assert entry.version == 4

    def test_standard_avgiftssone_creates_repair_issue(self, init_module):
        """Sør-Norge (standard) skal få repair-issue om mva-sjekk."""
        entry = _make_entry(
            version=2,
            data={"tso": "bkk", "avgiftssone": "standard"},
            entry_id="entry_sor",
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"
        init_module.ir = mock_ir

        _migrate(init_module, hass, entry)

        mock_ir.async_create_issue.assert_called_once()
        # Issue-id inneholder entry_id for unik identifikasjon
        call_args = mock_ir.async_create_issue.call_args
        assert "entry_sor" in str(call_args)

    def test_nord_norge_no_repair_issue(self, init_module):
        """Nord-Norge får ikke repair-issue (mva utgjør ingen forskjell)."""
        entry = _make_entry(
            version=2,
            data={"tso": "noranett", "avgiftssone": "nord_norge"},
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        init_module.ir = mock_ir

        _migrate(init_module, hass, entry)

        mock_ir.async_create_issue.assert_not_called()
        assert entry.data["spotpris_inkl_mva"] is False

    def test_tiltakssone_no_repair_issue(self, init_module):
        """Tiltakssonen får ikke repair-issue (mva-fritak)."""
        entry = _make_entry(
            version=2,
            data={"tso": "area_nett", "avgiftssone": "tiltakssone"},
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        init_module.ir = mock_ir

        _migrate(init_module, hass, entry)

        mock_ir.async_create_issue.assert_not_called()

    def test_missing_avgiftssone_treated_as_standard(self, init_module):
        """Manglende avgiftssone: defaulter til standard og trigger repair-issue."""
        entry = _make_entry(
            version=2,
            data={"tso": "bkk"},
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"
        init_module.ir = mock_ir

        _migrate(init_module, hass, entry)

        mock_ir.async_create_issue.assert_called_once()

    def test_preserves_other_fields(self, init_module):
        """Eksisterende felter skal ikke tukles med."""
        entry = _make_entry(
            version=2,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": 0.31870,
                "har_norgespris": True,
                "power_sensor": "sensor.power",
            },
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"
        init_module.ir = mock_ir

        _migrate(init_module, hass, entry)

        assert entry.data["energiledd_dag"] == 0.31870
        assert entry.data["har_norgespris"] is True
        assert entry.data["power_sensor"] == "sensor.power"


class TestV3ToV4Migration:
    """v3 → v4: unique_id settes til entry_id (stabil, uavhengig av power-sensor)."""

    def test_sets_unique_id_to_entry_id(self, init_module):
        """En v3-entry skal få unique_id = entry_id og bumpes til v4."""
        entry = _make_entry(
            version=3,
            data={"tso": "bkk", "avgiftssone": "standard", "spotpris_inkl_mva": False},
            entry_id="entry_v3",
            unique_id="stromkalkulator_sensor.gammel_power",
        )
        hass = _make_hass(entry)

        result = _migrate(init_module, hass, entry)

        assert result is True
        assert entry.version == 4
        assert entry.unique_id == "entry_v3"

    def test_preserves_data(self, init_module):
        """v3→v4 rører ikke entry.data (bare unique_id og versjon)."""
        original = {
            "tso": "bkk",
            "avgiftssone": "standard",
            "spotpris_inkl_mva": False,
            "power_sensor": "sensor.x",
            "energiledd_dag": 0.31870,
        }
        entry = _make_entry(version=3, data=dict(original), entry_id="e1")
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert entry.data == original


class TestChainedMigration:
    """v1 → v4 i én operasjon (kjedet)."""

    def test_v1_to_v4_full_chain(self, init_module):
        """v1-entry skal migreres helt fram til v4 i én call."""
        entry = _make_entry(
            version=1,
            data={
                "tso": "bkk",
                "avgiftssone": "standard",
                "energiledd_dag": 0.50,
            },
            entry_id="entry_chain",
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"
        init_module.ir = mock_ir

        result = _migrate(init_module, hass, entry)

        assert result is True
        assert entry.version == 4
        # v1→v2: energiledd konvertert
        assert entry.data["energiledd_dag"] == pytest.approx(0.31870, abs=1e-5)
        # v2→v3: spotpris-flag satt og repair-issue laget
        assert entry.data["spotpris_inkl_mva"] is False
        mock_ir.async_create_issue.assert_called_once()
        # v3→v4: unique_id byttet til entry_id
        assert entry.unique_id == "entry_chain"

    def test_v1_to_v4_calls_update_thrice(self, init_module):
        """v1→v4 skal kalle async_update_entry én gang per versjons-bump."""
        entry = _make_entry(
            version=1,
            data={"tso": "bkk", "avgiftssone": "standard"},
        )
        hass = _make_hass(entry)

        _migrate(init_module, hass, entry)

        assert hass.config_entries.async_update_entry.call_count == 3


class TestIdempotency:
    """v4 → v4 skal være no-op."""

    def test_v4_returns_true_without_changes(self, init_module):
        """Allerede migrert entry skal returnere True uten å røre data."""
        original_data = {
            "tso": "bkk",
            "avgiftssone": "standard",
            "spotpris_inkl_mva": False,
            "energiledd_dag": 0.31870,
        }
        entry = _make_entry(
            version=4, data=original_data, entry_id="entry1", unique_id="entry1"
        )
        hass = _make_hass(entry)

        mock_ir = MagicMock()
        init_module.ir = mock_ir

        result = _migrate(init_module, hass, entry)

        assert result is True
        assert entry.data == original_data
        assert entry.version == 4
        hass.config_entries.async_update_entry.assert_not_called()
        mock_ir.async_create_issue.assert_not_called()

    def test_future_version_returns_false_downgrade_protection(self, init_module):
        """Hypotetisk v5-entry (fra nedgradering) skal avvises, ikke lastes.

        HA-konvensjon: returner False når entry.version er høyere enn koden
        støtter, så en nedgradert installasjon ikke laster et ukjent skjema.
        """
        entry = _make_entry(version=5, data={"tso": "bkk"})
        hass = _make_hass(entry)

        result = _migrate(init_module, hass, entry)

        assert result is False
        assert entry.version == 5
        hass.config_entries.async_update_entry.assert_not_called()
