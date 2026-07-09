# CSI-only single-source cutover — validation checklist

**Why:** the dynamic-opt backtests this session were silently corrupted by STALE
two-source data — Barchart-origin (hourly) series sitting under CSI codes, ffill'd
flat. A >180-day flat tail zeroes `calculate_cost_deflator`'s `final_vol` → `inf`
cost → `inf*0=NaN` in the optimiser's `calculate_costs` → it freezes to prior
positions ~99% of days → fake concentration + fake DDs. Freshness audit found
**88/147 instruments stale** (100–10,000+ days). Fix = purge Barchart, keep ONE
clean CSI-only sim DB, all current.

Prices live in a **parquet store**: `private/data/parquet` (adjusted, multiple,
per-contract, FX). Siloing = archive the directory (reversible).

---

## Phase 0 — Pre-cutover (non-destructive silo)
- [ ] Stop any live/production processes touching the DB.
- [ ] Archive the parquet store (keep, don't delete):
      `mv private/data/parquet private/data/parquet_barchart_archive_YYYY-MM-DD`
- [ ] Create fresh empty store dir (or let the ingest create it).
- [ ] Confirm `private_config.yaml: parquet_store` still points at `private/data/parquet`.

## Phase 1 — CSI-only re-ingest (all 147, fresh CSVs)
- [ ] Fresh full CSI export landed under `private/data/futures/csi/UA/Data/PST`
      (verify newest `.Specs.txt` timestamps are today).
- [ ] Stage: `uv run python -m sysinit.futures.csi_pipeline --export-dir private.data.futures.csi --rename`
      → expect ~147 mapped, only AE/AL/ND3/TWE skipped.
- [ ] Ingest all: `uv run python -m sysinit.futures.csi_pipeline --instruments all`
      (or the explicit 147-code list) → expect "N succeeded, 0 failed".

## Phase 2 — Data-integrity validation (MUST pass before any backtest)
- [ ] **Freshness** — every instrument <5 days stale (was 88 stale):
      re-run the get_raw_price last-date scan; PASS = 0 instruments >10 days stale
      (except genuinely-delisted, which should be dropped not ffill'd).
- [ ] **Deflator scan** — ZERO inf/nan cost deflators (the root-cause bug):
      re-run `calculate_cost_deflator` over all instruments; PASS = broken count 0
      (was CORN/CRUDE_W/SOYBEAN/WHEAT).
- [ ] **Coverage / no Barchart residue** — DB instrument count == 147 (was 222):
      `diagPrices().db_futures_adjusted_prices_data.get_list_of_instruments()`;
      PASS = set == CSI map, the 75 Barchart-only codes GONE.
- [ ] **Negative-price check** — no back-adjusted series crossing/near zero that
      would re-break the deflator (CRUDE_W had 865 negs, SOYBEAN 1947). Decide:
      accept (guard) vs re-stitch proportional.
- [ ] **Roll calendars** — `uv run python -m sysinit.futures.validate_roll_calendars --instruments all`;
      the 11 truncations + 4 stale should now extend to present if data is fresh.

## Phase 3 — Optimiser + backtest re-validation (the payoff)
- [ ] **Optimiser health** — run `dynopt_backtest.py` (full universe, $110k, 25%);
      PASS = "All zeros/Trade costs" error count ~0 (was 7772), and it FUNDS a
      diversified book across all asset classes (was frozen to 5 ags/metals).
      Remove CORN/CRUDE_W/SOYBEAN/WHEAT from the BROKEN set in dynopt_backtest.py
      once their data is confirmed fresh.
- [ ] **Full-universe clean backtest** — record real Sharpe / ann / vol / maxDD.
      This REPLACES every corrupted number this session (-51/-46/-45%).
- [ ] **Clean vol-target sweep** — `dynopt_voltarget_sweep.py` (10/15/20/25%);
      now meaningful: expect lower target → lower DD on a diversified book
      (opposite of the frozen-book artifact).
- [ ] **Static selection on clean data** — `static_instrument_selection.py`;
      re-diff vs Rob's published lists (overlap should rise once costs/corr are clean;
      the odd Euro-bond clustering should ease).
- [ ] **Drawdown attribution** — `attribute_drawdown.py` on the clean book.

## Phase 4 — Guards (prevent recurrence)
- [ ] Add a **staleness gate**: before backtesting, exclude/error instruments whose
      raw price ends >N days before the run date (don't silently ffill flat).
- [ ] Confirm the **daily-update path covers CSI** (not just Barchart) so the DB
      stays current — the Barchart systemd timer we set up won't refresh CSI.
- [ ] Consider a deflator guard upstream (clip inf) — but data fix is primary.

## Scripts (all in sysinit/futures/)
freshness+deflator scans (inline this session — promote to a `data_freshness_audit.py`),
`validate_roll_calendars.py`, `dynopt_backtest.py` (SELECTION+CAPITAL env, currency
metrics, BROKEN exclude set), `dynopt_voltarget_sweep.py`, `static_instrument_selection.py`,
`attribute_drawdown.py`, `idm_diagnostic.py`, `optimiser_input_check.py`, `cost_nan_check.py`.

**Bottom line:** no backtest number is trustworthy until Phase 2 passes. The clean
23-set run (Sharpe 0.89, held 22/23) proved the *optimiser* works on clean data;
Phase 3 produces the real *numbers*.
