"""Tester for _compute_energy_delta (fix B: tpi-delta-akkumulasjon).

Dekker kjernen i energy_sensor-pathen som erstatter Riemann-sum av p-sensor.
Fanger regresjoner av counter-reset, outlier-clamp, unavailable-håndtering
og baseline-første-poll.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry, _make_state


def _hass_with_energy(value):
    """Hass-mock der sensor.energy returnerer ``value`` (tall, streng eller None)."""
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id != "sensor.energy" or value is None:
            return None
        if isinstance(value, str):
            state = MagicMock()
            state.state = value
            return state
        return _make_state(value)

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


@pytest.fixture
def coordinator_with_energy_sensor(coord_module):
    """Coordinator med energy_sensor konfigurert og _last_tpi_kwh = None."""
    hass = _hass_with_energy(0.0)
    entry = _make_entry(energy_sensor="sensor.energy")
    return coord_module.NettleieCoordinator(hass, entry)


class TestComputeEnergyDelta:
    """Direkte-test av _compute_energy_delta-metoden."""

    def test_first_poll_returns_zero_and_seeds_baseline(self, coordinator_with_energy_sensor):
        """Første poll (None): returner 0, sett baseline."""
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.0)
        assert coordinator_with_energy_sensor._last_tpi_kwh is None

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_normal_delta_returns_diff(self, coordinator_with_energy_sensor):
        """Normal voksende tpi: returner diff, oppdater state."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.5)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == pytest.approx(0.5)
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.5

    def test_counter_reset_returns_zero_resyncs_baseline(self, coordinator_with_energy_sensor):
        """Negativ delta (meter-bytte): returner 0, oppdater til ny verdi."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(0.5)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        # resync slik at neste poll måler fra ny baseline
        assert coordinator_with_energy_sensor._last_tpi_kwh == 0.5

    def test_outlier_over_max_returns_zero(self, coordinator_with_energy_sensor):
        """Delta > MAX_ENERGY_DELTA_KWH (100 kWh): returner 0, resync baseline."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(1101.0)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        # _last_tpi_kwh oppdateres uansett (linje 353) — neste poll får riktig baseline
        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1101.0

    def test_outlier_boundary_at_max(self, coord_module):
        """Delta == 100 kWh: koden bruker ``0 < raw_delta < MAX`` (strikt) → outlier."""
        from custom_components.stromkalkulator.const import MAX_ENERGY_DELTA_KWH

        hass = _hass_with_energy(1000.0 + MAX_ENERGY_DELTA_KWH)
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._last_tpi_kwh = 1000.0

        assert coordinator._compute_energy_delta() == 0.0

    def test_outlier_just_below_max_is_accepted(self, coord_module):
        """Delta like under grensen (99.999 kWh): teller som gyldig forbruk."""
        from custom_components.stromkalkulator.const import MAX_ENERGY_DELTA_KWH

        nearly_max = MAX_ENERGY_DELTA_KWH - 0.001
        hass = _hass_with_energy(1000.0 + nearly_max)
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._last_tpi_kwh = 1000.0

        delta = coordinator._compute_energy_delta()

        assert delta == pytest.approx(nearly_max)

    def test_unavailable_returns_zero_preserves_last_tpi(self, coordinator_with_energy_sensor):
        """Sensor unavailable: returner 0, IKKE rør _last_tpi_kwh."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy("unavailable")

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_unknown_returns_zero_preserves_last_tpi(self, coordinator_with_energy_sensor):
        """Sensor unknown: samme oppførsel som unavailable."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy("unknown")

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_nan_returns_zero(self, coordinator_with_energy_sensor):
        """float('nan'): math.isfinite-sjekken filtrerer bort, returner 0."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(float("nan"))

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        # NaN er ikke gyldig, _last_tpi_kwh skal beholdes
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_inf_returns_zero(self, coordinator_with_energy_sensor):
        """float('inf'): math.isfinite-sjekken filtrerer bort, returner 0."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(float("inf"))

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_garbage_string_returns_zero(self, coordinator_with_energy_sensor):
        """Sensor-state som ikke kan parses som float: returner 0 uten å rote baseline."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy("søppel")

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_negative_current_value_returns_zero(self, coordinator_with_energy_sensor):
        """current < 0 (sensor-feil): returner 0, behold gammel baseline."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(-1.0)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        # Linje 331 returnerer før _last_tpi_kwh oppdateres
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_zero_current_treated_as_invalid(self, coordinator_with_energy_sensor):
        """current == 0: behandles som ugyldig (linje 331: ``current_tpi <= 0``)."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(0.0)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        # Baseline beholdes; 0 regnes ikke som gyldig sample
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_baseline_zero_then_real_value_reseeds(self, coordinator_with_energy_sensor):
        """Baseline 0 fra storage behandles som "ikke seedet" (linje 335: ``> 0``).

        Med last = 0 og current = 1000 skal vi IKKE rapportere 1000 kWh forbruk
        i én poll — vi setter heller ny baseline og returnerer 0.
        """
        coordinator_with_energy_sensor._last_tpi_kwh = 0.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.0)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0

    def test_no_energy_sensor_returns_zero(self, coord_module):
        """Uten energy_sensor konfigurert: tidlig return 0, ingen state-oppslag."""
        hass = _hass_with_energy(1234.5)
        entry = _make_entry(energy_sensor=None)
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._last_tpi_kwh = 500.0

        delta = coordinator._compute_energy_delta()

        assert delta == 0.0
        # Baseline urørt — vi traff aldri linjen som setter den
        assert coordinator._last_tpi_kwh == 500.0

    def test_state_not_in_registry_returns_zero(self, coord_module):
        """hass.states.get returnerer None (sensor ikke registrert ennå)."""
        hass = _hass_with_energy(None)
        entry = _make_entry(energy_sensor="sensor.energy")
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._last_tpi_kwh = 1000.0

        delta = coordinator._compute_energy_delta()

        assert delta == 0.0
        assert coordinator._last_tpi_kwh == 1000.0

    def test_repeated_polls_accumulate_via_baseline(self, coordinator_with_energy_sensor):
        """To påfølgende delta-poll over samme baseline gir kumulativ forbruk."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0

        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.4)
        first = coordinator_with_energy_sensor._compute_energy_delta()

        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.9)
        second = coordinator_with_energy_sensor._compute_energy_delta()

        assert first == pytest.approx(0.4)
        assert second == pytest.approx(0.5)
        assert coordinator_with_energy_sensor._last_tpi_kwh == pytest.approx(1000.9)

    def test_flat_meter_returns_zero(self, coordinator_with_energy_sensor):
        """Identisk verdi som forrige poll (ingen forbruk): delta = 0."""
        coordinator_with_energy_sensor._last_tpi_kwh = 1000.0
        coordinator_with_energy_sensor.hass = _hass_with_energy(1000.0)

        delta = coordinator_with_energy_sensor._compute_energy_delta()

        # raw_delta == 0 faller utenfor ``0 < raw_delta < MAX``, så delta = 0
        assert delta == 0.0
        assert coordinator_with_energy_sensor._last_tpi_kwh == 1000.0
