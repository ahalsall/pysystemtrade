"""Capital sweep for the TRUSTWORTHY estimated-weights book (clean CSI, single source).
Loops capital levels, reports Sharpe / ann / REALIZED-vs-TARGET vol / maxDD / funded count.
The headline is realized vol converging toward the 20% target (AFTS) as capital rises — i.e. the
small-capital integer-lumpiness under-investment quantified. Env: VOL_TARGETS unused;
CAPITALS (comma list, default 110000,300000,500000,1000000)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
import pandas as pd
from collections import Counter
from sysproduction.data.prices import diagPrices
from sysdata.config.configdata import Config
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from systems.basesystem import System
from systems.forecasting import Rules
from systems.forecast_combine import ForecastCombine
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import volAttenForecastScaleCap
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.positionsizing import PositionSizing
from systems.portfolio import Portfolios
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import optimisedPositions
from systems.risk import Risk
from systems.provided.dynamic_small_system_optimise.accounts_stage import accountForOptimisedStage
from sysinit.futures.csi_catalog_map import load_pst_index
from sysinit.futures.backtest_results import full_stats, save_run

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
          if r and r[0] != "csi_symbol")
cfg_inst = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
data = dbFuturesSimData()  # reused across capitals (prices cached)
cands = csi & data_inst & cfg_inst
last = {}
for c in cands:
    try:
        last[c] = pd.Timestamp(data.get_raw_price(c).dropna().index[-1].date())
    except Exception:
        last[c] = pd.Timestamp("1900-01-01")
fresh = max(last.values())
our = sorted(c for c in cands if (fresh - last[c]).days <= 45)
w = 1.0 / len(our)
pidx = load_pst_index()
CAPITALS = [float(x) for x in os.environ.get("CAPITALS", "110000,300000,500000,1000000").split(",")]
# VOL_TARGET default 20% to match AFTS Strategy 25 (Rob uses a 20% risk target in the
# book; our rob_system config default is 25%). Set VOL_TARGET=25 to revert.
VOL_TARGET = float(os.environ.get("VOL_TARGET", 20))
print(f"universe {len(our)} clean instruments (of {len(cands)}) | estimated weights | "
      f"vol target {VOL_TARGET:.0f}% (AFTS uses 20%)\n", flush=True)
rows = []
for cap in CAPITALS:
    config = Config("systems.provided.rob_system.config.yaml")
    config.notional_trading_capital = cap
    config.percentage_vol_target = VOL_TARGET
    config.instrument_weights = {i: w for i in our}
    config.use_instrument_weight_estimates = True
    system = System(
        [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
         PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
        data, config,
    )
    print(f"===== capital ${cap:,.0f} (heavy)... =====", flush=True)
    acc = system.accounts.portfolio()
    pos = system.optimisedPositions.get_optimised_position_df()
    funded = int(((pos.abs() > 0).sum() > 0).sum())
    held_last = int((pos.iloc[-1].abs() > 0).sum())
    stats = full_stats(acc, cap, extra=dict(vol_target=VOL_TARGET, funded=funded,
                                            held_last=held_last, universe=len(our),
                                            weights="estimated"))
    outdir = save_run(f"capsweep_{int(cap)}", acc, cap, stats)  # curve + stats persisted
    print(f"  Sharpe {stats['sharpe']:.2f} | ann {stats['ann_return_pct']:.1f}% | "
          f"REALIZED vol {stats['ann_vol_pct']:.1f}% (target {VOL_TARGET:.0f}%) | maxDD {stats['max_dd_pct']:.1f}% | "
          f"AVG DD {stats['avg_dd_pct']:.1f}% | skew {stats['skew']:.2f} | "
          f"funded {funded}/{len(our)} | held today {held_last}  -> {outdir}", flush=True)
    rows.append(stats)

print(f"\n=== CAPITAL SWEEP SUMMARY (clean CSI, estimated weights, {VOL_TARGET:.0f}% target) ===")
cols = ["capital", "sharpe", "ann_return_pct", "ann_vol_pct", "max_dd_pct", "avg_dd_pct",
        "time_in_dd_pct", "skew", "funded", "held_last"]
print(pd.DataFrame(rows)[cols].to_string(index=False))
pd.DataFrame(rows).to_csv("/home/andrew/pysystemtrade/private/dynopt_capital_sweep.csv", index=False)
print("saved -> private/dynopt_capital_sweep.csv  (+ per-capital curves in private/backtest_runs/)")
