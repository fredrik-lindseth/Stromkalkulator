"""DST-overgang i Norge: vår 29.03.2026 og høst 25.10.2026.

Sjekker at coordinator.py:
- `_is_day_rate` bruker lokal time, ikke UTC
- Akkumulator hopper ikke over eller dobbelttelle energi
- Topp-3 datoer henger ikke fast i feil dato
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import _make_entry, _make_hass, _run_update

_real_datetime = datetime
OSLO = ZoneInfo("Europe/Oslo")

# 2026: vår-DST 29.03 (CET -> CEST), høst-DST 25.10 (CEST -> CET)
VAR_SONDAG = (2026, 3, 29)
VAR_MANDAG = (2026, 3, 30)
HOST_SONDAG = (2026, 10, 25)
HOST_MANDAG = (2026, 10, 26)


def _coord(coord_module, dso_id="bkk", power_w=5000):
    hass = _make_hass(power_w=power_w)
    entry = _make_entry(dso_id=dso_id)
    return coord_module.NettleieCoordinator(hass, entry)


class TestIsDayRateDstSondag:
    """DST-overgangs-søndager er helg = natt-tariff hele døgnet."""

    def test_var_sondag_alltid_natt(self, coord_module):
        """29.03.2026 (søndag) er natt-tariff for alle eksisterende timer."""
        coord = _coord(coord_module)
        for hour in range(24):
            if hour == 2:
                continue  # 02:00 eksisterer ikke ved vår-DST
            dt = _real_datetime(*VAR_SONDAG, hour, 0)
            assert coord._is_day_rate(dt) is False, f"kl {hour:02d}"

    def test_host_sondag_alltid_natt(self, coord_module):
        """25.10.2026 (søndag) er natt-tariff hele døgnet."""
        coord = _coord(coord_module)
        for hour in range(24):
            dt = _real_datetime(*HOST_SONDAG, hour, 0)
            assert coord._is_day_rate(dt) is False, f"kl {hour:02d}"

    def test_host_doblet_time_begge_ganger_natt(self, coord_module):
        """02:30 på høst-DST-søndag oppstår to ganger, begge er natt."""
        coord = _coord(coord_module)
        # Naiv samt fold=0 (CEST før omstilling) og fold=1 (CET etter)
        for fold in (0, 1):
            dt = _real_datetime(*HOST_SONDAG, 2, 30, tzinfo=OSLO, fold=fold)
            assert coord._is_day_rate(dt) is False
        assert coord._is_day_rate(_real_datetime(*HOST_SONDAG, 2, 30)) is False


class TestIsDayRateMandagEtterDst:
    """Mandag etter DST: vanlige tariff-grenser kl 06:00 og 22:00 lokal."""

    def test_var_mandag_grenser(self, coord_module):
        """30.03.2026: 05:59 natt, 06:00 dag, 21:59 dag, 22:00 natt."""
        coord = _coord(coord_module)
        assert coord._is_day_rate(_real_datetime(*VAR_MANDAG, 5, 59)) is False
        assert coord._is_day_rate(_real_datetime(*VAR_MANDAG, 6, 0)) is True
        assert coord._is_day_rate(_real_datetime(*VAR_MANDAG, 21, 59)) is True
        assert coord._is_day_rate(_real_datetime(*VAR_MANDAG, 22, 0)) is False

    def test_host_mandag_grenser(self, coord_module):
        """26.10.2026: samme grenser som ellers."""
        coord = _coord(coord_module)
        assert coord._is_day_rate(_real_datetime(*HOST_MANDAG, 5, 59)) is False
        assert coord._is_day_rate(_real_datetime(*HOST_MANDAG, 6, 0)) is True
        assert coord._is_day_rate(_real_datetime(*HOST_MANDAG, 21, 59)) is True
        assert coord._is_day_rate(_real_datetime(*HOST_MANDAG, 22, 0)) is False

    def test_aware_oslo_tid_gir_samme_resultat(self, coord_module):
        """Aware Oslo-tid gir samme tariff som naiv lokal tid."""
        coord = _coord(coord_module)
        dt = _real_datetime(*VAR_MANDAG, 12, 0, tzinfo=OSLO)
        assert coord._is_day_rate(dt) is True


class TestAkkumulatorOverDst:
    """Energi rundt DST-skifte: cap forhindrer feil pga klokkehopp.

    MAX_ELAPSED_HOURS i const.py setter taket på 6 min per intervall.
    DST-overganger gir 1-timers hopp, som dermed automatisk avvises.
    """

    def test_var_klokkehopp_avvises_av_cap(self, coord_module):
        """Vår-DST: 2-timers naiv klokke-delta cappes til 6 min."""
        coord = _coord(coord_module, power_w=6000)
        _run_update(coord_module, coord, now=_real_datetime(*VAR_SONDAG, 1, 30))
        result = _run_update(
            coord_module, coord, now=_real_datetime(*VAR_SONDAG, 3, 30)
        )
        total = result["monthly_consumption_total_kwh"]
        # Cap: 6 kW * 0.1 t = 0.6 kWh, ikke 12 kWh
        assert 0.0 < total < 1.0, f"forventet at cap forhindrer dobbelt-telling, fikk {total}"

    def test_kort_intervall_over_var_dst_akkumulerer(self, coord_module):
        """5 min reell tid over vår-DST gir normal akkumulering."""
        coord = _coord(coord_module, power_w=6000)
        # 01:58 -> 03:03 lokalt = 5 min reell tid (1 t 5 min naivt)
        _run_update(coord_module, coord, now=_real_datetime(*VAR_SONDAG, 1, 58))
        result = _run_update(
            coord_module, coord, now=_real_datetime(*VAR_SONDAG, 3, 3)
        )
        total = result["monthly_consumption_total_kwh"]
        assert 0.0 < total <= 0.7

    def test_host_doblet_tid_ikke_dobbelttellet(self, coord_module):
        """Samme naive tid to ganger gir ingen ny akkumulering."""
        coord = _coord(coord_module, power_w=3000)
        first = _real_datetime(*HOST_SONDAG, 2, 30)
        _run_update(coord_module, coord, now=first)

        next_step = _real_datetime(*HOST_SONDAG, 2, 35)
        first_total = _run_update(coord_module, coord, now=next_step)[
            "monthly_consumption_total_kwh"
        ]
        assert 0.2 < first_total < 0.3  # 3 kW * 5/60 t = 0.25 kWh

        # Andre passering av samme klokketid -> ingen ny energi
        second = _run_update(coord_module, coord, now=next_step)
        assert second["monthly_consumption_total_kwh"] == first_total

    def test_aldri_negativ_energi(self, coord_module):
        """Korte oppdateringer rundt DST gir aldri negativ energi."""
        coord = _coord(coord_module, power_w=2000)
        before = _real_datetime(*HOST_SONDAG, 1, 30, tzinfo=OSLO)
        after = _real_datetime(*HOST_SONDAG, 1, 35, tzinfo=OSLO)
        _run_update(coord_module, coord, now=before)
        result = _run_update(coord_module, coord, now=after)
        assert result["monthly_consumption_total_kwh"] >= 0.0


class TestTopp3RundtDst:
    """Topp-3-datoer bruker lokal dato og flippes ikke pga tidssone."""

    def test_keys_holder_lokal_dato(self, coord_module):
        """Plantede entries beholder lokale datostrenger."""
        coord = _coord(coord_module)
        coord._daily_max_power = {
            "2026-03-30": coord_module.DailyMaxEntry(kw=8.5, hour=10),
            "2026-03-29": coord_module.DailyMaxEntry(kw=4.0, hour=12),
            "2026-10-26": coord_module.DailyMaxEntry(kw=9.2, hour=18),
        }
        top_3 = coord._get_top_3_days()
        assert set(top_3.keys()) == {"2026-03-30", "2026-03-29", "2026-10-26"}
        assert next(iter(top_3)) == "2026-10-26"  # høyeste først

    def test_timegrense_pa_var_mandag_riktig_dato(self, coord_module):
        """Time fullført kl 07:00 mandag 30.03 lagres som 2026-03-30."""
        coord = _coord(coord_module, power_w=4000)
        for minute in (0, 15, 30, 45, 59):
            _run_update(
                coord_module, coord, now=_real_datetime(*VAR_MANDAG, 6, minute)
            )
        _run_update(coord_module, coord, now=_real_datetime(*VAR_MANDAG, 7, 0))
        assert "2026-03-30" in coord._daily_max_power
        assert "2026-03-29" not in coord._daily_max_power


class TestTidsstempelKonsistens:
    """Coordinator-løkken tåler DST uten exceptions, månedstracking holder."""

    def test_full_update_pa_var_sondag(self, coord_module):
        """Full _async_update_data på DST-søndag returnerer natt-tariff."""
        coord = _coord(coord_module, power_w=3000)
        result = _run_update(
            coord_module, coord, now=_real_datetime(*VAR_SONDAG, 14, 0)
        )
        assert result["is_day_rate"] is False
        assert "monthly_consumption_total_kwh" in result

    def test_sekvens_over_var_dst_holder_maned(self, coord_module):
        """Oppdateringer 28.03 -> 30.03 holder current_month = 2026-03."""
        coord = _coord(coord_module, power_w=2000)
        for dt in [
            _real_datetime(2026, 3, 28, 23, 0),
            _real_datetime(*VAR_SONDAG, 12, 0),
            _real_datetime(*VAR_MANDAG, 8, 0),
        ]:
            _run_update(coord_module, coord, now=dt)
        assert coord._current_month == "2026-03"

    def test_naiv_subtraksjon_er_klokke_delta(self):
        """Naiv datetime-subtraksjon gir klokke-delta, ikke reell tid."""
        before = _real_datetime(*VAR_SONDAG, 1, 30)
        after = _real_datetime(*VAR_SONDAG, 3, 30)
        assert (after - before) == timedelta(hours=2)
