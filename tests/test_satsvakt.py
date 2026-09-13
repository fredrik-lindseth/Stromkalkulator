"""Tester for satsvakten: kalendervarsler, årsskifte uten omstart og demping.

Satsene i const.py og dso.py er verifisert for ett år om gangen. Forbruksavgiften
settes i statsbudsjettet og skifter 1. januar, og mange nettselskap bytter tariff
samtidig, så årsskiftet er der satsene faktisk blir gale. Vakten skal derfor se på
kalenderen hver dag, ikke bare når Home Assistant startes, og varselet om utløpt
Norgespris skal gjelde det anlegget som har Norgespris, ikke alle.

Hvert varsel prøves i begge retninger: at det kommer når det skal, og at det ikke
kommer når det ikke skal.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import _make_entry

OSLO = ZoneInfo("Europe/Oslo")

# Ekte ULID-form, slik HA lager entry_id. Formen betyr noe: _ENTRY_ID_SUFFIX i
# __init__ bruker den til å kjenne igjen et anleggs-issue.
ENTRY_A = "01JAAAAAAAAAAAAAAAAAAAAAAA"
ENTRY_B = "01JBBBBBBBBBBBBBBBBBBBBBBB"


@pytest.fixture
def init_module():
    """Last __init__ på nytt og nullstill ir-mocken.

    ir er en delt MagicMock i sys.modules (conftest), så call_args_list
    akkumulerer på tvers av tester. reset_mock gir hver test et rent utgangspunkt.
    """
    import stromkalkulator.__init__ as init_mod

    importlib.reload(init_mod)
    init_mod.ir.async_create_issue.reset_mock()
    init_mod.ir.async_delete_issue.reset_mock()
    init_mod.ir.async_get.reset_mock()
    # ha_event lever i den samme delte mocken, og reload gir den ikke et nytt liv.
    init_mod.ha_event.async_track_time_change.reset_mock(return_value=True)
    # Utgangspunktet er at varselet ikke står fra før. Testene som ser på
    # demping setter sitt eget svar her.
    init_mod.ir.async_get.return_value.async_get_issue.return_value = None
    return init_mod


def _make_hass(entries=()):
    """HA-mock med ekte hass.data, siden vakten legger avmeldingen sin der."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_entries = MagicMock(return_value=list(entries))
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


def _fake_issue(data):
    """Etterligner HAs IssueEntry så langt vakten leser den."""
    issue = MagicMock()
    issue.data = data
    return issue


def _created_issue_ids(init_mod) -> list[str]:
    return [call.args[2] for call in init_mod.ir.async_create_issue.call_args_list]


def _deleted_issue_ids(init_mod) -> list[str]:
    return [call.args[2] for call in init_mod.ir.async_delete_issue.call_args_list]


def _norgespris_id(init_mod, entry_id: str) -> str:
    return f"{init_mod.NORGESPRIS_ISSUE_PREFIX}{entry_id}"


# ---------------------------------------------------------------------------
# Satsvarselet: hele integrasjonen, ett varsel
# ---------------------------------------------------------------------------


def test_satser_utdatert_varsel_etter_aarsskifte(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 1, 5, 12, 0, tzinfo=OSLO))
    assert init_module.SATSER_ISSUE_ID in _created_issue_ids(init_module)


def test_ingen_satsvarsel_i_gjeldende_aar(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2026, 6, 15, 12, 0, tzinfo=OSLO))
    assert init_module.SATSER_ISSUE_ID not in _created_issue_ids(init_module)
    # Skal ryddes bort under terskelen, så varselet forsvinner av seg selv når
    # satsene er oppdatert.
    assert init_module.SATSER_ISSUE_ID in _deleted_issue_ids(init_module)


def test_ingen_satsvarsel_uten_anlegg(init_module):
    """Et varsel om satsene til et anlegg som ikke finnes er ingen å varsle."""
    init_module._sjekk_satsvakt(_make_hass([]), datetime(2027, 1, 5, 12, 0, tzinfo=OSLO))
    assert init_module.SATSER_ISSUE_ID not in _created_issue_ids(init_module)


def test_satsvakten_leser_lokal_tid_ikke_utc(init_module):
    """Nyttårsnatt klokken 00:30 norsk tid er UTC fortsatt i fjor.

    Skatteåret skifter ved midnatt norsk tid. Leste vakten `utcnow().year`, ville
    varselet blitt holdt tilbake den første timen av det nye året, altså nettopp
    da satsene ble utdaterte.
    """
    nyttaarsnatt = datetime(2027, 1, 1, 0, 30, tzinfo=OSLO)
    assert nyttaarsnatt.astimezone(ZoneInfo("UTC")).year == 2026

    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)
    init_module._sjekk_satsvakt(_make_hass([entry]), nyttaarsnatt)
    assert init_module.SATSER_ISSUE_ID in _created_issue_ids(init_module)


def test_ingen_satsvarsel_siste_time_av_gammelt_aar(init_module):
    """Og motsatt: 23:30 nyttårsaften er satsene fortsatt gyldige."""
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2026, 12, 31, 23, 30, tzinfo=OSLO))
    assert init_module.SATSER_ISSUE_ID not in _created_issue_ids(init_module)


# ---------------------------------------------------------------------------
# Norgespris-varselet: ett anlegg, ett varsel
# ---------------------------------------------------------------------------


def test_norgespris_utlopt_kun_for_norgespris_kunde(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))
    created = _created_issue_ids(init_module)
    assert _norgespris_id(init_module, ENTRY_A) in created
    assert init_module.SATSER_ISSUE_ID in created


def test_ingen_norgespris_varsel_uten_norgespris(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))
    assert _norgespris_id(init_module, ENTRY_A) not in _created_issue_ids(init_module)
    assert _norgespris_id(init_module, ENTRY_A) in _deleted_issue_ids(init_module)


def test_ingen_norgespris_varsel_for_ordningen_utloper(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2026, 8, 1, 12, 0, tzinfo=OSLO))
    assert _norgespris_id(init_module, ENTRY_A) not in _created_issue_ids(init_module)


def test_to_anlegg_kan_ikke_slette_hverandres_norgespris_varsel(init_module):
    """Anlegg A har Norgespris, anlegg B har spotavtale.

    Med ett globalt id-nummer avgjorde rekkefølgen hvem som vant: B slettet
    varselet til A. Nå har hvert anlegg sitt eget, og B rører bare sitt.
    """
    a = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    b = _make_entry(entry_id=ENTRY_B, har_norgespris=False)

    init_module._sjekk_satsvakt(_make_hass([a, b]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))

    assert _created_issue_ids(init_module).count(_norgespris_id(init_module, ENTRY_A)) == 1
    assert _norgespris_id(init_module, ENTRY_A) not in _deleted_issue_ids(init_module)
    assert _norgespris_id(init_module, ENTRY_B) in _deleted_issue_ids(init_module)
    assert _norgespris_id(init_module, ENTRY_B) not in _created_issue_ids(init_module)


def test_rekkefolgen_mellom_anlegg_spiller_ingen_rolle(init_module):
    """Samme prøve med anleggene i motsatt rekkefølge, siden feilen var en kappestrid."""
    a = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    b = _make_entry(entry_id=ENTRY_B, har_norgespris=False)

    init_module._sjekk_satsvakt(_make_hass([b, a]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))

    assert _norgespris_id(init_module, ENTRY_A) in _created_issue_ids(init_module)
    assert _norgespris_id(init_module, ENTRY_A) not in _deleted_issue_ids(init_module)


def test_gammelt_globalt_norgespris_varsel_ryddes(init_module):
    """Id-en uten entry_id er fra før varselet ble per anlegg, og skal bort."""
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))
    assert "norgespris_utlopt" in _deleted_issue_ids(init_module)


def test_slettet_anlegg_rydder_sitt_norgespris_varsel(init_module):
    """async_remove_entry tar alt som er suffikset med entry_id, også vårt."""
    hass = _make_hass()
    registry = MagicMock()
    registry.issues = {
        (init_module.DOMAIN, _norgespris_id(init_module, ENTRY_A)): MagicMock(),
        (init_module.DOMAIN, _norgespris_id(init_module, ENTRY_B)): MagicMock(),
        (init_module.DOMAIN, init_module.SATSER_ISSUE_ID): MagicMock(),
    }
    init_module.ir.async_get.return_value = registry

    asyncio.run(init_module.async_remove_entry(hass, _make_entry(entry_id=ENTRY_A)))

    slettede = _deleted_issue_ids(init_module)
    assert slettede == [_norgespris_id(init_module, ENTRY_A)]


# ---------------------------------------------------------------------------
# Demping med utløpsdato
# ---------------------------------------------------------------------------


def test_demping_overlever_omstart_samme_aar(init_module):
    """Har brukeren tatt stilling til varselet, skal en omstart ikke vekke det.

    HA husker dempingen på selve issuen. Sletter vi og reiser på nytt, ryker
    den, så varselet skal bare oppdateres så lenge året er det samme.
    """
    init_module.ir.async_get.return_value.async_get_issue.return_value = _fake_issue(
        {init_module._AAR_I_ISSUE: 2027}
    )
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)

    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 6, 1, 12, 0, tzinfo=OSLO))

    assert init_module.SATSER_ISSUE_ID in _created_issue_ids(init_module)
    assert init_module.SATSER_ISSUE_ID not in _deleted_issue_ids(init_module)


def test_demping_utloper_ved_neste_aarsskifte(init_module):
    """Et nytt år er et nytt varsel. Dempingen fra i fjor gjelder ikke det."""
    init_module.ir.async_get.return_value.async_get_issue.return_value = _fake_issue(
        {init_module._AAR_I_ISSUE: 2027}
    )
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)

    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2028, 1, 2, 12, 0, tzinfo=OSLO))

    # Slettingen tar dempingen med seg, og varselet reises på nytt etterpå.
    assert init_module.SATSER_ISSUE_ID in _deleted_issue_ids(init_module)
    assert init_module.SATSER_ISSUE_ID in _created_issue_ids(init_module)


def test_varsel_uten_aarstall_regnes_som_udempet(init_module):
    """Et varsel fra en eldre versjon bærer ingen dato, og kan ikke stoles på."""
    init_module.ir.async_get.return_value.async_get_issue.return_value = _fake_issue(None)
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=False)

    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 6, 1, 12, 0, tzinfo=OSLO))

    assert init_module.SATSER_ISSUE_ID in _deleted_issue_ids(init_module)
    assert init_module.SATSER_ISSUE_ID in _created_issue_ids(init_module)


def test_aarstallet_foelger_med_varselet(init_module):
    """Uten året på issuen har dempingen ingenting å utløpe mot."""
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    init_module._sjekk_satsvakt(_make_hass([entry]), datetime(2027, 3, 1, 12, 0, tzinfo=OSLO))

    for call in init_module.ir.async_create_issue.call_args_list:
        assert call.kwargs["data"] == {init_module._AAR_I_ISSUE: 2027}


# ---------------------------------------------------------------------------
# Den daglige kjøringen
# ---------------------------------------------------------------------------


def test_vakten_planlegges_fem_over_midnatt(init_module):
    hass = _make_hass([_make_entry(entry_id=ENTRY_A)])
    init_module._start_satsvakt(hass)

    kall = init_module.ha_event.async_track_time_change.call_args
    assert kall.kwargs == {"hour": 0, "minute": 5, "second": 0}


def test_aarsskiftet_oppdages_uten_omstart(init_module):
    """Selve poenget: installasjonen har stått siden i fjor, og varselet kommer.

    Vakten registreres ved oppstart i desember, kalenderen ruller, og den
    planlagte kjøringen finner varselet uten at noen har startet HA på nytt.
    """
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    hass = _make_hass([entry])
    init_module._start_satsvakt(hass)

    tikk = init_module.ha_event.async_track_time_change.call_args.args[1]
    asyncio.run(tikk(datetime(2027, 1, 1, 0, 5, tzinfo=OSLO)))

    created = _created_issue_ids(init_module)
    assert init_module.SATSER_ISSUE_ID in created
    assert _norgespris_id(init_module, ENTRY_A) in created


def test_daglig_tikk_i_gjeldende_aar_varsler_ikke(init_module):
    entry = _make_entry(entry_id=ENTRY_A, har_norgespris=True)
    hass = _make_hass([entry])
    init_module._start_satsvakt(hass)

    tikk = init_module.ha_event.async_track_time_change.call_args.args[1]
    asyncio.run(tikk(datetime(2026, 12, 31, 0, 5, tzinfo=OSLO)))

    assert _created_issue_ids(init_module) == []


def test_vakten_registreres_en_gang_for_flere_anlegg(init_module):
    hass = _make_hass([_make_entry(entry_id=ENTRY_A), _make_entry(entry_id=ENTRY_B)])
    init_module._start_satsvakt(hass)
    init_module._start_satsvakt(hass)

    assert init_module.ha_event.async_track_time_change.call_count == 1


def test_vakten_meldes_av_naar_siste_anlegg_er_ute(init_module):
    entry = _make_entry(entry_id=ENTRY_A)
    hass = _make_hass([entry])
    avmelding = MagicMock()
    init_module.ha_event.async_track_time_change.return_value = avmelding
    init_module._start_satsvakt(hass)

    asyncio.run(init_module.async_unload_entry(hass, entry))

    avmelding.assert_called_once_with()
    assert init_module._SATSVAKT_UNSUB not in hass.data[init_module.DOMAIN]


def test_vakten_staar_naar_det_er_flere_anlegg_igjen(init_module):
    a = _make_entry(entry_id=ENTRY_A)
    b = _make_entry(entry_id=ENTRY_B)
    hass = _make_hass([a, b])
    avmelding = MagicMock()
    init_module.ha_event.async_track_time_change.return_value = avmelding
    init_module._start_satsvakt(hass)

    asyncio.run(init_module.async_unload_entry(hass, a))

    avmelding.assert_not_called()
    assert init_module._SATSVAKT_UNSUB in hass.data[init_module.DOMAIN]
