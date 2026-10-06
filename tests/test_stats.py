from datetime import datetime

import pytest

from parallel_lives.stats import daily_normalized_shape, pearson


def test_pearson_identical_sequences_is_one():
    assert pearson([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)


def test_pearson_scaled_sequence_is_still_one():
    # correlation is scale-invariant - this is exactly why it works across currencies
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)


def test_pearson_inverted_sequence_is_negative_one():
    assert pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_pearson_constant_sequence_is_zero_not_an_error():
    # zero variance on one side makes correlation undefined in the pure math sense;
    # we define it as 0 (no detectable relationship) rather than raising or NaN-ing.
    assert pearson([5, 5, 5], [1, 2, 3]) == 0.0


def test_pearson_rejects_mismatched_or_too_short_input():
    with pytest.raises(ValueError):
        pearson([1, 2], [1, 2, 3])
    with pytest.raises(ValueError):
        pearson([1], [1])


def test_daily_normalized_shape_flat_day_has_zero_volatility():
    rows = [(datetime(2026, 1, 1, h), 7.0) for h in range(4)]
    result = daily_normalized_shape(rows, min_hours=4)
    assert result.complete_days == 1
    assert result.coefficient_of_variation == pytest.approx(0.0)
    assert result.normalized_hourly_shape[0] == pytest.approx(1.0)
    assert result.normalized_hourly_shape[1] == pytest.approx(1.0)
    assert result.normalized_hourly_shape[4] is None  # untouched hour


def test_daily_normalized_shape_hand_calculable_case():
    # mean=8, pstdev([6,10])=2, cov=2/8=0.25, normalized = 6/8=0.75 and 10/8=1.25
    rows = [(datetime(2026, 1, 1, 0), 6.0), (datetime(2026, 1, 1, 1), 10.0)]
    result = daily_normalized_shape(rows, min_hours=2)
    assert result.coefficient_of_variation == pytest.approx(0.25)
    assert result.normalized_hourly_shape[0] == pytest.approx(0.75)
    assert result.normalized_hourly_shape[1] == pytest.approx(1.25)


def test_daily_normalized_shape_skips_incomplete_days():
    # only 2 hours present, default min_hours=20 - day doesn't qualify
    rows = [(datetime(2026, 1, 1, 0), 6.0), (datetime(2026, 1, 1, 1), 10.0)]
    assert daily_normalized_shape(rows) is None


def test_daily_normalized_shape_averages_across_multiple_days():
    # two days, same shape (hour0 always 0.75x, hour1 always 1.25x of that day's mean)
    # but different absolute price levels - average should land exactly on that shape.
    rows = [
        (datetime(2026, 1, 1, 0), 6.0), (datetime(2026, 1, 1, 1), 10.0),
        (datetime(2026, 1, 2, 0), 60.0), (datetime(2026, 1, 2, 1), 100.0),
    ]
    result = daily_normalized_shape(rows, min_hours=2)
    assert result.complete_days == 2
    assert result.normalized_hourly_shape[0] == pytest.approx(0.75)
    assert result.normalized_hourly_shape[1] == pytest.approx(1.25)
