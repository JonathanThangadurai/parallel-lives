"""Daily entry point: fetch both markets, compute the comparison, append to history.

Run manually with `python -m parallel_lives.run`, or via the scheduled GitHub Actions
workflow (.github/workflows/daily.yml), which commits the updated data files back to
the repo - that commit history is the dataset's own changelog.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from parallel_lives.sources import fetch_caiso_dam, fetch_energyzero_nl
from parallel_lives.stats import daily_normalized_shape, pearson

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_PATH = DATA_DIR / "history.jsonl"
LATEST_PATH = DATA_DIR / "latest.json"

DEFAULT_WINDOW_DAYS = 14


def run(days: int = DEFAULT_WINDOW_DAYS) -> dict:
    caiso_fetch = fetch_caiso_dam(days)
    nl_fetch = fetch_energyzero_nl(days)

    caiso_shape = daily_normalized_shape(caiso_fetch.rows)
    nl_shape = daily_normalized_shape(nl_fetch.rows)

    if caiso_shape is None or nl_shape is None:
        raise RuntimeError(
            f"not enough complete days to compare (caiso={caiso_shape}, nl={nl_shape})"
        )

    correlation = pearson(
        [v for v in caiso_shape.normalized_hourly_shape if v is not None],
        [v for v in nl_shape.normalized_hourly_shape if v is not None],
    )

    record = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "window_days": days,
        "caiso": {
            "label": "CAISO NP15 (DAM)",
            "timezone": "America/Los_Angeles",
            "complete_days": caiso_shape.complete_days,
            "coefficient_of_variation": round(caiso_shape.coefficient_of_variation, 4),
            "normalized_hourly_shape": [
                round(v, 4) if v is not None else None for v in caiso_shape.normalized_hourly_shape
            ],
            "provenance": caiso_fetch.provenance,
        },
        "nl": {
            "label": "EnergyZero NL (day-ahead)",
            "timezone": "Europe/Amsterdam",
            "complete_days": nl_shape.complete_days,
            "coefficient_of_variation": round(nl_shape.coefficient_of_variation, 4),
            "normalized_hourly_shape": [
                round(v, 4) if v is not None else None for v in nl_shape.normalized_hourly_shape
            ],
            "provenance": nl_fetch.provenance,
        },
        "shape_correlation_pearson": round(correlation, 4),
    }

    DATA_DIR.mkdir(exist_ok=True)
    with open(HISTORY_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    with open(LATEST_PATH, "w") as f:
        json.dump(record, f, indent=2)
        f.write("\n")

    return record


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
