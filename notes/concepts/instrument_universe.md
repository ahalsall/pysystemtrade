# Instrument universe: research set, live tradeable set, and the broker-tradeable adjunct

Three related lists — keep them distinct. Do NOT hard-lock the tradeable set to a
capital number; PST self-scales (see below).

## 1. Research / backtest (SIM) universe — BROAD (more data = better)
Purpose: fit forecasts, estimate correlations/diversification, run cross-sectional
rules. Cost/capital/tradeability do NOT constrain this. The **CSI deep-history
download target**.
- Computed 2026-07-01: Rob's full list (581) ∩ has rollconfig ∩ in IB config = **501**.
- Include LME here (data-only for research) even though not live-tradeable from Canada.
- → Pull CSI deep history for as much of the 501 as CSI covers.

## 2. Live tradeable set — CONFIGURED BROAD, self-scales with capital (NOT locked)
The dynamic optimiser picks daily positions from the sim universe MINUS the exclusion
lists (section 3). We do NOT lock a "~30 at CAD 150k" list. Instead:

### Capital is (mostly) automatic — verified in code/docs
- Daily P&L → capital: **automatic**. `update_total_capital` polls the IB account value
  daily; with **full compounding** (`syscore/capital.py: full_compounding`) the capital
  base tracks the account. Never hand-edited for trading gains.
- Deposits/withdrawals: **one manual entry**. Run `interactive_update_capital_manual`
  once to flag the jump as new cash, not profit (else the daily poll absorbs it or trips
  the >10% safety filter — docs/production.md:1894). Then it flows automatically.
- Strategy allocation: **automatic**. `update_strategy_capital` re-allocates total capital
  to strategies daily (our rob_dynamic @ 100%).
→ Allocating more funds = deposit at IB + ONE `interactive_update_capital_manual` entry.
  No re-selection, no config rebuild.

### Affordability is handled continuously by dynamic opt
The greedy optimiser ("Mr Greedy", AFTS S25) builds the integer-contract portfolio that
best tracks the risk-optimal portfolio, subject to costs + position limits. An instrument
whose single contract is too big for its risk share at current capital is simply **held
at zero** — not an error, just not selected. So we can CONFIGURE more instruments than we
can currently afford; they **come online automatically** as capital grows. No re-run.

### Membership screens are config-driven and PERIODIC (not per-capital)
What is genuinely "set" is config: the exclusion lists (section 3), per-instrument
`position_limit_contracts`/`position_limit_weight`. Re-run the screening reports
occasionally (quarterly-ish) via `interactive_controls` + Costs/Liquidity/Remove-markets
on OUR data to add newly-liquid or retire degraded instruments. Maintenance, not
capital-driven. Screen on OUR data, not Rob's (his thresholds are institutional-scale
and over-exclude at our size; his cost report also has coverage gaps for micros).

## 3. Broker-tradeable adjunct — PST's built-in `exclude_instrument_lists`
This answers "how do we stop dynamic opt selecting an instrument we can't actually trade
at IB?" PST has a three-tier mechanism in `sysdata/config/defaults.yaml:349`, overridable
in `private_config.yaml` (the defaults note the lists are "regionally biased — override in
private_config"). This is exactly our IB-Canada tradeability list (its complement):

- **ignore_instruments** — dropped from backtests entirely (no data even in sim opt).
  Use for instruments with no accurate data yet. Prices still collected/rolled in prod.
- **trading_restrictions** — CAN'T TRADE (broker/region). Kept in sim data (for
  correlations), but for the dynamic strategy it's treated as **don't-trade** in sim and
  added to the production **reduce_only** list. ← this is where our IB-Canada-untradeable
  instruments (incl. LME) go.
- **bad_markets** — too expensive / illiquid. Same treatment. Auto-suggested by
  `interactive_controls` / Remove_markets on our data.

### No mis-/under-allocation — the guarantee (verified in code)
`optimised_positions_stage.get_reduce_only_instruments()` →
`get_list_of_markets_not_trading_but_with_data()` feeds these lists into the optimiser as
**per-instrument box constraints** (`set_up_constraints.py`): `reduce_only` forces the
position to only move toward zero (from a flat book → stays 0); `no_trade` locks at prior.
Because the constraint is applied *inside* the optimisation (not "optimise then filter"),
the risk that would have gone to an untradeable instrument is **redistributed to tradeable
ones** in the same solve. So the optimal *tradeable* portfolio is what's produced — we are
NOT left under-allocated. `reduce_only` in production is also the belt-and-suspenders: it
will never OPEN a new position in a restricted instrument, only close one.

### Action: IB-Canada tradeable probe → trading_restrictions  [BUILT]
`sysinit/futures/ib_tradeability_probe.py` determines, per instrument in the sim universe,
whether IB Canada offers a tradeable contract (metadata + current contract chain + a real
contract resolves) and optionally whether we hold market data (`--check-market-data`). The
COMPLEMENT (untradeable, incl. LME which IB resolves but Canada can't trade) is emitted as a
`trading_restrictions` YAML snippet for private_config.yaml. Re-run periodically as IB's
offering / our subscriptions change.
- Offline (no Gateway): `--no-connect` classifies LME + not-in-ib-config (validated: flags the 6 LME).
- Full: needs a HEALTHY Gateway (farms connected, not just the port open). A competing IB
  login breaks the Gateway's upstream link → all requests time out; reconnect first.
- ib_config currently lists 584 instruments (the probe's default universe).

## Sequencing
1. CSI-backfill the broad research set (501) → good backtests + fitting.
2. Build the IB-Canada tradeable probe → set `trading_restrictions` (untradeable complement).
3. Run OUR Costs/Liquidity/Remove-markets/Min-capital reports → set `bad_markets` + limits.
4. Dynamic opt then trades the tradeable, cost-OK, affordable subset — self-scaling with capital.

## Decisions (2026-07-01)
- Research/CSI breadth: **full 501** (broad; can trim later if some are truly never useful).
- Micros/minis: **yes** — the capital-efficiency lever for high-value underlyings.
- Tradeable set: **not locked** — configured broad; capital + dynamic opt + the exclusion
  lists determine what's actually held; ~30 is merely what's effectively active at ~CAD 150k.
