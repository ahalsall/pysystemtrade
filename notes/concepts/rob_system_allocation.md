# rob_system — actual strategy allocation & realized rule P&L

Computed from `systems/provided/rob_system/config.yaml` (forecast_weights are
per-instrument; averaged here) and Rob's `Trading_rule_p&l.pdf` report (realized
Sharpe per rule). This is Rob's ACTUAL live system = the fully-combined AFTS final
strategy + dynamic optimization, not any single numbered book strategy.

## System params
40 rules · 170 instruments · vol target 25% · IDM 2.75 · capital 500k USD · forecast weights ~100%/instrument.

## Allocation by family (avg per-instrument forecast weight)
| Style | Weight | book grouping |
|---|---|---|
| Trend (EWMAC: momentum + normmom + assettrend) | 30.8% | divergent |
| Breakout | 20.4% | divergent |
| Carry (outright) | 12.9% | convergent |
| Mean reversion (cross-sectional, mrinasset1000) | 9.3% | convergent |
| Skew (abs + relative-value) | 9.1% | convergent |
| Relative momentum | 6.9% | divergent |
| Acceleration | 6.0% | divergent |
| Carry (relative) | 4.6% | convergent |

Divergent (trend-like) ≈ 64% · Convergent (carry/MR/skew) ≈ 36% · total carry 17.5%.

**Slow-tilt:** within each family the slow variants dominate (momentum64 5.6% vs momentum4 0.1%; breakout320 9.3% vs breakout10 0.1%) — cost-aware handcrafting. Biggest single lines: breakout320 & mrinasset1000 at 9.3% each.

Three flavors of EWMAC trend: momentum (raw price), normmom (vol-normalized returns), assettrend (asset-class-relative price). 6 breakout speeds, 4 carry speeds, 4 skew variants. Vol attenuation applied to trend/breakout/relmom/MR rules.

## Realized Sharpe by family (from Trading_rule_p&l.pdf)
| Family | SR 99Y (full) | SR 10Y (recent) |
|---|---|---|
| Breakout | +0.79 | +0.65 |
| Trend | +0.78 | ~+0.6 |
| Carry (outright) | +0.72 | +0.6 |
| Carry (relative) | +0.55 | +0.34 |
| Skew | +0.46 | +0.6 |
| Acceleration | +0.43 | NEGATIVE (~−0.1) |
| Relative momentum | +0.17 | low |
| Mean reversion (x-sect) | −0.36 | −0.09 |

Per-rule highlights (99Y): best = breakout80 +1.15, momentum32/normmom16/normmom32 +1.07, momentum16 +1.06, breakout160 +1.04. Worst = mrwrings4 −1.05, mrinasset160 −0.36, assettrend2 −0.14, normmom2 −0.13, breakout10 −0.09. Fast variants consistently weak/negative → validates the slow-tilt allocation.

## Allocation vs performance — reads
1. Allocation broadly tracks realized SR (top earners breakout/trend/carry get most weight; fast/weak variants get little).
2. **Mean reversion gets ~9% despite negative standalone SR** — a PORTFOLIO/diversification decision (low/neg-correlated rules improve combined Sharpe even with low standalone SR), not an SR ranking. Forecast weights ≠ pure SR ordering.
3. **Acceleration has decayed**: +0.43 full history but NEGATIVE over last 10Y. Flag for expectations.
4. **General recent decay**: 10Y SRs < full-history across the board → use recent numbers for realistic expectations.

## Caveat
The P&L report has 41 rules and does NOT perfectly match the live config's 40 — it includes research/candidate rules (mrinasset160, mrwrings4) where the live config trades mrinasset1000. So the report is Rob's RESEARCH output, not a 1:1 live mirror; family-level reads hold.

## How it maps to the book (AFTS)
Each family = an AFTS strategy/chapter (EWMAC trend, breakout, carry, relative carry, skew, acceleration, relative momentum, cross-sectional mean reversion). rob_system stacks them all + dynamic optimization (S25). The book introduces variants progressively and presents cleaner handcrafted group weights; the live system has fitted per-instrument weights averaging to the above. To diff exact numbers, compare against the book's final-strategy weight table (need book text).

Sources: systems/provided/rob_system/config.yaml; raw.githubusercontent.com/robcarver17/reports/master/Trading_rule_p%26l.pdf
