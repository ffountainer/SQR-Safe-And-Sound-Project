"""
Domain error tests for business logic.

These tests focus on error conditions and edge cases in the domain logic,
ensuring robustness against invalid inputs and unexpected scenarios.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.business_logic import (
    check_status,
    infer_inferred_status,
    INFERRED_FREE,
    INFERRED_BUSY,
    INFERRED_UNAVAILABLE,
    INFERRED_PROBABLY_FREE,
    STATUS_FREE,
    STATUS_BUSY,
    STATUS_UNAVAILABLE,
)


class TestCheckStatusErrors:
    """Test error conditions for check_status function."""

    def test_check_status_none_input(self):
        """Test check_status with None input."""
        result = check_status(None)
        assert result == INFERRED_FREE

    def test_check_status_unavailable(self):
        """Test check_status with unavailable status."""
        result = check_status(STATUS_UNAVAILABLE)
        assert result == INFERRED_UNAVAILABLE

    def test_check_status_free(self):
        """Test check_status with free status."""
        result = check_status(STATUS_FREE)
        assert result == INFERRED_FREE

    def test_check_status_unknown_status(self):
        """Test check_status with unknown status string."""
        result = check_status("unknown_status")
        assert result == INFERRED_FREE  # Failsafe behavior

    def test_check_status_empty_string(self):
        """Test check_status with empty string."""
        result = check_status("")
        assert result == INFERRED_FREE

    def test_check_status_busy_returns_none(self):
        """Test that check_status returns None for busy (handled elsewhere)."""
        result = check_status(STATUS_BUSY)
        assert result is None


class TestInferInferredStatusErrors:
    """Test error conditions for infer_inferred_status function."""

    def test_infer_inferred_status_all_none(self):
        """Test with all None inputs except now."""
        now = datetime.now(timezone.utc)
        result = infer_inferred_status(None, None, None, now)
        assert result == INFERRED_FREE

    def test_infer_inferred_status_invalid_status_type(self):
        """Test with invalid status type (not string)."""
        now = datetime.now(timezone.utc)
        result = infer_inferred_status(123, None, None, now)
        assert result == INFERRED_FREE  # Failsafe behavior

    def test_infer_inferred_status_invalid_datetime_type(self):
        """Test with invalid datetime type."""
        now = datetime.now(timezone.utc)
        with pytest.raises(AttributeError):
            infer_inferred_status(STATUS_BUSY, "invalid_date", None, now)

    def test_infer_inferred_status_invalid_time_remaining_type(self):
        """Test with invalid time_remaining type."""
        now = datetime.now(timezone.utc)
        report_time = now - timedelta(minutes=5)
        with pytest.raises(TypeError):
            infer_inferred_status(STATUS_BUSY, report_time, "invalid", now)

    def test_infer_inferred_status_negative_time_remaining(self):
        """Test with negative time_remaining."""
        now = datetime.now(timezone.utc)
        report_time = now - timedelta(minutes=5)
        result = infer_inferred_status(STATUS_BUSY, report_time, -10, now)
        # Should still work, but might not make sense
        assert isinstance(result, str)

    def test_infer_inferred_status_future_report_time(self):
        """Test with report_time in the future."""
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(hours=1)
        result = infer_inferred_status(STATUS_BUSY, future_time, 30, now)
        # Should handle gracefully
        assert result == INFERRED_BUSY  # Since future report, but busy

    def test_infer_inferred_status_very_old_report(self):
        """Test with very old report time."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=365)
        result = infer_inferred_status(STATUS_BUSY, old_time, None, now)
        assert result == INFERRED_PROBABLY_FREE

    def test_infer_inferred_status_zero_time_remaining(self):
        """Test with zero time_remaining."""
        now = datetime.now(timezone.utc)
        report_time = now - timedelta(minutes=5)
        result = infer_inferred_status(STATUS_BUSY, report_time, 0, now)
        assert result == INFERRED_FREE  # Timer expired

    def test_infer_inferred_status_naive_datetime(self):
        """Test with naive datetime (no timezone)."""
        now_naive = datetime.now()
        report_time_naive = now_naive - timedelta(minutes=5)
        result = infer_inferred_status(STATUS_BUSY, report_time_naive, 10, now_naive)
        assert result == INFERRED_BUSY

    def test_infer_inferred_status_mixed_timezone(self):
        """Test with mixed timezone awareness."""
        now_utc = datetime.now(timezone.utc)
        now_naive = datetime.now()
        report_time_utc = now_utc - timedelta(minutes=5)
        result = infer_inferred_status(STATUS_BUSY, report_time_utc, 10, now_naive)
        # Should handle the conversion
        assert isinstance(result, str)


class TestBusinessLogicIntegrationErrors:
    """Test integration error scenarios."""

    def test_status_inference_with_corrupted_data(self):
        """Test inference with potentially corrupted database data."""
        now = datetime.now(timezone.utc)

        # Simulate corrupted status
        result = infer_inferred_status("corrupted", now, None, now)
        assert result == INFERRED_FREE  # Failsafe

    def test_timer_calculation_edge_cases(self):
        """Test timer calculations at boundaries."""
        now = datetime.now(timezone.utc)

        # Exactly at the end time
        report_time = now - timedelta(minutes=10)
        result = infer_inferred_status(STATUS_BUSY, report_time, 10, now)
        assert result == INFERRED_FREE  # Timer just expired

        # Just before end time
        result = infer_inferred_status(STATUS_BUSY, report_time, 11, now)
        assert result == INFERRED_BUSY