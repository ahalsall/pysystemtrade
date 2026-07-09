"""Vol-target sweep for the $110k dynamic-opt backtest: does a lower (or higher)
percentage_vol_target reduce the small-capital concentration? Reports funded-count
by asset class per target. Metrics from CURRENCY P&L (finite on empty-book days,
unlike .percent which -> inf at low capital). Env: CAPITAL, VOL_TARGETS."""
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

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
          if r and r[0] != "csi_symbol")
EXCLUDE = {"GAS_US_mini", "YENEUR", "FEEDCOW", "BRE", "US3", "GAS-LAST", "US-REALESTATE",
           "EPRA-EUROPE", "EU-TECH", "FTSECHINAH", "FTSEINDO", "OMX", "GBPEUR", "VNKI"}
CAPITAL = float(os.environ.get("CAPITAL", 110000))
targets = [float(x) for x in os.environ.get("VOL_TARGETS", "15,25,40").split(",")]
pidx = load_pst_index()
data = dbFuturesSimData()  # reused across targets so prices stay cached

_c0 = Config("systems.provided.rob_system.config.yaml")
cfg_inst = set(_c0.instrument_weights.keys())
our = sorted((csi & data_inst & cfg_inst) - EXCLUDE)
w = 1.0 / len(our)
print(f"universe: {len(our)} instruments | capital ${CAPITAL:,.0f}\n", flush=True)


def clean_metrics(acc):
    """Sharpe (scale-free) + max DD %, from currency P&L (finite on 0-position days).
    acc.as_ts is a PROPERTY (Series), not a method; acc is base-currency (acc.percent
    is what divides by capital -> inf at low capital)."""
    raw = acc.as_ts
    raw = raw() if callable(raw) else raw
    ts = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
    if len(ts) < 50:
        return None
    daily = ts if ts.abs().max() < 5 * ts.diff().abs().max() else ts.diff().dropna()
    daily = daily[np.isfinite(daily)]
    mu, sd = daily.mean(), daily.std()
    sharpe = (mu / sd) * np.sqrt(256) if sd else float("nan")
    cum = daily.cumsum()
    dd = (cum - cum.cummax())
    maxdd_pct = dd.min() / CAPITAL * 100
    ann_ccy = mu * 256
    return dict(sharpe=sharpe, ann_pct=ann_ccy / CAPITAL * 100,
                vol_pct=sd * np.sqrt(256) / CAPITAL * 100, maxdd_pct=maxdd_pct,
                skew=daily.skew(), start=ts.index[0].date(), end=ts.index[-1].date())


rows = []
for vt in targets:
    config = Config("systems.provided.rob_system.config.yaml")
    config.notional_trading_capital = CAPITAL
    config.percentage_vol_target = vt
    config.instrument_weights = {i: w for i in our}
    config.use_instrument_weight_estimates = False
    system = System(
        [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
         PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
        data, config,
    )
    print(f"===== vol target {vt}% (heavy)... =====", flush=True)
    try:
        acc = system.accounts.portfolio()
        m = clean_metrics(acc)
    except Exception as e:
        import traceback; traceback.print_exc(); m = None
    pos = system.optimisedPositions.get_optimised_position_df()
    ever = (pos.abs() > 0).sum()
    funded = sorted(ever[ever > 0].index.tolist())
    aheld = Counter(pidx.get(i, {}).get("asset_class", "?") for i in funded)
    aall = Counter(pidx.get(i, {}).get("asset_class", "?") for i in our)
    ms = (f"Sharpe {m['sharpe']:.2f} | ann {m['ann_pct']:.1f}% | vol {m['vol_pct']:.1f}% | "
          f"maxDD {m['maxdd_pct']:.1f}% | {m['start']}..{m['end']}") if m else "metrics n/a"
    print(f"  funded {len(funded)}/{len(our)}  |  {ms}", flush=True)
    print("  by asset:", {a: f"{aheld.get(a,0)}/{aall[a]}" for a in sorted(aall)}, flush=True)
    print("  funded:", funded, flush=True)
    rows.append(dict(vol_target=vt, funded=len(funded),
                     **({f"sharpe": round(m["sharpe"], 2), "ann_pct": round(m["ann_pct"], 1),
                         "vol_pct": round(m["vol_pct"], 1), "maxdd_pct": round(m["maxdd_pct"], 1)} if m else {})))

print("\n=== SWEEP SUMMARY ===")
print(pd.DataFrame(rows).to_string(index=False))
pd.DataFrame(rows).to_csv("/home/andrew/pysystemtrade/private/dynopt_voltarget_sweep.csv", index=False)
print("saved -> private/dynopt_voltarget_sweep.csv")
