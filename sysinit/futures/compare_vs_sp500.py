"""'All on black' reference: our diversified fund vs simply going long the S&P 500
(held 1x via SP500 micro futures), same $1 start, over the 2012-inception window.

Fund returns come from a SAVED backtest run (daily_pnl/capital). S&P return is the
correctly-rolled futures return: adjusted-price $ change / actual front-contract price
(NOT pct_change on the Panama series, which damps early returns). Both are pure market
P&L -- both leave most capital idle as margin, so the money-market uplift applies about
equally to each and is omitted here.

Usage:  uv run python -m sysinit.futures.compare_vs_sp500 [fund_label] [inception_year] [sp_leverage]
        (defaults: rob_dynamic_prod_250k_dm275, 2012, 1.0)
        sp_leverage 1.0 = 100% notional long ("all on black"); e.g. 0.66 for a risk-lighter bet.
"""
import os, sys, json
os.environ["MPLBACKEND"] = "Agg"
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
plt.rcParams["text.parse_math"] = False
from sysinit.futures.backtest_results import RUNS_DIR
from sysproduction.data.prices import diagPrices

BDAYS = 256
label = sys.argv[1] if len(sys.argv) > 1 else "rob_dynamic_prod_250k_dm275"
INCEP = int(sys.argv[2]) if len(sys.argv) > 2 else 2012
LEV = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

d = os.path.join(RUNS_DIR, label)
stats = json.load(open(os.path.join(d, "stats.json")))
cap = float(stats["capital"])
fund = (pd.read_parquet(os.path.join(d, "daily_pnl.parquet")).iloc[:, 0].dropna() / cap)

dp = diagPrices()
adj = dp.get_adjusted_prices("SP500_micro").dropna()
price = dp.get_multiple_prices("SP500_micro")["PRICE"].reindex(adj.index).ffill()
spx = (adj.diff() / price.shift(1)).dropna() * LEV        # correctly-rolled 1x (x LEV) S&P futures return

# common window, from INCEP
idx = fund.index.intersection(spx.index)
idx = idx[idx.year >= INCEP]
fund, spx = fund.reindex(idx).fillna(0), spx.reindex(idx).fillna(0)
ef, es = (1 + fund).cumprod(), (1 + spx).cumprod()
yrs = len(idx) / BDAYS


def stat(r, e):
    cagr = e.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(BDAYS)
    sharpe = r.mean() / r.std() * np.sqrt(BDAYS)
    dn = r[r < 0]; sortino = r.mean() / dn.std() * np.sqrt(BDAYS)
    mdd = (e / e.cummax() - 1).min()
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, sortino=sortino, mdd=mdd, term=e.iloc[-1])


sf, ss = stat(fund, ef), stat(spx, es)
# lever the fund: to its TARGET vol, and (for the risk-matched read) to the S&P's vol
fund_vol = float(fund.std() * np.sqrt(BDAYS))
target_vol = float(stats.get("vol_target", 25.0)) / 100
lev_t = target_vol / fund_vol                              # scale to hit the design target
lev_m = ss["vol"] / fund_vol                               # scale to match the S&P's realized vol
fund_t = fund * lev_t; ef_t = (1 + fund_t).cumprod()
fund_m = fund * lev_m; ef_m = (1 + fund_m).cumprod()
sft, sfm = stat(fund_t, ef_t), stat(fund_m, ef_m)

# 60/40-style blend: 60% S&P (growth) + 40% our fund (uncorrelated ballast), daily-rebalanced
W_SPX = 0.60
blend = W_SPX * spx + (1 - W_SPX) * fund; eb = (1 + blend).cumprod()
sb = stat(blend, eb)
corr = float(fund.corr(spx))

spx_name = f"S&P 500 long {LEV:g}x (all on black)"
blend_name = f"blend {int(W_SPX*100)}/{int((1-W_SPX)*100)} S&P/fund"
print(f"\n=== {label} vs S&P-500-{LEV:g}x, since {idx[0].date()} -> {idx[-1].date()} ({yrs:.1f}y) ===")
print(f"realized fund vol {fund_vol*100:.1f}% vs {target_vol*100:.0f}% target -> lever x{lev_t:.2f} to reach target; "
      f"x{lev_m:.2f} to match S&P vol")
print(f"corr(fund, S&P) = {corr:+.2f}   <- the diversification lever\n")
print(f"{'':32} {'CAGR%':>7} {'Vol%':>6} {'Sharpe':>7} {'Sortino':>7} {'MaxDD%':>7} {'$1 ->':>7}")
for nm, s in [(f"our fund (realized ~{fund_vol*100:.0f}% vol)", sf),
              (f"our fund LEVERED to {target_vol*100:.0f}% target (x{lev_t:.2f})", sft),
              (f"our fund risk-matched to S&P (x{lev_m:.2f})", sfm),
              (spx_name, ss),
              (f"{blend_name} (rebal daily)", sb)]:
    print(f"{nm:32} {s['cagr']*100:>7.1f} {s['vol']*100:>6.1f} {s['sharpe']:>7.2f} "
          f"{s['sortino']:>7.2f} {s['mdd']*100:>7.1f} {s['term']:>7.2f}")

fig, ax = plt.subplots(figsize=(13, 7.2))
ax.plot(ef.index, ef.values, lw=1.3, color="#6baed6", label=f"our fund, realized ~{sf['vol']*100:.0f}% vol — CAGR {sf['cagr']*100:.1f}%, Sharpe {sf['sharpe']:.2f}, DD {sf['mdd']*100:.0f}%")
ax.plot(ef_t.index, ef_t.values, lw=1.7, color="#08519c", label=f"our fund LEVERED to {target_vol*100:.0f}% target (x{lev_t:.2f}) — CAGR {sft['cagr']*100:.1f}%, vol {sft['vol']*100:.0f}%, Sharpe {sft['sharpe']:.2f}, DD {sft['mdd']*100:.0f}%")
ax.plot(es.index, es.values, lw=1.4, color="#d62728", label=f"{spx_name} — CAGR {ss['cagr']*100:.1f}%, vol {ss['vol']*100:.0f}%, Sharpe {ss['sharpe']:.2f}, DD {ss['mdd']*100:.0f}%")
ax.plot(eb.index, eb.values, lw=1.9, color="#238b45", label=f"{blend_name} — CAGR {sb['cagr']*100:.1f}%, vol {sb['vol']*100:.0f}%, Sharpe {sb['sharpe']:.2f}, DD {sb['mdd']*100:.0f}%  (corr {corr:+.2f})")
ax.set_yscale("log")
_fmt = mticker.FuncFormatter(lambda x, _: f"${x:,.1f}")
ax.yaxis.set_major_formatter(_fmt)
ax.yaxis.set_minor_formatter(_fmt)      # <1-decade range -> ticks are minor; format them too
ax.set_ylabel("growth of $1 (compounded, log)"); ax.set_xlabel("date"); ax.grid(alpha=0.3, which="both")
ax.legend(loc="upper left", fontsize=10, framealpha=0.92)
ax.set_title(f"'All on black' reference — diversified fund vs long S&P 500 ({LEV:g}x micros)\n"
             f"since {idx[0].date()}  ·  pure market P&L (money-market uplift applies ~equally to both)",
             fontsize=12)
png = os.path.join(d, f"compare_vs_sp500_{INCEP}_{LEV:g}x.png")
fig.savefig(png, dpi=130, bbox_inches="tight"); plt.close(fig)
print(f"\nplot -> {png}")
