# In-Sample Fitting & Backtest Overfitting — Reference Note

*Compiled 2026-07-15. A cited synthesis of (1) Rob Carver's writing/philosophy and (2) the academic literature on backtest overfitting, written to underpin this project's rule against selecting, dropping, or reweighting instruments on the basis of backtest P&L.*

---

## Why this note exists

This project is a Rob-Carver-style diversified **trend + carry futures system** (`pysystemtrade`) run with a dynamic optimizer over roughly **117 instruments**, **$250k** capital, and a **20% annualised volatility target**. The standing project rule is:

> **Never select, drop, or reweight instruments by backtest P&L. Include or exclude an instrument only on ex-ante structural grounds** — liquidity, minimum capital / contract size, cost and speed-limit, and data trustworthiness — not because its historical simulated return was good or bad.

That rule is not arbitrary caution. It is the direct, practical consequence of two independent bodies of evidence that arrive at the same conclusion from different directions:

1. **Rob Carver's practitioner philosophy** — treat parameter and weight choice as a *diversification* problem, not an *optimization* problem; prefer robust to optimal; handcraft rather than mean-variance optimize; pool data across instruments; and never let the researcher's knowledge of the full sample leak into the design. Carver names the specific failure mode we are guarding against — **implicit fitting** and **selection bias** — as two of his "three Judases" of overfitting.
2. **The academic multiple-testing literature** — Bailey & López de Prado (Deflated Sharpe Ratio, Probability of Backtest Overfitting, *Pseudo-Mathematics and Financial Charlatanism*), Harvey & Liu (the Sharpe "haircut"), and Harvey, Liu & Zhu (the *t* > 3 hurdle), building on White's Reality Check and Hansen's SPA test. Their central, quantified finding: **the more strategies/variants/instruments you look at, the higher the best observed Sharpe ratio will be even with zero true skill** — so an uncorrected backtest that does not disclose the number of trials is, in Bailey & López de Prado's words, *"worthless, regardless of how excellent the reported performance might be."* [DSR]

Selecting instruments by backtest P&L is exactly a multiple-testing search over ~117 candidate return series. It inflates the reported Sharpe of the surviving universe by a mechanism the literature can quantify — and Carver's own fund-level discipline is built to prevent. This note collects the primary sources so that any future universe/weight/parameter change can be checked against them.

---

## Part 1 — Rob Carver's philosophy

### 1.1 The three ways to overfit: explicit, implicit, and selection bias

Carver decomposes overfitting into three mechanisms (his "three Judases"), and the distinction is the crux of this project's rule [ReSolve]:

- **Explicit fitting** — automated parameter optimisation (e.g. a walk-forward optimiser choosing a lookback). Manageable *if* done as a genuine out-of-sample / expanding-window test.
- **Implicit fitting** — manually tweaking parameters after looking at the results. The researcher unconsciously optimises using knowledge of the *whole* sample, so the "out-of-sample" claim is false. Carver's general principle: *"if you've used the whole data set to make a decision about what the parameters should be, you've still done something that someone who was doing a truly out-of-sample test couldn't possibly do."* [robust-search summary]
- **Selection bias** — **dropping under-performing strategies (or instruments) before/after backtesting inflates the reported result.** [ReSolve]

**This third mechanism is precisely instrument selection by P&L.** Deciding to keep instruments whose backtest looked good and drop those whose backtest looked bad is selection bias — a form of overfitting — regardless of whether you ever touched a single parameter. Carver's institutional fix is to keep a **fund-level backtest that includes *all* attempted strategies**, and let a portfolio-allocation algorithm gently down-weight degraded ones over time, rather than deleting them by hand. [ReSolve]

> **Sources:** ReSolve "Uncertainty Principles" interview (three Judases, fund-level backtest); Better System Trader ep. 026 (robust rules).
> https://investresolve.com/podcasts/rob-carver-uncertainty-principles/
> https://bettersystemtrader.com/026-robert-carver/

### 1.2 Robust rather than optimal — "no single true set of parameters"

Carver's criteria for a good trading rule: it must **not be overfitted** ("work across a variety of market conditions, not just the specific period you tested it on"), be **simple** ("more complicated rules are more likely to have been overfitted and relatively simple rules, less so"), and have a **plausible economic rationale** (black-box rules fail because you cannot tell when the regime has changed). [BetterSystemTrader]

He explicitly treats parameter choice as a **diversification problem, not an optimization problem**: there is *no single best parameter set* waiting to be discovered by short-window walk-forward tests. Instead of picking one "optimal" lookback, identify a **plateau of parameters that perform consistently**, and — crucially — his research finds that **averaging across parameter variations beats selecting the single best prior-window performer**: *"Trading rule returns are pretty noisy from year to year... it's really hard to pick out which one is the best. And by far the best approach is just to take an average."* [BetterSystemTrader]

He also warns that a year of live/OOS data is far too little to judge a rule: *"A year is a very, very short period of time to actually find any sort of statistical evidence about whether something is working or not"* — his research points to **~10 years** as a minimum to distinguish signal from noise, which is why single-window walk-forward is statistically weak. [BetterSystemTrader]

> **Sources:** Better System Trader ep. 026.
> https://bettersystemtrader.com/026-robert-carver/

### 1.3 The complexity/overfitting demonstration (EWMAC)

In "Quickies #1: Overfitting and EWMAC forecast scalars," Carver shows the canonical overfitting curve empirically: increasing model complexity keeps improving *in-sample* performance up to a point, then out-of-sample performance **radically deteriorates**. A complex 16-period model fitted to Microsoft pre-2015 performs terribly on post-2015 Microsoft data *and* terribly when applied to Apple — it fitted instrument-specific noise. A simple 64-day trend model stays stable across training periods and transfers to new instruments. The lesson: *robust, simpler models generalize; optimized complex ones do not.* [Quickies1]

> **Source:** qoppac "Quickies #1: Overfitting and EWMAC forecast scalars" (Jun 2025).
> https://qoppac.blogspot.com/2025/06/quickies-1-overfitting-and-ewmac.html

### 1.4 Handcrafting instead of mean-variance optimization

Carver rejects mean-variance / Markowitz optimization for portfolio (and forecast/instrument) weights because it is **unstable and non-robust**: *"Small differences in these estimates can result in highly unstable, extreme, weights"*, routinely producing corner solutions like *"0% and 100% in a two asset problem"* that are *"intuitively unattractive to humans, and... more likely to perform badly in out of sample testing."* The root cause is estimation uncertainty — *"We cannot know the optimal portfolio weights with any certainty"* — with **expected returns / Sharpe ratios the largest source of uncertainty**, while volatilities and correlations are estimated more reliably. [Handcraft-motivating]

His **handcrafting** alternative is a heuristic designed to be transparent, robust, and reproducible by a human in a spreadsheet [Handcraft-method]:

- **Hierarchical grouping** — nest assets into groups of similar things, similarity measured by correlation; allocate between groups, then within groups.
- **Equal risk (inverse-vol) weighting within a group** as the robust default, on the assumption that Sharpe ratios within comparable groups are *statistically indistinguishable*.
- A **diversification multiplier** = ratio of group risk to single-asset risk, so highly-correlated groups don't get over-allocated.
- An **optional Sharpe-ratio adjustment** that is *bounded*: the weight multiplier is never below **0.6** nor above **1.4**, so even when you do lean on relative Sharpe, you cannot produce extreme weights. [handcraft-heuristic summary]

The design principle throughout is to **build around estimation uncertainty rather than pretend precise forecasts exist**. For allocating across *trading strategies* (as opposed to individual instruments), correlations are lower and more stable, supporting longer (~5-year) lookbacks; volatility uses ~30d–6m, correlations ~6–12m, and he *avoids predicting Sharpe ratios for strategic allocation entirely* because factor/strategy timing is among the hardest forecasting problems in finance. [ReSolve]

> **Sources:** qoppac handcrafting "motivating" and "method" posts; ReSolve interview.
> https://qoppac.blogspot.com/2018/12/portfolio-construction-through.html
> https://qoppac.blogspot.com/2018/12/portfolio-construction-through_7.html
> https://investresolve.com/podcasts/rob-carver-uncertainty-principles/

### 1.5 Pooling trading-rule fitting across instruments

When fitting forecast weights, Carver's tested conclusion is to **pool information across markets** rather than fit each instrument on its own: *"There just isn't enough meaningful information in a single market"* to estimate weights reliably, so instrument-by-instrument fitting overfits noise. His preferred method is to **pool gross returns across instruments, then apply each instrument's own costs** (so expensive instruments end up trading slower). Because trading-rule correlation structures are similar across markets, pooling gains statistical power without much loss of accuracy, and *"fitting by grouped instruments will make things more robust and also probably improve performance."* He also notes that for simple, well-filtered rule sets with regular correlation structure, **equal weighting beats all optimization approaches**, and that the robust method *"will mostly correct for anything you do that is stupid."* [Pooling]

> **Source:** qoppac "Fit forecast weights by instrument, by group or fit across all markets?" (May 2021).
> https://qoppac.blogspot.com/2021/05/fit-forecast-weights-by-instrument-by.html

### 1.6 Expanding-window (out-of-sample) backtesting

`pysystemtrade` fits variable forecast/instrument weights and diversification multipliers using an **expanding-window** ("expanding date") method with bootstrapping over pooled gross daily returns, and smooths the resulting weights (`forecast_weight_ewma_span` and the instrument equivalent). Expanding-window means each estimate uses **only data available up to that date** — the genuine out-of-sample discipline Carver insists on, and the antidote to implicit fitting from §1.1. [Pysys-weights]

> **Sources:** qoppac "Correlations, Weights, Multipliers... (pysystemtrade)"; qoppac "Optimising weights with costs".
> https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html
> https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html

---

## Part 2 — The academic literature on backtest overfitting

### 2.1 The core mechanism: more trials → higher best observed Sharpe, even with zero skill

Bailey & López de Prado frame it bluntly: with modern compute, analysts backtest *"millions (if not billions)"* of strategy variants, and *"the most important piece of information missing from virtually all backtests... is the number of trials attempted."* Without it, *"a backtest where the researcher has not controlled for the extent of the search involved in his or her finding is worthless, regardless of how excellent the reported performance might be."* [DSR]

The formal result (Deflated Sharpe Ratio paper, Eq. 1). For **N independent trials** whose Sharpe estimates $\{\widehat{SR}_n\}$ have mean $E[\{\widehat{SR}_n\}]$ and variance $V[\{\widehat{SR}_n\}]$, the **expected maximum** Sharpe is approximately:

$$
E\!\left[\max\{\widehat{SR}_n\}\right] \approx E[\{\widehat{SR}_n\}] + \sqrt{V[\{\widehat{SR}_n\}]}\left((1-\gamma)\,Z^{-1}\!\left[1-\tfrac{1}{N}\right] + \gamma\,Z^{-1}\!\left[1-\tfrac{1}{N}e^{-1}\right]\right)
$$

where $\gamma \approx 0.5772$ is the Euler–Mascheroni constant and $Z^{-1}$ is the inverse standard-Normal CDF. The message of the equation: **the expected best-of-N Sharpe grows with N and with the dispersion of trial Sharpes, even when the true mean Sharpe is zero.** *"We will observe better candidates even if there is no investment skill associated with this strategy class."* Selecting the winner over many alternatives exposes you to *"the winner's curse"* and out-of-sample *"regression to the mean."* [DSR, Eqs. 1–2]

> **Source:** Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014), *J. Portfolio Management*.
> https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
> SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

### 2.2 The Deflated Sharpe Ratio (DSR)

The DSR corrects the observed Sharpe for **both** selection bias under multiple testing **and** non-Normal returns (skew/kurtosis). It is the Probabilistic Sharpe Ratio (PSR) evaluated against a deflated benchmark $\widehat{SR}_0$ (DSR paper, Eq. 2):

$$
\widehat{DSR} \equiv \widehat{PSR}(\widehat{SR}_0) = Z\!\left[\frac{(\widehat{SR}-\widehat{SR}_0)\sqrt{T-1}}{\sqrt{1-\hat\gamma_3\,\widehat{SR}+\frac{\hat\gamma_4-1}{4}\,\widehat{SR}^2}}\right]
$$

where $\widehat{SR}$ is the estimated Sharpe of the *selected* strategy, $T$ the sample length, $\hat\gamma_3$ the skew and $\hat\gamma_4$ the kurtosis of returns, and $\widehat{SR}_0$ is the **expected maximum Sharpe under the null of zero skill** (from Eq. 1 above, using the variance across the trials and N). Practitioner reading:

- **Longer track record (T) helps** — the $\sqrt{T-1}$ term rewards more data.
- **Negative skew and fat tails hurt** — the denominator penalises strategies whose Sharpe rests on a short-option-like return profile.
- **More trials, or more dispersed trials, raise $\widehat{SR}_0$** — so the same raw Sharpe deflates toward insignificance the harder you searched.

DSR is a probability: it answers *"what is the chance the true Sharpe exceeds zero, given that this was the best of N tries?"* Related tools from the same authors: the **Probabilistic Sharpe Ratio** (Bailey & López de Prado 2012) and the **Minimum Track Record Length** (how long a track record must be for a Sharpe to be significant). [DSR]

> **Source:** as §2.1.

### 2.3 Probability of Backtest Overfitting (PBO) via CSCV

Bailey, Borwein, López de Prado & Zhu define **PBO** = the probability that the strategy which is **optimal in-sample underperforms the median strategy out-of-sample.** It is computed by **Combinatorially-Symmetric Cross-Validation (CSCV)** [PBO]:

1. Split the sample into **S** non-overlapping equal blocks.
2. Form all $\binom{S}{S/2}$ ways of splitting blocks into an in-sample (IS) half and its complementary out-of-sample (OOS) half — symmetric, so each IS combination's blocks are another's OOS.
3. For each split, pick the IS-best strategy and record its **rank OOS**.
4. **PBO** = fraction of splits in which the IS-best strategy lands **below the OOS median** (equivalently, the probability its OOS logit/rank is negative).

CSCV uses **ranks, not raw returns**, so it is non-parametric and robust to the magnitude of P&L. It cleanly demonstrates the danger of picking the best of many variants: a high PBO means "your in-sample winner is expected to be a below-average performer live." Critically, the same authors show that the **plain holdout method cannot fix this** — apply a 95% holdout test 20 times and a false positive is *expected*, not unlikely. [PBO]

> **Source:** Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting."
> https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
> SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

### 2.4 Pseudo-Mathematics and Financial Charlatanism (Notices of the AMS)

The same group's *Notices of the AMS* article (May 2014) makes the point accessibly and quantitatively: with enough trials you are *guaranteed* to find a spuriously profitable strategy, and because financial series have **memory** (mean reversion "undoes" extreme patterns rather than merely "diluting" them), overfitting doesn't just fail to help — it can systematically lead to **loss maximization** out of sample. Their headline number: due to data mining, **only ~7 trials are needed to produce a spurious 2-year backtest with an in-sample Sharpe > 1.0 whose expected out-of-sample Sharpe is zero** — the basis of the **Minimum Backtest Length** concept (a backtest shorter than a function of the number of trials is essentially certain to be overfit). [PseudoMath / DSR restatement]

> **Source:** Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism," *Notices of the AMS* 61(5), 2014.
> https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf
> SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659

### 2.5 Harvey & Liu — the Sharpe-ratio "haircut"

Harvey & Liu ("Backtesting," *J. Portfolio Management*, 2015) attack the same problem from classical multiple-testing statistics. A single strategy's Sharpe maps to a *t*-ratio ($\widehat{SR}=t/\sqrt{T}$ for a given sample length $T$; equivalently $t\text{-stat}=\hat\mu/(\hat\sigma/\sqrt{T})$). Under a **single** test, $t=2.0 \Rightarrow p=0.05$. But if you searched over **N** strategies and reported the best, the single-test p-value understates the truth. For N independent tests the multiple-testing ("family-wise") p-value is:

$$
p^{M} = 1-(1-p^{S})^{N}
$$

so e.g. with $N=10$ and single-test $p^{S}=0.05$, the honest $p^{M}\approx0.40$. Inverting $p^{M}=\Pr(|r|>\widehat{HSR}\cdot\sqrt{T})$ gives the **haircut Sharpe ratio** $\widehat{HSR}<\widehat{SR}$. Their worked example: **20 years of monthly data ($T=240$), an annual SR of 0.75 → single-test $p=0.0008$; but with $N=200$ tests, $p^{M}=0.15$, implying a haircut SR of ~0.32 — roughly a 60% haircut.** [HL]

Two practitioner-critical properties [HL]:

- **The 50% haircut rule-of-thumb is wrong.** The haircut is **nonlinear**: very high Sharpes are only *moderately* penalised (they are probably real discoveries — a 50% cut is *too punitive*), while **marginal Sharpes are penalised heavily** (they are probably data-mining artefacts — 50% is *too lenient*).
- They implement **three multiple-testing adjustments** — **Bonferroni** ($p^{Bonf}_{(i)}=\min[M p_{(i)},1]$, most conservative, controls family-wise error), **Holm** (sequential, less conservative, also FWER), and **Benjamini–Hochberg–Yekutieli / BHY** (controls the *false-discovery rate*, allows correlated tests) — and take stands on the number of tests using the ~316+ factors documented in Harvey–Liu–Zhu.

> **Source:** Harvey & Liu, "Backtesting" (2015).
> https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
> SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489

### 2.6 Harvey, Liu & Zhu — the *t* > 3 hurdle

In "…and the Cross-Section of Expected Returns" (*Review of Financial Studies*, 2016), Harvey, Liu & Zhu catalogue the hundreds of published "factors" and argue that after accounting for the sheer number of tests, *"it does not make any economic or statistical sense to use the usual significance criteria for a newly discovered factor, e.g., a t-ratio greater than 2.0."* A genuinely new factor should clear roughly **t > 3.0**, and *"most claimed research findings in financial economics are likely false."* Their framework allows for correlation among tests and for publication bias, and supplies the historical multiple-testing cutoffs Harvey & Liu use for the haircut. [HLZ]

> **Source:** Harvey, Liu & Zhu, "…and the Cross-Section of Expected Returns" (2016).
> https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF
> SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314

### 2.7 White's Reality Check and Hansen's SPA test

The foundational data-snooping tests. **White's Reality Check** (2000) is a bootstrap procedure that tests whether the **best** strategy from a universe of candidates genuinely beats a benchmark, *accounting for the full set of strategies examined* — so it corrects for the fact that the best-of-many will look good by luck. **Hansen's Superior Predictive Ability (SPA)** test (2005) improves the power of White's Reality Check by **re-centring the null distribution** and down-weighting irrelevant poor strategies, making it less sensitive to the inclusion of obviously-bad candidates. Both use stationary/block bootstraps and are the classical statistical answer to "is my best backtested rule real, or did I just try a lot of rules?" [SPA-refs — *secondary sources; White 2000 and Hansen 2005 primary papers not fetched directly* — [unverified] specifics of re-centring]

> **Sources (secondary):** arch SPA docs; survey of Reality Check extensions.
> https://arch.readthedocs.io/en/latest/multiple-comparison/generated/arch.bootstrap.SPA.html
> https://econweb.rutgers.edu/nswanson/papers/corradi_swanson_whitefest_1108_2011_09_06.pdf

---

## Part 3 — Answering the concrete questions

### 3.1 What counts as "implicit fitting" via SELECTION, and why is dropping instruments by P&L overfitting?

**Implicit fitting** is any design choice that uses knowledge of the *full sample* in a way a genuine out-of-sample analyst could not — even if no optimiser was run and no parameter was typed. Manually nudging a lookback after seeing the equity curve is implicit fitting; so is **keeping the instruments whose backtest looked good and cutting those whose backtest looked bad.**

Selecting/dropping instruments by backtest P&L is overfitting for three converging reasons:

1. **It is selection bias — Carver's third Judas.** You are choosing survivors from a set of return series on the basis of their realised in-sample performance. That is the definition of selection bias, and it inflates the surviving portfolio's Sharpe. [ReSolve]
2. **It is a multiple-testing search.** Choosing "the best K of ~117 instruments" is choosing the best of many trials. Eq. 1 (§2.1) says the expected best-of-N Sharpe rises with N *even with zero skill*; the surviving universe's backtest is therefore biased upward by construction, and the bias is largest exactly where per-instrument data is thinnest. [DSR]
3. **Memory makes it worse than neutral.** Because futures returns mean-revert, the instruments that looked best in-sample are disproportionately those that rode a non-repeating run — precisely the ones expected to *underperform* out of sample (high PBO / winner's curse / *Pseudo-Mathematics* loss-maximization). [PBO, PseudoMath]

The tell-tale: **P&L is an *ex-post*, sample-dependent quantity.** Any include/exclude decision that would change if you re-ran on a different historical window is fitting. Structural criteria (below) are *ex-ante* — they would give the same answer regardless of realised returns.

### 3.2 How the number of trials inflates Sharpe, and how DSR / Harvey–Liu quantify and correct it

**Inflation mechanism.** With N trials of dispersion $\sqrt{V[\{\widehat{SR}_n\}]}$, the expected maximum Sharpe is $E[\{\widehat{SR}_n\}] + \sqrt{V}\cdot(\ldots\text{grows in }N)$ (§2.1, Eq. 1). Try more variants, or variants that are more spread out, and the best one looks better — with **no** true edge required.

**Deflated Sharpe correction (López de Prado).** Compute $\widehat{SR}_0$ = expected max Sharpe under the null (Eq. 1, feeding in N and the variance across your trials), then evaluate DSR (Eq. 2, §2.2). DSR outputs the *probability the true Sharpe > 0*, after charging you for the number of looks, the sample length, and the return skew/kurtosis. Rule of thumb: DSR ≥ ~0.95 to treat a discovery as real; anything lower means the raw Sharpe is plausibly a fluke of the search.

**Harvey–Liu haircut correction.** Convert Sharpe → t-ratio, inflate the p-value for N tests ($p^{M}=1-(1-p^{S})^{N}$, or Bonferroni/Holm/BHY for correlated tests), then invert to a **haircut Sharpe**. Worked benchmark to memorise: **T=240 months, SR=0.75, N=200 tests → ~60% haircut to SR≈0.32.** And remember the shape: **high SR → small haircut, marginal SR → large haircut; the flat 50% rule-of-thumb is wrong.** [HL]

**Hurdle intuition (HLZ).** In a heavily-mined space, demand **t > 3**, not t > 2, before believing a result. [HLZ] For our system a rough analogue: a per-instrument or per-variant backtested edge that is only marginally positive should be assumed **spurious until proven otherwise**, and never used as an inclusion criterion.

### 3.3 The disciplined, ex-ante alternatives

1. **Structural instrument selection** (the project rule). Include/exclude only on:
   - **Liquidity** — enough volume/open interest to trade the required size without undue impact.
   - **Minimum capital / contract size** — can a $250k book at 20% vol hold a sensible position? A contract whose minimum increment is too large for the risk budget is excluded *structurally*, not by P&L. (Carver: "Diversification and small account size.")
   - **Cost & speed-limit** — expected trading cost per trade relative to the pre-cost edge; instruments too expensive for the strategy's turnover fail the "speed limit," independent of realised return. (Carver pools *gross* returns then applies each instrument's costs — §1.5.)
   - **Data trustworthiness** — clean, long, verifiable price history; suspect or short data is excluded on data-quality grounds, not because the backtest was poor.
2. **Handcrafting** portfolio/forecast/instrument weights instead of mean-variance optimization (§1.4): hierarchical grouping by correlation, equal-risk within groups, diversification multiplier, and *bounded* (0.6–1.4) Sharpe adjustments if any.
3. **Pooling across instruments** when fitting rule/forecast weights (§1.5): pool gross returns, apply per-instrument costs, fit by group not by single market.
4. **Expanding-window / genuine out-of-sample** estimation (§1.6): every parameter uses only data available up to that date; smooth the resulting weights.
5. **Robust-not-optimal parameters** (§1.2): choose a plateau, or average across variants, rather than the single in-sample-best; prefer simple rules with economic rationale.
6. **Fund-level backtest including everything** (§1.1): never delete a candidate by hand; let a robust allocator down-weight it, keeping the count-of-trials honest.

### 3.4 Practical rules of thumb BEFORE changing a universe, weights, or parameters

- **Would this decision change if the historical window were different?** If yes, it is fitting — stop.
- **Is the include/exclude reason *ex-ante structural* (liquidity, min-capital, cost, data) or *ex-post P&L*?** Only the former is allowed.
- **Count your trials.** If you looked at K instruments/variants and kept the best, you have K trials — apply a haircut mentally (SR≈0.75, N=200 → ~60% cut) before believing anything.
- **Demand t > 3 (not t > 2)** for any marginal edge you are tempted to act on.
- **Prefer averaging/plateaus over the single best.** Diversify parameters; don't optimise them.
- **Pool, don't per-instrument-fit.** Single-market data is too thin to fit reliably.
- **Use expanding-window estimation and smooth weights.** No full-sample peeking.
- **Keep the whole universe in the fund-level backtest**; down-weight, don't delete.
- **Ten years, not one.** Don't conclude a rule is dead (or alive) on a year of data.
- **Bound your weight adjustments** (0.6–1.4) so no single input can produce an extreme allocation.

---

## Sources

- **https://qoppac.blogspot.com/2025/06/quickies-1-overfitting-and-ewmac.html** — Carver's empirical demonstration that model complexity boosts in-sample but destroys out-of-sample performance (EWMAC / Microsoft example).
- **https://bettersystemtrader.com/026-robert-carver/** — Carver interview: robust-not-overfitted rules, simplicity, averaging beats selecting the best parameter, ~10 years needed for statistical evidence.
- **https://investresolve.com/podcasts/rob-carver-uncertainty-principles/** — Carver on the "three Judases" (explicit fitting, implicit fitting, selection bias), fund-level backtest, distrust of optimization, handcrafting, and uncertainty.
- **https://qoppac.blogspot.com/2018/12/portfolio-construction-through.html** — Handcrafting *motivation*: why mean-variance produces extreme/non-robust weights; estimation uncertainty; expected returns as the biggest source of error.
- **https://qoppac.blogspot.com/2018/12/portfolio-construction-through_7.html** — Handcrafting *method*: hierarchical grouping by correlation, equal-risk weighting, diversification multiplier, bounded (0.6–1.4) Sharpe adjustment.
- **https://qoppac.blogspot.com/2021/05/fit-forecast-weights-by-instrument-by.html** — Carver's conclusion to pool forecast-weight fitting across markets/groups rather than per-instrument; pool gross returns, apply per-instrument costs.
- **https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html** — pysystemtrade expanding-window weight estimation, pooling, smoothing.
- **https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html** — Optimising weights with costs in pysystemtrade (bootstrap, pooling, cost handling).
- **https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf** — Bailey & López de Prado, *The Deflated Sharpe Ratio* (Eq. 1 expected max Sharpe under N trials; Eq. 2 DSR formula; "worthless without number of trials"; winner's curse).
- **https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551** — SSRN landing page for the Deflated Sharpe Ratio paper.
- **https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf** — Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting* (PBO definition; CSCV procedure; holdout cannot fix overfitting).
- **https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253** — SSRN landing page for the PBO paper.
- **https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf** — Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and Financial Charlatanism* (Notices of the AMS; ~7 trials → spurious SR>1; memory effects → loss maximization; Minimum Backtest Length).
- **https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659** — SSRN landing page for the Pseudo-Mathematics paper.
- **https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF** — Harvey & Liu, *Backtesting* (haircut Sharpe; $p^{M}=1-(1-p^S)^N$; SR=0.75/N=200→~60% haircut; nonlinear haircut; 50% rule-of-thumb wrong; Bonferroni/Holm/BHY).
- **https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489** — SSRN landing page for Harvey & Liu, *Backtesting*.
- **https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF** — Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns* (t > 3 hurdle; most findings likely false; multiple-testing framework).
- **https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314** — SSRN landing page for Harvey, Liu & Zhu.
- **https://arch.readthedocs.io/en/latest/multiple-comparison/generated/arch.bootstrap.SPA.html** — Documentation of Hansen's SPA / White's Reality Check bootstrap test (secondary source).
- **https://econweb.rutgers.edu/nswanson/papers/corradi_swanson_whitefest_1108_2011_09_06.pdf** — Survey of White's Reality Check and extensions (secondary source).

*Verification notes:* All Carver claims and all Bailey/López de Prado and Harvey/Liu(/Zhu) formulas and worked examples were taken from the primary PDFs/posts listed above and cross-checked against the fetched text. The White (2000) and Hansen (2005) *primary* papers were not fetched directly; §2.7's characterisation rests on secondary sources and standard summaries, and the specific mechanism of Hansen's null re-centring is flagged **[unverified]** at that level of detail.

---

## Practitioner checklist — apply before ANY universe / weight / parameter change

1. **Ex-ante test.** State the reason for the change in one sentence. If the sentence contains "because the backtest P&L was good/bad," **reject it.** Allowed reasons: liquidity, minimum capital / contract size, cost & speed-limit, data trustworthiness.
2. **Window-invariance test.** Would this decision be the same on a different historical window? If not, it is fitting — reject.
3. **Trial count.** Write down how many instruments/variants/parameters you looked at (N). Acknowledge that the best-of-N is inflated by Eq. 1 with *zero* true skill.
4. **Haircut it.** Apply a mental Harvey–Liu haircut (large N → large haircut on marginal edges; the flat 50% rule is wrong). Treat marginal edges as spurious.
5. **Hurdle.** Require t > 3, not t > 2, before believing any new edge.
6. **Deflate.** For a serious change, compute (or at least reason about) the Deflated Sharpe Ratio / PBO; target DSR ≳ 0.95 and low PBO.
7. **Diversify, don't optimize.** Prefer a robust plateau or an average across variants over the single in-sample best.
8. **Pool, don't per-instrument-fit.** One market's data is too thin.
9. **Expanding-window only.** No full-sample peeking; smooth the weights.
10. **Keep everything in the fund-level backtest.** Down-weight via the robust allocator; never hand-delete an instrument to improve the curve.
11. **Handcraft with bounds.** If adjusting weights, keep multipliers within ~0.6–1.4 so no single noisy input produces an extreme allocation.
12. **Give it time.** Don't declare a rule/instrument dead on a year of data; think in ~10-year horizons.
