"""Production book + account curve + estimated-IDM capture, in ONE system build.

Builds the corrected rob_dynamic production system straight from the yaml (now 20% / $250k /
estimated IDM -- the QA-audited config) and emits:
  - ESTIMATED IDM, pre-cap AND post-cap (dm_max=2.5), full timeseries + latest, vs the handcrafted
    fixed 2.75 -> private/backtest_runs/<label>/idm.csv
  - account curve STATS (full_stats) -> stats.json
  - the FULL curve: cumulative %-of-capital (curve.csv) + raw daily P&L (daily_pnl.parquet) for
    offline analysis
  - a matplotlib PNG (cumulative curve + drawdown) -> curve.png
  - TARGET BOOK (optimal integer positions today) -> target_book_250k.csv
Read-only / places nothing.
"""
import os
os.environ["MPLBACKEND"] = "Agg"
os.environ.setdefault("TZ", "UTC")
from copy import copy
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sysdata.config.configdata import Config
from systems.basesystem import System
from systems.risk import Risk
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import optimisedPositions
from systems.provided.dynamic_small_system_optimise.accounts_stage import accountForOptimisedStage
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.forecast_combine import ForecastCombine
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import volAttenForecastScaleCap
from systems.forecasting import Rules
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysquant.estimators.diversification_multipliers import diversification_multiplier_from_list
from sysinit.futures.backtest_results import full_stats, save_run, RUNS_DIR

config = Config("private.systems.rob_dynamic.config.yaml")
CAP = float(config.notional_trading_capital)
VOL = float(config.percentage_vol_target)
FIXED_IDM = float(config.instrument_div_multiplier)
# DM_MAX env overrides the estimated-IDM cap for a side-by-side COMPARISON run (e.g. 2.5 vs 2.75).
# A comparison run writes its own labelled artifacts but does NOT overwrite the production target_book.
_dm_override = os.environ.get("DM_MAX")
if _dm_override:
    config.instrument_div_mult_estimate["dm_max"] = float(_dm_override)
    print(f"[DM_MAX override] dm_max -> {_dm_override} (comparison run; target_book NOT overwritten)", flush=True)
try:
    _dm = float(config.instrument_div_mult_estimate["dm_max"])  # label tracks the cap for side-by-side runs
except Exception:
    _dm = FIXED_IDM
LABEL = f"rob_dynamic_prod_250k_dm{int(round(_dm * 100))}"
n = len(config.instrument_weights)
print(f"Building rob_dynamic PRODUCTION system from yaml: ${CAP:,.0f} / {VOL:.0f}% vol / "
      f"{n} instruments / estimated IDM (fixed fallback {FIXED_IDM})", flush=True)

system = System([Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
                 PositionSizing(), myFuturesRawData(), ForecastCombine(),
                 volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)

outdir = os.path.join(RUNS_DIR, LABEL)
os.makedirs(outdir, exist_ok=True)

# ---------- ESTIMATED IDM: post-cap (as the system uses) + pre-cap (dm_max lifted) ----------
print("\n[IDM] estimating instrument diversification multiplier...", flush=True)
idm_postcap = system.portfolio.get_instrument_diversification_multiplier()
corr = system.portfolio.get_instrument_correlation_matrix()
weights = system.portfolio.get_instrument_weights()
params = copy(config.instrument_div_mult_estimate)
params.pop("func")
params["dm_max"] = 999.0  # lift the cap to expose the raw estimate
idm_precap = diversification_multiplier_from_list(corr, weights, **params)

idm = pd.DataFrame({"idm_precap": pd.Series(idm_precap), "idm_postcap": pd.Series(idm_postcap)}).dropna()
idm.to_csv(os.path.join(outdir, "idm.csv"))
pre_last, post_last = float(idm["idm_precap"].iloc[-1]), float(idm["idm_postcap"].iloc[-1])
cap_binds_pct = float((idm["idm_precap"] > 2.5).mean() * 100)
print(f"  latest estimated IDM  pre-cap {pre_last:.3f}  post-cap {post_last:.3f}  | handcrafted fixed {FIXED_IDM}", flush=True)
print(f"  pre-cap series: min {idm['idm_precap'].min():.3f} / mean {idm['idm_precap'].mean():.3f} / "
      f"max {idm['idm_precap'].max():.3f} | cap(2.5) binds {cap_binds_pct:.0f}% of history", flush=True)
print(f"  -> {outdir}/idm.csv", flush=True)

# ---------- ACCOUNT CURVE: stats + full curve capture ----------
print("\n[CURVE] building optimised account curve (heavy)...", flush=True)
acc = system.accounts.portfolio()
pos = system.optimisedPositions.get_optimised_position_df()
funded = int(((pos.abs() > 0).sum() > 0).sum())
held_last = int((pos.iloc[-1].abs() > 0).sum())
stats = full_stats(acc, CAP, extra=dict(vol_target=VOL, universe=n, funded=funded,
                                        held_last=held_last, weights="fixed(rob)", idm="estimated",
                                        idm_precap_last=round(pre_last, 3), idm_postcap_last=round(post_last, 3)))
save_run(LABEL, acc, CAP, stats)  # curve.csv + stats.json
# raw daily P&L for offline analysis
raw = acc.as_ts; raw = raw() if callable(raw) else raw
daily = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
try:
    daily.to_frame("daily_pnl_ccy").to_parquet(os.path.join(outdir, "daily_pnl.parquet"))
except Exception:
    daily.to_csv(os.path.join(outdir, "daily_pnl.csv"), header=["daily_pnl_ccy"])
print(f"  Sharpe {stats['sharpe']:.2f} | ann {stats['ann_return_pct']:.1f}% | REALIZED vol "
      f"{stats['ann_vol_pct']:.1f}% (target {VOL:.0f}%) | maxDD {stats['max_dd_pct']:.1f}% | "
      f"avgDD {stats['avg_dd_pct']:.1f}% | skew {stats['skew']:.2f} | funded {funded}/{n} | "
      f"[{stats['start']}..{stats['end']}]", flush=True)

# ---------- MATPLOTLIB: cumulative curve + drawdown ----------
cum = daily.cumsum() / CAP * 100
dd = cum - cum.cummax()
fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
a1.plot(cum.index, cum.values, lw=0.9, color="#1f77b4")
a1.set_title(f"{LABEL}  |  ${CAP:,.0f} @ {VOL:.0f}% vol, estimated IDM  "
             f"(Sharpe {stats['sharpe']:.2f}, vol {stats['ann_vol_pct']:.1f}%, maxDD {stats['max_dd_pct']:.1f}%)")
a1.set_ylabel("cumulative % of capital"); a1.grid(alpha=0.3)
a2.fill_between(dd.index, dd.values, 0, color="#d62728", alpha=0.5)
a2.set_ylabel("drawdown %"); a2.grid(alpha=0.3)
fig.tight_layout()
png = os.path.join(outdir, "curve.png")
fig.savefig(png, dpi=110); plt.close(fig)
print(f"  plot -> {png}", flush=True)

# ---------- TARGET BOOK ----------
today = pos.iloc[-1]; asof = pos.index[-1].date()
tgt = today.round().astype(int); tgt = tgt[tgt != 0].sort_values()
print(f"\n[BOOK] {len(tgt)} held / {n} universe | gross {int(tgt.abs().sum())} contracts (as of {asof})", flush=True)
print(tgt.to_string(), flush=True)
if _dm_override:
    print(f"\n[comparison run dm_max={_dm_override}] target_book NOT overwritten; artifacts under {outdir}/", flush=True)
else:
    tgt.to_csv("private/target_book_250k.csv", header=["target_contracts"])
    print(f"\nsaved -> private/target_book_250k.csv  | all artifacts under {outdir}/", flush=True)
