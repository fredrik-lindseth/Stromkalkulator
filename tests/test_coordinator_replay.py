"""Ende-til-ende-replay av hourly-fixturer gjennom NettleieCoordinator.

Mater hver fixture time-for-time inn i `_async_update_data()` via tpi-delta-
stien (kumulativ energy_sensor) og sammenligner akkumulerte sluttverdier
mot fakturatall. Fanger bugs som unit-tester ikke ser: bias over hundrevis
av polls, persistens-tap, fortegnsfeil i Norgespris-komp osv.

Eksisterende `test_faktura_hourly_snapshot.py` er en false-positive: den
reimplementerer dag/natt-split, topp-3 og Norgespris-komp parallelt med
coordinator og asserter mot den. Coordinator-koden kjøres aldri. Denne
filen fyller gapet ved å kjøre ekte `_async_update_data()`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry, _make_state
from tests.test_faktura_bkk import (
    FAKTURA_APRIL_2026,
    FAKTURA_DESEMBER_2025,
    FAKTURA_FEBRUAR_2026,
    FAKTURA_JUNI_2026,
    FAKTURA_MAI_2026,
    FAKTURA_MARS_2026,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Map fakturanavn -> (fixture-fil, faktura-dict, første dag i måned).
# Faktura-dict har "navn" som matcher YYYY-MM-strukturen i tpi-feltet.
FAKTURA_MAP: dict[str, tuple[str, dict, datetime]] = {
    "desember_2025": (
        "bkk_desember_2025_hourly.json",
        FAKTURA_DESEMBER_2025,
        datetime(2025, 12, 1),
    ),
    "februar_2026": (
        "bkk_februar_2026_hourly.json",
        FAKTURA_FEBRUAR_2026,
        datetime(2026, 2, 1),
    ),
    "mars_2026": (
        "bkk_mars_2026_hourly.json",
        FAKTURA_MARS_2026,
        datetime(2026, 3, 1),
    ),
    "april_2026": (
        "bkk_april_2026_hourly.json",
        FAKTURA_APRIL_2026,
        datetime(2026, 4, 1),
    ),
    "mai_2026": (
        "bkk_mai_2026_hourly.json",
        FAKTURA_MAI_2026,
        datetime(2026, 5, 1),
    ),
    "juni_2026": (
        "bkk_juni_2026_hourly.json",
        FAKTURA_JUNI_2026,
        datetime(2026, 6, 1),
    ),
}


def _load_fixture(name: str) -> dict:
    """Last hourly-fixture og returner som dict."""
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


def _make_replay_state(power_w: float, spot_eks_mva: float, tpi_kwh: float):
    """Returner state-mapper som matcher coordinatorens sensor-oppslag.

    `sensor.power`: instantan effekt i W (brukes til current_power_kw,
    ikke til akkumulering siden vi har energy_sensor).
    `sensor.spot_price`: spot eks. mva (config bruker spotpris_inkl_mva=False).
    `sensor.tpi`: kumulativ energi i kWh.
    """
    states = {
        "sensor.power": _make_state(power_w),
        "sensor.spot_price": _make_state(spot_eks_mva),
        "sensor.tpi": _make_state(tpi_kwh),
    }
    return lambda eid: states.get(eid)


def _make_replay_coordinator(coord_module, init_now: datetime, har_norgespris=True):
    """Lag en coordinator konfigurert for replay-test.

    `init_now` styrer hvilken måned coordinator initialiserer som "current"
    (settes via dt_util.now()), slik at månedsskifte ikke trigges utilsiktet
    før månedens hourly-data er matet inn.
    """
    coord_module.dt_util.now.return_value = init_now
    hass = MagicMock()
    entry = _make_entry(
        dso_id="bkk",
        har_norgespris=har_norgespris,
        avgiftssone="standard",
        spotpris_inkl_mva=False,
        energy_sensor="sensor.tpi",
    )
    coord = coord_module.NettleieCoordinator(hass, entry)
    return coord, hass


def _replay_month(
    coord_module,
    fixture_name: str,
    faktura: dict,
    har_norgespris: bool = True,
) -> dict:
    """Mat en hourly-fixture inn i coordinator og trigg månedsskifte.

    For hver time settes `now` til time-start lokaltid, tpi-sensoren
    oppdateres med kumulativ kWh, og coordinator polles. Etter siste
    time mates en ekstra poll på første time i neste måned for å
    trigge `_handle_month_rollover` og dermed arkivere alt i
    `_previous_month_*`.

    Returnerer det siste result-dictet (etter rollover), som inneholder
    de relevante previous_month_*-feltene.
    """
    fixture = _load_fixture(fixture_name)
    hours = fixture["hours"]
    tpi_start = fixture["metadata"]["tpi_start_kwh"]

    # Primer-tidspunkt: identisk med første fixture-time. Coordinator
    # initialiseres på denne tiden så `_current_month` matcher fixture-måneden
    # og ingen utilsiktet månedsskifte trigges.
    first_hour_iso = hours[0]["start_local"]
    first_hour_now = datetime.fromisoformat(first_hour_iso).replace(tzinfo=None)

    coord, hass = _make_replay_coordinator(
        coord_module, init_now=first_hour_now, har_norgespris=har_norgespris
    )

    # Primer-poll: sett `_last_tpi_kwh = tpi_start` uten å akkumulere
    # forbruk. Uten dette returnerer `_compute_energy_delta` 0 på første poll
    # (line 335 i coordinator.py) og første times energi blir tapt.
    hass.states.get = MagicMock(
        side_effect=_make_replay_state(
            power_w=0,
            spot_eks_mva=hours[0]["spot_nok_kwh_eks_mva"],
            tpi_kwh=tpi_start,
        )
    )
    coord_module.dt_util.now.return_value = first_hour_now
    import asyncio
    asyncio.run(coord._async_update_data())

    # Kjør coordinator gjennom hver fixture-time. Vi setter dt_util.now()
    # til time-startens *naive* lokale tid; det er det coordinator selv
    # bruker (`now.hour`, `now.weekday()`, strftime).
    cumulative_kwh = tpi_start
    last_result = None
    for hour in hours:
        start_iso = hour["start_local"]
        # ISO "2026-04-01T00:00:00+02:00" -> naiv lokal "2026-04-01T00:00:00"
        now = datetime.fromisoformat(start_iso).replace(tzinfo=None)

        cumulative_kwh += hour["kwh"]
        hass.states.get = MagicMock(
            side_effect=_make_replay_state(
                power_w=hour["p_max_w"],
                spot_eks_mva=hour["spot_nok_kwh_eks_mva"],
                tpi_kwh=cumulative_kwh,
            )
        )
        coord_module.dt_util.now.return_value = now

        import asyncio
        last_result = asyncio.run(coord._async_update_data())

    # Trigge månedsskifte: én ekstra poll på første time neste måned.
    last_hour = datetime.fromisoformat(hours[-1]["start_local"]).replace(tzinfo=None)
    next_month_first_hour = (last_hour + timedelta(hours=1)).replace(
        day=1, hour=0, minute=0, second=0
    )
    if last_hour.month == 12:
        next_month_first_hour = datetime(last_hour.year + 1, 1, 1, 0, 0)
    else:
        next_month_first_hour = datetime(last_hour.year, last_hour.month + 1, 1, 0, 0)

    # Behold siste tpi-verdi og siste spot (ny måned skal ikke akkumulere mer).
    hass.states.get = MagicMock(
        side_effect=_make_replay_state(
            power_w=0,
            spot_eks_mva=hours[-1]["spot_nok_kwh_eks_mva"],
            tpi_kwh=cumulative_kwh,
        )
    )
    coord_module.dt_util.now.return_value = next_month_first_hour

    import asyncio
    last_result = asyncio.run(coord._async_update_data())

    return {
        "result": last_result,
        "coord": coord,
        "faktura": faktura,
    }


class TestReplayDesember2025:
    """Desember 2025 replay (pre-Norgespris, strømstøtte-kunde).

    Fixturen mangler spotpris-data (alle timer har spot=None), så vi kan ikke
    verifisere strømstøtte eller kostnad. Vi sjekker bare det som er drevet
    av forbruks- og effekt-data: total kWh, dag/natt-split, topp 3 og
    kapasitetstrinn. Strømstøtte-beløpet i fakturaen er verifisert separat
    i `test_faktura_bkk.py::test_2025_*`.
    """

    @pytest.fixture
    def replay(self, coord_module):
        return _replay_month(
            coord_module,
            "bkk_desember_2025_hourly.json",
            FAKTURA_DESEMBER_2025,
            har_norgespris=False,
        )

    def test_total_kwh_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_consumption_total_kwh"] == pytest.approx(
            faktura["forbruk_total_kwh"], abs=0.05
        )

    def test_dag_natt_split_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        # 2 kWh-toleranse; se docstring på
        # TestReplayParametrized.test_dag_natt_split_matcher_faktura.
        assert result["previous_month_consumption_dag_kwh"] == pytest.approx(
            faktura["forbruk_dag_kwh"], abs=2.0
        )
        assert result["previous_month_consumption_natt_kwh"] == pytest.approx(
            faktura["forbruk_natt_kwh"], abs=2.0
        )

    def test_dag_natt_split_med_jul_nyttar_aften_helligdager(self, replay):
        """Manuell reklassifisering av 24.12 og 31.12 som helligdag matcher fakturaen.

        Dokumenterer at avviket i `test_dag_natt_split_matcher_faktura` skyldes
        helligdagsdefinisjonen og ingenting annet. Beregner dag/natt-split direkte
        fra fixturen med BKKs 2025-konvensjon.
        """
        from datetime import datetime as _datetime

        fixture = _load_fixture("bkk_desember_2025_hourly.json")
        bkk_helligdager = {"2025-12-24", "2025-12-25", "2025-12-26", "2025-12-31"}

        dag_kwh = 0.0
        natt_kwh = 0.0
        for hour in fixture["hours"]:
            dt = _datetime.fromisoformat(hour["start_local"])
            dato = dt.strftime("%Y-%m-%d")
            is_helligdag = dato in bkk_helligdager
            is_weekend = dt.weekday() >= 5
            is_dag_tariff = (6 <= dt.hour < 22) and not is_weekend and not is_helligdag
            if is_dag_tariff:
                dag_kwh += hour["kwh"]
            else:
                natt_kwh += hour["kwh"]

        faktura = replay["faktura"]
        assert dag_kwh == pytest.approx(faktura["forbruk_dag_kwh"], abs=0.5)
        assert natt_kwh == pytest.approx(faktura["forbruk_natt_kwh"], abs=0.5)

    def test_topp_3_kapasitet_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_avg_top_3_kw"] == pytest.approx(
            faktura["maks_effekt_snitt"], abs=0.10
        )

    def test_kapasitetsledd_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_kapasitetsledd"] == faktura["forventet_kapasitet_kr"]


@pytest.mark.parametrize(
    "replay",
    ["februar_2026", "mars_2026", "april_2026", "mai_2026", "juni_2026"],
    indirect=True,
    ids=["februar", "mars", "april", "mai", "juni"],
)
class TestReplayParametrized:
    """Samme replay for feb-juni, parametrisert via indirect fixture.

    April-caset er samme fixture/faktura som ville fanget Norgespris-36%-bugen
    (tidligere en egen TestReplayAprilThroughCoordinator, slått sammen hit for
    å unngå duplisert replay av samme måned).
    """

    @pytest.fixture
    def replay(self, coord_module, request):
        fixture_name, faktura, _ = FAKTURA_MAP[request.param]
        return _replay_month(coord_module, fixture_name, faktura)

    def test_total_kwh_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_consumption_total_kwh"] == pytest.approx(
            faktura["forbruk_total_kwh"], abs=0.05
        )

    def test_dag_natt_split_matcher_faktura(self, replay):
        """Dag/natt-fordeling matcher faktura.

        Toleranse: 2 kWh hver vei. Fixture-data (kWh per klokke-time) og
        fakturaens dag/natt-split er begge avrundet, og BKKs klassifisering
        av enkelt-timer rundt DST-overgangen avviker noen tideler fra naiv
        lokaltid. 2 kWh fanger fortsatt grov mis-klassifisering.
        """
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_consumption_dag_kwh"] == pytest.approx(
            faktura["forbruk_dag_kwh"], abs=2.0
        )
        assert result["previous_month_consumption_natt_kwh"] == pytest.approx(
            faktura["forbruk_natt_kwh"], abs=2.0
        )

    def test_norgespris_compensation_matcher_faktura(self, replay):
        """Norgespris-kompensasjon matcher faktura innen 5 kr.

        Dette er testen som ville fanget Norgespris-bug-en (april 2026:
        kompensasjonen kom ut 36% for lav). Coordinator akkumulerer
        `(norgespris - spot_price) * energy_kwh` per poll; ved replay må
        sluttsummen matche fakturaens `forventet_norgespris_kr`.
        """
        coord = replay["coord"]
        faktura = replay["faktura"]
        komp = coord._previous_month_norgespris_compensation
        assert komp == pytest.approx(faktura["forventet_norgespris_kr"], abs=5.0)

    def test_topp_3_kapasitet_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_avg_top_3_kw"] == pytest.approx(
            faktura["maks_effekt_snitt"], abs=0.10
        )

    def test_kapasitetsledd_matcher_faktura(self, replay):
        result = replay["result"]
        faktura = replay["faktura"]
        assert result["previous_month_kapasitetsledd"] == faktura["forventet_kapasitet_kr"]
