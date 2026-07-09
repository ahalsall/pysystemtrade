"""IDM + affordability diagnostic for the static-selected set at a given capital.
Prints the instrument diversification multiplier and, per instrument, the Layer-1
OPTIMAL position (fractional contracts, pre-dynamic-opt) vs the Layer-2 OPTIMISED
integer position. Reveals whether 'only 5 funded' is a low-IDM artifact or a genuine
capital wall (optimal << 1 contract). Env: CAPITAL, SELECTION."""
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
from sysinit.futures.csi_catalog_map import load_pst_index

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
          if r and r[0] != "csi_symbol")
config = Config("systems.provided.rob_system.config.yaml")
cfg_inst = set(config.instrument_weights.keys())
CAPITAL = float(os.environ.get("CAPITAL", 110000))
sel = os.environ.get("SELECTION", "").strip()
our = sorted(set(c.strip() for c in sel.split(",")) & (csi & data_inst & cfg_inst))
config.notional_trading_capital = CAPITAL
w = 1.0 / len(our)
config.instrument_weights = {i: w for i in our}
config.use_instrument_weight_estimates = False

system = System(
    [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
     PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
    dbFuturesSimData(), config,
)
print(f"universe {len(our)} | capital ${CAPITAL:,.0f} | vol target {config.percentage_vol_target}% "
      f"| equal weight {w:.4f}", flush=True)

# IDM
idm = system.portfolio.get_instrument_diversification_multiplier()
print(f"\nIDM (instrument diversification multiplier): last={float(idm.iloc[-1]):.2f}  "
      f"mean={float(idm.mean()):.2f}", flush=True)

# config flags that affect IDM/weights
for k in ["use_instrument_div_mult_estimates", "instrument_div_mult_estimate"]:
    print(f"  config.{k} = {getattr(config, k, '<not set>')}", flush=True)

pidx = load_pst_index()
opt_df = system.optimisedPositions.get_optimised_position_df()
rows = []
for code in our:
    notional = system.portfolio.get_notional_position(code)   # Layer-1 optimal (fractional contracts)
    opt_last = float(opt_df[code].iloc[-1]) if code in opt_df.columns else np.nan
    # peak absolute optimal (best chance to clear 1 contract)
    peak = float(notional.abs().max())
    last = float(notional.iloc[-1])
    rows.append(dict(instrument=code, asset=pidx.get(code, {}).get("asset_class", "?"),
                     opt_last=last, opt_peak=peak, integer_last=opt_last))

df = pd.DataFrame(rows).set_index("instrument")
df["ever_1_contract"] = df["opt_peak"] >= 1.0
pd.set_option("display.width", 130)
print(f"\nLayer-1 OPTIMAL (fractional contracts) vs Layer-2 INTEGER, per instrument:")
print(df.sort_values("opt_peak", ascending=False).round(3).to_string())
print(f"\ninstruments whose optimal EVER reaches >=1 contract: "
      f"{int(df['ever_1_contract'].sum())} of {len(df)}")
print(f"instruments whose optimal peak <0.5 contract (genuinely unaffordable): "
      f"{int((df['opt_peak'] < 0.5).sum())}")
df.to_csv("/home/andrew/pysystemtrade/private/idm_diagnostic.csv")
print("saved -> private/idm_diagnostic.csv", flush=True)
