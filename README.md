# Parallel Lives

[![CI](https://github.com/JonathanThangadurai/parallel-lives/actions/workflows/ci.yml/badge.svg)](https://github.com/JonathanThangadurai/parallel-lives/actions/workflows/ci.yml)

A daily, fully automated comparison of two power markets that share no grid,
currency, or continent: **CAISO's NP15 hub** (California, day-ahead, USD/MWh) and
**EnergyZero's NL day-ahead price** (Netherlands, EUR/kWh). The name is a nod to
Plutarch, who paired a Greek and a Roman life side by side to find the shared
structure underneath two different worlds — this repo does the same thing with two
power grids instead of two statesmen.

The first finding, from a one-off 14-day sample: **r = 0.79** correlation between the
two markets' normalized daily price shape, despite nothing connecting them. Both show
the solar-driven "duck curve" - cheap at midday, expensive in the early evening. See
the published write-up: *The Duck Curve, Twice*.

This repo turns that one-off analysis into something that keeps running: a daily
GitHub Actions job re-fetches both markets, recomputes the comparison, and commits the
result - so the dataset grows on its own, with a full history in `data/history.jsonl`
and its own commit log as a changelog.

## Why no server

Both markets only publish new prices once a day, so there is no 5-minute-cadence
problem to solve here (that's what justifies an in-process scheduler in
[us-power-poc](https://github.com/JonathanThangadurai/us-power-poc) and
[eu-power-poc](https://github.com/JonathanThangadurai/eu-power-poc)). A once-daily
GitHub Actions cron job is the right-sized tool, and it's free - no hosting, no
database service, no Dockerfile.

## Where the data actually comes from

- **CAISO (US)**: read through us-power-poc's own live API
  (`/prices?market=DAM`, `/pipeline/status`) - not re-scraped from CAISO directly. That
  pipeline already owns ingestion, idempotency, and quality checks for this data; this
  repo is a consumer of it, not a second extractor.
- **NL**: fetched directly from EnergyZero's public API. The honest reason:
  eu-power-poc is deliberately kept local-only (no hosting cost for a service with no
  other live consumer yet), so there's no live API to read it from on a schedule. This
  does mean the EnergyZero fetch logic exists in two repos instead of one - a real
  tradeoff, made to avoid paying for hosting that nothing else currently needs.

## The method

Comparing in native currency (USD/MWh vs. EUR/kWh) would require an exchange-rate
assumption this project isn't about. Instead, each day's prices are divided by that
day's own mean before averaging across days - a unit-independent measure of *when*
a market is relatively cheap or expensive, not its absolute price level. Coefficient
of variation (std/mean) measures volatility the same unit-independent way.

## Data

- `data/latest.json` - the most recent comparison.
- `data/history.jsonl` - one line per daily run, append-only. Each record carries
  provenance: the fetch window, row counts, and (for CAISO) the source pipeline's
  latest `pipeline_runs` id at fetch time, so a result can be traced back to the state
  of the source system that produced it.

## Running it

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src python -m parallel_lives.run
ruff check .
pytest -v
```

`tests/test_stats.py` checks the comparison math itself (Pearson correlation,
normalization, coefficient of variation) against hand-calculable synthetic cases -
independent of either live API being reachable.

## Known limitations

- CAISO history is only as deep as us-power-poc has been running. A fresh deployment
  of that service means this repo's first several daily runs may not find a full
  comparison window yet - the job fails loudly in that case rather than reporting a
  comparison built on too little data.
- NL's fetch logic is duplicated from eu-power-poc (see above) - a deliberate,
  documented tradeoff, not an oversight.
