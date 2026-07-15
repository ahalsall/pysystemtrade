"""CURIOSITY EXPERIMENT (NOT production) -- can we bank more of the 2022 trend payoff by de-throttling?
Overrides at RUNTIME only (production config untouched): capital $1M, vol target 30%, vol-attenuation OFF
(use_attenuation=[]). Tests the hypothesis that the attenuate_vol stage cut risk in high-vol 2022 and
cost us the industry's ~+25% CTA year. Reports overall + PER-YEAR 2018-2026 with a direct 2022 vs the
throttled dm2.5 baseline ($250k/20%/atten-on). Saves under private/backtest_runs/EXPERIMENT_*/.
"""
import os
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
import pandas as pd
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
from sysinit.futures.backtest_results import full_stats, save_run

CAPITAL = float(os.environ.get("CAPITAL", 1_000_000))
VOL = float(os.environ.get("VOL_TARGET", 30))
ATTEN_OFF = os.environ.get("ATTEN_OFF", "1") == "1"
LABEL = f"EXPERIMENT_{int(CAPITAL/1000)}k_{int(VOL)}vol_{'noatten' if ATTEN_OFF else 'atten'}"

config = Config("private.systems.rob_dynamic.config.yaml")
config.notional_trading_capital = CAPITAL
config.percentage_vol_target = VOL
if ATTEN_OFF:
    config.use_attenuation = []   # disable vol attenuation for ALL rules (same stage, no throttling)
n = len(config.instrument_weights)
print(f"EXPERIMENT: ${CAPITAL:,.0f} / {VOL:.0f}% vol / attenuation {'OFF' if ATTEN_OFF else 'ON'} / "
      f"{n} instruments / estimated IDM", flush=True)

system = System([Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
                 PositionSizing(), myFuturesRawData(), ForecastCombine(),
                 volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)

acc = system.accounts.portfolio()
raw = acc.as_ts; raw = raw() if callable(raw) else raw
d = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
d.index = pd.to_datetime(d.index)

stats = full_stats(acc, CAPITAL, extra=dict(vol_target=VOL, attenuation=not ATTEN_OFF, universe=n))
outdir = save_run(LABEL, acc, CAPITAL, stats)          # curve.csv (full daily cumulative %) + stats.json
# also persist raw daily P&L for full-fidelity offline analysis (parity with the dm2.5/2.75 runs)
try:
    d.to_frame("daily_pnl_ccy").to_parquet(os.path.join(outdir, "daily_pnl.parquet"))
except Exception:
    d.to_csv(os.path.join(outdir, "daily_pnl.csv"), header=["daily_pnl_ccy"])
print(f"captured full curve -> {outdir}/curve.csv + daily_pnl.parquet + stats.json", flush=True)
print(f"\n=== OVERALL (1996-2026) ===", flush=True)
print(f"  Sharpe {stats['sharpe']:.2f} | ann {stats['ann_return_pct']:.1f}% | REALIZED vol "
      f"{stats['ann_vol_pct']:.1f}% (target {VOL:.0f}%) | maxDD {stats['max_dd_pct']:.1f}% | "
      f"avgDD {stats['avg_dd_pct']:.1f}% | skew {stats['skew']:.2f}", flush=True)

# baseline dm2.5 daily pnl for a like-for-like 2022 (and per-year) comparison
base = pd.read_parquet("private/backtest_runs/rob_dynamic_prod_250k_dm250/daily_pnl.parquet").iloc[:, 0]
base.index = pd.to_datetime(base.index); base = base.replace([np.inf, -np.inf], np.nan).dropna()
BASE_CAP = 250000

print(f"\n=== PER-YEAR 2018-2026 : EXPERIMENT vs throttled dm2.5 baseline ===", flush=True)
print(f"{'yr':<6}{'EXP ret':>9}{'EXP vol':>9}{'EXP DD':>9}   {'base ret':>9}{'base vol':>9}", flush=True)
for yr in range(2018, 2027):
    e = d.loc[str(yr)]; b = base.loc[str(yr)]
    if len(e) == 0:
        continue
    ec = e.cumsum() / CAPITAL * 100; edd = (ec - ec.cummax()).min()
    er = e.sum() / CAPITAL * 100; ev = e.std() * np.sqrt(256) / CAPITAL * 100
    br = b.sum() / BASE_CAP * 100 if len(b) else float("nan")
    bv = b.std() * np.sqrt(256) / BASE_CAP * 100 if len(b) else float("nan")
    star = "  <<< 2022" if yr == 2022 else ""
    print(f"{yr:<6}{er:>8.1f}%{ev:>8.1f}%{edd:>8.1f}%   {br:>8.1f}%{bv:>8.1f}%{star}", flush=True)

print(f"\nsaved -> private/backtest_runs/{LABEL}/", flush=True)
