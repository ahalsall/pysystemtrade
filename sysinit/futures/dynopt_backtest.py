"""Dynamic-opt backtest on our CSI deep-history instruments (rob_system template)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
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

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
          if r and r[0] != "csi_symbol")
config = Config("systems.provided.rob_system.config.yaml")
cfg_inst = set(config.instrument_weights.keys())
EXCLUDE = {"GAS_US_mini", "YENEUR", "FEEDCOW"}  # truncated -> stale/NaN recent data
our = sorted((csi & data_inst & cfg_inst) - EXCLUDE)
print(f"BACKTEST universe: {len(our)} instruments (CSI deep-history, Rob-fitted)")

w = 1.0 / len(our)
config.instrument_weights = {i: w for i in our}
config.use_instrument_weight_estimates = False

system = System(
    [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
     PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
    dbFuturesSimData(), config,
)
print("Running dynamic-opt account curve (this is the heavy part)...", flush=True)
acc = system.accounts.portfolio()
p = acc.percent  # values are already in PERCENTAGE POINTS (20.0 = 20%)
print("\n=== DYNAMIC-OPT BACKTEST RESULTS ===", flush=True)
print(f"  Sharpe:       {p.sharpe():.2f}")
print(f"  Ann return:   {p.ann_mean():.2f}%")
print(f"  Ann vol:      {p.ann_std():.2f}%")
print(f"  Skew:         {p.skew():.2f}")
try:
    print(f"  Avg drawdown: {p.avg_drawdown():.1f}%   Max drawdown: {p.worst_drawdown():.1f}%")
except Exception as e:
    print(f"  (drawdown skipped: {type(e).__name__})")
# robust curve accessor
curve = None
for getter in (lambda: p.curve(), lambda: getattr(acc, "as_ts"), lambda: acc.curve()):
    try:
        c = getter()
        if hasattr(c, "index") and len(c):
            curve = c
            break
    except Exception:
        pass
if curve is not None:
    print(f"  Period:       {curve.index[0].date()} -> {curve.index[-1].date()}")
    curve.to_csv("/home/andrew/pysystemtrade/private/dynopt_backtest_curve.csv")
    print("  saved cumulative %% curve -> private/dynopt_backtest_curve.csv")
# dynamic-opt sparsity: how many instruments actually held on the last date
try:
    pos = system.optimisedPositions.get_optimised_position_df()
    held = int((pos.iloc[-1].abs() > 0).sum())
    print(f"  Instruments held on last date: {held} of {len(our)} (dynamic-opt sparsity)")
except Exception as e:
    print(f"  (position count skipped: {type(e).__name__})")
