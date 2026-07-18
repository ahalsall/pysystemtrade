"""Regime-summary: our fund vs long S&P 500 vs a 60/40 blend, across inception windows
(1996 full history / 2005 incl. GFC / 2012 bull-only). Shows how the standalone winner
flips with the sample while the blend stays top-or-near-top and correlation stays low --
the non-cherry-picked case for the diversifier. Prints a table + renders a PNG.

Returns: fund from a saved run (daily_pnl/capital); S&P = correctly-rolled futures return
(adjusted-price $ change / actual front-contract price). Blend = 60% S&P / 40% fund, daily-rebal.

Usage:  uv run python -m sysinit.futures.sp500_regime_summary [fund_label]
"""
import os, sys, json
os.environ["MPLBACKEND"] = "Agg"
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["text.parse_math"] = False
from sysinit.futures.backtest_results import RUNS_DIR
from sysproduction.data.prices import diagPrices

BDAYS = 256
WINDOWS = [(1996, "full"), (2005, "+GFC"), (2012, "bull")]
W_SPX = 0.60
label = sys.argv[1] if len(sys.argv) > 1 else "rob_dynamic_prod_250k_dm275"
d = os.path.join(RUNS_DIR, label)
stats = json.load(open(os.path.join(d, "stats.json")))
cap = float(stats["capital"])
fund_all = (pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna() / cap)

dp = diagPrices()
adj = dp.get_adjusted_prices("SP500_micro").dropna()
price = dp.get_multiple_prices("SP500_micro")["PRICE"].reindex(adj.index).ffill()
spx_all = (adj.diff() / price.shift(1)).dropna()


def stat(r):
    e = (1 + r).cumprod(); yrs = len(r) / BDAYS
    return dict(cagr=e.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(BDAYS),
                sharpe=r.mean() / r.std() * np.sqrt(BDAYS), mdd=(e / e.cummax() - 1).min())


rows = []
for yr, tag in WINDOWS:
    idx = fund_all.index.intersection(spx_all.index); idx = idx[idx.year >= yr]
    f, s = fund_all.reindex(idx).fillna(0), spx_all.reindex(idx).fillna(0)
    b = W_SPX * s + (1 - W_SPX) * f
    sf, ss, sb = stat(f), stat(s), stat(b)
    corr = float(f.corr(s))
    rows.append((f"{yr}-26  {tag}", sf, ss, sb, corr, len(idx) / BDAYS))

hdr = f"{'window':>20} | {'FUND cagr/shrp/DD':>22} | {'S&P cagr/shrp/DD':>22} | {'60/40 cagr/shrp/DD':>22} | {'corr':>5}"
print(f"\n=== {label}: fund vs S&P vs 60/40 blend, by inception window ===")
print(hdr); print("-" * len(hdr))
def cell(s): return f"{s['cagr']*100:5.1f}% {s['sharpe']:4.2f} {s['mdd']*100:5.0f}%"
for w, sf, ss, sb, corr, yrs in rows:
    print(f"{w:>20} | {cell(sf):>22} | {cell(ss):>22} | {cell(sb):>22} | {corr:>+5.2f}")

# ---- PNG table ----
cols = ["Window", "Fund\nCAGR", "Fund\nSharpe", "Fund\nMaxDD", "S&P\nCAGR", "S&P\nSharpe", "S&P\nMaxDD",
        "60/40\nCAGR", "60/40\nSharpe", "60/40\nMaxDD", "corr"]
cell_txt = [[w,
             f"{sf['cagr']*100:.1f}%", f"{sf['sharpe']:.2f}", f"{sf['mdd']*100:.0f}%",
             f"{ss['cagr']*100:.1f}%", f"{ss['sharpe']:.2f}", f"{ss['mdd']*100:.0f}%",
             f"{sb['cagr']*100:.1f}%", f"{sb['sharpe']:.2f}", f"{sb['mdd']*100:.0f}%",
             f"{corr:+.2f}"] for w, sf, ss, sb, corr, yrs in rows]
fig, ax = plt.subplots(figsize=(14.5, 3.2)); ax.axis("off")
tbl = ax.table(cellText=cell_txt, colLabels=cols, cellLoc="center", loc="center",
               colWidths=[0.13] + [0.083] * (len(cols) - 1))
tbl.auto_set_font_size(False); tbl.set_fontsize(10); tbl.scale(1, 2.0)
for (r_, c_), cell_ in tbl.get_celld().items():
    if r_ == 0:
        cell_.set_facecolor("#08519c"); cell_.set_text_props(color="white", fontweight="bold")
    elif 7 <= c_ <= 9:
        cell_.set_facecolor("#e5f5e0")          # highlight the blend block
    elif 1 <= c_ <= 3:
        cell_.set_facecolor("#eef4fb")
    if c_ == 0 and r_ > 0:
        cell_.set_text_props(fontweight="bold")
ax.set_title("Fund vs 'all on black' S&P 500 vs 60/40 blend — the standalone winner flips with the sample,\n"
             "but the blend stays top-or-near-top and correlation stays low (the diversifier's real case)",
             fontsize=11, pad=12)
png = os.path.join(d, "sp500_regime_summary.png")
fig.savefig(png, dpi=140, bbox_inches="tight"); plt.close(fig)
print(f"\nplot -> {png}")
