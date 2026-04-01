"""Tests for diagnostics.py — async_get_config_entry_diagnostics.

Verifies that the diagnostics output has the correct structure
and includes all required sections.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from stromkalkulator.diagnostics import async_get_config_entry_diagnostics


@pytest.fixture
def mock_hass():
    return MagicMock()


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator._dso_id = "bkk"
    coordinator.dso = {"name": "BKK"}
    coordinator.energiledd_dag = 0.4613
    coordinator.energiledd_natt = 0.2329
    coordinator.kapasitetstrinn = [
        (2, 155), (5, 250), (10, 415), (15, 600), (20, 770),
        (25, 940), (50, 1800), (75, 2650), (100, 3500), (float("inf"), 6900),
    ]
    coordinator.data = {
        "energiledd": 0.4613,
        "spot_price": 1.20,
        "total_price": 1.50,
    }
    return coordinator


@pytest.fixture
def mock_entry(mock_coordinator):
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.version = 1
    entry.domain = "stromkalkulator"
    entry.title = "Strømkalkulator BKK"
    entry.runtime_data = mock_coordinator
    entry.data = {
        "tso": "bkk",
        "avgiftssone": "standard",
        "har_norgespris": False,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.nordpool",
        "electricity_provider_price_sensor": None,
    }
    return entry


class TestDiagnosticsStructure:
    """Verify the diagnostics output structure."""

    def test_returns_dict(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert isinstance(result, dict)

    def test_has_integration_section(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert "integration" in result
        assert "version" in result["integration"]
        assert "domain" in result["integration"]
        assert "title" in result["integration"]

    def test_has_config_entry_section(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert "config_entry" in result
        assert "entry_id" in result["config_entry"]
        assert "data" in result["config_entry"]

    def test_has_sensor_entity_ids(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert "sensor_entity_ids" in result
        assert "power_sensor" in result["sensor_entity_ids"]
        assert "spot_price_sensor" in result["sensor_entity_ids"]

    def test_has_dso_info(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert "dso_info" in result
        assert result["dso_info"]["id"] == "bkk"
        assert result["dso_info"]["name"] == "BKK"
        assert result["dso_info"]["energiledd_dag"] == 0.4613
        assert result["dso_info"]["energiledd_natt"] == 0.2329
        assert result["dso_info"]["kapasitetstrinn_count"] == 10

    def test_has_coordinator_data(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert "coordinator_data" in result
        assert result["coordinator_data"]["energiledd"] == 0.4613

    def test_coordinator_data_empty_when_no_data(self, mock_hass, mock_entry, mock_coordinator):
        mock_coordinator.data = None
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert result["coordinator_data"] == {}

    def test_config_entry_includes_dso(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert result["config_entry"]["data"]["dso"] == "bkk"

    def test_config_entry_includes_avgiftssone(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert result["config_entry"]["data"]["avgiftssone"] == "standard"

    def test_config_entry_includes_har_norgespris(self, mock_hass, mock_entry):
        result = asyncio.run(async_get_config_entry_diagnostics(mock_hass, mock_entry))
        assert result["config_entry"]["data"]["har_norgespris"] is False
