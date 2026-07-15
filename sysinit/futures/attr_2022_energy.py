"""Decompose our dm2.5 book over ROB'S 2021-22 tax year (Apr'21->Apr'05'22 -- his "year of energy",
+27%, oil/gas +21.7%). Question: were we even IN the energy trades, and why did our same-window return
land at -4.6% (raw) / -12.5% (vol-scaled)? Builds the production system, recovers optimised positions,
and computes per-instrument P&L + avg position over the window, grouped by asset class with ENERGY
called out. Saves positions + attribution for offline slicing. NOT production; read-only.
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
from sysinit.futures.csi_catalog_map import load_pst_index

W0, W1 = "2021-04-06", "2022-04-05"
OUT = "private/backtest_runs/attr_2022_energy"
os.makedirs(OUT, exist_ok=True)

config = Config("private.systems.rob_dynamic.config.yaml")   # dm2.5 production: $250k / 20% / est-IDM
print(f"Building dm2.5 production system for window {W0}..{W1} ...", flush=True)
system = System([Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
                 PositionSizing(), myFuturesRawData(), ForecastCombine(),
                 volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)

pos = system.optimisedPositions.get_optimised_position_df()
pos.to_parquet(os.path.join(OUT, "positions_full.parquet"))
pidx = load_pst_index()

rows = []
for code in pos.columns:
    try:
        p = pos[code]
        price = system.rawdata.get_daily_prices(code).reindex(p.index).ffill()
        block = float(system.data.get_value_of_block_price_move(code))
        try:
            fx = pd.Series(system.data.get_fx_for_instrument(code, "USD")).reindex(p.index).ffill()
        except Exception:
            fx = pd.Series(1.0, index=p.index)
        pnl = (p.shift(1) * price.diff() * block * fx).replace([np.inf, -np.inf], np.nan)
        pw = pnl.loc[W0:W1].sum()
        avg_pos = p.loc[W0:W1].mean()
        held = int((p.loc[W0:W1].abs() > 0).sum())
        rows.append(dict(instrument=code, asset=pidx.get(code, {}).get("asset_class", "?"),
                         pnl_k=round(float(pw) / 1000, 1), avg_pos=round(float(avg_pos), 2),
                         days_held=held))
    except Exception:
        continue

df = pd.DataFrame(rows).set_index("instrument")
df.to_csv(os.path.join(OUT, "attr_2022.csv"))
cap = 250000
tot = df.pnl_k.sum()
print(f"\n=== WINDOW P&L {W0}..{W1}  (total ${tot:.0f}k = {tot*1000/cap*100:.1f}% of ${cap/1000:.0f}k) ===", flush=True)

print("\n--- by ASSET CLASS (P&L $k) ---", flush=True)
byc = df.groupby("asset")["pnl_k"].sum().sort_values()
print(byc.to_string(), flush=True)

print("\n--- ENERGY / OIL-GAS instruments (Rob's +21.7% driver) ---", flush=True)
en = df[df.asset.astype(str).str.contains("Oil|Gas|Energy|OilGas|energy", case=False, na=False)]
if len(en) == 0:
    # fallback: known energy codes
    ecodes = ["CRUDE_W","BRENT-LAST","GAS-LAST","GAS-PEN","GAS_US_mini","GASOILINE","HEATOIL","EU-OIL","ETHANOL"]
    en = df[df.index.isin(ecodes)]
print(en.sort_values("pnl_k").to_string() if len(en) else "  (no energy instruments found held)", flush=True)
print(f"\n  energy total: ${en.pnl_k.sum():.0f}k ({en.pnl_k.sum()*1000/cap*100:+.1f}% of capital)", flush=True)

print("\n--- top winners / losers overall ($k) ---", flush=True)
print("winners:", df.sort_values("pnl_k", ascending=False).head(6)[["asset","pnl_k","avg_pos"]].to_string(), flush=True)
print("losers :", df.sort_values("pnl_k").head(6)[["asset","pnl_k","avg_pos"]].to_string(), flush=True)
print(f"\nsaved -> {OUT}/", flush=True)
