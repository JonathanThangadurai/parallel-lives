"""The comparison math: unit-independent, so two markets in different currencies
can be compared without an exchange-rate assumption.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketShape:
    label: str
    complete_days: int
    coefficient_of_variation: float
    normalized_hourly_shape: list[float | None]  # 24 values, index = local hour


def daily_normalized_shape(rows: list[tuple[datetime, float]], min_hours: int = 20) -> MarketShape | None:
    """rows: (local-time timestamp, price) pairs, any timezone the caller already localized.

    For each day with at least `min_hours` readings, divides every hour's price by
    that day's own mean (so a day's shape is independent of its absolute price level),
    then averages the normalized value for each hour-of-day across all qualifying days.
    Returns None if no day has enough readings.
    """
    by_day: dict = defaultdict(dict)
    for ts, price in rows:
        by_day[ts.date()][ts.hour] = price

    hourly_normalized: dict = defaultdict(list)
    covs = []
    complete_days = 0
    for _day, hours in by_day.items():
        if len(hours) < min_hours:
            continue
        complete_days += 1
        prices = list(hours.values())
        mean = statistics.mean(prices)
        if mean == 0:
            continue
        covs.append(statistics.pstdev(prices) / mean)
        for hour, price in hours.items():
            hourly_normalized[hour].append(price / mean)

    if complete_days == 0:
        return None

    shape = [
        statistics.mean(hourly_normalized[h]) if hourly_normalized[h] else None
        for h in range(24)
    ]
    return MarketShape(
        label="",
        complete_days=complete_days,
        coefficient_of_variation=statistics.mean(covs) if covs else 0.0,
        normalized_hourly_shape=shape,
    )


def pearson(a: list[float], b: list[float]) -> float:
    """Standard Pearson correlation coefficient. Returns 0.0 for degenerate (zero-variance) input."""
    if len(a) != len(b) or len(a) < 2:
        raise ValueError("pearson requires two equal-length sequences of at least 2 points")
    mean_a, mean_b = statistics.mean(a), statistics.mean(b)
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(len(a)))
    std_a = sum((x - mean_a) ** 2 for x in a) ** 0.5
    std_b = sum((x - mean_b) ** 2 for x in b) ** 0.5
    if std_a == 0 or std_b == 0:
        return 0.0
    return cov / (std_a * std_b)
