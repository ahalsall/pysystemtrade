# IB historical data depth — measured (2026-06-30, paper account)

Empirical probe of how much history IB provides for futures, to decide whether IB
can bootstrap full instrument coverage vs waiting for the barchart build-out.
Tested via ib_async reqHistoricalData / reqContractDetails on paper (DU1739659),
read-only on (data reads work), reqMarketDataType(3) delayed.

## Findings
- **Continuous (back-adjusted) depth** via ContFuture reqHistoricalData("15 Y","1 day","TRADES"):
  - MES (CME micro S&P): 759 daily bars, 2023-06-20 → 2026-06-30 (~3 yr)
  - GC (COMEX gold): 931 daily bars, 2022-09-30 → 2026-06-30 (~3.75 yr)
- **Contract listing window** (reqContractDetails): IB lists only CURRENT + FORWARD contracts.
  - MES: 5 contracts, 2026-09 → 2027-09. GC: 34 contracts, 2026-07 → 2032-06. GBL/Bund: 3, current+2.
- **Expired contract retention:** requesting MES Mar-2023 / Mar-2020 → "Unknown contract", no data. IB does NOT retain/serve expired individual contracts.
- **Subscription:** historical EOD TRADES bars returned WITHOUT a paid market-data subscription on the paper account (good; live/intraday/real-time may differ).

## Implications
IB gives ~3-4 yr of CONTINUOUS history + the current front month, but NOT deep history and NOT individual expired contracts.

**IB can immediately provide (no waiting for barchart):**
- Current front-month contract for every tradeable instrument → fixes the expired-contract EXECUTION blocker.
- ~3-4 yr continuous daily history per instrument → enough overlapping returns to fix the dynamic-opt "negative covariance" degeneracy and run forecasts on recent data, across the full instrument set NOW.

**IB cannot replace barchart for depth:**
- Only ~3-4 yr vs AFTS 50yr / rob_system 20yr slow-vol → weaker vol/forecast fitting.
- Exposes the continuous series but not the individual expired contracts pysystemtrade's per-contract→back-adjusted pipeline uses, and no deep historical carry (carry rule needs two-contract history).

## Recommended architecture (complementary, not either/or)
- IB → immediate broad coverage: current contracts (execution) + ~3-4yr continuous (covariance + recent forecasts). Bootstrap via `sysinit/futures/seed_price_data_from_IB.py`.
- Barchart build-out → deep multi-decade history accumulating in background for robust forecast fitting.

Net: IB gets us to a USABLE full-coverage state immediately (solves covariance degeneracy + expired-contract execution gap); barchart deepens history over time. Confirm subscription/depth behaviour on the LIVE account before relying on it.

## Seeding test (sysinit/futures/seed_price_data_from_IB.py), AEX, 2026-06-30
`seed_price_data_from_IB('AEX')` works: it asks the broker for the instrument's contract dates (from roll config, allow_expired=True) and pulls hourly+daily per contract from IB into parquet.
- IB returned data ONLY for recent+forward contracts: AEX 20250700→20260900 (14→248 daily lines, growing toward front); ALL older (2024, early 2025) → Error 162 "HMDS query returned no data" (expired, not retained). Confirms ~recent-only per-contract depth (deeper for liquid US contracts per the ContFuture test).
- Per-contract depth here ≈ ~12 months (varies by instrument liquidity).

### KEY GOTCHA: data gaps stall the roll/adjusted chain
After seeding, AEX adjusted series stayed at 2024 (242 rows, ends 2024-12-20) and priced contract stayed 20241200 (expired) — even though IB's 2026 contracts are in the DB. Reason: barchart gave 2024 contracts, IB gave 2025-07→2026, but Jan-Jun 2025 is MISSING from both (IB doesn't retain those). The roll calendar can't bridge the gap, so multiple/adjusted stop at 2024 and the priced contract doesn't advance to a current one.
Implications:
- To get a CURRENT priced contract + continuous recent adjusted series from IB, need either (a) a CLEAN pure-IB seed per instrument (IB's recent run is continuous ~2025-07→2026 → builds a clean ~1yr series + current contract), not mixed with partial barchart that leaves gaps; or (b) continuous coverage (barchart build-out fills the 2025 gap over time); or (c) production roll-status tooling to advance the priced contract to the live front month.
- So IB seeding alone doesn't auto-produce a current priced contract when mixed with gappy historical data; roll continuity matters.
RECOMMENDED for immediate usability: pure-IB recent seed (clean per-instrument) → contemporaneous recent series across all instruments (fixes covariance) + current contracts (fixes execution); barchart fills/deepens. Production uses update_sampled_contracts + roll status to keep the priced contract current.
