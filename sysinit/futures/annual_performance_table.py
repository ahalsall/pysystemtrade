"""Year-by-year performance table for a SAVED backtest run.

Two blocks per row:
  THIS YEAR   : annual return, vol, Sharpe, Sortino, max intra-year DD, %+ months, skew
  SINCE INCEP : cumulative return, CAGR, Sharpe, max DD -- computed from inception (1996) up to the
                END of that year, i.e. what an inception-to-date factsheet would have shown that Dec 31.

Compounded %-returns on fixed capital (daily_pnl/capital), matching factsheet.py. Prints text + a PNG.

Usage:  uv run python -m sysinit.futures.annual_performance_table [label] [n_years] [inception_year]
        (defaults: rob_dynamic_prod_250k_dm275, 15, full history)
        inception_year rebases "since inception" to Jan 1 of that year (treats the fund as starting then).
"""
import os
import sys
import json
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["text.parse_math"] = False

from sysinit.futures.backtest_results import RUNS_DIR

BDAYS = 256
label = sys.argv[1] if len(sys.argv) > 1 else "rob_dynamic_prod_250k_dm275"
NYEARS = int(sys.argv[2]) if len(sys.argv) > 2 else 15
d = os.path.join(RUNS_DIR, label)
stats = json.load(open(os.path.join(d, "stats.json")))
cap = float(stats["capital"])

INCEP_YEAR = int(sys.argv[3]) if len(sys.argv) > 3 else None

dp = pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna()
r = dp / cap                                     # daily fractional return on fixed capital
if INCEP_YEAR is not None:                        # treat the fund as starting Jan 1 of INCEP_YEAR
    r = r[r.index.year >= INCEP_YEAR]
equity = (1.0 + r).cumprod()                     # compounded, start=1.0
incep = r.index[0]


def block_stats(rr):
    """annual-style stats for a daily-return slice rr."""
    if len(rr) < 2:
        return dict(ret=np.nan, vol=np.nan, sharpe=np.nan, sortino=np.nan, mdd=np.nan, pos=np.nan, skew=np.nan)
    eq = (1.0 + rr).cumprod()
    ret = eq.iloc[-1] - 1.0
    vol = rr.std() * np.sqrt(BDAYS)
    sharpe = rr.mean() / rr.std() * np.sqrt(BDAYS) if rr.std() else np.nan
    dn = rr[rr < 0]
    sortino = rr.mean() / dn.std() * np.sqrt(BDAYS) if len(dn) and dn.std() else np.nan
    mdd = (eq / eq.cummax() - 1.0).min()
    mo = (1.0 + rr).resample("M").prod() - 1.0
    pos = (mo > 0).mean() if len(mo) else np.nan
    return dict(ret=ret, vol=vol, sharpe=sharpe, sortino=sortino, mdd=mdd, pos=pos, skew=rr.skew())


years = sorted(set(r.index.year))
show = years[-NYEARS:]
rows = []
for y in show:
    ry = r[r.index.year == y]
    a = block_stats(ry)
    # since inception, up to end of year y
    ri = r[r.index.year <= y]
    ei = (1.0 + ri).cumprod()
    yrs_elapsed = len(ri) / BDAYS
    cum = ei.iloc[-1] - 1.0
    cagr = ei.iloc[-1] ** (1.0 / yrs_elapsed) - 1.0
    si_sharpe = ri.mean() / ri.std() * np.sqrt(BDAYS)
    si_mdd = (ei / ei.cummax() - 1.0).min()
    partial = "*" if (y == show[-1] and ry.index[-1].month < 12) else ""
    rows.append([f"{y}{partial}", a["ret"]*100, a["vol"]*100, a["sharpe"], a["sortino"], a["mdd"]*100,
                 a["pos"]*100, a["skew"], cum*100, cagr*100, si_sharpe, si_mdd*100])

cols = ["Year", "Ret%", "Vol%", "Shrp", "Sort", "MaxDD%", "+Mo%", "Skew",
        "CumRet%", "CAGR%", "Shrp", "MaxDD%"]
df = pd.DataFrame(rows, columns=cols)

# ---- text ----
last = r.index[-1]
print(f"\n=== {label}: year-by-year ({stats.get('universe','?')} futures, ${cap:,.0f} @ "
      f"{stats.get('vol_target','?')}% vol) ===")
print(f"    inception {incep.date()} -> {last.date()}   (* = partial year to {last.date()})")
print(f"{'':>18}|{'  --- THIS YEAR ---':^46}|{'  --- SINCE INCEPTION (to Dec 31) ---':^34}")
hdr = f"{'Year':>6} {'Ret%':>7} {'Vol%':>6} {'Shrp':>5} {'Sort':>5} {'MaxDD%':>7} {'+Mo%':>5} {'Skew':>5} | " \
      f"{'CumRet%':>9} {'CAGR%':>6} {'Shrp':>5} {'MaxDD%':>7}"
print(hdr); print("-" * len(hdr))
for x in rows:  # positional (col names Shrp/MaxDD% repeat across the two blocks)
    print(f"{x[0]:>6} {x[1]:>7.1f} {x[2]:>6.1f} {x[3]:>5.2f} {x[4]:>5.2f} {x[5]:>7.1f} "
          f"{x[6]:>5.0f} {x[7]:>5.2f} | {x[8]:>9.0f} {x[9]:>6.1f} {x[10]:>5.2f} {x[11]:>7.1f}")

# ---- PNG table ----
fig, ax = plt.subplots(figsize=(13.5, 0.42 * len(df) + 1.7))
ax.axis("off")
cell = [[x[0], f"{x[1]:.1f}", f"{x[2]:.1f}", f"{x[3]:.2f}", f"{x[4]:.2f}", f"{x[5]:.1f}",
         f"{x[6]:.0f}", f"{x[7]:.2f}", f"{x[8]:,.0f}", f"{x[9]:.1f}", f"{x[10]:.2f}", f"{x[11]:.1f}"]
        for x in rows]
tbl = ax.table(cellText=cell, colLabels=cols, cellLoc="center", loc="center")
tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.35)
# shade the two blocks + header
for (rr_, cc), cellobj in tbl.get_celld().items():
    if rr_ == 0:
        cellobj.set_facecolor("#08519c"); cellobj.set_text_props(color="white", fontweight="bold")
    elif cc >= 8:
        cellobj.set_facecolor("#eef4fb")
    if cc == 0 and rr_ > 0:
        cellobj.set_text_props(fontweight="bold")
ax.set_title(f"rob_dynamic — annual performance, last {len(df)} yrs  ·  {stats.get('universe','?')} futures  "
             f"·  ${cap:,.0f} @ {stats.get('vol_target','?')}% vol  ·  since {incep.date()}\n"
             f"THIS YEAR (cols 2-8)  |  SINCE INCEPTION to that Dec 31 (cols 9-12)   "
             f"[* {show[-1]} partial to {last.date()}]", fontsize=10.5, pad=14)
png = os.path.join(d, "annual_performance_table.png")
fig.savefig(png, dpi=140, bbox_inches="tight"); plt.close(fig)
print(f"\nplot -> {png}")
