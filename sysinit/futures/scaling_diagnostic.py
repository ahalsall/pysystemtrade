"""Scaling audit: WHY does the fractional rob_system deploy ~15% vs a 20% target?
Distinguishes (A) weak forecasts / attenuation -> smaller positions when trends weak
(BY DESIGN, good) from (B) IDM/scaling under-leverage -> portfolio not levered back up
to match diversification (a fixable inefficiency).

Checks per the risk-scaling chain:
 - avg |combined forecast| per instrument (target 10; <10 => weaker positions by design)
 - subsystem realized vol (instrument traded ALONE; ~= target x avg|fc|/10 if scaled right)
 - IDM (instrument diversification multiplier) + its cap; portfolio_vol vs avg_subsystem_vol
   tells if IDM is correctly levering the diversified book back up (IDM efficient) or not.
 - FDM (forecast diversification multiplier)
Uses the STANDARD fractional Account (no optimiser)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
import pandas as pd
from systems.basesystem import System
from systems.accounts.accounts_stage import Account
from systems.forecasting import Rules
from systems.forecast_combine import ForecastCombine
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import volAttenForecastScaleCap
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.positionsizing import PositionSizing
from systems.portfolio import Portfolios
from sysproduction.data.prices import diagPrices
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysdata.config.configdata import Config

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv")) if r and r[0] != "csi_symbol")
cfg = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
d = dbFuturesSimData()
last = {}
for c in csi & data_inst & cfg:
    try: last[c] = pd.Timestamp(d.get_raw_price(c).dropna().index[-1].date())
    except Exception: last[c] = pd.Timestamp("1900")
fresh = max(last.values()); our = sorted(c for c in csi & data_inst & cfg if (fresh - last[c]).days <= 45)
VT = 20.0

config = Config("systems.provided.rob_system.config.yaml")
config.percentage_vol_target = VT
config.instrument_weights = {i: 1.0 / len(our) for i in our}
config.use_instrument_weight_estimates = True
system = System([Account(), Portfolios(), PositionSizing(), myFuturesRawData(),
                 ForecastCombine(), volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)
print(f"SCALING AUDIT: {len(our)} instruments, {VT}% target, fractional\n", flush=True)

# IDM + FDM + config caps
idm = system.portfolio.get_instrument_diversification_multiplier()
print(f"IDM: last={float(idm.iloc[-1]):.2f} mean={float(idm.mean()):.2f} | cap(dm_max)="
      f"{config.instrument_div_mult_estimate.get('dm_max','?')}", flush=True)

# per-instrument: avg |combined forecast| + subsystem realized vol
fc_abs, ss_vol, fdm = [], [], []
for c in our:
    try:
        f = system.combForecast.get_combined_forecast(c).abs()
        fc_abs.append((c, float(f.mean())))
    except Exception:
        pass
    try:
        v = float(system.accounts.pandl_for_subsystem(c).percent.ann_std())
        ss_vol.append((c, v))
    except Exception:
        pass
    try:
        fdm.append(float(system.combForecast.get_forecast_diversification_multiplier(c).iloc[-1]))
    except Exception:
        pass

fca = pd.Series(dict(fc_abs)); ssv = pd.Series(dict(ss_vol))
port_vol = float(system.accounts.portfolio().percent.ann_std())
print(f"\navg |combined forecast| across book: {fca.mean():.1f}  (target 10.0) "
      f"-> forecast strength = {fca.mean()/10*100:.0f}% of nominal", flush=True)
print(f"avg SUBSYSTEM realized vol (traded alone): {ssv.mean():.1f}%  (target {VT}%) "
      f"-> {ssv.mean()/VT*100:.0f}% of target", flush=True)
print(f"FDM mean: {np.mean(fdm):.2f}", flush=True)
print(f"PORTFOLIO realized vol: {port_vol:.1f}%  (target {VT}%)", flush=True)
print(f"\n--- DIAGNOSIS ---", flush=True)
print(f"portfolio_vol / avg_subsystem_vol = {port_vol/ssv.mean():.2f}  "
      f"(if ~1.0, IDM correctly levers the diversified book back to subsystem level = IDM EFFICIENT;"
      f" if <1.0, IDM under-levers = fixable)", flush=True)
print(f"subsystem shortfall ({VT}->{ssv.mean():.1f}%) tracks forecast strength "
      f"({fca.mean():.1f}/10)? -> if yes, the shortfall is WEAK FORECASTS (by design/conditions), NOT scaling",
      flush=True)
print(f"\nsubsystem vol distribution: min {ssv.min():.0f} / med {ssv.median():.0f} / max {ssv.max():.0f}%", flush=True)
pd.DataFrame({"avg_abs_fc": fca, "subsystem_vol": ssv}).to_csv("private/scaling_diagnostic.csv")
print("saved -> private/scaling_diagnostic.csv", flush=True)
