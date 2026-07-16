# Rob Carver on Volatility Targeting and Why Diversified Systems Under-Realise Their Target

Research note compiled from primary sources (Rob Carver's blog *qoppac.blogspot.com* and his
books, where referenced). Focus: **why a diversified systematic futures system tends to realise
LESS annualised volatility than its target**, and what Rob himself says about the Instrument
Diversification Multiplier (IDM), correlation estimation, vol attenuation, and the risk overlay.

Compiled 2026-07-16. Every substantive claim is tagged with a source; see the **Sources** section
at the end. Claims not directly confirmable from a primary source are tagged **[unverified]**.

---

## 0. TL;DR

Rob Carver's own writing corroborates most of the vol-shortfall hypothesis, but attributes the
shortfall to several stacked, deliberate conservatisms rather than a single cause:

1. **He caps the IDM at 2.5** and explicitly notes his live IDM is "somewhat below the estimated
   value" because of that ceiling — i.e. the cap sits below the diversification the portfolio
   actually offers. This is a direct, by-design suppressor of deployed risk.
2. **He runs a fixed vol target "on average"**, and expects daily realised risk to deviate from it
   because of forecast strength and a "relative correlation factor" (correlations used for sizing
   differ from realised correlations).
3. **A risk overlay** (three conservative multipliers, all ≤ 1) knocks roughly **3% off both return
   and risk** every year — a permanent downward bias on realised vol, by design.
4. **Vol attenuation** (scaling forecasts down when vol is high, `L = 2 − 1.5Q`) lowers average
   deployed risk in exchange for a better Sharpe.

So: under-realisation is **largely expected and by design** in Rob's framework. See the "Bottom
line" section for how this maps onto our 20%-target / ~15%-realised situation.

---

## 1. The Instrument Diversification Multiplier (IDM)

### 1.1 What it is and the formula

Carver defines the IDM from the portfolio standard deviation. If instrument weights are `w` and the
correlation matrix is `H`, then (assuming each instrument's return stream is scaled to unit
standard deviation, so covariance can be replaced by correlation):

> IDM = `1 / sqrt(w H w')`

with **IDM² equal to the number of effective independent bets** in the portfolio. Worked example he
gives: two uncorrelated, equally weighted assets → `wHw' = 0.5`, `sqrt(wHw') = 0.707`,
`1/sqrt(wHw') = 1.414` (= √2, the classic two-independent-bets result).
[Source: "I got more than 99 instruments…", 2023]

The IDM is "the inverse of how much risk should fall versus trading a portfolio of just one
instrument" — i.e. it is the scale-up factor you apply to sub-system positions so that the *whole
portfolio* hits the target vol even though it is diversified.
[Source: search summary of qoppac IDM posts]

### 1.2 How correlations are estimated (and the conservatisms baked in)

From the pysystemtrade config Carver describes, the correlation estimate used for the IDM is
deliberately conservative in several ways:
[Source: "Correlations, Weights, Multipliers…", 2016]

- **Pooled across instruments** (`pool_instruments: True`) — uses a pooled/average correlation
  structure rather than per-instrument idiosyncratic correlations.
- **Downsampled to weekly** frequency before estimating correlations.
- **Exponentially weighted** with a long lookback (~250 periods), so the estimate carries a long
  memory that **averages in past crisis/high-correlation regimes**.
- **Negative correlations floored at zero** (`floor_at_zero: True`) — you get *no* diversification
  credit for genuinely negatively correlated instruments. This is a one-directional haircut that
  pushes the estimated correlation matrix *up*, and therefore the IDM *down*.
- Missing-data instruments are assigned the **average correlation** (not upweighted), because he is
  "already penalising instruments without enough data by giving them lower weights."

Each of these choices makes the correlation matrix used for sizing **higher (more correlated) than a
naive point estimate**, which mechanically **lowers the IDM** and hence lowers deployed risk. This
is the "prices forward correlation conservatively" mechanism in our hypothesis, stated in Rob's own
config.

### 1.3 The cap at 2.5 — and his acknowledgement it sits *below* the estimate

This is the single most on-point quote for the hypothesis. In "My trading system" (2021), describing
his *live* system:

> "The IDM is 2.5; somewhat below the estimated value (readers of *Systematic Trading* will know
> that I set a ceiling on this value of 2.5)."
[Source: "My trading system", 2021]

Two things follow directly:

- He **caps the IDM at 2.5** as a matter of policy (the ceiling comes from *Systematic Trading*).
- His **estimated** IDM is *higher* than 2.5, so the cap is **binding** and **actively holds
  deployed risk below** what the diversification estimate would justify. He accepts this trade-off
  knowingly.

Note the tension with his research post ("I got more than 99 instruments…", 2023), where the
*computed* IDM for a 100-instrument trend portfolio reaches **~4.2** (and ~4.8 long-only). So an
un-capped, richly diversified portfolio can have an IDM well north of 4, yet his production ceiling
is 2.5 — a very large deliberate haircut to deployed risk.
[Source: "I got more than 99 instruments…", 2023]

**Why cap it?** The rationale (from *Systematic Trading*, as he references it) is robustness:
estimated correlations are noisy and tend to *break down in crises* (everything correlates toward 1
exactly when you need diversification), so a high estimated IDM overstates the diversification you
can actually rely on. Capping protects against realising far *more* than target vol in a
correlation shock. The cost is chronic under-realisation in benign periods.
[Rationale attribution to *Systematic Trading* — the numeric ceiling of 2.5 is confirmed; the full
robustness argument as phrased here is **[unverified]** against the exact book text.]

### 1.4 IDM vs number of instruments (diminishing returns)

- Common IDM ranges cited: **1 → 2.5 for multi-asset-class** portfolios, **1 → 1.4 for
  single-asset-class**, both approaching their max around the **30+ instrument** level, beyond which
  additional instruments add little diversification.
  [Source: search summary of qoppac / Raposa write-ups of Carver — treat exact ranges as
  **[unverified]** vs the primary text.]
- In his 2023 research, **long-only diversification asymptotes ~50 instruments**, but **trend
  following keeps benefiting past 100** ("the blue line here is still going, suggesting adding even
  more instruments could potentially boost SR further").
  [Source: "I got more than 99 instruments…", 2023]

**Implication for deployable vol:** more (low-correlation) instruments raise the *estimated* IDM, so
in principle let you deploy closer to target. But once the estimate exceeds the 2.5 cap, adding
instruments **stops helping you reach target vol** — the cap, not the instrument count, is binding.
This matches our finding that un-capping the IDM barely moved realised vol (2.50→2.84, 15.2→15.5%):
the marginal diversification is real but small relative to the gap, and the shortfall is being
driven by the correlation *level* and the other conservatisms below, not by the cap alone.

---

## 2. Achieved vs Target Volatility — does he under-realise?

### 2.1 It's a "target on average", not a daily guarantee

In "Should I run my trading system at a fixed expected volatility target?" (2020), Carver:

- States his risk target is **an annual standard deviation of returns, "and happens to be 25%."**
- Says the intent is that **"the actual ex-post standard deviation of returns in my backtest should
  also be 25% on average."** — emphasis his: **"The important word here is on average."**
[Source: "Should I run my trading system at a fixed volatility target?", 2020]

So the target is a long-run average; daily/period realised vol is expected to scatter around it.

### 2.2 The two drivers of deviation he names

He attributes deviation of *expected* daily risk from the target to:

1. **Forecast strength** — "A higher forecast means we have higher conviction in our trades, and
   thus our expected risk should be higher." When forecasts are weak/mixed across the book (which is
   common — many instruments flat or fighting each other), the *combined* forecast is below its
   average, so deployed risk sits below target. This is a portfolio-level dilution that does **not**
   show up at the single-subsystem level (each subsystem is sized to over-realise when its own
   forecast is strong).
2. **Relative correlation factor (RCF)** — the mismatch between the **historical average
   correlations used for position sizing** and the **current/realised correlations**. On days when
   realised correlations differ from the sizing correlations, "our actual expected risk may be quite
   different from 25%."
[Source: "Should I run my trading system at a fixed volatility target?", 2020]

The RCF is exactly the "correlation estimate is conservative → under-realise" channel in our
hypothesis, in Rob's own terms: if the sizing correlations are set higher (more conservative) than
what actually realises in normal times, the RCF is persistently < 1 and realised vol sits below
target on average.

### 2.3 Which stat he cares about most

When judging a system's health, Carver ranks **realised volatility vs expectation as the #1 check**,
ahead of costs-vs-expectation and skew — i.e. he treats a persistent vol gap as a first-order
diagnostic, not a rounding error.
[Source: search summary of "Skew and Trend following" / podcast discussions — **[unverified]**
against exact wording.]

### 2.4 Live-system undershoot ("doesn't bother me") — status

A widely-cited paraphrase is that in *live* trading Rob has "undershot [the 25% target] quite
consistently, and this doesn't bother me," and that "average realised volatility is about right; if
anything a little lower and more conservative than it should be," which he attributes to the risk
overlay. I could **not** locate this exact phrasing verbatim in the primary posts fetched (it did
not appear in the 2020 fixed-target post, the Oct-2020 archive, or "My trading system" 2021).

- **Status: [unverified] as a direct quote.** The *substance* is, however, well supported by §1.3
  (binding IDM cap below estimate), §2.2 (RCF < 1), and §3 (risk overlay knocks ~3% off risk) —
  each of which independently biases live realised vol below target and is described by Rob as
  acceptable/by-design.

---

## 3. The Risk Overlay — a permanent downward bias on realised vol

In "When endogenous risk management isn't enough: a simple risk overlay" (2020), Carver adds an
overlay on top of the normal vol-targeting machinery. It computes **three multipliers, each in
[0,1]**, and takes the **most conservative (lowest)**:
[Source: "When endogenous risk management isn't enough…", 2020]

1. **Maximum expected risk:** `min(1, 2 × target risk / current expected risk)` — caps expected
   Gaussian risk at 2× target.
2. **Correlation risk (crisis correlations):** recompute expected risk with the **worst-possible
   correlation matrix (all correlations = 1)**, then `min(1, 4 × target risk / that risk)`. This is
   the explicit "diversifying positions suddenly all correlate in a crisis" guard. He notes
   "correlations do vary especially in the kind of crisis we've just seen."
3. **Standard-deviation risk:** use the **99th percentile** of each instrument's historical vol
   instead of current vol, then `min(1, 6 × target risk / that risk)`.

Effect he reports: the overlay **"knock[s] about 3% annually off both the returns and the risk."**
[Source: "When endogenous risk management isn't enough…", 2020]

This is a structural, always-on-or-latent downward bias: because the overlay can only reduce
positions (multiplier ≤ 1), the *average* effect over time is to pull realised vol **below** the
nominal target — again, by design, to protect against tail/correlation events. A follow-up refines
this into an *exogenous* (VIX-style) overlay but the same asymmetry applies.
[Source: "Exogenous risk overlay: take two", 2022]

---

## 4. Vol Attenuation (scaling risk down when vol is high)

Carver's dedicated treatment is "Does it make sense to change your trading behaviour in different
periods of volatility?" (2021). Mechanism:
[Source: "Does it make sense to change your trading behaviour…", 2021]

- Compute a **volatility percentile Q** (where current vol sits in its own history), then multiply
  the **raw forecast** by an attenuation factor:

  > `L = 2 − 1.5 × Q`

  So `L` ranges from **2.0 in the calmest regime down to 0.5 in the most volatile regime**.
- Applied to raw forecasts **before** forecast scalars (so re-estimated scalars keep correct
  scaling), and **smoothed with a 10-day EWMA** to avoid whipsaw.
- Result: **Sharpe improves modestly but consistently** across rules (e.g. ewmac2_8 0.43→0.52;
  carry 1.07→1.11), most statistically significant. Conclusion: **"scaling back your positions
  during periods of high vol"** universally helps.

Consequence for realised vol: because attenuation cuts exposure hard in high-vol regimes (down to
0.5×) and only lifts it to 2× in calm regimes on the *forecast* (still subject to the +20 forecast
cap and the overlay), the **average deployed risk is lowered**, contributing to sub-target realised
vol. He accepts this because it buys Sharpe and skew protection.

Related: the general vol-targeting "paradox" he describes — "We are long. The price jumps up. Good.
But this means the risk goes up. So cut our position, just as we're finally making serious money."
Vol targeting itself already trims exposure into rising-vol trends; attenuation goes further.
[Source: "Vol Targeting and Trend Following", 2018]

---

## 5. Number of Instruments, Correlation and Deployable Vol ("cost of diversification")

- Even one extra random instrument can lift a single-instrument system's Sharpe ~20%; benefits slow
  markedly beyond ~20–30 instruments. [Source: search summary — **[unverified]** exact figures.]
- **"Diversification is a free lunch, but you still need to get to the buffet":** capturing the
  diversification requires **more capital** (to hold the many small positions at whole-contract
  granularity) or **dynamic optimisation** to fit the target book under a capital constraint.
  [Source: "I got more than 99 instruments…", 2023]
- This is directly relevant to our **integer-rounding** shortfall (15% fractional → 11–13% at
  $250k): at a given account size you cannot hold enough contracts to realise the fractional target;
  Rob's answer is either more capital or his dynamic optimisation (buffered integer optimiser), not a
  higher IDM.

---

## 6. Does he run a HIGHER target to compensate? What target does he actually use?

- **His live/backtest target is 25% annualised** (repeatedly stated).
  [Sources: "Should I run…", 2020; "My trading system", 2021 (implied via the 1.06/25 speed-limit
  calc).]
- 25% is already *high* relative to most institutional CTAs (who run nearer 10–15%). One reading:
  he sets a **high nominal target precisely because the stacked conservatisms (capped IDM, RCF < 1,
  overlay, attenuation) mean he will realise materially less** than the nominal number — so 25%
  nominal lands at a sane realised figure after all the haircuts. This is a plausible, and
  commonly-inferred, rationale but I did **not** find him stating "I set the target high to
  compensate for under-realisation" in these words. **[unverified] as an explicit claim.**
- His **Advanced Futures Trading Strategies (AFTS)** strategies are typically illustrated at a
  ~**20% target** for individual strategy examples; the exact per-strategy target varies by
  chapter. **[unverified]** against the book text here.

---

## 7. Is under-realising EXPECTED / BY DESIGN?

Yes — the framework treats sub-target realised vol as an acceptable consequence of robustness, on
multiple independent grounds, each sourced above:

- **Capped IDM below estimate** (§1.3): a deliberate policy ceiling that holds deployed risk below
  the diversification the portfolio nominally offers, to survive correlation shocks.
- **RCF and "on average"** (§2.1–2.2): the target is a long-run average; conservative sizing
  correlations bias the RCF < 1 in normal times.
- **Risk overlay** (§3): can only cut, so it structurally shaves ~3% off realised risk, explicitly
  to guard against crisis correlations (all-correlations-to-1 scenario).
- **Vol attenuation** (§4): trades average deployed risk for Sharpe/skew.

The common thread is the **crisis-correlation-protection argument**: correlations that look
diversifying in calm periods snap toward 1 in a crisis, so a system sized to hit target *given calm
correlations* would blow through target in a crisis. Rob deliberately sizes for the pessimistic
correlation case, which necessarily under-deploys risk the rest of the time.

---

## 8. Bottom line for our vol-shortfall question

**Our situation:** rob_system-style trend+carry, 20% target, ~15% realised (fractional), ~11–13%
after integer rounding at $250k; subsystems over-realise (~23%); shortfall is at the *portfolio*
level; un-capping IDM barely helps (2.50→2.84, 15.2→15.5%).

**Does Rob corroborate the hypothesis?** Largely **yes**, with an important refinement:

1. **IDM cap** — Confirmed as real and by-design ("ceiling of 2.5"; his live IDM is "somewhat below
   the estimated value"). BUT our own test (un-capping barely moved realised vol) matches his data:
   the cap is only *part* of the story. Once you're diversified, the *level* of the estimated
   correlations — not the cap — is the dominant lever. That points at the **correlation estimator
   itself** (pooled, weekly, long-EWMA, negatives floored at zero) as the primary suppressor, which
   Rob's config confirms is deliberately conservative (§1.2). This is your "prices forward
   correlation conservatively / averages in crisis periods" hypothesis, and Rob's estimator settings
   directly support it.

2. **Portfolio-level, not subsystem-level** — Confirmed and expected. Subsystems are sized to their
   own vol and over-realise when their forecast is strong; the portfolio dilutes because (a) the RCF
   (sizing-vs-realised correlation gap) runs < 1 in normal times, and (b) cross-instrument forecasts
   are usually not all strong/aligned. Rob's "forecast strength" + "RCF" decomposition (§2.2) is
   exactly this mechanism.

3. **By design?** Yes. Rob explicitly accepts realised < nominal target as the price of robustness
   against correlation shocks, and stacks *additional* deliberate reducers (risk overlay ≈ −3%,
   vol attenuation) on top. So chronic under-realisation is a feature, not a bug, in his framework.

4. **What actually closes the gap (per Rob), if you want to):**
   - Not un-capping the IDM (matches our result: negligible).
   - Rather: **less-conservative correlation estimation** (shorter lookback / less crisis-weighting /
     don't floor negatives at zero) if you accept more crisis risk — this is the real lever on the
     RCF and the IDM level. This is a **structural/ex-ante** change (correlation methodology), not a
     P&L-based one, so it's compatible with the no-in-sample-fitting rule.
   - **More capital or dynamic (buffered integer) optimisation** to recover the integer-rounding
     portion of the loss (15%→11–13%). Rob's stated answer to the rounding problem is capital or his
     dynamic optimiser, not a higher IDM.
   - Or simply **raise the nominal target** knowing the machinery will shave it — which is arguably
     why *his* nominal target is 25% while realised lands lower. (His explicit "set it high to
     compensate" statement is **[unverified]**, but the numbers are consistent with it.)

**One caveat to flag:** if you reduce the correlation conservatism to hit 20% realised, you are
deliberately giving up some of the crisis protection Rob built in — you'll realise closer to target
in calm periods but can overshoot target in a correlation shock. That is the exact trade-off the cap
and the conservative estimator exist to prevent.

---

## Sources

- **"Should I run my trading system at a fixed expected volatility target?"** (2020) —
  https://qoppac.blogspot.com/2020/10/should-i-run-my-trading-system-at-fixed.html
  — Target is 25% annual SD; "on average"; deviation driven by forecast strength and the relative
  correlation factor (RCF).
- **"My trading system"** (2021) —
  https://qoppac.blogspot.com/2021/12/my-trading-system.html
  — "The IDM is 2.5; somewhat below the estimated value … I set a ceiling on this value of 2.5";
  25% target implied via the 1.06/25 speed-limit calc.
- **"I got more than 99 instruments in my portfolio…"** (2023) —
  https://qoppac.blogspot.com/2023/03/i-got-more-than-99-instruments-in-my.html
  — IDM = 1/sqrt(wHw'), IDM² = independent bets; computed IDM ~4.2 (trend)/~4.8 (long-only) for 100
  instruments; long-only asymptotes ~50, trend keeps benefiting; "free lunch but you still need to
  get to the buffet" (capital / dynamic optimisation).
- **"Correlations, Weights, Multipliers…. (pysystemtrade)"** (2016) —
  https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html
  — Correlation estimator config: pooled instruments, weekly downsampling, ~250 EWMA, floor
  negatives at zero, missing-data = average correlation. (The conservatism baked into IDM inputs.)
- **"When endogenous risk management isn't enough: a simple risk overlay"** (2020) —
  https://qoppac.blogspot.com/2020/05/when-endogenous-risk-management-isnt.html
  — Three risk-overlay multipliers (2×/4×-worst-correlations/6×-99th-pct-vol, take the min); "knocks
  about 3% annually off both returns and risk"; crisis-correlation guard.
- **"Exogenous risk overlay: take two"** (2022) —
  https://qoppac.blogspot.com/2022/02/exogenous-risk-overlay-take-two.html
  — Refinement of the overlay to an exogenous (market-vol) signal; same only-can-reduce asymmetry.
- **"Does it make sense to change your trading behaviour in different periods of volatility?"** (2021) —
  https://qoppac.blogspot.com/2021/03/does-it-make-sense-to-change-your.html
  — Vol attenuation: L = 2 − 1.5Q (2.0 calm → 0.5 volatile), applied to raw forecasts, 10-day EWMA
  smoothing; modest consistent Sharpe gains; "scale back positions during periods of high vol."
- **"Vol Targeting and Trend Following"** (2018) —
  https://qoppac.blogspot.com/2018/07/vol-targeting-and-trend-following.html
  — The vol-targeting "paradox" (cut into rising-vol winners); vol targeting improves Sharpe at some
  cost to skew ("waterbed effect").
- **"Skew and Trend following"** (2019) —
  https://qoppac.blogspot.com/2019/02/skew-and-trend-following.html
  — Context on realised-vol-vs-expectation being a top diagnostic; trend is positively skewed
  (used for the [unverified] §2.3 point).

### Books referenced (not fetched here; treat book-specific numbers as [unverified])
- *Systematic Trading* (Carver) — origin of the IDM ceiling of 2.5 (referenced in "My trading
  system").
- *Advanced Futures Trading Strategies* (Carver) — per-strategy vol targets (commonly ~20%);
  exact figures **[unverified]** here.

### Verification flags
- **[unverified]** Exact live-system quote "undershot consistently … doesn't bother me / average
  realised vol a little lower and more conservative than it should be." Substance supported by
  §1.3, §2.2, §3, but not confirmed verbatim in the fetched posts.
- **[unverified]** IDM range tables (1→2.5 multi-asset, 1→1.4 single-asset, max at 30+) — from
  secondary summaries, not the primary text.
- **[unverified]** "Sets target high to compensate for under-realisation" — inferred/consistent,
  not stated in these words.
- **[unverified]** AFTS per-strategy target figures.
