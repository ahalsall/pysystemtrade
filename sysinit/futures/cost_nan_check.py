"""Find which instrument feeds a NaN cost into the dynamic optimiser (the bug that
makes it bail to 'prior weights'). Prints per-instrument cost-per-notional-weight +
raw cost + block value + last price, flagging NaN/zero. Env: SELECTION."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
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
sel = os.environ.get("SELECTION", "").strip()
our = sorted(set(c.strip() for c in sel.split(",")) & (csi & data_inst & cfg_inst))
config.notional_trading_capital = float(os.environ.get("CAPITAL", 110000))
w = 1.0 / len(our)
config.instrument_weights = {i: w for i in our}
config.use_instrument_weight_estimates = False
system = System(
    [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
     PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
    dbFuturesSimData(), config,
)
op = system.optimisedPositions
print(f"{'instr':<15}{'cost/notional_wt':>18}{'raw_cost':>12}{'block_val':>12}{'last_price':>12}  FLAG")
for code in our:
    flag = ""
    try:
        cnw = float(op.get_cost_per_notional_weight_as_proportion_of_capital(code))
    except Exception as e:
        cnw = float("nan"); flag += f"ERR:{type(e).__name__} "
    try:
        raw = float(op.get_cost_per_contract_in_base_ccy(code))
    except Exception:
        raw = float("nan")
    try:
        block = float(system.data.get_value_of_block_price_move(code))
    except Exception:
        block = float("nan")
    try:
        px = float(system.rawdata.get_daily_prices(code).iloc[-1])
    except Exception:
        px = float("nan")
    if np.isnan(cnw): flag += "NaN-COST "
    if cnw == 0: flag += "ZERO-COST "
    print(f"{code:<15}{cnw:>18.8f}{raw:>12.4f}{block:>12.2f}{px:>12.2f}  {flag}")

# also dump the full costs vector the optimiser builds on the last date
print("\n--- costs_per_contract_as_proportion_of_capital (all instruments, last date) ---")
try:
    allc = op.get_costs_per_contract_as_proportion_of_capital_all_instruments()
    last = allc.iloc[-1]
    bad = last[last.isna() | (last == 0)]
    print("NaN/zero on last date:", dict(bad))
except Exception as e:
    import traceback; traceback.print_exc()
