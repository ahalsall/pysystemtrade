# Rob Carver — live systematic FUTURES results (annual reviews)

His own real-money account, run on the pysystemtrade rob_system we're reproducing. Reported by **UK
tax year (~6 Apr → 5 Apr)**, ~25% vol target, full universe, net of real costs. Posts are usually
published mid-April. Years 1–2 were pure-futures posts; 3–9 were whole-portfolio with futures as a
breakout section (numbers below are the FUTURES component); 10 was **skipped**; 11–12 pure-futures again.

Collected 2026-07 from qoppac.blogspot.com (sources at bottom). This is our live benchmark.

| Yr | Period (tax yr end) | Futures return | Realized vol (t=25%) | Sharpe | vs SG CTA idx (vol-adj) | vs AHL (vol-adj) | Driver |
|----|--------------------|----------------|----------------------|--------|-------------------------|------------------|--------|
| 1  | Apr'14–Apr'15 | **+124.1%** (risk-adj +57.2%) | 22.0% | 2.54 | — | AHL 4.0 (Sharpe) | "year of the bond" — EU bonds/QE (OAT/BTP) — "brilliantly flukey" |
| 2  | 2015→2016 | **+23.2%** | 24.6% | ~1.0 (12m 1.33) | — | AHL -0.59 (12m) | metals +13.4%, oil/gas +12.5%; equities -5.8% |
| 3  | 2016→2017 | **-14.0%** | — | ~1.0 cum | -7.5% | -6.2% | short-vol good, but nat gas / ED carry / GBP-Brexit whipsaw |
| 4  | 2017→2018 | **-3.7%** | 23.8% | 0.98 incep | -3.8% | +16.4% | "sea of flatness", soybean whipsaw, FX drag |
| 5  | 2018→2019 | **+5.2%** | — | — | +0.7% | +10.3% | profit factor ~1.0, hit rate 43% |
| 6  | 2019→2020 | **+39.7%** | — | — | +8.0% | +23.4% | made it all by end-Jan, flat through COVID crash |
| 7  | 2020→2021 | **+0.4%** | — | 0.6 ann | +10.9% | +0.7% | equity hedge -4.3% dragged; "first time SG beat me" |
| 8  | 2021→2022 | **+27.0%** | ~25% | 0.70 | +38.3% | -4.9% | **YEAR OF ENERGY** — oil/gas +21.7%, ags +5.1% |
| 9  | 2022→2023 | **-8.7%** | 24.3% | 0.58 (9yr) | -1.3% | +5.0% | broad rule losses, Mar-2023 selloff |
| 10 | 2023→2024 | **SKIPPED** (no post — "sad, it was my tenth anniversary") | | | | | |
| 11 | 2024→2025 | **-16.3%** ("worst ever") | 16.8% | 0.76 incep | idx ~-18% | CAGR 12.0 vs SG 6.4 / AHL 5.9 | univariate momentum awful; only rel-value skew/carry + fast rel-mom profited |
| 12 | 2025→2026 | **+23.7%** | vol-adj 25.9% | 0.80 | SG 0.54 (Sharpe) | AHL 0.52 (Sharpe) | half slow Jun–Nov, half fast Dec–Jan; metals + equities; matched Vanguard 80:20 |

**Since-inception (as of yr11):** CAGR **12.0%** vs SG CTA 6.4%, AHL 5.9%. Sharpe drifted from flukey
early highs to ~0.58 (yr9) → 0.76–0.80 (yr11–12).

## Why this matters for us
- **The 2022 divergence is the headline.** Rob's yr8 (Apr'21–Apr'22) = **+27% on energy**; his yr6
  (2020) = **+39.7%**. OUR backtest's 2022 = **-6.2%** at 4.6% realized vol. He fully deployed into the
  energy/COVID trends; we throttled (vol attenuation) and/or under-weighted energy — this is the
  concrete evidence behind the 2022 diagnosis. See [[validation-before-strategy-changes]].
- **Risk deployment gap.** Rob realizes ~24–25% vol (near his 25% target); we realize ~9–13% (vs 20%
  target). He runs ~2× our risk AND catches the trends → his big years are far bigger than ours.
- **The drought hit him too** (yr9 -8.7%, yr11 **-16.3% worst ever**) — but punctuated by +27% and a
  +23.7% rebound. Trend isn't dead in his live results; it's lumpy. yr12 rebound (metals+equities)
  is a data point for the reassertion thesis.
- Even the pros swing wildly and the SG CTA index beat Rob in several years — variance is enormous.

## Sources (qoppac.blogspot.com)
Yr1 /2015/04/futures-trading-performance-year-one.html · Yr2 /2016/04/futures-trading-performance-year-two.html ·
Yr3 /2017/04/investment-and-trading-performance-year.html · Yr4 /2018/04/trading-performance-year-four.html ·
Yr5 /2019/04/trading-and-investing-performance-year.html · Yr6 /2020/04/trading-and-investing-performance-year.html ·
Yr7 /2021/04/trading-and-investing-performance-year.html · Yr8 /2022/04/trading-and-investing-performance-year.html ·
Yr9 /2023/05/trading-and-investing-performance-year.html · Yr11 /2025/04/annual-performance-update-returneth.html ·
Yr12 /2026/04/annual-performance-update-year-12.html
