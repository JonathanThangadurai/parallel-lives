"""Where the two markets' data actually comes from.

CAISO (US) is read through us-power-poc's own live API, not re-scraped from CAISO
directly - that pipeline already owns ingestion, idempotency, and quality checks for
this data, so this is a consumer, not a second extractor.

NL is fetched directly from EnergyZero's public API. The honest reason: eu-power-poc
is deliberately kept local-only (no hosting cost for a project this size), so there is
no live API to read it from on a schedule. This does mean the EnergyZero fetch logic
is duplicated between that repo and this one - a real, acknowledged tradeoff made to
avoid paying for hosting a service with no other live consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

US_POWER_POC_BASE_URL = "https://us-power-poc-api-production.up.railway.app"
ENERGYZERO_BASE_URL = "https://api.energyzero.nl/v1/energyprices"

CAISO_TZ = ZoneInfo("America/Los_Angeles")
NL_TZ = ZoneInfo("Europe/Amsterdam")


@dataclass
class FetchResult:
    rows: list[tuple[datetime, float]]  # (local-time timestamp, price)
    provenance: dict


def fetch_caiso_dam(days: int, client: httpx.Client | None = None) -> FetchResult:
    client = client or httpx.Client(timeout=30)
    now = datetime.now(UTC)
    start = now - timedelta(days=days)

    resp = client.get(
        f"{US_POWER_POC_BASE_URL}/prices",
        params={"market": "DAM", "start": start.isoformat(), "end": now.isoformat(), "limit": 1000},
    )
    resp.raise_for_status()
    prices = resp.json()

    status_resp = client.get(f"{US_POWER_POC_BASE_URL}/pipeline/status")
    status_resp.raise_for_status()
    latest_run = status_resp.json().get("latest_run") or {}

    rows = [
        (datetime.fromisoformat(r["interval_start_utc"]).astimezone(CAISO_TZ), r["lmp"])
        for r in prices
        if r.get("lmp") is not None
    ]
    provenance = {
        "source": "us-power-poc live API (/prices?market=DAM)",
        "window_start_utc": start.isoformat(),
        "window_end_utc": now.isoformat(),
        "rows_fetched": len(rows),
        "source_latest_pipeline_run_id": latest_run.get("id"),
        "source_latest_pipeline_run_status": latest_run.get("status"),
    }
    return FetchResult(rows=rows, provenance=provenance)


def fetch_energyzero_nl(days: int, client: httpx.Client | None = None) -> FetchResult:
    client = client or httpx.Client(timeout=30)
    now = datetime.now(UTC)
    start_day = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows: list[tuple[datetime, float]] = []
    cursor = start_day
    while cursor < now:
        day_end = cursor + timedelta(days=1) - timedelta(milliseconds=1)
        resp = client.get(
            ENERGYZERO_BASE_URL,
            params={
                "fromDate": cursor.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "tillDate": day_end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
                "interval": "4",
                "usageType": "1",
                "inclBtw": "false",
            },
        )
        resp.raise_for_status()
        for p in resp.json()["Prices"]:
            ts = datetime.fromisoformat(p["readingDate"].replace("Z", "+00:00")).astimezone(NL_TZ)
            rows.append((ts, p["price"]))
        cursor += timedelta(days=1)

    provenance = {
        "source": "EnergyZero direct (api.energyzero.nl) - eu-power-poc is local-only, not read from",
        "window_start_utc": start_day.isoformat(),
        "window_end_utc": now.isoformat(),
        "rows_fetched": len(rows),
    }
    return FetchResult(rows=rows, provenance=provenance)
