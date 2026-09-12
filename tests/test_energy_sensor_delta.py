"""Tester for `_compute_energy_delta`: delta fra den kumulative energisensoren.

Dekker kjernen i energy_sensor-stien som erstatter Riemann-summen av
effektsensoren, og etter kontrakten i `docs/kontrakter/input-og-konfig.md` §5
også at baselinen er bundet til kilden sin. Uten den bindingen ble et
målerbytte til falskt forbruk: en ny teller som sto på 1020 der den gamle sto
på 1000 ga 20 kWh som aldri var brukt.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry, _make_state

NAA = datetime(2026, 6, 15, 12, 0)


def _hass_with_energy(value, *, unit=None, state_class="total_increasing", unique_id="maaler-1"):
    """Hass-mock der sensor.energy returnerer ``value``.

    `unique_id` er kildeidentiteten baselinen bindes til. Å bytte den er det
    samme som å bytte fysisk måler.
    """
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id != "sensor.energy" or value is None:
            return None
        if isinstance(value, str) and value in ("unavailable", "unknown", "søppel"):
            state = MagicMock()
            state.state = value
            state.attributes = {"state_class": state_class}
            state.last_updated = None
            return state
        return _make_state(value, unit=unit, state_class=state_class)

    hass.states.get = MagicMock(side_effect=get_state)
    register = MagicMock()
    register.async_get = MagicMock(return_value=MagicMock(unique_id=unique_id))
    hass._entity_register = register
    return hass


@pytest.fixture(autouse=True)
def _patch_entity_registry(coord_module):
    """La kildeidentiteten komme fra hass-mockens eget register."""
    import stromkalkulator.inputadapter as adapter

    adapter.er = MagicMock()
    adapter.er.async_get = MagicMock(side_effect=lambda hass: hass._entity_register)
    return adapter


def _delta(coord):
    """Én full runde: les inputene, så regn deltaet, som i en ekte poll."""
    coord._les_inputer(NAA)
    return coord._compute_energy_delta(NAA)


def _sett_baseline(coord, kwh, *, unique_id="maaler-1", entity_id="sensor.energy"):
    from stromkalkulator.inputadapter import Baseline

    coord._baseline = Baseline(unique_id, entity_id, kwh, NAA)


def _baseline_kwh(coord):
    return coord._baseline.value_kwh if coord._baseline else None


@pytest.fixture
def coordinator_with_energy_sensor(coord_module):
    """Coordinator med energy_sensor konfigurert og uten baseline."""
    hass = _hass_with_energy(0.0)
    entry = _make_entry(energy_sensor="sensor.energy")
    return coord_module.NettleieCoordinator(hass, entry)


class TestComputeEnergyDelta:
    """Direkte-test av `_compute_energy_delta`."""

    def test_first_poll_returns_zero_and_seeds_baseline(self, coordinator_with_energy_sensor):
        """Første poll uten baseline: returner 0, sett baseline."""
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.0)
        assert coordinator_with_energy_sensor._baseline is None

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_normal_delta_returns_diff(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.5)

        assert _delta(coordinator_with_energy_sensor) == pytest.approx(0.5)
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.5

    def test_counter_reset_returns_zero_resyncs_baseline(self, coordinator_with_energy_sensor):
        """Negativt delta: returner 0, flytt baselinen til den nye standen."""
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(0.5)

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 0.5

    def test_outlier_over_max_returns_zero(self, coordinator_with_energy_sensor):
        """Delta over MAX_ENERGY_DELTA_KWH forkastes, men baselinen flyttes."""
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(1101.0)

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1101.0

    def test_outlier_boundary_at_max(self, coord_module):
        """Delta lik 100 kWh: `0 < raw_delta < MAX` er strikt, så det er outlier."""
        from custom_components.stromkalkulator.const import MAX_ENERGY_DELTA_KWH

        hass = _hass_with_energy(1000.0 + MAX_ENERGY_DELTA_KWH)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0)

        assert _delta(coordinator) == 0.0

    def test_outlier_just_below_max_is_accepted(self, coord_module):
        from custom_components.stromkalkulator.const import MAX_ENERGY_DELTA_KWH

        nearly_max = MAX_ENERGY_DELTA_KWH - 0.001
        hass = _hass_with_energy(1000.0 + nearly_max)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0)

        assert _delta(coordinator) == pytest.approx(nearly_max)

    def test_unavailable_returns_zero_preserves_baseline(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy("unavailable")

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_unknown_returns_zero_preserves_baseline(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy("unknown")

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_nan_returns_zero(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(float("nan"))

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_inf_returns_zero(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(float("inf"))

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_garbage_string_returns_zero(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy("søppel")

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_negative_current_value_returns_zero(self, coordinator_with_energy_sensor):
        """En negativ teller er sensorfeil: behold den gamle baselinen."""
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(-1.0)

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_zero_current_treated_as_invalid(self, coordinator_with_energy_sensor):
        """0 duger ikke som baseline: det er like gjerne en blank oppstartsverdi."""
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(0.0)

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0

    def test_no_energy_sensor_returns_zero(self, coord_module):
        """Uten energy_sensor konfigurert: ingen delta, baselinen urørt."""
        hass = _hass_with_energy(1234.5)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor=None))
        _sett_baseline(coordinator, 500.0)

        assert _delta(coordinator) == 0.0
        assert _baseline_kwh(coordinator) == 500.0

    def test_state_not_in_registry_returns_zero(self, coord_module):
        """Entiteten finnes ikke: ingen måling, og baselinen røres ikke."""
        hass = _hass_with_energy(None)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0)

        assert _delta(coordinator) == 0.0
        assert _baseline_kwh(coordinator) == 1000.0

    def test_repeated_polls_accumulate_via_baseline(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)

        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.4)
        first = _delta(coordinator_with_energy_sensor)

        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.9)
        second = _delta(coordinator_with_energy_sensor)

        assert first == pytest.approx(0.4)
        assert second == pytest.approx(0.5)
        assert _baseline_kwh(coordinator_with_energy_sensor) == pytest.approx(1000.9)

    def test_flat_meter_returns_zero(self, coordinator_with_energy_sensor):
        _sett_baseline(coordinator_with_energy_sensor, 1000.0)
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.0)

        assert _delta(coordinator_with_energy_sensor) == 0.0
        assert _baseline_kwh(coordinator_with_energy_sensor) == 1000.0


class TestEnhetsnormalisering:
    """Energisensoren kan komme i Wh, kWh eller MWh, og alt skal bli kWh."""

    @pytest.mark.parametrize(
        ("verdi", "enhet", "forventet_baseline"),
        [
            (1000.0, "kWh", 1000.0),
            (1_000_000.0, "Wh", 1000.0),
            (1.0, "MWh", 1000.0),
        ],
    )
    def test_baselinen_lagres_i_kwh(self, coord_module, verdi, enhet, forventet_baseline):
        hass = _hass_with_energy(verdi, unit=enhet)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))

        _delta(coordinator)

        assert _baseline_kwh(coordinator) == pytest.approx(forventet_baseline)

    def test_wh_sensor_gir_riktig_delta(self, coord_module):
        """Tusen-gangen: en Wh-sensor lest som kWh ga tusen ganger for mye."""
        hass = _hass_with_energy(1_000_000.0, unit="Wh")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _delta(coordinator)

        coordinator.hass = _hass_with_energy(1_000_500.0, unit="Wh")
        assert _delta(coordinator) == pytest.approx(0.5)

    def test_sensor_uten_kumulativ_state_class_gir_ingen_delta(self, coord_module):
        """En øyeblikksverdi har ingen differanse å måle."""
        hass = _hass_with_energy(1000.0, unit="kWh", state_class="measurement")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 900.0)

        assert _delta(coordinator) == 0.0
        assert _baseline_kwh(coordinator) == 900.0


class TestKildebundetBaseline:
    """§5: baselinen hører til én fysisk måler.

    Dette er feilen fra stromkalkulator-40mbs7k: persistens lagret siste kWh
    uten sensor-id, så forskjellen mot den gamle måleren ble tolket som forbruk.
    """

    def test_ny_kilde_gir_delta_null(self, coord_module):
        """Repro-en fra issuet: 1000 til 1020 skal gi 0 kWh, ikke 20."""
        hass = _hass_with_energy(1020.0, unique_id="maaler-2")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0, unique_id="maaler-1")

        assert _delta(coordinator) == 0.0
        assert _baseline_kwh(coordinator) == 1020.0
        assert coordinator._baseline.source_identity == "maaler-2"

    def test_ny_kilde_rorer_ikke_maanedsdata(self, coord_module):
        hass = _hass_with_energy(1020.0, unique_id="maaler-2")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0, unique_id="maaler-1")
        coordinator._monthly_consumption.dag = 123.4
        coordinator._monthly_consumption.natt = 56.7

        _delta(coordinator)

        assert coordinator._monthly_consumption.dag == 123.4
        assert coordinator._monthly_consumption.natt == 56.7

    def test_samme_kilde_gjenopptar(self, coord_module):
        """Motsatt retning: samme måler etter omstart skal måle videre."""
        hass = _hass_with_energy(1020.0, unique_id="maaler-1")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0, unique_id="maaler-1")

        assert _delta(coordinator) == pytest.approx(20.0)

    def test_uten_unique_id_faller_sammenligningen_tilbake_pa_entity_id(self, coord_module):
        """Uten registeroppføring er entity-id-en det eneste vi har."""
        hass = _hass_with_energy(1020.0, unique_id=None)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0, unique_id=None, entity_id="sensor.energy")

        assert _delta(coordinator) == pytest.approx(20.0)

    def test_uten_unique_id_og_annen_entity_id_er_ny_kilde(self, coord_module):
        hass = _hass_with_energy(1020.0, unique_id=None)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry(energy_sensor="sensor.energy"))
        _sett_baseline(coordinator, 1000.0, unique_id=None, entity_id="sensor.gammel_maaler")

        assert _delta(coordinator) == 0.0
