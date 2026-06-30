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
