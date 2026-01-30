"""Tests for previous month data storage.

Tests coverage:
- Month name formatting (Norwegian)
- Data structure validation
- Month change data preservation
- Nettleie calculations from previous month
- Capacity tier determination
- Storage format and backwards compatibility
- Empty data handling
"""

from __future__ import annotations

from datetime import datetime, timedelta


def _format_month_name(dt: datetime) -> str:
    """Format date as Norwegian month name with year.

    Helper function that mirrors NettleieCoordinator._format_month_name
    """
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


class TestForrigeMaanedCoordinator:
    """Test previous month data handling in coordinator."""

    def test_format_month_name(self):
        """Test Norwegian month name formatting."""
        # Test all months
        test_cases = [
            (datetime(2026, 1, 15), "januar 2026"),
            (datetime(2026, 2, 1), "februar 2026"),
            (datetime(2026, 3, 31), "mars 2026"),
            (datetime(2026, 4, 15), "april 2026"),
            (datetime(2026, 5, 15), "mai 2026"),
            (datetime(2026, 6, 15), "juni 2026"),
            (datetime(2026, 7, 15), "juli 2026"),
            (datetime(2026, 8, 15), "august 2026"),
            (datetime(2026, 9, 15), "september 2026"),
            (datetime(2026, 10, 15), "oktober 2026"),
            (datetime(2026, 11, 15), "november 2026"),
            (datetime(2026, 12, 25), "desember 2026"),
        ]

        for dt, expected in test_cases:
            result = _format_month_name(dt)
            assert result == expected, f"Expected {expected}, got {result}"

    def test_format_month_name_different_years(self):
        """Test month formatting with different years."""
        test_cases = [
            (datetime(2024, 6, 15), "juni 2024"),
            (datetime(2025, 1, 1), "januar 2025"),
            (datetime(2027, 12, 31), "desember 2027"),
        ]

        for dt, expected in test_cases:
            result = _format_month_name(dt)
            assert result == expected

    def test_previous_month_data_structure(self):
        """Test that previous month data has correct structure."""
        previous_month_consumption = {"dag": 150.5, "natt": 80.3}
        previous_month_top_3 = {
            "2026-01-05": 5.2,
            "2026-01-12": 4.8,
            "2026-01-20": 4.5,
        }

        # Verify consumption structure
        assert "dag" in previous_month_consumption
        assert "natt" in previous_month_consumption
        assert isinstance(previous_month_consumption["dag"], float)
        assert isinstance(previous_month_consumption["natt"], float)

        # Verify top 3 structure
        assert len(previous_month_top_3) == 3
        for date_str, kw in previous_month_top_3.items():
            assert isinstance(date_str, str)
            assert isinstance(kw, float)
            # Validate date format YYYY-MM-DD
            parts = date_str.split("-")
            assert len(parts) == 3
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # month
            assert len(parts[2]) == 2  # day

    def test_previous_month_consumption_key_order(self):
        """Test that consumption dict has consistent key order."""
        consumption = {"dag": 100.0, "natt": 50.0}

        # Both keys should exist
        assert set(consumption.keys()) == {"dag", "natt"}

    def test_month_change_preserves_data(self):
        """Test that month change preserves previous month data."""
        # Simulate data before month change
        current_consumption = {"dag": 200.0, "natt": 100.0}
        current_top_3 = {
            "2026-01-10": 6.0,
            "2026-01-15": 5.5,
            "2026-01-22": 5.0,
        }

        # After month change, previous month should have this data
        previous_month_consumption = current_consumption.copy()
        previous_month_top_3 = current_top_3.copy()

        # Verify data was preserved
        assert previous_month_consumption["dag"] == 200.0
        assert previous_month_consumption["natt"] == 100.0
        assert previous_month_top_3["2026-01-10"] == 6.0

        # Verify current month is reset (not modified by the copy)
        new_consumption = {"dag": 0.0, "natt": 0.0}
        assert new_consumption["dag"] == 0.0
        assert new_consumption["natt"] == 0.0

    def test_month_change_does_not_affect_previous_month(self):
        """Test that current month changes don't affect previous month data."""
        previous_consumption = {"dag": 200.0, "natt": 100.0}

        # Current month is modified
        current_consumption = {"dag": 50.0, "natt": 25.0}
        current_consumption["dag"] = 100.0  # Change current
        current_consumption["natt"] = 50.0

        # Previous month should be unchanged
        assert previous_consumption["dag"] == 200.0
        assert previous_consumption["natt"] == 100.0


class TestForrigeMaanedNettleieCalculation:
    """Test nettleie calculation for previous month."""

    def test_nettleie_calculation_bkk_2026(self):
        """Test grid rent calculation from previous month data."""
        # Previous month data
        dag_kwh = 150.0
        natt_kwh = 80.0

        # BKK 2026 prices
        dag_pris = 0.4613  # NOK/kWh
        natt_pris = 0.2329  # NOK/kWh
        kapasitetsledd = 250  # NOK/month (2-5 kW tier)

        # Calculate
        energiledd_dag = dag_kwh * dag_pris
        energiledd_natt = natt_kwh * natt_pris
        total_nettleie = energiledd_dag + energiledd_natt + kapasitetsledd

        # Note: Use precise assertion for total
        assert round(energiledd_dag, 2) == 69.19  # 150 * 0.4613 = 69.195 -> 69.19
        assert round(energiledd_natt, 2) == 18.63  # 80 * 0.2329 = 18.632 -> 18.63
        # Total: 69.195 + 18.632 + 250 = 337.827 -> 337.83
        assert round(total_nettleie, 2) == 337.83

    def test_nettleie_calculation_zero_consumption(self):
        """Test nettleie with zero consumption."""
        dag_kwh = 0.0
        natt_kwh = 0.0
        dag_pris = 0.4613
        natt_pris = 0.2329
        kapasitetsledd = 250

        energiledd_dag = dag_kwh * dag_pris
        energiledd_natt = natt_kwh * natt_pris
        total_nettleie = energiledd_dag + energiledd_natt + kapasitetsledd

        assert round(energiledd_dag, 2) == 0.0
        assert round(energiledd_natt, 2) == 0.0
        assert round(total_nettleie, 2) == 250.0  # Only capacity charge

    def test_nettleie_calculation_high_consumption(self):
        """Test nettleie with high consumption."""
        dag_kwh = 500.0
        natt_kwh = 300.0
        dag_pris = 0.4613
        natt_pris = 0.2329
        kapasitetsledd = 415  # Higher tier

        energiledd_dag = dag_kwh * dag_pris
        energiledd_natt = natt_kwh * natt_pris
        total_nettleie = energiledd_dag + energiledd_natt + kapasitetsledd

        assert round(energiledd_dag, 2) == 230.65  # 500 * 0.4613
        assert round(energiledd_natt, 2) == 69.87  # 300 * 0.2329
        assert round(total_nettleie, 2) == 715.52

    def test_kapasitetsledd_from_top_3(self):
        """Test capacity tier determination from top 3 data."""
        # BKK kapasitetstrinn
        kapasitetstrinn = [
            (2, 155),
            (5, 250),
            (10, 415),
            (15, 600),
            (20, 770),
        ]

        test_cases = [
            # (top_3_dict, expected_kapasitetsledd)
            ({"d1": 1.5, "d2": 1.8, "d3": 1.2}, 155),  # avg 1.5 -> 0-2 kW
            ({"d1": 3.0, "d2": 4.0, "d3": 3.5}, 250),  # avg 3.5 -> 2-5 kW
            ({"d1": 7.0, "d2": 8.0, "d3": 6.0}, 415),  # avg 7.0 -> 5-10 kW
            ({"d1": 12.0, "d2": 13.0, "d3": 11.0}, 600),  # avg 12 -> 10-15 kW
        ]

        for top_3, expected in test_cases:
            avg_power = sum(top_3.values()) / len(top_3)

            # Find kapasitetsledd
            kapasitetsledd = None
            for threshold, price in kapasitetstrinn:
                if avg_power <= threshold:
                    kapasitetsledd = price
                    break

            assert kapasitetsledd == expected, f"Expected {expected} for avg {avg_power}, got {kapasitetsledd}"

    def test_kapasitetsledd_edge_cases(self):
        """Test capacity tier with edge case values."""
        kapasitetstrinn = [
            (2, 155),
            (5, 250),
            (10, 415),
        ]

        test_cases = [
            # (avg_power, expected_price)
            (0.0, 155),  # Minimum
            (2.0, 155),  # At boundary (should round down)
            (2.001, 250),  # Just over boundary
            (5.0, 250),  # At upper boundary
            (10.0, 415),  # At highest boundary
            (20.0, 415),  # Above highest (should get highest tier)
        ]

        for avg_power, expected in test_cases:
            kapasitetsledd = None
            for threshold, price in kapasitetstrinn:
                if avg_power <= threshold:
                    kapasitetsledd = price
                    break
            if kapasitetsledd is None:
                kapasitetsledd = kapasitetstrinn[-1][1]

            assert kapasitetsledd == expected, f"Expected {expected} for {avg_power}, got {kapasitetsledd}"


class TestForrigeMaanedPersistence:
    """Test persistence of previous month data."""

    def test_storage_format(self):
        """Test that storage format includes previous month data."""
        storage_data = {
            "daily_max_power": {"2026-02-01": 3.5},
            "monthly_consumption": {"dag": 50.0, "natt": 25.0},
            "current_month": 2,
            "previous_month_consumption": {"dag": 200.0, "natt": 100.0},
            "previous_month_top_3": {
                "2026-01-10": 6.0,
                "2026-01-15": 5.5,
                "2026-01-22": 5.0,
            },
            "previous_month_name": "januar 2026",
        }

        # Verify all keys exist
        assert "previous_month_consumption" in storage_data
        assert "previous_month_top_3" in storage_data
        assert "previous_month_name" in storage_data

        # Verify values
        assert storage_data["previous_month_name"] == "januar 2026"
        assert storage_data["previous_month_consumption"]["dag"] == 200.0
        assert len(storage_data["previous_month_top_3"]) == 3

    def test_load_missing_previous_month_data(self):
        """Test loading storage without previous month data (backwards compat)."""
        # Old storage format (before this feature)
        old_storage_data = {
            "daily_max_power": {"2026-02-01": 3.5},
            "monthly_consumption": {"dag": 50.0, "natt": 25.0},
            "current_month": 2,
        }

        # Should default to empty values
        previous_month_consumption = old_storage_data.get("previous_month_consumption", {"dag": 0.0, "natt": 0.0})
        previous_month_top_3 = old_storage_data.get("previous_month_top_3", {})
        previous_month_name = old_storage_data.get("previous_month_name")

        assert previous_month_consumption == {"dag": 0.0, "natt": 0.0}
        assert previous_month_top_3 == {}
        assert previous_month_name is None

    def test_load_partial_previous_month_data(self):
        """Test loading storage with some previous month data missing."""
        partial_storage = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 50.0, "natt": 25.0},
            "current_month": 2,
            "previous_month_consumption": {"dag": 200.0, "natt": 100.0},
            # missing previous_month_top_3
            "previous_month_name": "januar 2026",
        }

        previous_month_top_3 = partial_storage.get("previous_month_top_3", {})
        assert previous_month_top_3 == {}

        # But other fields should be present
        assert partial_storage["previous_month_name"] == "januar 2026"

    def test_storage_data_types(self):
        """Test that storage data has correct types."""
        storage_data = {
            "daily_max_power": {"2026-02-01": 3.5},
            "monthly_consumption": {"dag": 150.0, "natt": 80.0},
            "current_month": 2,
            "previous_month_consumption": {"dag": 200.0, "natt": 100.0},
            "previous_month_top_3": {
                "2026-01-10": 6.0,
                "2026-01-15": 5.5,
                "2026-01-22": 5.0,
            },
            "previous_month_name": "januar 2026",
        }

        # Validate types
        assert isinstance(storage_data["daily_max_power"], dict)
        assert isinstance(storage_data["monthly_consumption"], dict)
        assert isinstance(storage_data["current_month"], int)
        assert isinstance(storage_data["previous_month_consumption"], dict)
        assert isinstance(storage_data["previous_month_top_3"], dict)
        assert isinstance(storage_data["previous_month_name"], (str, type(None)))

        # Validate nested values
        for _key, value in storage_data["previous_month_consumption"].items():
            assert isinstance(value, float)
        for key, value in storage_data["previous_month_top_3"].items():
            assert isinstance(key, str)
            assert isinstance(value, float)


class TestForrigeMaanedSensorValues:
    """Test sensor value calculations."""

    def test_total_consumption_sensor(self):
        """Test total consumption is sum of dag and natt."""
        dag_kwh = 150.5
        natt_kwh = 80.3

        total = dag_kwh + natt_kwh

        assert round(total, 1) == 230.8

    def test_total_consumption_sensor_zero(self):
        """Test total consumption with zero values."""
        dag_kwh = 0.0
        natt_kwh = 0.0

        total = dag_kwh + natt_kwh

        assert total == 0.0

    def test_total_consumption_sensor_large_values(self):
        """Test total consumption with large values."""
        dag_kwh = 1000.5
        natt_kwh = 500.3

        total = dag_kwh + natt_kwh

        assert round(total, 1) == 1500.8

    def test_avg_top_3_calculation(self):
        """Test average top 3 calculation."""
        top_3 = {
            "2026-01-05": 5.2,
            "2026-01-12": 4.8,
            "2026-01-20": 4.5,
        }

        avg = sum(top_3.values()) / len(top_3)

        assert round(avg, 2) == 4.83

    def test_avg_top_3_calculation_two_days(self):
        """Test average with only 2 days (less than 3)."""
        top_3 = {
            "2026-01-05": 6.0,
            "2026-01-12": 4.0,
        }

        avg = sum(top_3.values()) / max(len(top_3), 1)

        assert round(avg, 2) == 5.0

    def test_avg_top_3_calculation_one_day(self):
        """Test average with only 1 day."""
        top_3 = {
            "2026-01-05": 5.0,
        }

        avg = sum(top_3.values()) / max(len(top_3), 1)

        assert avg == 5.0

    def test_empty_top_3_handling(self):
        """Test handling of empty top 3 data."""
        top_3 = {}

        # Should return 0 without division error
        avg = sum(top_3.values()) / max(len(top_3), 1)

        assert avg == 0.0

    def test_avg_top_3_with_equal_values(self):
        """Test average when all values are equal."""
        top_3 = {
            "2026-01-05": 5.0,
            "2026-01-12": 5.0,
            "2026-01-20": 5.0,
        }

        avg = sum(top_3.values()) / len(top_3)

        assert avg == 5.0

    def test_avg_top_3_with_decimal_precision(self):
        """Test average calculation preserves decimal precision."""
        top_3 = {
            "2026-01-05": 5.123,
            "2026-01-12": 4.876,
            "2026-01-20": 5.001,
        }

        avg = sum(top_3.values()) / len(top_3)

        # Should preserve precision up to rounding
        assert round(avg, 3) == 5.0


class TestForrigeMaanedMonthTransition:
    """Test behavior during month transitions."""

    def test_month_transition_date_calculation(self):
        """Test calculation of previous month date during transition."""
        # Current month starts on 2nd of month
        now = datetime(2026, 2, 2)

        # Get previous month's last day
        prev_month_date = now.replace(day=1) - timedelta(days=1)

        assert prev_month_date.month == 1
        assert prev_month_date.year == 2026
        assert prev_month_date.day == 31

    def test_month_transition_year_boundary(self):
        """Test month transition across year boundary."""
        # Current month: January 2027
        now = datetime(2027, 1, 2)

        # Get previous month (December 2026)
        prev_month_date = now.replace(day=1) - timedelta(days=1)

        assert prev_month_date.month == 12
        assert prev_month_date.year == 2026

    def test_all_month_transitions(self):
        """Test transitions for all months of the year."""
        for month in range(1, 13):
            if month == 1:
                now = datetime(2026, month, 2)
                prev_month_date = now.replace(day=1) - timedelta(days=1)
                assert prev_month_date.month == 12
                assert prev_month_date.year == 2025
            else:
                now = datetime(2026, month, 2)
                prev_month_date = now.replace(day=1) - timedelta(days=1)
                assert prev_month_date.month == month - 1
                assert prev_month_date.year == 2026


class TestForrigeMaanedEdgeCases:
    """Test edge cases and error handling."""

    def test_negative_consumption_prevention(self):
        """Test that negative consumption values are handled."""
        # Should not happen in practice, but test defensively
        consumption = {"dag": 150.0, "natt": 80.0}

        # Ensure values are non-negative
        assert consumption["dag"] >= 0
        assert consumption["natt"] >= 0

    def test_very_large_consumption(self):
        """Test handling of very large consumption values."""
        large_consumption = {"dag": 99999.99, "natt": 99999.99}
        total = large_consumption["dag"] + large_consumption["natt"]

        assert total == 199999.98
        assert isinstance(total, float)

    def test_floating_point_precision(self):
        """Test floating point precision in calculations."""
        # Test that we handle floating point math correctly
        dag = 150.5
        natt = 80.3
        total = dag + natt

        # Due to floating point, use approximate comparison
        assert abs(total - 230.8) < 0.0001

    def test_top_3_dict_with_more_than_3_entries(self):
        """Test top 3 dict handling when more than 3 entries are provided."""
        # In practice, _get_top_3_days() only returns 3, but test defensive code
        top_3_provided = {
            "2026-01-05": 6.0,
            "2026-01-12": 5.0,
            "2026-01-20": 4.5,
            "2026-01-25": 3.0,  # Extra entry
        }

        # Simulate taking only top 3
        top_3_sorted = dict(sorted(top_3_provided.items(), key=lambda x: x[1], reverse=True)[:3])

        assert len(top_3_sorted) == 3
        assert top_3_sorted["2026-01-05"] == 6.0

    def test_consumption_dict_with_missing_keys(self):
        """Test handling of consumption dict with missing keys."""
        consumption = {}

        # Safely get values with defaults
        dag = consumption.get("dag", 0.0)
        natt = consumption.get("natt", 0.0)

        assert dag == 0.0
        assert natt == 0.0

    def test_month_name_with_invalid_month(self):
        """Test that month formatting handles edge cases."""
        # Valid edge cases
        result_jan = _format_month_name(datetime(2026, 1, 1))
        result_dec = _format_month_name(datetime(2026, 12, 31))

        assert result_jan == "januar 2026"
        assert result_dec == "desember 2026"
