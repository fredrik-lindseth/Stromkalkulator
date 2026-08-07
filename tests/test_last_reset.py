"""Tester for last_reset på TOTAL-sensorer som nullstilles ved periodeskifte.

Uten last_reset bokfører HA-statistikken fallet fra periodesum til 0 som et
negativt delta, så første time i ny måned viser hele forrige månedssum med
minus i Energy-dashboardet (issue #14). Testene her sjekker at periodestarten
følger med i samme coordinator-oppdatering som nullstillingen.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import _make_entry, _make_hass, _run_update

_real_datetime = datetime

OSLO = ZoneInfo("Europe/Oslo")


@pytest.fixture
def lokal_midnatt():
    """Gi sensor-modulens mockede dt_util en ekte start_of_local_day."""
    with patch("stromkalkulator.sensor.dt_util") as mock_dt:
        mock_dt.start_of_local_day.side_effect = lambda d: datetime.combine(
            d.date(), time(), tzinfo=OSLO
        )
        yield mock_dt


def _make_coordinator(data: dict) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    return coord


def _kjor_maanedsskifte(coord_module):
    """Kjør en ekte coordinator over månedsskiftet juni -> juli 2026.

    Returnerer (juni_data, juli_data): de to dictene sensorene ser før og
    etter rollover.
    """
    c = coord_module.NettleieCoordinator(_make_hass(power_w=5000, spot_price=1.20), _make_entry())
    t0 = _real_datetime(2026, 6, 30, 23, 58)
    _run_update(coord_module, c, t0)
    juni_data = _run_update(coord_module, c, t0 + timedelta(minutes=1))
    juli_data = _run_update(coord_module, c, _real_datetime(2026, 7, 1, 0, 1))
    return juni_data, juli_data


class TestMaanedsskifte:
    """Månedssensorene flytter last_reset i samme oppdatering som nullstillingen."""

    def test_akkumulert_kostnad_nullstilles_og_flytter_last_reset(
        self, coord_module, lokal_midnatt
    ):
        """Verdien faller til 0 og last_reset flytter til 1. juli i samme data-dict."""
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        juni_data, juli_data = _kjor_maanedsskifte(coord_module)

        coord = _make_coordinator(juni_data)
        sensor = AkkumulertKostnadSensor(coord, _make_entry())
        assert sensor.native_value > 0
        assert sensor.last_reset == datetime(2026, 6, 1, tzinfo=OSLO)

        coord.data = juli_data
        assert sensor.native_value == 0.0
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)

    def test_alle_maanedssensorer_flytter_last_reset(self, coord_module, lokal_midnatt):
        """Hver månedssensor med state_class TOTAL rapporterer månedsstart."""
        from stromkalkulator.sensor import (
            AkkumulertKostnadSensor,
            MaanedligAvgifterSensor,
            MaanedligEksportInntektSensor,
            MaanedligNettleieSensor,
            MaanedligNettokostnadSensor,
            MaanedligNorgesprisDifferanseSensor,
            MaanedligNorgesprisKompensasjonSensor,
            MaanedligStromstotteSensor,
            MaanedligTotalSensor,
        )

        juni_data, juli_data = _kjor_maanedsskifte(coord_module)
        coord = _make_coordinator(juni_data)
        entry = _make_entry()

        sensorer = [
            klasse(coord, entry)
            for klasse in (
                MaanedligNettleieSensor,
                MaanedligAvgifterSensor,
                MaanedligStromstotteSensor,
                MaanedligTotalSensor,
                MaanedligNorgesprisDifferanseSensor,
                MaanedligNorgesprisKompensasjonSensor,
                AkkumulertKostnadSensor,
                MaanedligEksportInntektSensor,
                MaanedligNettokostnadSensor,
            )
        ]

        for sensor in sensorer:
            assert sensor.last_reset == datetime(2026, 6, 1, tzinfo=OSLO), sensor.__class__.__name__

        coord.data = juli_data
        for sensor in sensorer:
            assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO), sensor.__class__.__name__

    def test_maanedlig_total_nullstilles_med_ny_last_reset(self, coord_module, lokal_midnatt):
        """Månedsforbruket nullstilles, så MaanedligTotal faller sammen med last_reset."""
        from stromkalkulator.sensor import MaanedligTotalSensor

        c = coord_module.NettleieCoordinator(
            _make_hass(power_w=5000, spot_price=1.20), _make_entry()
        )
        c._monthly_consumption = coord_module.ConsumptionData(dag=500.0, natt=200.0)

        juni_data = _run_update(coord_module, c, _real_datetime(2026, 6, 30, 23, 58))
        coord = _make_coordinator(juni_data)
        sensor = MaanedligTotalSensor(coord, _make_entry())
        juni_verdi = sensor.native_value
        assert juni_verdi > 200
        assert sensor.last_reset == datetime(2026, 6, 1, tzinfo=OSLO)

        coord.data = _run_update(coord_module, c, _real_datetime(2026, 7, 1, 0, 1))
        assert sensor.native_value < juni_verdi
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)


class TestDognskifte:
    """Dagskostnaden bruker døgnstart, ikke månedsstart."""

    def test_dagskostnad_flytter_last_reset_ved_midnatt(self, coord_module, lokal_midnatt):
        """Verdien faller og last_reset flytter til det nye døgnet."""
        from stromkalkulator.sensor import DagskostnadSensor

        c = coord_module.NettleieCoordinator(
            _make_hass(power_w=5000, spot_price=1.20), _make_entry()
        )

        # Bygg opp en times dagskostnad i 5-minutters steg.
        start = _real_datetime(2026, 6, 15, 23, 0)
        data = _run_update(coord_module, c, start)
        for i in range(1, 12):
            data = _run_update(coord_module, c, start + timedelta(minutes=i * 5))

        coord = _make_coordinator(data)
        sensor = DagskostnadSensor(coord, _make_entry())
        forrige_verdi = sensor.native_value
        assert forrige_verdi > 0
        assert sensor.last_reset == datetime(2026, 6, 15, tzinfo=OSLO)

        # Kryss midnatt: dagskostnaden nullstilles før ny akkumulering.
        coord.data = _run_update(coord_module, c, _real_datetime(2026, 6, 16, 0, 1))
        assert sensor.native_value < forrige_verdi
        assert sensor.last_reset == datetime(2026, 6, 16, tzinfo=OSLO)


class TestPeriodestart:
    """Utleding av periodestart fra coordinator-merkelappene."""

    def test_maanedsstart_er_lokal_midnatt(self, lokal_midnatt):
        """"2026-07" gir 1. juli kl. 00:00 lokal tid."""
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        sensor = AkkumulertKostnadSensor(
            _make_coordinator({"current_month": "2026-07"}), _make_entry()
        )
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)

    def test_dognstart_er_lokal_midnatt(self, lokal_midnatt):
        """"2026-07-15" gir 15. juli kl. 00:00 lokal tid."""
        from stromkalkulator.sensor import DagskostnadSensor

        sensor = DagskostnadSensor(
            _make_coordinator({"current_date": "2026-07-15"}), _make_entry()
        )
        assert sensor.last_reset == datetime(2026, 7, 15, tzinfo=OSLO)

    @pytest.mark.parametrize("data", [None, {}, {"current_month": "tull"}, {"current_month": 7}])
    def test_manglende_eller_ugyldig_merkelapp_gir_none(self, data, lokal_midnatt):
        """Sensoren publiserer verdien sin selv om periodemerkelappen er ubrukelig."""
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        sensor = AkkumulertKostnadSensor(_make_coordinator(data), _make_entry())
        assert sensor.last_reset is None

    def test_sensorer_uten_periodenullstilling_har_ingen_last_reset(self, lokal_midnatt):
        """MEASUREMENT- og TOTAL_INCREASING-sensorer skal ikke ha last_reset."""
        from stromkalkulator.sensor import MaanedligForbrukTotalSensor, TotalPriceSensor

        data = {"current_month": "2026-07", "current_date": "2026-07-15"}
        coord = _make_coordinator(data)
        entry = _make_entry()

        assert MaanedligForbrukTotalSensor(coord, entry).last_reset is None
        assert TotalPriceSensor(coord, entry).last_reset is None


class TestCoordinatorKontrakt:
    """Coordinatoren leverer periodemerkelappene sensorene trenger."""

    def test_data_inneholder_periodemerkelapper(self, coord_module):
        """current_month og current_date følger hver oppdatering."""
        c = coord_module.NettleieCoordinator(
            _make_hass(power_w=5000, spot_price=1.20), _make_entry()
        )
        data = _run_update(coord_module, c, _real_datetime(2026, 6, 15, 12, 0))

        assert data["current_month"] == "2026-06"
        assert data["current_date"] == "2026-06-15"
