# Portfolio Construction & Dynamic Optimization — Conceptual Reference

A synthesized conceptual guide to how Rob Carver's systematic futures framework
(pysystemtrade) builds positions, and why "dynamic optimization" exists. The goal
here is the *why*, not just the mechanics, with each idea mapped to the
`rob_system` config keys we actually run.

The pipeline, top to bottom:

```
raw price/carry  ->  trading rule forecasts  ->  scaled & capped forecasts
   ->  forecast weights + FDM  ->  combined forecast (per instrument)
   ->  position sizing (vol target / instrument vol)  ->  subsystem position
   ->  instrument weights + IDM  ->  notional optimal portfolio (fractional contracts)
   ->  DYNAMIC OPTIMIZATION  ->  integer, tradeable portfolio
```

Everything above the dynamic-optimization step produces an *idealized* portfolio
that assumes you can hold fractional contracts. Dynamic optimization is the layer
that turns that ideal into something a finite-capital account can actually hold.

---

## 1. Volatility targeting & position sizing

### The core idea
Risk, not notional exposure, is the unit of account. You decide *how much
annualized volatility of returns* you are willing to run on the whole account
(the risk target), then every position is sized so that the portfolio's expected
risk lands on that target. This is the foundation that makes everything else
(weights, diversification multipliers) compose cleanly: each layer is expressed
in risk units, so they multiply together.

### From risk target to a position
Two quantities matter for sizing a single instrument:

- **Risk target** — desired annualized standard deviation of account returns,
  expressed as a % of capital. In pysystemtrade this is `percentage_vol_target`.
- **Instrument volatility** — the annualized price/return volatility of the
  instrument *right now*, in the account's base currency per contract. A more
  volatile instrument needs *fewer* contracts to contribute the same risk.

The position for a *full-strength* signal (forecast = average) is, conceptually:

```
volatility scalar = (capital * daily vol target in cash) / (instrument value volatility)
```

i.e. how many contracts give this instrument its "fair share" of the daily cash
risk budget. The actual position then scales linearly with the forecast (Section 2):

```
position = volatility scalar * (combined forecast / average forecast)
         * instrument weight * IDM
```

So a forecast of +20 (double the average of 10) doubles the position; a forecast
of -10 flips it short at average size.

### Why estimate vol the way Carver does
Position size is inversely proportional to estimated instrument vol, so the vol
estimate directly drives turnover and risk accuracy. Carver uses a **blended
("mixed") vol estimate**: mostly recent realized vol, partly a long-run average.

- Pure short-window vol whips positions around (high turnover, instability).
- Pure long-run vol is slow to cut risk when markets blow up.
- A blend that is *partially mean-reverting* shrinks positions promptly when
  vol spikes, but doesn't let a single quiet month inflate positions to dangerous
  levels.

Config: `volatility_calculation` in `rob_system` uses `mixed_vol_calc` with
`days: 35`, `slow_vol_years: 20`, `proportion_of_slow_vol: 0.35` — i.e. ~65%
recent / 35% 20-year vol.

A related refinement is **vol attenuation**: for momentum-type rules, the forecast
is *reduced* when current vol is high relative to history, because trend rules
empirically perform worse in high-vol regimes. See the long `use_attenuation`
list in `rob_system`.

---

## 2. Forecasts → combined forecast → Forecast Diversification Multiplier (FDM)

### Raw forecasts and scaling
A **trading rule** maps data to a forecast: a positive/negative number whose sign
is the desired direction and whose magnitude is conviction. Raw rule outputs are
on arbitrary scales, so each is multiplied by a **forecast scalar** so that its
long-run absolute average is **10** (`forecast_scalars` in `rob_system`). This
gives every rule a common "10 = average conviction" language and is what makes the
linear position scaling in Section 1 meaningful.

Scaled forecasts are then **capped** at ±20 (`forecast_cap: 20.0`) to stop a
single extreme signal from dominating risk.

### Combining rules: forecast weights
Most instruments run many rules (the `rob_system` config has ~40: EWMAC/momentum
at several speeds, breakouts, carry, relative momentum, cross-sectional mean
reversion, skew, acceleration). The **combined forecast** is a weighted average:

```
combined (pre-mult) = sum_i ( forecast_weight_i * scaled_forecast_i )
```

**Why handcraft the weights instead of optimizing them?** Rule returns are noisy
and highly correlated, so a mean-variance optimizer will happily concentrate on
whatever rule had the best in-sample Sharpe — overfitting. Handcrafting assigns
weights by a top-down hierarchy (e.g. trend-ish vs. non-trend, then by rule
family, then by speed) using priors about diversification and cost, not just
backtested returns. It is robust precisely because it ignores most of the noise.
Expensive rules (fast trend on costly instruments) get zeroed out so the
instrument isn't traded too fast for its costs — visible in `rob_system` where
many instruments have `momentum4: 0.0`, `breakout10: 0.0`, etc.

### The Forecast Diversification Multiplier (FDM)
A weighted average of rules that don't move together has *lower* volatility than
any single rule. So after combining, the average absolute combined forecast is
**below 10** — we've diluted our risk. The FDM scales the combined forecast back
up so its long-run average absolute value is again ~10:

```
combined forecast = FDM * sum_i ( weight_i * scaled_forecast_i )
```

Conceptually:

```
FDM = 1 / sqrt( w' . C . w )
```

where `w` is the forecast-weight vector and `C` the correlation matrix of the
rules' forecasts. Intuition: the more *correlated* the rules, the closer the
quadratic form is to 1 and the smaller the FDM (little diversification to recover);
the more *independent* the rules, the larger the FDM. Negative correlations are
floored at zero so we don't claim implausible diversification, and the resulting
series is smoothed (125-day EWMA) so the multiplier doesn't trade us around.

---

## 3. Instrument weights & the Instrument Diversification Multiplier (IDM)

### Subsystems and instrument weights
A **subsystem** is the full strategy applied to one instrument as if it were the
whole portfolio (vol-targeted to the account risk target on its own). **Instrument
weights** then allocate capital across subsystems — a second, separate portfolio
optimization whose "assets" are the subsystem P&L curves.

Like forecast weights, these are handcrafted/robust rather than naively optimized,
for the same overfitting reason, plus a structural one: futures returns cluster by
asset class (all bond markets co-move, all equity indices co-move). Handcrafting by
asset-class buckets prevents the portfolio from silently loading 80% into one
correlated cluster just because it backtested well. In `rob_system`,
`instrument_weights` lists ~150 instruments each with a small weight (they sum to
~1), with sector-style groupings reflected in the magnitudes.

### The Instrument Diversification Multiplier (IDM)
If you size each subsystem to the full risk target and then hold a weighted basket,
the basket's realized risk is **far below** target, because the subsystems are not
perfectly correlated. The IDM scales all positions up to restore the target:

```
IDM = 1 / sqrt( v' . C . v )
```

`v` = instrument weights, `C` = correlation matrix of subsystem returns. Same
mathematical shape as the FDM, one level up.

### How diversification scales with instrument count
The free lunch, quantified. With N instruments that share an average pairwise
correlation ρ, the achievable risk-reduction (and therefore the IDM ceiling) grows
roughly like:

```
diversification benefit  ~  1 / sqrt( ρ + (1 - ρ)/N )
```

- ρ = 0 (independent): benefit ≈ √N — unlimited upside from adding markets.
- ρ > 0 (realistic, ~0.05 average across Carver's universe but much higher within
  a cluster): the term `(1-ρ)/N` vanishes as N grows, so the benefit **asymptotes
  at 1/√ρ**. Adding the 150th correlated instrument barely helps once you already
  hold its cluster-mates.

This is why Carver **caps the IDM at 2.5** (`dm_max: 2.5` in the estimator
defaults) even with ~150 instruments: the math says further markets add real but
sharply diminishing risk-reduction, and an uncapped IDM would lever the book up on
the strength of correlation estimates that are themselves noisy. The `rob_system`
config sets a fixed `instrument_div_multiplier: 2.75` as the static value but turns
the *estimated* IDM on (`use_instrument_div_mult_estimates: True`), which applies
the capped, smoothed estimate.

---

## 4. Why small / limited-capital accounts can't hold the diversified portfolio

Sections 1–3 describe an *ideal* portfolio of fractional contracts. The catch:
**you cannot trade fractional futures contracts.** This is the granularity problem,
and it bites small accounts hardest.

Suppose the ideal book wants an average of ~0.4 contracts in each of 100
instruments. You can't hold 0.4 — you hold 0 or 1. Three pathologies follow:

1. **Binary / all-or-nothing behavior.** An instrument sits at 0 contracts until
   its forecast and vol push the ideal past ~0.5, then jumps to 1. You only trade
   on huge signal changes, so the smooth, continuously-rebalanced strategy that was
   backtested is replaced by a coarse on/off switch.

2. **Arbitrary, instrument-dependent cutoffs.** Contract sizes differ wildly. The
   same 1% capital allocation might round to several contracts of a small-notional
   market but zero of a large-notional one (e.g. DAX). Which markets you actually
   end up holding becomes an artifact of contract sizes and current vol, not of
   your intended weights.

3. **Systematically too little risk.** Rounding toward zero on many small positions
   truncates the position distribution; realized portfolio risk comes in *below*
   target and diversification collapses to the handful of markets big enough to
   round to ≥1 contract.

So the small trader faces a forced choice: trade **few instruments properly**
(losing the diversification free lunch) or trade **many instruments badly** (binary,
arbitrary, under-risked). Dynamic optimization exists to escape this dilemma.

---

## 5. Dynamic optimization — in depth

The journey matters, because it explains the design.

### First attempt (the "EPIC FAIL"): expected-return grid search
The initial idea borrowed Black-Litterman: treat the ideal fractional weights as
optimal, **reverse-engineer implied expected returns** (`μ = λΣw`), then grid-search
over integer contract combinations to **maximize `w'μ − (λ/2) w'Σw − costs`**. It
brute-forced millions of grid points across CPU cores.

It *underperformed naive rounding* — Sharpe fell (~1.0 → ~0.56) and risk
overshot. Lesson: optimizing a noisy *return* estimate reintroduced exactly the
overfitting that handcrafted weights were designed to avoid, and the grid search
was computationally brutal for little gain.

### The winning reframing: minimize tracking error (Doug Hohner's insight)
Don't try to *beat* the ideal portfolio — try to **track it**. The ideal fractional
portfolio is already the answer; the only job is to find the integer portfolio
*closest* to it in risk space. Borrow the index-fund concept of **tracking error**.

Define the difference between the ideal weights `x*` and a candidate integer
portfolio `x` as the **tracking-error portfolio** `d = x − x*`. Its risk is:

```
tracking error variance = d' . Σ . d         (Σ = instrument-return covariance)
```

The objective adds a trading-cost penalty so the optimizer doesn't churn:

```
minimize   sqrt( d' . Σ . d )  +  shadow_cost * (cost of trading from current to x)
```

This is far more robust than the return-maximizing version: it contains **no
expected-return estimate at all**, only a covariance matrix. There is nothing to
overfit toward — the optimizer just stays as close as integer arithmetic allows to
a portfolio we already trust.

Key modeling choices:
- Uses the **covariance of instrument returns** (not subsystem returns), so the
  tracking metric reflects *current* market risk conditions.
- The correlation matrix is **shrunk toward its average** to stabilize it
  (a noisy 150x150 correlation matrix would otherwise dominate the solution).

### Mr Greedy: the greedy integer algorithm
Grid search is exponential and was thrown out. The production algorithm is a
**greedy hill-climb** that scales *linearly*:

1. Start every instrument at **zero** contracts (or its constrained minimum).
2. Each instrument may only move **in the sign direction of its ideal position**
   (no betting against the signal), in steps of **one contract**.
3. At each iteration, try adding one contract to each eligible instrument; compute
   the objective for each trial.
4. **Commit** the single move that reduces the objective most.
5. Repeat until no single contract addition improves the objective. Stop.

Because the objective is convex-ish in this discrete space and the ideal portfolio
is the anchor, greedy finds a near-optimal integer portfolio without exploring the
combinatorial space. A useful empirical observation: even with ~45–150 instruments
available, the optimizer typically holds **only ~6–18 at once** — correlations make
most markets redundant *given the ones already held*. The unheld instruments still
matter: their presence in Σ informs which 6–18 best represent the whole book.

### Shadow cost — the units bridge
The objective mixes two incommensurable things: tracking-error *risk* (a vol) and
*trading costs* (cash/SR). The **shadow cost** is the exchange rate between them —
how many units of tracking-error risk one unit of trading cost is "worth." Set it
too low and the optimizer over-trades chasing tiny tracking improvements; too high
and it freezes, tolerating large tracking error to avoid any cost. It is calibrated
so dynamic-opt turnover roughly matches the baseline system's turnover.

### Tracking-error buffer — no-trade zone
Even with a shadow cost, you don't want to re-optimize to a slightly different
integer book every day. The **tracking-error buffer** defines a tolerance band: if
the *current* held portfolio's tracking error vs. the new ideal is within the
buffer, **don't trade at all**. Only when the ideal has drifted far enough that
tracking error exceeds the buffer do you re-solve and move. This is the integer-
portfolio analogue of position-inertia buffering — it converts a continuous stream
of tiny rebalances into occasional meaningful trades, slashing costs.

### Cost multiplier
A scaling factor applied to the modeled trading costs inside the optimization,
letting you make the optimizer more or less cost-averse independently of the shadow
cost (e.g. to stress-test cost assumptions or be deliberately conservative).

### Why it beats the naive alternatives
- **vs. naive rounding:** rounding kills diversification (many forced zeros,
  under-risked). Dynamic opt keeps realized risk on target and stays statistically
  indistinguishable from the unrounded ideal — e.g. ~1.19 Sharpe vs. ~1.06 for
  rounding at $100k over 45 markets.
- **vs. static top-N selection:** picking a fixed "best" subset has larger tracking
  error and, crucially, **can't adapt** — as forecasts, vols and correlations move,
  the right markets to hold change. Dynamic opt re-chooses the held subset every
  period from the *full* universe, capturing diversification information from
  markets it isn't currently trading.

---

## 6. Mapping to the pysystemtrade `rob_system` config

Files: `systems/provided/rob_system/config.yaml` (live values) and
`sysdata/config/defaults.yaml` (defaults; the `small_system` block lives here).

### Sizing & top-level portfolio (Sections 1–3)
| Concept | Key | Value in `rob_system` | Notes |
|---|---|---|---|
| Risk target (Section 1) | `percentage_vol_target` | `25.0` | Annualized % vol target for the account. (default is `16.0`.) |
| Instrument vol estimate | `volatility_calculation` | `mixed_vol_calc`, `days: 35`, `slow_vol_years: 20`, `proportion_of_slow_vol: 0.35` | Partially mean-reverting blend (Section 1). |
| Forecast scaling | `forecast_scalars`, `forecast_cap: 20.0` | per-rule scalars | Normalize each rule to avg-abs 10, cap at ±20 (Section 2). |
| Forecast weights (Section 2) | `forecast_weights` | per-instrument dict of ~40 rule weights | Handcrafted (`use_forecast_weight_estimates: False`); expensive rules zeroed. |
| FDM (Section 2) | `forecast_div_multiplier` | per-instrument dict (e.g. ~1.2–1.9) | Fixed values (`use_forecast_div_mult_estimates: False`); default `1.0`. |
| Instrument weights (Section 3) | `instrument_weights` | per-instrument dict (~150, sum ≈ 1) | Handcrafted (`use_instrument_weight_estimates: False`). |
| IDM (Section 3) | `instrument_div_multiplier` | `2.75` static; `use_instrument_div_mult_estimates: True` | Estimated IDM used, capped at `dm_max: 2.5` and 125-day smoothed. |
| Risk overlay | `risk_overlay` | `max_risk_fraction_normal_risk: 1.75`, `..._stdev_risk: 4.0`, `..._sum_abs_risk: 4.0`, `max_risk_leverage: 20.0` | Hard caps on aggregate risk, applied after sizing. |

Note: `use_attenuation` (long rule list in `rob_system`) enables the
high-vol forecast attenuation described in Section 1.

### Dynamic optimization — the `small_system` block (Section 5)
Defined in `sysdata/config/defaults.yaml`:

```yaml
small_system:
  shadow_cost: 50
  cost_multiplier: 1.0
  tracking_error_buffer: 0.0125
  shrink_instrument_returns_correlation: 0.5
```

| Concept | Key | Value | Maps to |
|---|---|---|---|
| Cost-vs-tracking-error exchange rate | `shadow_cost` | `50` | Shadow cost (Section 5). Higher = more cost-averse / less trading. |
| Scaling of modeled costs in the optimizer | `cost_multiplier` | `1.0` | Cost multiplier (Section 5). |
| No-trade tolerance band | `tracking_error_buffer` | `0.0125` | Tracking-error buffer; only re-trade when tracking error exceeds it. |
| Correlation-matrix stabilization | `shrink_instrument_returns_correlation` | `0.5` | Shrink the instrument-return correlation matrix 50% toward its mean before computing Σ for the tracking-error objective. |

Supporting key: `instrument_returns_correlation` (defaults.yaml ~L308) defines how
the instrument-return correlation matrix used by the optimizer is estimated
(weekly, exponential `ew_lookback: 75`, `clip: 0.99`) — this is the Σ that the
tracking-error objective and the shrink factor act on.

Also note the separate optimizer `cost_multiplier` keys at defaults.yaml L185
(`forecast_weight_estimate`, value `2.0`) and L263 (`instrument_weight_estimate`,
value `1.0`) — these belong to the *weight-estimation* optimizers, **not** the
dynamic optimizer, and are inactive here because `rob_system` uses fixed
(handcrafted) weights.

---

## How the layers compose (one-line recap)
Risk target ÷ instrument vol gives a sizing scalar; the **combined forecast**
(rules × forecast weights × **FDM**) scales it; **instrument weights × IDM**
assemble the cross-instrument book to hit the account risk target — all in fractional
contracts. **Dynamic optimization** then finds the integer portfolio with minimum
tracking error to that ideal (greedy, sign-constrained, one contract at a time),
trading only when tracking error breaks the buffer and penalizing turnover via the
shadow cost. That last step is what lets a finite-capital account capture the
diversification of a 150-instrument portfolio it could never hold by naive rounding.

---

## Sources
- Index: https://qoppac.blogspot.com/p/pysystemtrade.html
- My trading system (vol targeting, forecasts, position sizing): https://qoppac.blogspot.com/2021/12/my-trading-system.html
- Correlations, weights, multipliers (handcrafting, FDM, IDM): https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html
- Diversification and small account size (granularity problem): https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html
- Optimising my way out of a small fund problem — part one (dynamic opt concept, Black-Litterman framing): https://qoppac.blogspot.com/2021/06/optimising-my-way-out-of-small-fund.html
- Optimising portfolios for small accounts: Dynamic optimisation testing -> EPIC FAIL (return-grid attempt that failed): https://qoppac.blogspot.com/2021/06/optimising-portfolios-for-small.html
- Mr Greedy and the Tale of the Minimum Tracking Error Variance (the winning method): https://qoppac.blogspot.com/2021/10/mr-greedy-and-tale-of-minimum-tracking.html

### Notes on fetching
- All qoppac/Blogspot posts fetched cleanly as rendered HTML/markdown.
- One URL initially tried for the "testing" post (`2021/07/optimising-portfolios-for-small.html`) returned HTTP 404; the correct URL is the `2021/06/` one listed above, which fetched fine.
</content>
</invoke>
