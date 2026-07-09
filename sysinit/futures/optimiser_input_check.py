"""Inspect the EXACT inputs the dynamic optimiser consumes on a recent date, to
find why some instruments (DOW/equities) are never held despite healthy upstream
optimal positions. Prints per-instrument: target contracts, cost/contract, per-
contract-value, covariance-variance. Flags NaN/zero (which throws -> freeze). Env: SELECTION."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
import pandas as pd
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
date = op.common_index()[-1]
print(f"inspecting optimiser inputs on {date}\n", flush=True)

target = op.original_position_contracts_for_relevant_date(date)     # what greedy tracks (contracts)
costs = op.get_costs_per_contract_as_proportion_of_capital_all_instruments(date)
pcv = op.get_per_contract_value(date)
cov = op.get_covariance_matrix(relevant_date=date)

def val(obj, code):
    try:
        if hasattr(obj, "get"): return obj.get(code, np.nan)
        if isinstance(obj, dict): return obj.get(code, np.nan)
        return obj[code]
    except Exception:
        return np.nan

# covariance diagonal (variance) per instrument
try:
    cov_df = pd.DataFrame(cov.values, index=cov.columns, columns=cov.columns) if hasattr(cov, "values") else None
except Exception:
    cov_df = None

print(f"{'instr':<15}{'target_contracts':>17}{'cost/contract':>15}{'per_contract_val':>18}{'variance':>12}  FLAG")
for code in our:
    t = float(val(target, code)); c = float(val(costs, code)); v = float(val(pcv, code))
    try:
        var = float(cov.subset([code]).values[0][0])
    except Exception:
        var = np.nan
    flag = ""
    if np.isnan(t): flag += "TARGET-NaN "
    if t == 0: flag += "target0 "
    if np.isnan(c): flag += "COST-NaN "
    if c == 0: flag += "cost0 "
    if np.isnan(v) or v == 0: flag += "PCV-bad "
    if np.isnan(var) or var == 0: flag += "VAR-bad "
    print(f"{code:<15}{t:>17.4f}{c:>15.8f}{v:>18.6f}{var:>12.6f}  {flag}")
