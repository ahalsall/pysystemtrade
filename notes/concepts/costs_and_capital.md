# Costs & minimum capital — instrument tradeability (from Rob's reports)

Source: github.com/robcarver17/reports — `Costs_report` (29/06/2026) and
`Minimum_capital_report` (29/06/2026). His live numbers; use as reference for OUR
instrument selection. Backtesting is unaffected by these; they gate LIVE trading.

## Minimum capital — why "minis/micros" matter
Formula (his report):
- `min_capital_one_contract = point_size_base × price × annual_stdev% / risk_target`
  = capital to hold ONE contract standalone at the risk target.
- `minimum_capital (portfolio) = min_capital_one_contract × F / (G × H)`
  where F = min position (4 contracts), G = instrument_weight (~0.04), H = IDM (2.5).
  ⇒ portfolio min ≈ **~40×** the single-contract figure.

**Full-size high-value contracts need enormous capital per contract:**
NASDAQ ≈ $448k, GOLD ≈ $346k, KOSPI ≈ $377k, TIN_LME ≈ $285k, ETHEREUM ≈ $202k (per SINGLE contract).
**Micros bridge the gap** (per single contract): ETHER-micro $408, CAD_micro $923, GBP_micro $1,646, AUD_micro $1,758, EUR_micro $2,434, CORN_mini $2,812.

⇒ To trade big underlyings at sane capital you NEED the micro/mini variants. This is the core small-account constraint.

## How dynamic optimization (AFTS S25) helps — and its limit
Dynamic opt does NOT require holding the minimum position (F) in every instrument. It picks INTEGER positions that best track the ideal risk-weighted portfolio given your actual capital, so you can run a BROAD instrument set with limited capital (the `minimum_capital` "×40" figure is the *naive* requirement; dynamic opt sidesteps it).
**BUT** it cannot trade a fraction of a contract — so an instrument whose *single full-size contract* already exceeds your risk budget is simply unusable; for those underlyings you must use the micro/mini. (Andrew's read is correct: dyn-opt lets us pull from more instruments, but we're still floored by single-contract size of the big full-size contracts → need minis.)

## Costs — the SR-cost screen
`SR_cost = percentage_cost / avg_annual_vol_perc` (expected cost per trade in Sharpe units).
Rob's tradeability threshold: **avoid instruments with SR_cost > 0.010** (from Remove_markets_report).
- Of 660 instruments with cost data: **599 tradeable (<0.01), 61 too expensive (≥0.01)**.
- Cheapest (~0 SR cost): deep-liquid LME metals (NICKEL/LEAD/COPPER/TIN_LME), rates (SONIA3, GILT, EURIBOR-ICE), etc.
- Most expensive (avoid live): HOUSE-US (0.28), CNH-onshore (0.22), SUGAR16 (0.09), COAL-GEORDIE (0.08), WHEY, MILKWET, MSCIWORLD…

### Of OUR 224 build-out instruments, 24 are flagged too-expensive (drop from LIVE, keep for backtest research):
BOVESPA, BUTTER, CH10, CNH-onshore, COAL, COAL-GEORDIE, CZK, EU-MID, EURIBOR, EUROSTX-SMALL, EUROSTX200-LARGE, HOUSE-US, IRS, MILKDRY, MILKWET, MSCIWORLD, OMX, SMI-MID, STEEL, SUGAR16, SWISSLEAD, VNKI, WHEAT_ICE, WHEY.
(pysystemtrade enforces this in production via `config.bad_markets` / the Remove_markets logic + dynamic-opt reduce-only.)

## Implications for our project
1. **Backtesting now:** costs/min-capital don't block research — proceed with the data we have.
2. **Production (IB):** prices come from IB for anything tradeable, so the barchart "no micros" gap disappears once live — we can trade & price NASDAQ_micro, GOLD_micro, SP500_micro, micro FX, etc. So the micros gap is mainly a *backtest data* limitation, not a live one.
3. **Instrument selection (live):** start from the cost-screened set (<0.01 SR), prefer micro/mini for high-value underlyings, let dynamic opt size across them given our capital.
4. **Our capital: CAD ~150,000** (flexible to scale). ≈ USD ~110k (CAD/USD ~0.73). Per Static_selection_of_instruments (~28 @ $100k, ~35 @ $250k) ⇒ **~28-32 instruments** for a diversified live portfolio. That tier's selection leans on micros (EUR_micro, SP500_micro, COPPER-micro, GOLD_micro, NASDAQ_micro, KOSPI_mini…) → those are mandatory for live but come from IB.
5. **Base currency (CAD vs USD) is an open decision** — affects vol targeting, FX conversion of USD-denominated futures, and ties to the Canada tax/FX workstream. Rob uses USD base. Worth deciding before production config.

Sources: raw.githubusercontent.com/robcarver17/reports/master/{Costs_report,Minimum_capital_report,Remove_markets_report}
