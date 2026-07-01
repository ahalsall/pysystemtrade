# Instrument universe: research set vs live tradeable portfolio

Two DISTINCT sets — conflating them is a mistake. Decide/maintain both explicitly.

## 1. Research / backtest universe (BROAD — more data is better)
Purpose: fit forecasts, estimate correlations/diversification, run cross-sectional
rules (relative momentum, cross-sectional MR need many instruments per asset class).
Cost/capital/tradeability do NOT constrain this. This is the **CSI deep-history
download target**.

Definition (computed 2026-07-01): Rob's full instrument list (581) ∩ has rollconfig
∩ in IB config = **501 instruments** (buildable + IB-known). Include LME here too
(data-only, for research) even though not live-tradeable from Canada.
→ Pull CSI deep history for as much of this 501 as CSI covers.

## 2. Live tradeable portfolio (CURATED — for real orders at ~CAD 150k)
Purpose: the set dynamic optimization picks daily positions from. Must pass ALL
live constraints. Dynamic opt then chooses the sparse actual holdings.

Hard constraints (apply to us):
- **IB-Canada tradeable**: in IB config; EXCLUDE **LME** (6: ALUMINIUM_LME, COPPER_LME,
  LEAD_LME, NICKEL_LME, TIN_LME, ZINC_LME — IB's LME is synthetic OTC, blocked for Canada).
  Also exclude anything IB Canada blocks / regulatory bad_markets.
- **Cost**: SR cost per trade < ~0.01 (Rob's screen). MUST compute on OUR data (see below).
- **Capital-appropriate**: a single contract's minimum capital must be a sane fraction
  of ~USD 110k so we can diversify → favors MICRO/MINI for high-value underlyings
  (SP500_micro, NASDAQ_micro, GOLD_micro, COPPER-micro, EUR_micro, *_mini). Micros are
  IB-tradeable (data via IB).
- **Liquidity**: enough that we (tiny) can fill a few contracts. NOTE: Rob's
  Remove_markets volume thresholds ($1.5m ann-risk/day, 100 contracts/day) are
  INSTITUTIONAL-scale and TOO STRICT for us — they over-exclude (and flag micros as
  low $-notional). Use a size-appropriate liquidity bar, not Rob's wholesale.

### KEY PRINCIPLE: screen on OUR data, not Rob's
Rob's Costs/Liquidity/Remove_markets/Static_selection reports use HIS data and HIS
(large) capital. His cost report also has coverage gaps for micros/newer names (they
default to "excluded" in a naive filter). So use them as a STARTING guide, but finalize
the tradeable set with pysystemtrade's OWN reports run on OUR data once we have it:
`interactive_controls` (auto-populate position limits, cost/liquidity screens),
Costs/Liquidity/Remove-markets reports on our DB, Minimum_capital_report. This is the
guideline-compliant way and ties into the QA audit (task #25).

### Starting seed (Rob's Static_selection @ capital, minus LME — refine with our data)
Rob's own capital-based selection (cost+liquidity+capital+diversification optimized on
his data) is the best available seed:
- ~$100k → 28 instruments; ~$250k → 35; ~$500k → 46 (scales with capital).
- At our ~CAD 150k (~USD 110k) → interpolate ~30 instruments; heavy on micros/minis +
  cheap diversifiers (V2X, IRON, MXP, RUBBER, CORN, EU sector indices, KOSPI_mini,
  SP500_micro, EUR_micro, KRWUSD_mini, etc.).
Take Static_selection @ ~$100-250k, drop LME, then re-screen cost/liquidity on OUR data.

## Sequencing
1. CSI deep history for the broad research set (501) → good backtests + fitting.
2. Compute OUR cost/liquidity/min-capital via PST reports on our data.
3. Finalize the live tradeable portfolio (~30 at current capital; scales if we add capital).
4. Dynamic opt trades the tradeable set; research set stays broad for strategy work.

## Open decisions for Andrew
- Capital tier to size the tradeable set (150k now; scale later?).
- Research breadth: full 501, or trim (e.g., drop instruments with no realistic future use)?
- Confirm micros are acceptable for the live book (they are the capital-efficiency lever).
