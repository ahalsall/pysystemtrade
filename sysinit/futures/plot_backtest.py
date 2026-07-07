"""Plot the dynamic-opt backtest account curve (equity + drawdown) -> PNG."""
import os
os.environ.setdefault("MPLBACKEND", "Agg")
import pandas as pd
import matplotlib.pyplot as plt

CURVE = "private/dynopt_backtest_curve.csv"
OUT = "private/dynopt_backtest_curve.png"

s = pd.read_csv(CURVE, index_col=0, parse_dates=True).iloc[:, 0]  # cumulative % returns
dd = s - s.cummax()  # drawdown in cumulative-return space (pct points)

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
)
ax1.plot(s.index, s.values, color="#1f3b73", lw=1.1)
ax1.fill_between(s.index, 0, s.values, color="#1f3b73", alpha=0.08)
ax1.set_ylabel("Cumulative return (% points)")
ax1.set_title(
    "Dynamic-opt backtest — 66 CSI deep-history instruments (1996–2026)\n"
    "Sharpe 1.00  |  Ann return 19.9%  |  Ann vol 19.9%  |  Skew −0.69  |  Max DD −51.1%",
    fontsize=12,
)
ax1.grid(alpha=0.3)

ax2.fill_between(dd.index, dd.values, 0, color="#c0392b", alpha=0.45)
ax2.set_ylabel("Drawdown (% pts)")
ax2.set_xlabel("Date")
ax2.grid(alpha=0.3)

fig.tight_layout()
fig.savefig(OUT, dpi=120)
print(f"saved {OUT}  ({len(s)} points, {s.index[0].date()} -> {s.index[-1].date()})")
