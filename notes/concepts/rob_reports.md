# Rob Carver's public repos & the `reports` repo (production diagnostics)

Rob runs pysystemtrade live; his GitHub (github.com/robcarver17) exposes real output
useful for sanity-checking and instrument selection. NOT our data — his — but a
high-quality reference for "what good looks like" and for selection criteria.

## Public repos (8)
| repo | use |
|---|---|
| `pysystemtrade` | the code (we run a fork) |
| `reports` | **auto-generated production diagnostics** (see below) |
| `pysystemtrade_examples` | runnable blog example code by topic: smallaccountsize, optimisation, riskmanagement, fitting, forecastscaling, breakout, somemoretradingrules, riskenvelope, variablecapital, vix, regressionrule |
| `systematictradingexamples` | first book ("Systematic Trading") + blog code |
| `python-uk-trading-tax-calculator` | UK tax calc — contrast point for our Canada tax workstream |
| `ibswigsystematicexamples`, `pyargfeeder`, `skipperman`, `pys3db` | older/peripheral |

## `reports` repo — signal files (ignore `_tempfile_*.pdf` junk)
Raw base URL: `https://raw.githubusercontent.com/robcarver17/reports/master/<file>`
Most are fixed-width TEXT (fetch/parse directly); a few are PDF (charts).

| file | content / why it matters |
|---|---|
| `Instrument_list` | his full instrument config (~581) — we used this for the build-out list |
| `Static_selection_of_instruments` | **which instruments his static optimizer picks at each capital level** — drives OUR selection (see below) |
| `Remove_markets_report` | which markets to mark untradeable (cost/liquidity/risk/too-safe) + criteria |
| `Minimum_capital_report` | capital needed per instrument |
| `Costs_report`, `Commission_report`, `Slippage_report` | real per-instrument costs |
| `Liquidity_report`, `Instrument_risk_report` | liquidity & per-instrument risk |
| `Trading_rule_p&l.pdf` | per-rule P&L — which rules actually earn |
| `Dynamic_Optimisation_Graphical.pdf`, `Dynamic_Optimisation_Text`, `Strategy_report` | his live dynamic-opt / position output to sanity-check ours |
| `Account_curve_report.pdf`, `Risk_report`, `Roll_report`, `Status_report`, `Market_monitor_report`, `Reconcile_report`, `Trade_report`, `Duplicate_markets_report` | live ops/monitoring |

## KEY FINDING: static instrument selection by capital (from Static_selection_of_instruments)
Number of instruments his optimizer selects scales with capital:
- $10k → 8 · $25k → 13 · $50k → 19 · $100k → 28 · $250k → 35 · $500k → 46 · $1M → 53
At LOW capital the picks lean heavily on **micro/mini contracts** (EUR_micro, SP500_micro, COPPER-micro, GOLD_micro, NASDAQ_micro, KOSPI_mini, KRWUSD_mini, GAS_US_mini…) for capital efficiency, plus cheap/diversifying markets (V2X, IRON, MXP, RUBBER, CORN, EU sector indices, BITCOIN).

## ⚠️ TENSION for our setup (important)
Rob's capital-efficient selection depends substantially on **micro/mini contracts**, but those are in the **357 instruments bc-utils CANNOT download** — our 224-instrument build-out EXCLUDES them. So:
- We cannot currently source the very contracts most useful for a smaller account.
- Implications: (a) find an alternative data source for the micros we'd actually trade, OR (b) accept a larger minimum capital / use the full-size contracts we do have, OR (c) map micro↔full-size equivalents (same underlying, different multiplier) and trade the full-size where capital allows.
- This intersects the Canada workstream: instrument availability/cost differs for a Canadian via IBKR vs Rob's UK access.

## OPEN QUESTION
What is Andrew's intended trading capital? It directly determines the selected instrument set (above) and whether the micros gap is a blocker.

## Remove_markets_report criteria (his thresholds, for reference)
- bad_markets (risk/liquidity/cost) at 0.30 threshold
- too expensive: SR cost per trade > 0.010
- not enough risk volume: < $1.5m ann. risk/day
- not enough contract volume: < 100 contracts/day
- too safe: annual % std dev < 5.0 (many rates/STIR/FX)
