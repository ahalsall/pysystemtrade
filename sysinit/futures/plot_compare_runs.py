"""Overlay several SAVED backtest runs on one chart (cumulative curve + drawdown) for side-by-side
comparison. Reads only private/backtest_runs/<label>/{curve.csv,stats.json} -- no rebuild, no sim-DB.

Usage:
  uv run python -m sysinit.futures.plot_compare_runs rob_dynamic_prod_250k_dm250 rob_dynamic_prod_250k_dm275
  uv run python -m sysinit.futures.plot_compare_runs <labelA> <labelB> ... --out compare_idm_cap.png
"""
import os
import sys
import json
os.environ["MPLBACKEND"] = "Agg"
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["text.parse_math"] = False

from sysinit.futures.backtest_results import RUNS_DIR

args = sys.argv[1:]
out = "compare_runs.png"
if "--out" in args:
    i = args.index("--out"); out = args[i + 1]; args = args[:i] + args[i + 2:]
labels = args
if len(labels) < 2:
    raise SystemExit("give >=2 saved run labels")

colors = ["#08519c", "#b30000", "#1a9850", "#6a51a3", "#d95f02"]
fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
legend_bits = []
for i, lab in enumerate(labels):
    d = os.path.join(RUNS_DIR, lab)
    st = json.load(open(os.path.join(d, "stats.json")))
    cum = pd.read_csv(os.path.join(d, "curve.csv"), index_col=0, parse_dates=True).iloc[:, 0]
    dd = cum - cum.cummax()
    c = colors[i % len(colors)]
    dmax = st.get("idm_postcap_last", "?")
    tag = f"{lab.split('_')[-1]} (cap {dmax}): SR {st['sharpe']:.3f}, vol {st['ann_vol_pct']:.1f}%, maxDD {st['max_dd_pct']:.1f}%, skew {st['skew']:.2f}"
    a1.plot(cum.index, cum.values, lw=0.9, color=c, label=tag)
    a2.plot(dd.index, dd.values, lw=0.7, color=c)
    legend_bits.append(tag)

a1.set_title(f"Comparison: {'  vs  '.join(l.split('_')[-1] for l in labels)}  "
             f"(same universe/data; additive cumulative %-of-capital)")
a1.set_ylabel("cumulative % of capital"); a1.grid(alpha=0.3); a1.legend(fontsize=8.5, loc="upper left")
a2.set_ylabel("drawdown %"); a2.set_xlabel("date"); a2.grid(alpha=0.3)
fig.tight_layout()
png = os.path.join(RUNS_DIR, out)
fig.savefig(png, dpi=120); plt.close(fig)
print("runs compared:")
for b in legend_bits:
    print("  " + b)
print(f"\nplot -> {png}")
