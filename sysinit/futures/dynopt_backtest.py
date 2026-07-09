"""Dynamic-opt backtest on our CSI deep-history instruments (rob_system template).
Capital via env CAPITAL (default 110000 = Andrew's ~CAD150k in USD)."""
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
# DYNAMIC STALENESS GUARD (post CSI-only cutover): exclude any instrument whose raw
# price ends >STALE_DAYS before the freshest instrument. Auto-handles the 17 truncated
# series (OMX 1996, GBPEUR/BRE 2000, US3 2010, ...) whose CSI data genuinely ends early,
# WITHOUT a hardcoded list, and future-proofs against silent staleness. The 4 old
# deflator-breakers (CORN/CRUDE_W/SOYBEAN/WHEAT) are now FRESH and included.
STALE_DAYS = int(os.environ.get("STALE_DAYS", 45))
_cands = (csi & data_inst & cfg_inst)
_simd = dbFuturesSimData()
_last = {}
for _c in _cands:
    try:
        _last[_c] = pd.Timestamp(_simd.get_raw_price(_c).dropna().index[-1].date())
    except Exception:
        _last[_c] = pd.Timestamp("1900-01-01")
_fresh_end = max(_last.values())
STALE = {c for c, d in _last.items() if (_fresh_end - d).days > STALE_DAYS}
# SELECTION env (comma list) overrides the universe with a static-selected set.
_sel = os.environ.get("SELECTION", "").strip()
if _sel:
    our = sorted((set(c.strip() for c in _sel.split(",")) & _cands) - STALE)
    src = f"SELECTION ({len(our)})"
else:
    our = sorted(_cands - STALE)
    src = f"full universe ({len(our)})"
CAPITAL = float(os.environ.get("CAPITAL", 110000))
config.notional_trading_capital = CAPITAL
# ESTIMATED=1 -> canonical correlation-aware handcrafted instrument weights (Rob's mode);
# else equal 1/N. Either way the dict KEYS define the universe (_get_raw_instrument_list_
# from_config reads instrument_weights.keys()); the VALUES are used only in fixed mode.
_estimated = os.environ.get("ESTIMATED", "").strip().lower() in ("1", "true", "yes")
w = 1.0 / len(our)
config.instrument_weights = {i: w for i in our}
config.use_instrument_weight_estimates = _estimated
print(f"BACKTEST universe: {src} | capital ${CAPITAL:,.0f} | "
      f"vol target {config.percentage_vol_target}% | weights: "
      f"{'ESTIMATED (handcrafted)' if _estimated else 'equal 1/N'}")

system = System(
    [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
     PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
    dbFuturesSimData(), config,
)
print("Running dynamic-opt account curve (this is the heavy part)...", flush=True)
acc = system.accounts.portfolio()
# CURRENCY P&L (acc.as_ts is a PROPERTY/Series; acc.percent divides by capital -> inf
# on empty-book days at low capital). Sharpe is scale-free; DD/return as % of capital.
import numpy as np
raw = acc.as_ts
raw = raw() if callable(raw) else raw
daily = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
mu, sd = daily.mean(), daily.std()
sharpe = (mu / sd) * np.sqrt(256) if sd else float("nan")
cum = daily.cumsum()
dd = cum - cum.cummax()
print("\n=== DYNAMIC-OPT BACKTEST RESULTS ===", flush=True)
print(f"  Sharpe:       {sharpe:.2f}")
print(f"  Ann return:   {mu * 256 / CAPITAL * 100:.1f}%")
print(f"  Ann vol:      {sd * np.sqrt(256) / CAPITAL * 100:.1f}%")
print(f"  Skew:         {daily.skew():.2f}")
print(f"  Max drawdown: {dd.min() / CAPITAL * 100:.1f}%   (currency ${dd.min():,.0f})")
print(f"  Period:       {daily.index[0].date()} -> {daily.index[-1].date()}")
(cum / CAPITAL * 100).to_csv("/home/andrew/pysystemtrade/private/dynopt_backtest_curve.csv")
print("  saved cumulative %-of-capital curve -> private/dynopt_backtest_curve.csv")
try:
    from sysinit.futures.backtest_results import save_run, full_stats
    _lbl = os.environ.get("RUN_LABEL",
                          f"dynopt_{'est' if _estimated else 'eq'}_{int(CAPITAL)}")
    save_run(_lbl, acc, CAPITAL, full_stats(acc, CAPITAL, extra=dict(
        universe=len(our), weights="estimated" if _estimated else "equal",
        vol_target=float(config.percentage_vol_target))))
    print(f"  persisted full curve+stats -> private/backtest_runs/{_lbl}/")
except Exception as e:
    print(f"  (save_run skipped: {type(e).__name__}: {e})")
# dynamic-opt sparsity + AFFORDABILITY: which instruments does the optimiser ever fund
# at this capital, and which asset classes drop out entirely (-> micro shopping list)?
try:
    from sysinit.futures.csi_catalog_map import load_pst_index
    pidx = load_pst_index()
    pos = system.optimisedPositions.get_optimised_position_df()
    ever = (pos.abs() > 0).sum()
    ever_held = sorted(ever[ever > 0].index.tolist())
    last_held = sorted(pos.iloc[-1][pos.iloc[-1].abs() > 0].index.tolist())
    print(f"\n  === AFFORDABILITY at ${CAPITAL:,.0f} ===")
    print(f"  ever funded: {len(ever_held)} of {len(our)}   |   held on last date: {len(last_held)}")
    from collections import Counter
    aheld = Counter(pidx.get(i, {}).get("asset_class", "?") for i in ever_held)
    aall = Counter(pidx.get(i, {}).get("asset_class", "?") for i in our)
    print("  by asset class (funded / in-universe):")
    for a in sorted(aall):
        print(f"    {a:<14} {aheld.get(a,0):>2} / {aall[a]:<2}"
              + ("   <-- ZERO funded (needs micros)" if aheld.get(a, 0) == 0 else ""))
    print(f"  ever-funded instruments: {ever_held}")
    with open("/home/andrew/pysystemtrade/private/dynopt_held_110k.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["instrument", "asset", "days_held", "held_last"])
        for i in our:
            wr.writerow([i, pidx.get(i, {}).get("asset_class", "?"),
                         int(ever.get(i, 0)), int(i in last_held)])
    print("  saved -> private/dynopt_held_110k.csv")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"  (affordability analysis skipped: {type(e).__name__})")
