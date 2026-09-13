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
        mock_dt.start_of_local_day.side_effect = lambda d: datetime.combine(d.date(), time(), tzinfo=OSLO)
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

    def test_akkumulert_kostnad_nullstilles_og_flytter_last_reset(self, coord_module, lokal_midnatt):
        """Verdien faller til julis eget minutt og last_reset flytter i samme data-dict.

        Ikke helt til null: rulleringen skjer nå før nåtidssnapshotet bygges
        (2ferkiq), så juli-dicten viser juli, og det første minuttet av juli har
        både forbruk og sin andel av fastleddet. Poenget for last_reset er det
        samme: tallet er en ny måneds tall, ikke junis.
        """
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        juni_data, juli_data = _kjor_maanedsskifte(coord_module)

        coord = _make_coordinator(juni_data)
        sensor = AkkumulertKostnadSensor(coord, _make_entry())
        assert sensor.native_value > 0
        assert sensor.last_reset == datetime(2026, 6, 1, tzinfo=OSLO)

        juni_verdi = sensor.native_value
        coord.data = juli_data
        assert 0 < sensor.native_value < juni_verdi / 100
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

        c = coord_module.NettleieCoordinator(_make_hass(power_w=5000, spot_price=1.20), _make_entry())
        c._monthly_consumption = coord_module.ConsumptionData(dag=500.0, natt=200.0)

        juni_data = _run_update(coord_module, c, _real_datetime(2026, 6, 30, 23, 58))
        coord = _make_coordinator(juni_data)
        sensor = MaanedligTotalSensor(coord, _make_entry())
        juni_verdi = sensor.native_value
        # Forbruket er satt rett på akkumulatoren uten at noe er bokført, så
        # kronene her er nesten bare fastleddet for juni. Poenget er at det er
        # et junitall som faller når juli begynner.
        assert juni_verdi > 100
        assert sensor.last_reset == datetime(2026, 6, 1, tzinfo=OSLO)

        coord.data = _run_update(coord_module, c, _real_datetime(2026, 7, 1, 0, 1))
        assert sensor.native_value < juni_verdi
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)


class TestDognskifte:
    """Dagskostnaden bruker døgnstart, ikke månedsstart."""

    def test_dagskostnad_flytter_last_reset_ved_midnatt(self, coord_module, lokal_midnatt):
        """Verdien faller og last_reset flytter til det nye døgnet."""
        from stromkalkulator.sensor import DagskostnadSensor

        c = coord_module.NettleieCoordinator(_make_hass(power_w=5000, spot_price=1.20), _make_entry())

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
        """ "2026-07" gir 1. juli kl. 00:00 lokal tid."""
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        sensor = AkkumulertKostnadSensor(_make_coordinator({"current_month": "2026-07"}), _make_entry())
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)

    def test_dognstart_er_lokal_midnatt(self, lokal_midnatt):
        """ "2026-07-15" gir 15. juli kl. 00:00 lokal tid."""
        from stromkalkulator.sensor import DagskostnadSensor

        sensor = DagskostnadSensor(_make_coordinator({"current_date": "2026-07-15"}), _make_entry())
        assert sensor.last_reset == datetime(2026, 7, 15, tzinfo=OSLO)

    @pytest.mark.parametrize("data", [None, {}, {"current_month": "tull"}, {"current_month": 7}])
    def test_manglende_eller_ugyldig_merkelapp_gir_none(self, data, lokal_midnatt):
        """Sensoren publiserer verdien sin selv om periodemerkelappen er ubrukelig."""
        from stromkalkulator.sensor import AkkumulertKostnadSensor

        sensor = AkkumulertKostnadSensor(_make_coordinator(data), _make_entry())
        assert sensor.last_reset is None

    def test_sensorer_uten_periodenullstilling_har_ingen_last_reset(self, lokal_midnatt):
        """MEASUREMENT- og TOTAL_INCREASING-sensorer skal ikke ha last_reset."""
        from stromkalkulator.sensor import (
            ForrigeMaanedToppforbrukSensor,
            MaanedligForbrukTotalSensor,
            TotalPriceSensor,
        )

        data = {"current_month": "2026-07", "current_date": "2026-07-15"}
        coord = _make_coordinator(data)
        entry = _make_entry()

        assert MaanedligForbrukTotalSensor(coord, entry).last_reset is None
        assert TotalPriceSensor(coord, entry).last_reset is None
        # Toppforbruket er MEASUREMENT og arver ikke gruppens last_reset.
        assert ForrigeMaanedToppforbrukSensor(coord, entry).last_reset is None


class TestForrigeMaanedSnapshot:
    """Snapshotet av en avsluttet måned byttes ved månedsskiftet (4qba).

    For statistikk-kompilatoren er byttet en nullstilling: uten last_reset
    bokføres forskjellen mellom to måneders snapshot som et delta, og en måned
    som var lavere enn forrige gir et negativt delta i Energy-dashboardet.
    """

    FORRIGE_MAANED_TOTAL = (
        "ForrigeMaanedForbrukDagSensor",
        "ForrigeMaanedForbrukNattSensor",
        "ForrigeMaanedForbrukTotalSensor",
        "ForrigeMaanedNettleieSensor",
        "ForrigeMaanedNorgesprisKompensasjonSensor",
        "ForrigeMaanedEksportKwhSensor",
        "ForrigeMaanedEksportInntektSensor",
    )

    @pytest.mark.parametrize("navn", FORRIGE_MAANED_TOTAL)
    def test_last_reset_er_inneverende_maanedsstart(self, navn, lokal_midnatt):
        """Snapshotet ble byttet da denne måneden begynte, og det er svaret."""
        import stromkalkulator.sensor as sensor_mod

        coord = _make_coordinator({"current_month": "2026-07", "current_date": "2026-07-15"})
        sensor = getattr(sensor_mod, navn)(coord, _make_entry())
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)

    @pytest.mark.parametrize("navn", FORRIGE_MAANED_TOTAL)
    def test_last_reset_flytter_med_maanedsskiftet(self, navn, lokal_midnatt):
        import stromkalkulator.sensor as sensor_mod

        coord = _make_coordinator({"current_month": "2026-07", "current_date": "2026-07-31"})
        sensor = getattr(sensor_mod, navn)(coord, _make_entry())
        assert sensor.last_reset == datetime(2026, 7, 1, tzinfo=OSLO)

        coord.data = {"current_month": "2026-08", "current_date": "2026-08-01"}
        assert sensor.last_reset == datetime(2026, 8, 1, tzinfo=OSLO)

    @pytest.mark.parametrize("navn", FORRIGE_MAANED_TOTAL)
    def test_alle_har_state_class_total(self, navn):
        """last_reset er bare gyldig sammen med TOTAL."""
        import stromkalkulator.sensor as sensor_mod

        assert getattr(sensor_mod, navn)._attr_state_class == "total"


class TestCoordinatorKontrakt:
    """Coordinatoren leverer periodemerkelappene sensorene trenger."""

    def test_data_inneholder_periodemerkelapper(self, coord_module):
        """current_month og current_date følger hver oppdatering."""
        c = coord_module.NettleieCoordinator(_make_hass(power_w=5000, spot_price=1.20), _make_entry())
        data = _run_update(coord_module, c, _real_datetime(2026, 6, 15, 12, 0))

        assert data["current_month"] == "2026-06"
        assert data["current_date"] == "2026-06-15"
