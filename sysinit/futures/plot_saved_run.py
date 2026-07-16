"""Plot a SAVED backtest run (curve + drawdown) with its full stats annotated.

Reads only private/backtest_runs/<label>/ artifacts (curve.csv / daily_pnl.parquet /
stats.json) -- no system rebuild, no sim-DB access -- so it's safe to run anytime,
including while a data re-ingest is writing the sim stores.

Two modes:
  additive  (default) : pysystemtrade-native cumulative %-of-capital (cumsum of %-returns),
                        fixed capital -- matches the saved stats.json (max_dd_pct etc.).
  compound            : reinvest P&L -> COMPOUNDED $ equity curve from the starting capital,
                        with the "real" %-of-equity drawdown and CAGR. Log y-axis.

Usage:
  uv run python -m sysinit.futures.plot_saved_run EXPERIMENT_1000k_30vol_noatten
  uv run python -m sysinit.futures.plot_saved_run EXPERIMENT_1000k_30vol_noatten compound
"""
import os
import sys
import json
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
plt.rcParams["text.parse_math"] = False  # render literal '$' in titles/labels (not LaTeX math)

from sysinit.futures.backtest_results import RUNS_DIR

label = sys.argv[1] if len(sys.argv) > 1 else "EXPERIMENT_1000k_30vol_noatten"
mode = sys.argv[2] if len(sys.argv) > 2 else "additive"
d = os.path.join(RUNS_DIR, label)
stats = json.load(open(os.path.join(d, "stats.json")))

# ================= FACT-SHEET (MONTHLY NAV) MODE =================
# The convention on fund fact sheets: compounded NAV marked at MONTH-END, and Maximum
# Drawdown = worst peak-to-trough decline of that monthly NAV as a % of the peak.
if mode.startswith("factsheet") or mode == "monthly":
    cap0 = float(stats["capital"])
    dp = pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna()
    eq_daily = cap0 * (1.0 + dp / cap0).cumprod()            # compounded daily equity
    nav = eq_daily.resample("M").last()                    # month-end NAV (fact-sheet mark)
    nav = pd.concat([pd.Series([cap0], index=[nav.index[0] - pd.offsets.MonthEnd(1)]), nav])
    mret = nav.pct_change().dropna()
    dd = (nav / nav.cummax() - 1.0) * 100                    # monthly underwater, %-of-peak
    maxdd = float(dd.min())
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    rec = nav.loc[trough:][nav.loc[trough:] >= nav.loc[peak]]
    recovered = rec.index[0] if len(rec) else None
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    terminal = float(nav.iloc[-1])
    cagr = (terminal / cap0) ** (1.0 / years) - 1.0
    ann_vol = float(mret.std() * np.sqrt(12) * 100)
    sharpe_m = float(mret.mean() / mret.std() * np.sqrt(12))
    # calendar-year returns (compounded within year)
    yr = nav.resample("A").last().pct_change().dropna() * 100

    print(f"\n=== {label} — FACT-SHEET (month-end NAV) view ===")
    print(f"  starting capital     ${cap0:,.0f}")
    print(f"  terminal NAV         ${terminal:,.0f}   ({terminal/cap0:,.1f}x)")
    print(f"  CAGR                 {cagr*100:.2f}%")
    print(f"  annualised vol       {ann_vol:.1f}%   (monthly x sqrt12)")
    print(f"  Sharpe               {sharpe_m:.2f}   (monthly)")
    print(f"  MAX DRAWDOWN         {maxdd:.1f}%   (month-end NAV, peak {peak.date()} -> trough {trough.date()}"
          f"{', recovered ' + str(recovered.date()) if recovered is not None else ', not recovered'})")
    print(f"  best / worst year    {yr.max():.1f}% ({yr.idxmax().year}) / {yr.min():.1f}% ({yr.idxmin().year})")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
    atten = stats.get("attenuation")
    atten_str = "attenuation OFF" if atten is False else ("attenuation ON" if atten else "")
    a1.plot(nav.index, nav.values, lw=1.1, color="#08519c")
    a1.set_yscale("log")
    a1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    a1.set_title(f"{label} — growth of ${cap0:,.0f}, month-end NAV (log scale)\n"
                 f"{stats.get('vol_target','?')}% vol{', ' + atten_str if atten_str else ''}, "
                 f"{stats.get('universe','?')} instruments  |  CAGR {cagr*100:.1f}%, vol {ann_vol:.1f}%, "
                 f"Sharpe {sharpe_m:.2f}, Max Drawdown {maxdd:.1f}%")
    a1.set_ylabel("NAV ($, log scale)"); a1.grid(alpha=0.3, which="both")
    box = "\n".join([
        f"start NAV       ${cap0:,.0f}",
        f"terminal NAV    ${terminal:,.0f}  ({terminal/cap0:,.1f}x)",
        f"CAGR            {cagr*100:.2f}%",
        f"annualised vol  {ann_vol:.1f}%",
        f"Sharpe          {sharpe_m:.2f}",
        f"MAX DRAWDOWN    {maxdd:.1f}%",
        f"  peak          {peak.date()}",
        f"  trough        {trough.date()}",
        f"  recovered     {recovered.date() if recovered is not None else 'not yet'}",
        f"best year       {yr.max():.1f}% ({yr.idxmax().year})",
        f"worst year      {yr.min():.1f}% ({yr.idxmin().year})",
    ])
    a1.text(0.012, 0.97, box, transform=a1.transAxes, va="top", ha="left",
            family="monospace", fontsize=8.5,
            bbox=dict(boxstyle="round", fc="#eef4fb", ec="#08519c", alpha=0.9))
    a2.fill_between(dd.index, dd.values, 0, color="#d62728", alpha=0.55)
    a2.axhline(maxdd, color="#7a0000", lw=0.8, ls="--")
    a2.set_ylabel("drawdown %\n(month-end NAV)"); a2.set_xlabel("date"); a2.grid(alpha=0.3)
    fig.tight_layout()
    png = os.path.join(d, "curve_factsheet.png")
    fig.savefig(png, dpi=120); plt.close(fig)
    print(f"\nplot -> {png}")
    sys.exit(0)

# ================= COMPOUNDED $ EQUITY MODE =================
if mode.startswith("compound"):
    cap0 = float(stats["capital"])
    dp = pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna()
    r = dp / cap0                                   # daily return on starting capital
    equity = cap0 * (1.0 + r).cumprod()             # reinvest P&L -> compounded $ equity
    ddc = (equity / equity.cummax() - 1.0) * 100    # real %-of-equity drawdown
    years = len(equity) / 256.0
    terminal = float(equity.iloc[-1])
    cagr = (terminal / cap0) ** (1.0 / years) - 1.0
    comp_maxdd = float(ddc.min())

    print(f"\n=== {label} — COMPOUNDED (reinvested) view ===")
    print(f"  starting capital     ${cap0:,.0f}")
    print(f"  terminal equity      ${terminal:,.0f}   ({terminal/cap0:,.1f}x)")
    print(f"  CAGR (geometric)     {cagr*100:.2f}%   [vs additive arith {stats['ann_return_pct']:.1f}%]")
    print(f"  compounded max DD    {comp_maxdd:.1f}%   [vs additive {stats['max_dd_pct']:.1f}%]")
    print(f"  realized vol         {stats['ann_vol_pct']:.1f}%   Sharpe {stats['sharpe']:.3f}   skew {stats['skew']:.3f}")
    print(f"  period               {stats['start']} -> {stats['end']}  ({len(equity):,} days)")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
    atten = stats.get("attenuation")
    atten_str = "attenuation OFF" if atten is False else ("attenuation ON" if atten else "")
    a1.plot(equity.index, equity.values, lw=0.9, color="#08519c")
    a1.set_yscale("log")
    a1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    a1.set_title(f"{label} — COMPOUNDED $ equity (reinvested), log scale\n"
                 f"${cap0:,.0f} start @ {stats.get('vol_target','?')}% vol"
                 f"{', ' + atten_str if atten_str else ''}, {stats.get('universe','?')} instruments  |  "
                 f"CAGR {cagr*100:.1f}%, terminal ${terminal:,.0f} ({terminal/cap0:,.0f}x), "
                 f"comp maxDD {comp_maxdd:.1f}%")
    a1.set_ylabel("equity ($, log scale)"); a1.grid(alpha=0.3, which="both")
    box = "\n".join([
        f"start capital   ${cap0:,.0f}",
        f"terminal equity ${terminal:,.0f}",
        f"growth multiple {terminal/cap0:,.1f}x",
        f"CAGR (compound) {cagr*100:.2f}%",
        f"arith ann ret   {stats['ann_return_pct']:.1f}%  (additive)",
        f"realized vol    {stats['ann_vol_pct']:.1f}%",
        f"Sharpe          {stats['sharpe']:.3f}",
        f"comp max DD     {comp_maxdd:.1f}%",
        f"additive max DD {stats['max_dd_pct']:.1f}%",
        f"skew            {stats['skew']:.3f}",
        f"period          {stats['start']} -> {stats['end']}",
    ])
    a1.text(0.012, 0.97, box, transform=a1.transAxes, va="top", ha="left",
            family="monospace", fontsize=8.5,
            bbox=dict(boxstyle="round", fc="#eef4fb", ec="#08519c", alpha=0.9))
    a2.fill_between(ddc.index, ddc.values, 0, color="#d62728", alpha=0.55)
    a2.set_ylabel("compounded DD %\n(of equity)"); a2.set_xlabel("date"); a2.grid(alpha=0.3)
    fig.tight_layout()
    png = os.path.join(d, "curve_compounded.png")
    fig.savefig(png, dpi=120); plt.close(fig)
    print(f"\nplot -> {png}")
    sys.exit(0)

# ================= ADDITIVE MODE (default) =================

# cumulative %-of-capital curve (prefer the saved curve.csv; fall back to daily P&L)
cpath = os.path.join(d, "curve.csv")
if os.path.exists(cpath):
    cum = pd.read_csv(cpath, index_col=0, parse_dates=True).iloc[:, 0]
else:
    dp = pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0]
    cum = dp.cumsum() / stats["capital"] * 100
dd = cum - cum.cummax()  # additive drawdown, %-of-capital (matches full_stats)

# ---- full stats to stdout ----
print(f"\n=== {label} — FULL STATS ===")
w = max(len(k) for k in stats)
for k, v in stats.items():
    print(f"  {k:<{w}} : {v}")

# ---- plot: cumulative curve + drawdown ----
fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
atten = stats.get("attenuation")
atten_str = "attenuation OFF" if atten is False else ("attenuation ON" if atten else "")
title = (f"{label}\n${stats['capital']:,} @ {stats.get('vol_target','?')}% vol target"
         f"{', ' + atten_str if atten_str else ''}, {stats.get('universe','?')} instruments  |  "
         f"Sharpe {stats['sharpe']:.3f}, realized vol {stats['ann_vol_pct']:.1f}%, "
         f"maxDD {stats['max_dd_pct']:.1f}%")
a1.plot(cum.index, cum.values, lw=0.9, color="#b30000")
a1.set_title(title)
a1.set_ylabel("cumulative % of capital (additive)")
a1.grid(alpha=0.3)

# full-stats text box on the curve panel
box = "\n".join([
    f"capital        ${stats['capital']:,}",
    f"vol target     {stats.get('vol_target','?')}%   ({atten_str})",
    f"ann return     {stats['ann_return_pct']:.1f}%",
    f"realized vol   {stats['ann_vol_pct']:.1f}%",
    f"Sharpe         {stats['sharpe']:.3f}",
    f"max DD         {stats['max_dd_pct']:.1f}%",
    f"avg DD         {stats['avg_dd_pct']:.1f}%",
    f"median DD      {stats['median_dd_pct']:.1f}%",
    f"time in DD     {stats['time_in_dd_pct']:.1f}%",
    f"skew           {stats['skew']:.3f}",
    f"period         {stats['start']} → {stats['end']}",
    f"days           {stats['n_days']:,}",
])
a1.text(0.012, 0.97, box, transform=a1.transAxes, va="top", ha="left",
        family="monospace", fontsize=8.5,
        bbox=dict(boxstyle="round", fc="#fff5f5", ec="#b30000", alpha=0.9))

a2.fill_between(dd.index, dd.values, 0, color="#d62728", alpha=0.55)
a2.set_ylabel("drawdown %"); a2.set_xlabel("date"); a2.grid(alpha=0.3)

fig.tight_layout()
png = os.path.join(d, "curve_annotated.png")
fig.savefig(png, dpi=120); plt.close(fig)
print(f"\nplot -> {png}")
