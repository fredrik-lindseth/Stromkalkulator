"""Tester for satsvakt: repair-varsel ved utdaterte satser og utløpt Norgespris.

_check_stale_rates skal opprette et informativt repair-issue når kalenderåret er
kommet forbi året satsene er verifisert for (SATSER_GJELDER_AAR), og et eget varsel
for Norgespris-kunder når ordningen kan ha opphørt (NORGESPRIS_SLUTT_AAR). Under
terskelen skal issuene slettes (auto-opprydding når satsene er oppdatert).
"""

from __future__ import annotations

import importlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry


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
    return init_mod


def _created_issue_ids(init_mod) -> list[str]:
    return [call.args[2] for call in init_mod.ir.async_create_issue.call_args_list]


def _deleted_issue_ids(init_mod) -> list[str]:
    return [call.args[2] for call in init_mod.ir.async_delete_issue.call_args_list]


def test_satser_utdatert_varsel_etter_aarsskifte(init_module):
    init_module.dt_util.now.return_value = datetime(2027, 1, 5, 12, 0)
    init_module._check_stale_rates(MagicMock(), _make_entry(har_norgespris=False))
    assert "satser_utdatert" in _created_issue_ids(init_module)


def test_ingen_satsvarsel_i_gjeldende_aar(init_module):
    init_module.dt_util.now.return_value = datetime(2026, 6, 15, 12, 0)
    init_module._check_stale_rates(MagicMock(), _make_entry(har_norgespris=False))
    assert "satser_utdatert" not in _created_issue_ids(init_module)
    # Skal ryddes bort under terskelen.
    assert "satser_utdatert" in _deleted_issue_ids(init_module)


def test_norgespris_utlopt_kun_for_norgespris_kunde(init_module):
    init_module.dt_util.now.return_value = datetime(2027, 3, 1, 12, 0)
    init_module._check_stale_rates(MagicMock(), _make_entry(har_norgespris=True))
    created = _created_issue_ids(init_module)
    assert "norgespris_utlopt" in created
    assert "satser_utdatert" in created


def test_ingen_norgespris_varsel_uten_norgespris(init_module):
    init_module.dt_util.now.return_value = datetime(2027, 3, 1, 12, 0)
    init_module._check_stale_rates(MagicMock(), _make_entry(har_norgespris=False))
    assert "norgespris_utlopt" not in _created_issue_ids(init_module)
    assert "norgespris_utlopt" in _deleted_issue_ids(init_module)
