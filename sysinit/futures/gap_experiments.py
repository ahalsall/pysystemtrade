"""Curiosity experiments on the two deployment levers, full stats, fractional rob_system:
  BASE  20% target, IDM cap 2.5  (the audited baseline: ~15.2% / SR 0.92)
  EXP1  26% target, IDM cap 2.5  (predict ~20% realized -- raising target scales the whole chain)
  EXP2  20% target, IDM cap REMOVED (dm_max=100) (uncaps the diversification the book actually has)
  EXP3  26% target, IDM cap removed (both levers, for reference)
Fractional => capital-invariant; realized vol = deployment. Reports full percent-based stats so we
see what each lever does to Sharpe / drawdown / skew, not just vol."""
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


def build(target, dm_max):
    config = Config("systems.provided.rob_system.config.yaml")
    config.percentage_vol_target = target
    config.instrument_weights = {i: 1.0 / len(our) for i in our}
    config.use_instrument_weight_estimates = True
    # IDM-estimate params live in system defaults (absent on a fresh Config); set the full block.
    config.instrument_div_mult_estimate = {
        "func": "sysquant.estimators.diversification_multipliers.diversification_multiplier_from_list",
        "ewma_span": 125, "dm_max": dm_max}
    return System([Account(), Portfolios(), PositionSizing(), myFuturesRawData(),
                   ForecastCombine(), volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)


def stats(label, target, dm_max):
    system = build(target, dm_max)
    p = system.accounts.portfolio().percent
    idm = system.portfolio.get_instrument_diversification_multiplier()
    raw = p.as_ts
    raw = raw() if callable(raw) else raw
    # NOTE: .percent returns are ALREADY in percent units (0.5% day -> 0.5), so NO extra x100.
    r = pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()
    # persist the daily return path so future DD/stat questions don't need a rebuild
    os.makedirs("private/gap_curves", exist_ok=True)
    r.to_csv(f"private/gap_curves/{label.split()[0]}.csv", header=["daily_pct_return"])
    def sr(x): return x.mean() / x.std() * np.sqrt(256)
    # additive (arithmetic) DD = pysystemtrade native: cumsum of % returns minus running peak
    dd = (r.cumsum() - r.cumsum().cummax())
    # compounded (geometric) DD = peak-to-trough of the reinvested equity curve, bounded at -100%
    eq = (1.0 + r / 100.0).cumprod()
    cdd = (eq / eq.cummax() - 1.0) * 100.0
    out = dict(
        label=label, target=target, dm_max=dm_max,
        ann_ret=r.mean() * 256, vol=r.std() * np.sqrt(256), sharpe=sr(r),
        maxDD=float(dd.min()), compDD=float(cdd.min()), timeInDD=float((dd < 0).mean()) * 100,
        skew=float(r.skew()), sr9621=sr(r.loc[:"2021-12-31"]),
        vol9621=r.loc[:"2021-12-31"].std() * np.sqrt(256),
        idm_last=float(idm.iloc[-1]), idm_mean=float(idm.mean()))
    print(f"  {label:<24} done: vol {out['vol']:.1f}% SR {out['sharpe']:.2f} IDM {out['idm_last']:.2f}", flush=True)
    return out


print(f"GAP EXPERIMENTS: {len(our)} instruments, fractional, full stats\n", flush=True)
rows = [stats("BASE 20% / cap 2.5", 20.0, 2.5),
        stats("EXP1 26% / cap 2.5", 26.0, 2.5),
        stats("EXP2 20% / NO cap", 20.0, 100.0),
        stats("EXP3 26% / NO cap", 26.0, 100.0)]
df = pd.DataFrame(rows)
print("\n" + "=" * 112)
print(f"{'scenario':<22}{'vol%':>7}{'annRet%':>9}{'Sharpe':>8}{'addDD%':>8}{'compDD%':>9}{'inDD%':>7}"
      f"{'skew':>7}{'IDM':>6}{'SR9621':>8}")
print("-" * 112)
for _, x in df.iterrows():
    print(f"{x['label']:<22}{x['vol']:>7.1f}{x['ann_ret']:>9.1f}{x['sharpe']:>8.2f}{x['maxDD']:>8.1f}"
          f"{x['compDD']:>9.1f}{x['timeInDD']:>7.0f}{x['skew']:>7.2f}{x['idm_last']:>6.2f}{x['sr9621']:>8.2f}")
print("=" * 112)
print("addDD = additive/arithmetic DD (pysystemtrade native, cumulative %-return path); "
      "compDD = compounded equity DD (bounded -100%).", flush=True)
print("Rob AFTS Table128 ref: ~18.8-21.1% vol, SR 1.06-1.22.", flush=True)
df.to_csv("private/gap_experiments.csv", index=False)
print("saved -> private/gap_experiments.csv", flush=True)
