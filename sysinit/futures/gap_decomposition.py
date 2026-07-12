"""Decompose the vol/Sharpe gap between our rob_system and Rob's AFTS Strategy-11 dynamic-opt
benchmark (Table 128: $100k SR 1.06 @ 18.8% vol; $500k SR 1.22 @ 21.1%).

CORRECTED: rob_system's futures_system() includes optimisedPositions (dynamic-opt). The TRUE
UNROUNDED (fractional) ceiling needs the standard Account stage WITHOUT the opt stages. Here we
build the fractional system and progressively simplify toward Strategy 11 to isolate each factor:
  V0 full rob_system (all rules + vol attenuation)   <- true unrounded ceiling
  V1 no vol attenuation                              <- attenuation effect
  V2 trend+carry only (Strategy-11-like)             <- relative-value/skew rule effect
Plus period slices (full vs 1996-2021) on V0 to isolate the 2022-26 drought.
Fractional positions => capital-invariant; realized vol reflects deployment only."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
import pandas as pd
from systems.basesystem import System
from systems.accounts.accounts_stage import Account      # STANDARD fractional account (no opt)
from systems.forecasting import Rules
from systems.forecast_combine import ForecastCombine
from systems.forecast_scale_cap import ForecastScaleCap  # plain, NO vol attenuation
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
data = dbFuturesSimData()
VT = 20.0

# trend+carry-only rule set (approx Strategy 11): keep breakout/momentum/normmom/accel (trend) + carry
TREND_CARRY = [r for r in ["breakout10","breakout20","breakout40","breakout80","breakout160","breakout320",
    "momentum4","momentum8","momentum16","momentum32","momentum64","normmom2","normmom4","normmom8",
    "normmom16","normmom32","normmom64","accel16","accel32","accel64","carry10","carry30","carry60","carry125"]]


def build(scale_cap, simple_rules=False):
    config = Config("systems.provided.rob_system.config.yaml")
    config.percentage_vol_target = VT
    config.instrument_weights = {i: 1.0 / len(our) for i in our}
    config.use_instrument_weight_estimates = True
    if simple_rules:
        fw = config.forecast_weights
        newfw = {}
        for inst, w in (fw.items() if isinstance(fw, dict) else []):
            keep = {k: v for k, v in w.items() if k in TREND_CARRY}
            s = sum(keep.values()) or 1
            newfw[inst] = {k: v / s for k, v in keep.items()}
        config.forecast_weights = newfw
    return System([Account(), Portfolios(), PositionSizing(), myFuturesRawData(),
                   ForecastCombine(), scale_cap(), Rules()], data, config)


def rr(system):
    p = system.accounts.portfolio().percent
    raw = p.as_ts
    raw = raw() if callable(raw) else raw
    s = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
    return s


def rep(label, s):
    def m(x):
        return f"vol {x.std()*np.sqrt(256):.1f}% SR {x.mean()/x.std()*np.sqrt(256):.2f}"
    full = m(s); w21 = m(s.loc[:"2021-12-31"]); w0521 = m(s.loc["2005-01-01":"2021-12-31"])
    print(f"  {label:<34} FULL[{full}]  1996-2021[{w21}]  2005-2021[{w0521}]", flush=True)


print(f"GAP DECOMPOSITION: {len(our)} instruments, {VT}% target, FRACTIONAL (unrounded). "
      f"Rob AFTS Table128: ~20% vol, SR 1.06-1.22\n", flush=True)
print("V0 full rob_system (all rules + vol attenuation)...", flush=True)
rep("V0 full (atten, all rules)", rr(build(volAttenForecastScaleCap)))
print("V1 NO vol attenuation...", flush=True)
rep("V1 no attenuation", rr(build(ForecastScaleCap)))
print("V2 trend+carry only (Strategy-11-like), no atten...", flush=True)
rep("V2 trend+carry, no atten", rr(build(ForecastScaleCap, simple_rules=True)))
print("V3 trend+carry only, WITH atten...", flush=True)
rep("V3 trend+carry, atten", rr(build(volAttenForecastScaleCap, simple_rules=True)))
print("\nEach row: realized vol tells DEPLOYMENT; compare V0->V1 (atten effect), V1->V2 (rule effect),"
      "\nFULL vs 1996-2021 (2022-26 drought effect). Target = reach ~20% vol / SR ~1.1 like Rob.", flush=True)
