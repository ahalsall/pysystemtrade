# Fund vs "all on black" S&P 500 vs 60/40 blend — regime summary

Reference comparison of the rob_dynamic fund (Carver trend+carry, dynamic-opt, $250k @ 25% vt) against
simply going long the S&P 500 (1x via micro futures), and a daily-rebalanced **60% S&P / 40% fund** blend
(fund as the uncorrelated, bond-like ballast). Pure market P&L; the money-market uplift on idle margin cash
applies ~equally to all and is omitted. S&P return = correctly-rolled futures return (adjusted-price $ change
/ actual front-contract price), NOT distorted pct_change on the Panama series.

Regenerate: `uv run python -m sysinit.futures.sp500_regime_summary`  (figure -> the run folder).
Per-window curves: `uv run python -m sysinit.futures.compare_vs_sp500 rob_dynamic_prod_250k_dm275 <year>`.

## The three windows (as of 2026-07)

| Window | Fund CAGR | Fund Sharpe | Fund MaxDD | S&P CAGR | S&P Sharpe | S&P MaxDD | 60/40 CAGR | 60/40 Sharpe | 60/40 MaxDD | corr |
|---|---|---|---|---|---|---|---|---|---|---|
| 1996-26 (full) | 16.0% | **1.04** | -29% | 7.5% | 0.47 | -63% | 11.6% | 0.89 | -29% | +0.02 |
| 2005-26 (+GFC) | 8.1% | 0.65 | -29% | 8.6% | 0.53 | -58% | 9.0% | **0.71** | -29% | +0.14 |
| 2012-26 (bull) | 7.0% | 0.63 | -29% | 13.0% | **0.82** | -34% | 11.0% | **0.91** | -25% | +0.31 |

## Takeaways
- **The standalone winner flips entirely with the sample.** S&P wins the bull-only window (2012-26); the fund
  wins once a bear is included (2005-26) and dominates full-history (1996-26, though that's front-loaded by the
  1996-2010 trend "golden age" — NOT a repeatable forward expectation; recent Sharpe ~0.63 is the honest number).
- **The blend is top-or-near-top in every window** (Sharpe 0.89 / 0.71 / 0.91) with the shallowest or
  near-shallowest drawdown, because **correlation stays low (+0.02 to +0.31)**. Low corr is what lets 40% of a
  lower-Sharpe asset RAISE the combined Sharpe above the S&P alone.
- **You don't hold the fund to win the horse race in any given decade** — you hold it because it's ~uncorrelated
  to equities, so the *combination* is the most efficient and least catastrophic portfolio regardless of regime.
  The S&P's -58% to -63% drawdowns (dot-com + GFC) are exactly what the blend halves.
- Reframes the vol-shortfall ([[vol-shortfall-rcf]]): you don't need the fund at its 25% standalone target
  (that's a -52% DD) — enough of it, uncorrelated, alongside a growth engine is where ~12-15% realized vol earns
  its keep. See [[no-in-sample-fitting]] re: not selecting windows/weights to flatter a result.
