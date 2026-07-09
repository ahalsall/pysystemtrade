"""Drawdown attribution for the TRUSTWORTHY estimated-weights book (post CSI-only
cutover). Auto-detects the worst peak-to-trough window on the portfolio curve, then
attributes per-instrument optimised P&L (currency) over that window + full period +
the 2021-25 trend-drought window. Aggregates by asset class. Deflator bug is fixed,
so pandl_for_optimised_instrument is clean now. Env: CAPITAL (110000), ESTIMATED (1)."""
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
STALE_DAYS = int(os.environ.get("STALE_DAYS", 45))
_cands = (csi & data_inst & cfg_inst)
_simd = dbFuturesSimData()
_last = {}
for _c in _cands:
    try:
        _last[_c] = pd.Timestamp(_simd.get_raw_price(_c).dropna().index[-1].date())
    except Exception:
        _last[_c] = pd.Timestamp("1900-01-01")
_fresh = max(_last.values())
our = sorted(c for c in _cands if (_fresh - _last[c]).days <= STALE_DAYS)
config.notional_trading_capital = CAPITAL
config.instrument_weights = {i: 1.0 / len(our) for i in our}
config.use_instrument_weight_estimates = os.environ.get("ESTIMATED", "1").strip().lower() in ("1", "true", "yes")
system = System(
    [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
     PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
    dbFuturesSimData(), config,
)
pidx = load_pst_index()

def ts(acc):
    raw = acc.as_ts
    raw = raw() if callable(raw) else raw
    return pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()

print(f"universe {len(our)} | capital ${CAPITAL:,.0f} | estimated={config.use_instrument_weight_estimates}", flush=True)
port = ts(system.accounts.portfolio())
cum = port.cumsum()
dd = cum - cum.cummax()
trough = dd.idxmin()
peak = cum.loc[:trough].idxmax()
rec = cum.loc[trough:]
recov = rec[rec >= cum.loc[peak]]
print(f"\nWORST DRAWDOWN: {dd.min()/CAPITAL*100:.1f}%  ({peak.date()} -> {trough.date()}"
      f"{' -> recovered '+str(recov.index[0].date()) if len(recov) else ' -> NOT recovered'})", flush=True)

WINDOWS = {"worstDD": (peak, trough), "full": (None, None),
           "y2021_25": (pd.Timestamp("2021-06-08"), pd.Timestamp("2025-04-11"))}
rows = []
for i, code in enumerate(our):
    try:
        s = ts(system.accounts.pandl_for_optimised_instrument(code))
    except Exception:
        continue
    rec = {"instrument": code, "asset": pidx.get(code, {}).get("asset_class", "?")}
    for name, (a, b) in WINDOWS.items():
        seg = s
        if a is not None: seg = seg.loc[a:]
        if b is not None: seg = seg.loc[:b]
        rec[name] = float(seg.sum())
    rows.append(rec)
    if (i + 1) % 25 == 0:
        print(f"  ...{i+1}/{len(our)}", flush=True)

df = pd.DataFrame(rows).set_index("instrument")
for c in ["worstDD", "full", "y2021_25"]:
    df[c] = df[c] / 1000.0  # $000s
df.to_csv("private/dynopt_attribution.csv")
pd.set_option("display.width", 130)
print(f"\ntotals ($000s): worstDD={df['worstDD'].sum():.0f}  full={df['full'].sum():.0f}  2021-25={df['y2021_25'].sum():.0f}")
print("\n=== by ASSET CLASS ($000s) ===")
print(df.groupby("asset")[["worstDD", "y2021_25", "full"]].sum().sort_values("worstDD").round(0).to_string())
print("\n=== WORST 15 instruments into the worst-DD window ($000s) ===")
print(df.sort_values("worstDD")[["asset", "worstDD", "y2021_25", "full"]].head(15).round(1).to_string())
print("\n=== BEST 8 over the worst-DD window ===")
print(df.sort_values("worstDD", ascending=False)[["asset", "worstDD", "full"]].head(8).round(1).to_string())
print("\nsaved -> private/dynopt_attribution.csv", flush=True)
