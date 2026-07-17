"""Hedge-fund-style factsheet for a SAVED backtest run.

Growth of $START (default $1,000) COMPOUNDED from the daily %-returns, a full stats panel, and the
drawdown shown BOTH ways for comparison:
  - TYPICAL (industry): compounded equity, peak-to-trough as a % of the running peak (what a fund reports)
  - PST (pysystemtrade-native): additive cumsum-of-%-returns / fixed capital (what stats.json max_dd_pct uses)
Also reports the month-end-NAV Max Drawdown (the exact fund-factsheet convention).

Reads only private/backtest_runs/<label>/{daily_pnl.parquet, stats.json} -- no rebuild, no sim-DB.

Usage:  uv run python -m sysinit.futures.factsheet [label] [start_capital]
        (defaults: rob_dynamic_prod_250k_dm275, 1000)
"""
import os
import sys
import json
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
plt.rcParams["text.parse_math"] = False

from sysinit.futures.backtest_results import RUNS_DIR

BDAYS = 256
label = sys.argv[1] if len(sys.argv) > 1 else "rob_dynamic_prod_250k_dm275"
START = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
d = os.path.join(RUNS_DIR, label)
stats = json.load(open(os.path.join(d, "stats.json")))
cap = float(stats["capital"])

dp = pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna()
r = dp / cap                                      # daily fractional return on fixed capital
equity = START * (1.0 + r).cumprod()              # COMPOUNDED growth of $START
years = len(r) / BDAYS

# ---- returns stats ----
cagr = (equity.iloc[-1] / START) ** (1.0 / years) - 1.0
ann_vol = float(r.std() * np.sqrt(BDAYS))
sharpe = float(r.mean() / r.std() * np.sqrt(BDAYS))
downside = r[r < 0]
sortino = float(r.mean() / downside.std() * np.sqrt(BDAYS)) if len(downside) else float("nan")
skew = float(r.skew())

# ---- drawdown, three ways ----
# TYPICAL (compounded, daily): % of running peak equity
dd_comp = (equity / equity.cummax() - 1.0) * 100
maxdd_comp = float(dd_comp.min())
# PST additive: cumsum of %-returns on fixed capital
cum_add = (r * 100).cumsum()
dd_add = cum_add - cum_add.cummax()
maxdd_add = float(dd_add.min())
# fund-standard: month-end NAV, %-of-peak
nav_m = equity.resample("M").last()
dd_m = (nav_m / nav_m.cummax() - 1.0) * 100
maxdd_m = float(dd_m.min())
calmar = cagr * 100 / abs(maxdd_comp) if maxdd_comp else float("nan")
time_in_dd = float((dd_comp < -0.01).mean() * 100)
avg_dd = float(dd_comp[dd_comp < 0].mean())

# ---- calendar-year returns ----
yr = equity.resample("A").last().pct_change().dropna() * 100
best_y, worst_y = (yr.max(), yr.idxmax().year), (yr.min(), yr.idxmin().year)

# max-DD peak/trough dates (compounded)
trough = dd_comp.idxmin(); peak = equity.loc[:trough].idxmax()
rec = equity.loc[trough:][equity.loc[trough:] >= equity.loc[peak]]
recovered = rec.index[0].date() if len(rec) else None

print(f"\n=== FACTSHEET  {label}  (${START:,.0f} start) ===")
print(f"  terminal ${equity.iloc[-1]:,.0f}  ({equity.iloc[-1]/START:,.0f}x)   CAGR {cagr*100:.2f}%")
print(f"  ann vol {ann_vol*100:.1f}%   Sharpe {sharpe:.2f}   Sortino {sortino:.2f}   skew {skew:.2f}")
print(f"  MAX DRAWDOWN  typical(compounded) {maxdd_comp:.1f}%  |  month-end NAV {maxdd_m:.1f}%  |  PST additive {maxdd_add:.1f}%")
print(f"  Calmar {calmar:.2f}   time-in-DD {time_in_dd:.0f}%   avg DD {avg_dd:.1f}%")
print(f"  best yr {best_y[0]:.1f}% ({best_y[1]})   worst yr {worst_y[0]:.1f}% ({worst_y[1]})")

# ================= PLOT =================
fig = plt.figure(figsize=(13, 9.5))
gs = fig.add_gridspec(3, 1, height_ratios=[3.0, 1.15, 1.15], hspace=0.28)
a1 = fig.add_subplot(gs[0]); a2 = fig.add_subplot(gs[1], sharex=a1); a3 = fig.add_subplot(gs[2], sharex=a1)

fig.suptitle(f"rob_dynamic (Carver-style trend+carry, dynamic-opt) — {stats.get('universe','?')} futures, "
             f"${cap:,.0f} @ {stats.get('vol_target','?')}% vol target\n"
             f"CAGR {cagr*100:.1f}%  ·  Vol {ann_vol*100:.1f}%  ·  Sharpe {sharpe:.2f}  ·  "
             f"Max DD {maxdd_comp:.1f}%  ·  {stats['start']} → {stats['end']}",
             fontsize=12, y=0.975)

# growth of $START (log)
a1.plot(equity.index, equity.values, lw=1.0, color="#08519c")
a1.set_yscale("log")
a1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
a1.set_ylabel(f"growth of ${START:,.0f} (compounded, log)"); a1.grid(alpha=0.3, which="both")
box = "\n".join([
    f"start                ${START:,.0f}",
    f"terminal             ${equity.iloc[-1]:,.0f}   ({equity.iloc[-1]/START:,.0f}x)",
    f"CAGR                 {cagr*100:.2f}%",
    f"annualised vol       {ann_vol*100:.1f}%",
    f"Sharpe               {sharpe:.2f}",
    f"Sortino              {sortino:.2f}",
    f"skew                 {skew:.2f}",
    f"Max DD (compounded)  {maxdd_comp:.1f}%",
    f"Max DD (month-end)   {maxdd_m:.1f}%",
    f"Max DD (PST additive){maxdd_add:.1f}%",
    f"Calmar               {calmar:.2f}",
    f"time in drawdown     {time_in_dd:.0f}%",
    f"best year            {best_y[0]:.1f}% ({best_y[1]})",
    f"worst year           {worst_y[0]:.1f}% ({worst_y[1]})",
    f"max-DD peak->trough  {peak.date()} -> {trough.date()}",
    f"recovered            {recovered if recovered else 'not yet'}",
])
a1.text(0.013, 0.985, box, transform=a1.transAxes, va="top", ha="left", family="monospace",
        fontsize=8.3, bbox=dict(boxstyle="round", fc="#eef4fb", ec="#08519c", alpha=0.92))

# TYPICAL drawdown (compounded, %-of-peak)
a2.fill_between(dd_comp.index, dd_comp.values, 0, color="#d62728", alpha=0.55)
a2.axhline(maxdd_comp, color="#7a0000", lw=0.8, ls="--")
a2.set_ylabel("drawdown %\n(TYPICAL: compounded,\n%-of-peak)"); a2.grid(alpha=0.3)
a2.text(0.013, 0.08, f"Max {maxdd_comp:.1f}%  (fund convention; month-end NAV {maxdd_m:.1f}%)",
        transform=a2.transAxes, fontsize=8.5, color="#7a0000")

# PST additive drawdown
a3.fill_between(dd_add.index, dd_add.values, 0, color="#6a51a3", alpha=0.5)
a3.axhline(maxdd_add, color="#3f007d", lw=0.8, ls="--")
a3.set_ylabel("drawdown %\n(PST: additive\ncumsum/fixed cap)"); a3.set_xlabel("date"); a3.grid(alpha=0.3)
a3.text(0.013, 0.08, f"Max {maxdd_add:.1f}%  (pysystemtrade-native; = stats.json max_dd_pct)",
        transform=a3.transAxes, fontsize=8.5, color="#3f007d")

png = os.path.join(d, f"factsheet_{int(START)}.png")
fig.savefig(png, dpi=120, bbox_inches="tight"); plt.close(fig)
print(f"\nplot -> {png}")
