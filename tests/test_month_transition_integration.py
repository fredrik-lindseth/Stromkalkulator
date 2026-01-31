"""Integration tests for month transition and previous month data storage.

These tests simulate the coordinator's behavior during month transitions
to verify that previous month data is correctly preserved.

Run with: pipx run pytest tests/test_month_transition_integration.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest


class MockStore:
    """Mock for Home Assistant's Store class."""

    def __init__(self):
        self.data: dict[str, Any] = {}

    def async_load(self) -> dict[str, Any] | None:
        """Load stored data (synchronous mock)."""
        return self.data if self.data else None

    def async_save(self, data: dict[str, Any]) -> None:
        """Save data to store (synchronous mock)."""
        self.data = data.copy()


class CoordinatorSimulator:
    """Simulates the NettleieCoordinator for testing month transitions.

    This class replicates the key logic from coordinator.py without
    requiring Home Assistant infrastructure.
    """

    def __init__(self, tso_id: str = "bkk"):
        # Current month tracking
        self._current_month: int = datetime.now().month
        self._daily_max_power: dict[str, float] = {}
        self._monthly_consumption: dict[str, float] = {"dag": 0.0, "natt": 0.0}

        # Previous month storage
        self._previous_month_consumption: dict[str, float] = {"dag": 0.0, "natt": 0.0}
        self._previous_month_top_3: dict[str, float] = {}
        self._previous_month_name: str | None = None

        # Mock store
        self._store = MockStore()
        self._store_loaded = False

        # TSO config (BKK defaults)
        self.energiledd_dag = 0.4613
        self.energiledd_natt = 0.2329
        self.kapasitetstrinn = [
            (2, 155),
            (5, 250),
            (10, 415),
            (15, 600),
            (20, 770),
            (25, 940),
            (50, 1800),
            (75, 2650),
            (100, 3500),
            (float("inf"), 6900),
        ]

    def _format_month_name(self, dt: datetime) -> str:
        """Format date as Norwegian month name with year."""
        months = [
            "januar",
            "februar",
            "mars",
            "april",
            "mai",
            "juni",
            "juli",
            "august",
            "september",
            "oktober",
            "november",
            "desember",
        ]
        return f"{months[dt.month - 1]} {dt.year}"

    def _get_top_3_days(self) -> dict[str, float]:
        """Get the top 3 days with highest power consumption."""
        sorted_days = sorted(self._daily_max_power.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_days[:3])

    def _is_day_rate(self, dt: datetime) -> bool:
        """Check if current time is day rate."""
        return dt.weekday() < 5 and 6 <= dt.hour < 22

    def simulate_update(self, now: datetime, power_kw: float = 3.0) -> dict[str, Any]:
        """Simulate a coordinator update at the given time."""

        # Load stored data on first run
        if not self._store_loaded:
            self._load_stored_data()
            self._store_loaded = True

        # Check for month transition
        if now.month != self._current_month:
            # Save previous month's data before reset
            self._previous_month_consumption = self._monthly_consumption.copy()
            self._previous_month_top_3 = self._get_top_3_days()

            # Format previous month name
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            self._previous_month_name = self._format_month_name(prev_month_date)

            # Reset current month data
            self._daily_max_power = {}
            self._monthly_consumption = {"dag": 0.0, "natt": 0.0}
            self._current_month = now.month
            self._save_stored_data()

        # Update daily max power
        today_str = now.strftime("%Y-%m-%d")
        old_max = self._daily_max_power.get(today_str, 0)
        if power_kw > old_max:
            self._daily_max_power[today_str] = power_kw

        # Add consumption (simulate 1 minute interval)
        tariff = "dag" if self._is_day_rate(now) else "natt"
        self._monthly_consumption[tariff] += power_kw * (1 / 60)  # 1 minute in hours

        self._save_stored_data()

        # Return data dict similar to coordinator
        top_3 = self._get_top_3_days()
        prev_top_3 = self._previous_month_top_3

        return {
            "current_month": self._current_month,
            "monthly_consumption_dag_kwh": round(self._monthly_consumption["dag"], 3),
            "monthly_consumption_natt_kwh": round(self._monthly_consumption["natt"], 3),
            "monthly_consumption_total_kwh": round(
                self._monthly_consumption["dag"] + self._monthly_consumption["natt"], 3
            ),
            "top_3_days": top_3,
            "previous_month_consumption_dag_kwh": round(self._previous_month_consumption["dag"], 3),
            "previous_month_consumption_natt_kwh": round(self._previous_month_consumption["natt"], 3),
            "previous_month_consumption_total_kwh": round(
                self._previous_month_consumption["dag"] + self._previous_month_consumption["natt"], 3
            ),
            "previous_month_top_3": prev_top_3,
            "previous_month_avg_top_3_kw": round(sum(prev_top_3.values()) / max(len(prev_top_3), 1), 2)
            if prev_top_3
            else 0.0,
            "previous_month_name": self._previous_month_name,
        }

    def _load_stored_data(self) -> None:
        """Load stored data."""
        data = self._store.async_load()
        if data:
            self._daily_max_power = data.get("daily_max_power", {})
            self._monthly_consumption = data.get("monthly_consumption", {"dag": 0.0, "natt": 0.0})
            self._previous_month_consumption = data.get("previous_month_consumption", {"dag": 0.0, "natt": 0.0})
            self._previous_month_top_3 = data.get("previous_month_top_3", {})
            self._previous_month_name = data.get("previous_month_name")
            stored_month = data.get("current_month")
            if stored_month:
                self._current_month = stored_month

    def _save_stored_data(self) -> None:
        """Save data to store."""
        data = {
            "daily_max_power": self._daily_max_power,
            "monthly_consumption": self._monthly_consumption,
            "current_month": self._current_month,
            "previous_month_consumption": self._previous_month_consumption,
            "previous_month_top_3": self._previous_month_top_3,
            "previous_month_name": self._previous_month_name,
        }
        self._store.async_save(data)


class TestMonthTransitionIntegration:
    """Integration tests for month transition behavior."""

    def test_full_month_simulation(self):
        """Simulate a full month of usage and verify month transition."""
        coordinator = CoordinatorSimulator()

        # Simulate January 2026 - add consumption over several days
        january_days = [
            # (day, hour, power_kw)
            (5, 10, 5.2),  # Day 5: 5.2 kW peak (day rate)
            (5, 14, 3.0),  # Day 5: lower usage
            (10, 18, 4.8),  # Day 10: 4.8 kW peak (day rate)
            (15, 20, 4.5),  # Day 15: 4.5 kW peak (day rate)
            (20, 8, 3.0),  # Day 20: 3.0 kW (day rate)
            (25, 23, 2.0),  # Day 25: 2.0 kW (night rate)
            (28, 12, 6.0),  # Day 28: 6.0 kW peak - new top! (day rate)
            (31, 15, 3.5),  # Day 31: 3.5 kW (day rate)
        ]

        for day, hour, power in january_days:
            dt = datetime(2026, 1, day, hour, 0)
            coordinator._current_month = 1  # Force January
            coordinator.simulate_update(dt, power)

        # Verify January state before transition
        data_jan = coordinator.simulate_update(datetime(2026, 1, 31, 23, 59), 1.0)
        assert data_jan["current_month"] == 1
        assert data_jan["monthly_consumption_dag_kwh"] > 0
        assert len(coordinator._daily_max_power) > 0

        # Get January's top 3 before transition
        jan_top_3 = coordinator._get_top_3_days()
        jan_consumption = coordinator._monthly_consumption.copy()

        # Trigger month transition - first update in February
        data_feb = coordinator.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        # Verify transition occurred
        assert data_feb["current_month"] == 2
        assert data_feb["previous_month_name"] == "januar 2026"

        # Verify previous month data was saved
        assert data_feb["previous_month_consumption_dag_kwh"] == round(jan_consumption["dag"], 3)
        assert data_feb["previous_month_consumption_natt_kwh"] == round(jan_consumption["natt"], 3)
        assert data_feb["previous_month_top_3"] == jan_top_3

        # Verify current month was reset
        assert data_feb["monthly_consumption_dag_kwh"] < 0.1  # Just the one update
        assert len(coordinator._daily_max_power) == 1  # Only Feb 1

    def test_top_3_preserved_correctly(self):
        """Verify top 3 power days are correctly preserved across month transition."""
        coordinator = CoordinatorSimulator()
        coordinator._current_month = 1

        # Create specific top 3 pattern in January
        test_data = [
            ("2026-01-05", 7.5),  # Highest
            ("2026-01-12", 6.2),  # Second
            ("2026-01-20", 5.8),  # Third
            ("2026-01-25", 3.0),  # Not in top 3
        ]

        for date_str, power in test_data:
            coordinator._daily_max_power[date_str] = power

        # Add some consumption
        coordinator._monthly_consumption = {"dag": 150.5, "natt": 80.3}

        # Trigger transition
        coordinator.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        # Verify top 3 was preserved
        prev_top_3 = coordinator._previous_month_top_3
        assert len(prev_top_3) == 3
        assert prev_top_3.get("2026-01-05") == 7.5
        assert prev_top_3.get("2026-01-12") == 6.2
        assert prev_top_3.get("2026-01-20") == 5.8
        assert "2026-01-25" not in prev_top_3  # 4th place excluded

    def test_year_boundary_transition(self):
        """Test month transition across year boundary (December -> January)."""
        coordinator = CoordinatorSimulator()
        coordinator._current_month = 12

        # Add December data
        coordinator._daily_max_power = {
            "2025-12-10": 5.0,
            "2025-12-15": 4.5,
            "2025-12-20": 4.0,
        }
        coordinator._monthly_consumption = {"dag": 200.0, "natt": 100.0}

        # Trigger year boundary transition
        data = coordinator.simulate_update(datetime(2026, 1, 1, 0, 1), 2.0)

        assert data["current_month"] == 1
        assert data["previous_month_name"] == "desember 2025"
        assert data["previous_month_consumption_total_kwh"] == 300.0

    def test_persistence_survives_restart(self):
        """Test that previous month data survives a simulated restart."""
        coordinator1 = CoordinatorSimulator()
        coordinator1._current_month = 1

        # Set up January data
        coordinator1._daily_max_power = {"2026-01-15": 5.0, "2026-01-20": 4.5, "2026-01-25": 4.0}
        coordinator1._monthly_consumption = {"dag": 100.0, "natt": 50.0}

        # Trigger transition to February
        coordinator1.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        # Get the stored data
        stored_data = coordinator1._store.data

        # Create new coordinator (simulate restart)
        coordinator2 = CoordinatorSimulator()
        coordinator2._store.data = stored_data  # Restore from "disk"

        # Load and verify
        data = coordinator2.simulate_update(datetime(2026, 2, 1, 0, 2), 2.0)

        assert data["previous_month_name"] == "januar 2026"
        assert data["previous_month_consumption_dag_kwh"] == 100.0
        assert data["previous_month_consumption_natt_kwh"] == 50.0

    def test_nettleie_calculation_from_previous_month(self):
        """Test that nettleie can be calculated from previous month data."""
        coordinator = CoordinatorSimulator()
        coordinator._current_month = 1

        # January data
        coordinator._daily_max_power = {
            "2026-01-05": 3.5,  # Top 1
            "2026-01-12": 3.2,  # Top 2
            "2026-01-20": 3.0,  # Top 3
        }
        coordinator._monthly_consumption = {"dag": 150.0, "natt": 80.0}

        # Transition
        coordinator.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        # Calculate nettleie from previous month
        dag_kwh = coordinator._previous_month_consumption["dag"]
        natt_kwh = coordinator._previous_month_consumption["natt"]
        top_3 = coordinator._previous_month_top_3

        # Energiledd
        energiledd_dag = dag_kwh * coordinator.energiledd_dag  # 150 * 0.4613 = 69.20
        energiledd_natt = natt_kwh * coordinator.energiledd_natt  # 80 * 0.2329 = 18.63

        # Kapasitetsledd from top 3 average
        avg_top_3 = sum(top_3.values()) / len(top_3)  # (3.5+3.2+3.0)/3 = 3.23 kW

        # Find tier (3.23 kW is in 2-5 kW tier = 250 kr)
        kapasitetsledd = 0
        for threshold, price in coordinator.kapasitetstrinn:
            if avg_top_3 <= threshold:
                kapasitetsledd = price
                break

        total_nettleie = energiledd_dag + energiledd_natt + kapasitetsledd

        assert energiledd_dag == pytest.approx(69.195, abs=0.01)
        assert round(energiledd_natt, 2) == 18.63
        assert kapasitetsledd == 250  # 2-5 kW tier
        assert round(total_nettleie, 2) == 337.83

    def test_empty_month_transition(self):
        """Test transition when current month has no data."""
        coordinator = CoordinatorSimulator()
        coordinator._current_month = 1

        # No data added for January

        # Transition
        data = coordinator.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        # Should still work, just with zeros
        assert data["previous_month_name"] == "januar 2026"
        assert data["previous_month_consumption_total_kwh"] == 0.0
        assert data["previous_month_top_3"] == {}
        assert data["previous_month_avg_top_3_kw"] == 0.0


class TestMonthTransitionEdgeCases:
    """Edge case tests for month transitions."""

    def test_multiple_updates_same_minute(self):
        """Test multiple updates in the same minute don't cause issues."""
        coordinator = CoordinatorSimulator()
        coordinator._current_month = 1
        coordinator._monthly_consumption = {"dag": 100.0, "natt": 50.0}

        # Multiple updates at transition time
        dt = datetime(2026, 2, 1, 0, 1)
        data = None
        for _ in range(5):
            data = coordinator.simulate_update(dt, 2.0)

        # Should only transition once
        assert data is not None
        assert data["previous_month_name"] == "januar 2026"
        assert data["current_month"] == 2

    def test_previous_month_only_stores_one_month(self):
        """Verify that transitioning again overwrites previous month."""
        coordinator = CoordinatorSimulator()

        # January -> February
        coordinator._current_month = 1
        coordinator._monthly_consumption = {"dag": 100.0, "natt": 50.0}
        coordinator.simulate_update(datetime(2026, 2, 1, 0, 1), 2.0)

        assert coordinator._previous_month_name == "januar 2026"

        # Add February consumption
        coordinator._monthly_consumption = {"dag": 120.0, "natt": 60.0}

        # February -> March
        coordinator.simulate_update(datetime(2026, 3, 1, 0, 1), 2.0)

        # January data should be gone, replaced by February
        assert coordinator._previous_month_name == "februar 2026"
        assert coordinator._previous_month_consumption["dag"] == 120.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
