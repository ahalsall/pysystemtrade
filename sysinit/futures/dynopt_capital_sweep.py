"""Capital sweep for the TRUSTWORTHY estimated-weights book (clean CSI, single source).
Loops capital levels, reports Sharpe / ann / REALIZED-vs-TARGET vol / maxDD / funded count.
The headline is realized vol converging toward the 20% target (AFTS) as capital rises — i.e. the
small-capital integer-lumpiness under-investment quantified. Env: VOL_TARGETS unused;
CAPITALS (comma list, default 110000,300000,500000,1000000)."""
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
from sysinit.futures.backtest_results import full_stats, save_run

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
          if r and r[0] != "csi_symbol")
cfg_inst = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
data = dbFuturesSimData()  # reused across capitals (prices cached)
cands = csi & data_inst & cfg_inst
# Tradeability = the CURRENT PRICED CONTRACT has current data (multiple-prices PRICE last-real date).
# This catches dead instruments AND roll-stuck ones (e.g. the 28 sector indices whose adjusted price
# extends via forward-fill but whose priced contract expired) -- get_raw_price/adjusted would miss the latter.
last = {}
for c in cands:
    try:
        mp = dp.db_futures_multiple_prices_data.get_multiple_prices(c)
        last[c] = pd.Timestamp(mp["PRICE"].dropna().index[-1].date())
    except Exception:
        last[c] = pd.Timestamp("1900-01-01")
fresh = max(last.values())
STALE_DAYS = int(os.environ.get("STALE_DAYS", 15))  # priced-contract data age; 15 excludes stuck-roll instruments
our = sorted(c for c in cands if (fresh - last[c]).days <= STALE_DAYS)
w = 1.0 / len(our)
pidx = load_pst_index()
CAPITALS = [float(x) for x in os.environ.get("CAPITALS", "110000,300000,500000,1000000").split(",")]
# VOL_TARGET default 20% to match AFTS Strategy 25 (Rob uses a 20% risk target in the
# book; our rob_system config default is 25%). Set VOL_TARGET=25 to revert.
VOL_TARGET = float(os.environ.get("VOL_TARGET", 20))
print(f"universe {len(our)} clean instruments (of {len(cands)}) | estimated weights | "
      f"vol target {VOL_TARGET:.0f}% (AFTS uses 20%)\n", flush=True)


def fast_attribution(system, our, acc, pos, capital, outdir):
    """Position x return drawdown attribution over the auto-detected worst-DD window.
    Reuses the built system + already-computed optimised positions (NO optimiser re-run,
    so it can't hang like pandl_for_optimised_instrument did at $500k). Vectorised per
    instrument, per-instrument try/except. Saves attribution.csv + positions.parquet
    (raw material to slice ANY window offline). Relative ranking is robust; absolute $
    approximate (back-adj roll gaps). Returns a summary dict."""
    raw = acc.as_ts
    raw = raw() if callable(raw) else raw
    port = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
    cum = port.cumsum(); dd = cum - cum.cummax()
    trough = dd.idxmin(); peak = cum.loc[:trough].idxmax()
    rows = []
    for code in our:
        try:
            p = pos[code].dropna()
            if p.abs().sum() == 0:
                continue
            price = system.rawdata.get_daily_prices(code).reindex(p.index).ffill()
            block = float(system.data.get_value_of_block_price_move(code))
            try:
                fx = pd.Series(system.data.get_fx_for_instrument(code, "USD")).reindex(p.index).ffill()
            except Exception:
                fx = pd.Series(1.0, index=p.index)
            pnl = (p.shift(1) * price.diff() * block * fx).replace([np.inf, -np.inf], np.nan).dropna()
            rows.append(dict(instrument=code, asset=pidx.get(code, {}).get("asset_class", "?"),
                             worstDD_k=round(float(pnl.loc[peak:trough].sum()) / 1000, 1),
                             full_k=round(float(pnl.sum()) / 1000, 1)))
        except Exception:
            continue
    adf = pd.DataFrame(rows).set_index("instrument")
    adf.to_csv(os.path.join(outdir, "attribution.csv"))
    try:
        pos.to_parquet(os.path.join(outdir, "positions.parquet"))
    except Exception:
        pos.to_csv(os.path.join(outdir, "positions.csv"))
    losers = adf.sort_values("worstDD_k").head(6)
    return dict(dd_peak=str(peak.date()), dd_trough=str(trough.date()),
                dd_pct=round(float(dd.min() / capital * 100), 1),
                by_asset=adf.groupby("asset")["worstDD_k"].sum().round(0).to_dict(),
                top_losers=list(losers.index))


rows = []
for cap in CAPITALS:
    config = Config("systems.provided.rob_system.config.yaml")
    config.notional_trading_capital = cap
    config.percentage_vol_target = VOL_TARGET
    config.instrument_weights = {i: w for i in our}
    config.use_instrument_weight_estimates = True
    system = System(
        [Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
         PositionSizing(), myFuturesRawData(), ForecastCombine(), volAttenForecastScaleCap(), Rules()],
        data, config,
    )
    print(f"===== capital ${cap:,.0f} (heavy)... =====", flush=True)
    acc = system.accounts.portfolio()
    pos = system.optimisedPositions.get_optimised_position_df()
    funded = int(((pos.abs() > 0).sum() > 0).sum())
    held_last = int((pos.iloc[-1].abs() > 0).sum())
    stats = full_stats(acc, cap, extra=dict(vol_target=VOL_TARGET, funded=funded,
                                            held_last=held_last, universe=len(our),
                                            weights="estimated"))
    outdir = save_run(f"capsweep_vt{int(VOL_TARGET)}_{int(cap)}", acc, cap, stats)  # curve+stats
    print(f"  Sharpe {stats['sharpe']:.2f} | ann {stats['ann_return_pct']:.1f}% | "
          f"REALIZED vol {stats['ann_vol_pct']:.1f}% (target {VOL_TARGET:.0f}%) | maxDD {stats['max_dd_pct']:.1f}% | "
          f"AVG DD {stats['avg_dd_pct']:.1f}% | skew {stats['skew']:.2f} | "
          f"funded {funded}/{len(our)} | held today {held_last}  -> {outdir}", flush=True)
    try:
        att = fast_attribution(system, our, acc, pos, cap, outdir)
        print(f"  attribution: worstDD {att['dd_pct']}% [{att['dd_peak']}..{att['dd_trough']}] "
              f"by-asset {att['by_asset']} | top losers {att['top_losers']}", flush=True)
    except Exception as e:
        print(f"  (attribution skipped: {type(e).__name__}: {e})", flush=True)
    rows.append(stats)

print(f"\n=== CAPITAL SWEEP SUMMARY (clean CSI, estimated weights, {VOL_TARGET:.0f}% target) ===")
cols = ["capital", "sharpe", "ann_return_pct", "ann_vol_pct", "max_dd_pct", "avg_dd_pct",
        "time_in_dd_pct", "skew", "funded", "held_last"]
print(pd.DataFrame(rows)[cols].to_string(index=False))
pd.DataFrame(rows).to_csv("/home/andrew/pysystemtrade/private/dynopt_capital_sweep.csv", index=False)
print("saved -> private/dynopt_capital_sweep.csv  (+ per-capital curves in private/backtest_runs/)")
