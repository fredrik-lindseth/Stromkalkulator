"""Analytiske fasiter for eksport over prisruter, prisgap og omstart."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.stromkalkulator.eksport import Eksportbok, Eksportsum
from tests.conftest import _make_entry, _make_hass, _make_state, _run_update


def tid(time=12, minutt=0):
    return datetime(2026, 6, 15, time, minutt, tzinfo=UTC)


def test_tidsfordeling_bruker_hver_rutes_egen_pris():
    bok = Eksportbok()
    bok.registrer_pris(tid(12, 14), 1)
    bok.registrer_pris(tid(12, 16), 3)
    bok.bokfor(tid(12, 14), tid(12, 16), 0.2)
    sum_ = bok.maaned("2026-06")
    assert sum_.kwh == pytest.approx(0.2)
    assert sum_.inntekt_kr == pytest.approx(0.4)
    assert sum_.kwh_uten_pris == 0


@pytest.mark.parametrize("pris", [0, -2])
def test_null_og_negativ_pris_er_komplett_grunnlag(pris):
    bok = Eksportbok()
    bok.registrer_pris(tid(12, 1), pris)
    bok.bokfor(tid(), tid(12, 2), 0.2)
    assert bok.maaned("2026-06").inntekt_kr == pytest.approx(0.2 * pris)
    assert bok.maaned("2026-06").kwh_uten_pris == 0


def test_ny_prisprove_retter_tidligere_energi_i_samme_rute():
    bok = Eksportbok()
    bok.bokfor(tid(), tid(12, 1), 0.1)
    assert bok.maaned("2026-06").kwh_uten_pris == 0.1
    bok.registrer_pris(tid(12, 1), 1)
    bok.registrer_pris(tid(12, 2), 2)
    assert bok.maaned("2026-06").inntekt_kr == 0.2
    assert bok.maaned("2026-06").kwh_uten_pris == 0
    bok.registrer_pris(tid(12, 3), 2)
    assert bok.maaned("2026-06").inntekt_kr == 0.2


def test_foldede_prisgap_og_minusinntekt_overlever_restart():
    bok = Eksportbok()
    bok.bokfor(tid(), tid(12, 1), 0.1)
    bok.registrer_pris(tid(12, 16), -2)
    bok.bokfor(tid(12, 15), tid(12, 16), 0.2)
    bok.avslutt_eldre(tid(16))
    lagret = bok.til_lagring()
    assert lagret["energi"] == []
    assert lagret["pris"]["ruter"] == []
    igjen = Eksportbok.fra_lagring(lagret)
    sum_ = igjen.maaned("2026-06")
    assert sum_.kwh == pytest.approx(0.3)
    assert sum_.inntekt_kr == -0.4
    assert sum_.kwh_uten_pris == 0.1


def test_dst_bruker_absolutte_tidsandeler():
    oslo = ZoneInfo("Europe/Oslo")
    fra = datetime(2026, 10, 25, 2, 59, tzinfo=oslo, fold=0)
    til = datetime(2026, 10, 25, 2, 1, tzinfo=oslo, fold=1)
    bok = Eksportbok()
    bok.registrer_pris(fra, 1)
    bok.registrer_pris(til, 3)
    bok.bokfor(fra, til, 0.2)
    assert bok.maaned("2026-10").inntekt_kr == pytest.approx(0.4)


def coordinator_med_pris(coord_module, pris):
    hass = _make_hass(power_w=0, spot_price=1, export_power_w=6000)
    opprinnelig = hass.states.get.side_effect
    hass.states.get.side_effect = lambda entitet: (
        _make_state(pris[0]) if entitet == "sensor.spot_price" else opprinnelig(entitet)
    )
    entry = _make_entry(export_power_sensor="sensor.export_power", spotpris_inkl_mva=False)
    return coord_module.NettleieCoordinator(hass, entry)


def test_coordinator_timegrense_ikke_siste_pollpris(coord_module):
    pris = [1]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = 3
    svar = _run_update(coord_module, coord, now=tid(13, 2))
    # 6 kW: 0,1 kWh i gammel time og 0,2 kWh i ny, henholdsvis 1 og 3 kr/kWh.
    assert svar["monthly_export_kwh"] == 0.3
    assert svar["monthly_export_revenue_kr"] == 0.7
    pris[0] = 4
    svar = _run_update(coord_module, coord, now=tid(13, 3))
    assert svar["monthly_export_revenue_kr"] == 1.3


def test_coordinator_prisgap_bruker_ikke_nabo_eller_visningscache(coord_module):
    pris = ["unavailable"]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = 2
    svar = _run_update(coord_module, coord, now=tid(13, 2))
    assert svar["monthly_export_revenue_kr"] == 0.4
    assert svar["monthly_export_kwh_uten_pris"] == 0.1
    assert svar["monthly_export_price_complete"] is False


def test_coordinator_egen_bok_bevarer_pris_over_maanedsrullering(coord_module):
    # Norsk månedsgrense er 22 UTC i sommertid, så bruk lokalt tidsstempel.
    oslo = ZoneInfo("Europe/Oslo")
    coord = coordinator_med_pris(coord_module, [1])
    _run_update(coord_module, coord, now=datetime(2026, 6, 30, 23, 59, tzinfo=oslo))
    # Bytt prissensoren ved første julipoll.
    gammel = coord.hass.states.get.side_effect
    coord.hass.states.get.side_effect = lambda entitet: (
        _make_state(3) if entitet == "sensor.spot_price" else gammel(entitet)
    )
    svar = _run_update(coord_module, coord, now=datetime(2026, 7, 1, 0, 2, tzinfo=oslo))
    assert svar["previous_month_export_kwh"] == 0.1
    assert svar["previous_month_export_revenue_kr"] == 0.1
    assert svar["monthly_export_kwh"] == 0.2
    assert svar["monthly_export_revenue_kr"] == 0.6


def test_visningscache_er_ikke_prisgrunnlag_for_ny_eksport(coord_module):
    pris = [1]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = "unavailable"
    svar = _run_update(coord_module, coord, now=tid(13, 2))
    assert svar["spot_price_valid"] is True  # visningscachen er fortsatt lovlig
    assert svar["monthly_export_revenue_kr"] == 0.1
    assert svar["monthly_export_kwh_uten_pris"] == 0.2


def test_coordinator_prisgap_overlever_store_og_restart(coord_module):
    pris = ["unavailable"]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = -2
    _run_update(coord_module, coord, now=tid(13, 2))
    lagret = coord._store.async_save.call_args.args[0]
    igjen = coordinator_med_pris(coord_module, pris)
    igjen._store = MagicMock()
    igjen._store.async_load = AsyncMock(return_value=lagret)
    igjen._store.async_save = AsyncMock()
    svar = _run_update(coord_module, igjen, now=tid(13, 3))
    assert svar["monthly_export_revenue_kr"] == -0.6
    assert svar["monthly_export_kwh_uten_pris"] == 0.1
    assert svar["monthly_export_price_complete"] is False


def test_inntektssensor_prisgap_viser_kjent_delsum_med_dekning(coord_module):
    from stromkalkulator.sensor import MaanedligEksportInntektSensor

    pris = ["unavailable"]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = 2
    data = _run_update(coord_module, coord, now=tid(13, 2))
    visning = MagicMock(data=data)
    sensor = MaanedligEksportInntektSensor(visning, _make_entry())
    assert sensor.native_value == 0.4
    attrs = sensor.extra_state_attributes
    # Snittet er over energien som har pris, ikke over hele eksporten.
    assert attrs["snitt_spotpris"] == 2.0
    assert attrs["kwh_uten_pris"] == 0.1
    assert attrs["prisgrunnlag_komplett"] is False


def test_kort_prisgap_gjor_ikke_resten_av_maaneden_ukjent(coord_module):
    """Ett kvarter uten pris, f.eks. en omstart midt på dagen, skal ikke
    gjøre inntekt og nettokostnad ukjent til månedsskiftet. Senere kvarter
    med pris legges til den kjente delsummen, og summen hopper ikke."""
    pris = ["unavailable"]
    coord = coordinator_med_pris(coord_module, pris)
    _run_update(coord_module, coord, now=tid(12, 59))
    pris[0] = 2
    foer = _run_update(coord_module, coord, now=tid(13, 2))
    etter = _run_update(coord_module, coord, now=tid(13, 5))
    assert etter["monthly_export_kwh_uten_pris"] == 0.1
    assert etter["monthly_export_price_complete"] is False
    assert etter["monthly_export_revenue_kr"] == pytest.approx(foer["monthly_export_revenue_kr"] + 0.6)
    assert etter["monthly_net_cost_kr"] == pytest.approx(
        etter["monthly_cost_kr"] - etter["monthly_export_revenue_kr"], abs=0.01
    )


def test_forrige_maaneds_eksport_gjelder_maaneden_som_ble_arkivert(coord_module):
    """Etter et flermånedersgap er forrige måned nullstilt uten navn. Eksporten
    som lå i kalendermåneden før skal da ikke vises som om den var arkivert."""
    oslo = ZoneInfo("Europe/Oslo")
    coord = coordinator_med_pris(coord_module, [1])
    _run_update(coord_module, coord, now=datetime(2026, 4, 30, 12, 2, tzinfo=oslo))
    # Oppdateringene har stått i to måneder; den første etterpå ligger rett
    # etter midnatt, så eksportvinduet bak den krysser inn i juni.
    svar = _run_update(coord_module, coord, now=datetime(2026, 7, 1, 0, 2, tzinfo=oslo))
    assert coord._eksportbok.maaned("2026-06").kwh > 0
    assert svar["previous_month_name"] is None
    assert svar["previous_month_export_kwh"] == 0
    assert svar["previous_month_export_revenue_kr"] == 0
    assert svar["previous_month_export_kwh_uten_pris"] == 0


def test_lagrede_eksportsummer_er_bokens_ogsaa_ved_maanedsskiftet(coord_module):
    """Summene ved siden av boken er til nedgradering, og skal være bokens egne.

    De ble tidligere speilet i egne felt og kopiert ved rulleringen, men regnet
    om fra boken etterpå. Lagringen leser nå boken direkte.
    """
    oslo = ZoneInfo("Europe/Oslo")
    coord = coordinator_med_pris(coord_module, [1])
    _run_update(coord_module, coord, now=datetime(2026, 6, 30, 23, 58, tzinfo=oslo))
    svar = _run_update(coord_module, coord, now=datetime(2026, 7, 1, 0, 2, tzinfo=oslo))
    lagret = coord._store.async_save.call_args.args[0]
    assert svar["previous_month_export_kwh"] > 0
    assert lagret["previous_month_export_kwh"] == pytest.approx(svar["previous_month_export_kwh"], abs=1e-3)
    assert lagret["previous_month_export_revenue"] == pytest.approx(
        svar["previous_month_export_revenue_kr"], abs=0.01
    )
    assert lagret["monthly_export_kwh"] == pytest.approx(svar["monthly_export_kwh"], abs=1e-3)
    assert lagret["monthly_export_revenue"] == pytest.approx(svar["monthly_export_revenue_kr"], abs=0.01)


@pytest.mark.parametrize("uten_pris,komplett", [(0.0, True), (1e-10, True), (1e-6, False)])
def test_prisdekningen_tilgir_bare_flyttallsstoy(uten_pris, komplett):
    assert Eksportsum(kwh=1.0, kwh_uten_pris=uten_pris).prisdekning_komplett is komplett


@pytest.mark.parametrize("verdi", [float("nan"), float("inf"), -1, "feil"])
def test_lagret_eksportenergi_maa_vaere_endelig_og_positiv(verdi):
    lagret = Eksportbok().til_lagring()
    lagret["energi"] = [{"start": tid().isoformat(), "kwh": verdi}]
    with pytest.raises(ValueError):
        Eksportbok.fra_lagring(lagret)


def test_naiv_lagret_eksporttid_avvises_foer_bruk():
    lagret = Eksportbok().til_lagring()
    lagret["energi"] = [{"start": "2026-06-15T12:00:00", "kwh": 1}]
    with pytest.raises(ValueError):
        Eksportbok.fra_lagring(lagret)


@pytest.mark.parametrize("felt,verdi", [("inntekt_kr", float("nan")), ("kwh_uten_pris", 2)])
def test_ugyldig_lagret_eksportsum_avvises(felt, verdi):
    lagret = Eksportbok().til_lagring()
    lagret["ferdige"] = {"2026-06": {"kwh": 1, "inntekt_kr": -2, "kwh_uten_pris": 0, felt: verdi}}
    with pytest.raises(ValueError):
        Eksportbok.fra_lagring(lagret)


def test_samme_eksportpris_skriver_ikke_lagringen_hvert_minutt(coord_module):
    """Lagringen skrives når en prisrute får ny pris, ikke ved hver prøve."""
    pris = [1]
    hass = _make_hass(power_w=0, spot_price=1, export_power_w=0)
    opprinnelig = hass.states.get.side_effect
    hass.states.get.side_effect = lambda entitet: (
        _make_state(pris[0]) if entitet == "sensor.spot_price" else opprinnelig(entitet)
    )
    entry = _make_entry(export_power_sensor="sensor.export_power", spotpris_inkl_mva=False)
    coord = coord_module.NettleieCoordinator(hass, entry)
    coord._store_loaded = True
    coord._current_month = "2026-06"

    def lagringer():
        return coord._store.async_save.call_count

    _run_update(coord_module, coord, now=tid(12, 1))
    etter_forste = lagringer()
    assert etter_forste == 1, "Første pris i ruten skal lagres"
    for minutt in (2, 3, 4):
        _run_update(coord_module, coord, now=tid(12, minutt))
    assert lagringer() == etter_forste, "Samme pris i samme rute skal ikke lagres på nytt"
    _run_update(coord_module, coord, now=tid(12, 16))
    assert lagringer() == etter_forste + 1, "Ny rute har ny pris"
    pris[0] = 2
    _run_update(coord_module, coord, now=tid(12, 17))
    assert lagringer() == etter_forste + 2, "Endret pris i ruten skal lagres"
