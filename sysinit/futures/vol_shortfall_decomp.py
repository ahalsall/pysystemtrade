"""Decompose the achieved-vs-target VOL SHORTFALL of the production system.

Puzzle: fractional (no rounding, no optimiser) the rob_dynamic system targets 20% but realises
~15% -- and uncapping the IDM barely helps (2.50->2.84, 15.2->15.5%). So the cap is NOT the cause.
Hypothesis: subsystems OVER-realise (~23%), but the diversification-multiplier estimator prices
forward correlation conservatively (crisis-aware), so IDM sits below the level that would hit target
-> chronic under-realisation. This script tests that directly.

Builds the STANDARD (non-dynamic-opt) rob_dynamic system = the fractional notional portfolio (the clean
15.2% number). Extracts, for the funded universe:
  - portfolio fractional vol  V_p                         (target = 20%)
  - per-instrument subsystem vols  s_i  (avg)
  - the PRE-IDM weighted-subsystem portfolio vol  V_raw   -> realised diversification factor
  - the estimated IDM (latest + 30y mean)  vs  the VOL-HITTING IDM = target / V_raw
  - estimator-implied vs realised diversification factor  (the smoking gun)
  - realised average pairwise subsystem correlation
Then a multiplicative attribution  target -> V_p.

Read-heavy backtest; writes private/backtest_runs/vol_decomp/summary.json. No orders, read-only.

Usage:  uv run python -m sysinit.futures.vol_shortfall_decomp
"""
import os
os.environ["MPLBACKEND"] = "Agg"
os.environ.setdefault("TZ", "UTC")
import json
import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from systems.basesystem import System
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.forecast_combine import ForecastCombine
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import volAttenForecastScaleCap
from systems.forecasting import Rules
from systems.accounts.accounts_stage import Account
from sysdata.sim.db_futures_sim_data import dbFuturesSimData

BDAYS = 256
OUTDIR = "private/backtest_runs/vol_decomp"


def ann_vol(daily_pct: pd.Series) -> float:
    return float(daily_pct.std() * np.sqrt(BDAYS))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    config = Config("private.systems.rob_dynamic.config.yaml")
    VOL = float(config.percentage_vol_target)
    print(f"Building STANDARD (fractional, no dyn-opt) rob_dynamic: {VOL:.0f}% target, "
          f"{len(config.instrument_weights)} instruments", flush=True)
    system = System([Account(), Portfolios(), PositionSizing(), myFuturesRawData(),
                     ForecastCombine(), volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)

    insts = system.get_instrument_list()

    # ---- IDM (estimated) time series ----
    idm = system.portfolio.get_instrument_diversification_multiplier().dropna()
    idm_latest, idm_mean = float(idm.iloc[-1]), float(idm.mean())

    # ---- fixed instrument weights (Rob's fit), renormalised to sum 1 (framework does this) ----
    raw_w = {k: float(v) for k, v in config.instrument_weights.items() if k in insts}
    wsum = sum(raw_w.values())
    w = {k: v / wsum for k, v in raw_w.items()}

    # ---- portfolio fractional % returns (with weights + IDM) ----
    print("[curve] portfolio account (heavy)...", flush=True)
    port = system.accounts.portfolio().percent
    port = pd.Series(port).replace([np.inf, -np.inf], np.nan).dropna()
    V_p = ann_vol(port)

    # ---- per-instrument SUBSYSTEM % returns (unweighted, each ~sized to target alone) ----
    print(f"[subsystems] {len(insts)} subsystem curves (heavy)...", flush=True)
    ss = {}
    for i, code in enumerate(insts):
        try:
            r = system.accounts.pandl_for_subsystem(code).percent
            r = pd.Series(r).replace([np.inf, -np.inf], np.nan).dropna()
            if len(r) > 250:
                ss[code] = r
        except Exception as e:
            print(f"  {code}: subsystem err {type(e).__name__}", flush=True)
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(insts)}", flush=True)
    SS = pd.DataFrame(ss)  # T x N daily % returns
    funded = list(SS.columns)
    s_i = {c: ann_vol(SS[c]) for c in funded}
    avg_sub_vol = float(np.mean(list(s_i.values())))

    # weighted-avg subsystem vol and PRE-IDM weighted portfolio (no IDM)
    wv = pd.Series({c: w.get(c, 0.0) for c in funded})
    wv = wv / wv.sum()
    weighted_avg_sub_vol = float((wv * pd.Series(s_i)).sum())
    pre_idm_ret = (SS[funded] * wv).sum(axis=1).dropna()
    V_raw = ann_vol(pre_idm_ret)

    # realised diversification factor = sqrt(w' C_realised w) ; estimator-implied = 1/IDM
    realised_div = V_raw / weighted_avg_sub_vol
    est_div_latest = 1.0 / idm_latest
    est_div_mean = 1.0 / idm_mean
    vol_hitting_idm = VOL / V_raw            # IDM that would make portfolio vol = target
    idm_effective = V_p / V_raw              # IDM actually realised in the portfolio curve

    # realised average pairwise correlation of subsystem returns
    C = SS[funded].corr()
    off = C.values[np.triu_indices_from(C.values, k=1)]
    realised_avg_corr = float(np.nanmean(off))

    res = dict(
        vol_target_pct=round(VOL, 1),
        portfolio_vol_pct=round(V_p, 1),
        realisation_ratio=round(V_p / VOL, 3),
        avg_subsystem_vol_pct=round(avg_sub_vol, 1),
        weighted_avg_subsystem_vol_pct=round(weighted_avg_sub_vol, 1),
        pre_idm_portfolio_vol_pct=round(V_raw, 1),
        realised_div_factor=round(realised_div, 3),
        estimator_div_factor_latest=round(est_div_latest, 3),
        estimator_div_factor_mean=round(est_div_mean, 3),
        idm_estimated_latest=round(idm_latest, 3),
        idm_estimated_mean_30y=round(idm_mean, 3),
        idm_effective_realised=round(idm_effective, 3),
        idm_vol_hitting=round(vol_hitting_idm, 3),
        realised_avg_pairwise_corr=round(realised_avg_corr, 3),
        n_funded=len(funded),
    )
    json.dump(res, open(os.path.join(OUTDIR, "summary.json"), "w"), indent=2)

    print("\n" + "=" * 78)
    print("VOL SHORTFALL DECOMPOSITION (fractional, standard portfolio)")
    print("=" * 78)
    print(f"  vol TARGET                         {VOL:.1f}%")
    print(f"  portfolio realised vol  V_p        {V_p:.1f}%   -> realisation {V_p/VOL:.0%} of target")
    print(f"  avg subsystem vol (per-inst alone) {avg_sub_vol:.1f}%   (weighted {weighted_avg_sub_vol:.1f}%)")
    print(f"     -> subsystems {'OVER' if weighted_avg_sub_vol>VOL else 'UNDER'}-realise vs target"
          f" ({weighted_avg_sub_vol/VOL:.0%})  => shortfall is at the PORTFOLIO level, not per-instrument")
    print(f"  pre-IDM weighted portfolio  V_raw  {V_raw:.1f}%")
    print(f"  realised diversification factor    {realised_div:.3f}   (= V_raw / weighted subsystem vol)")
    print("-" * 78)
    print(f"  IDM estimated  latest {idm_latest:.2f} / 30y-mean {idm_mean:.2f} / effective {idm_effective:.2f}")
    print(f"  IDM VOL-HITTING (target/V_raw)     {vol_hitting_idm:.2f}   <- needed to realise {VOL:.0f}%")
    print(f"     -> IDM deficit: estimator ~{idm_mean:.2f} vs vol-hitting ~{vol_hitting_idm:.2f}"
          f"  ({idm_mean/vol_hitting_idm:.0%})")
    print("-" * 78)
    print(f"  SMOKING GUN -- diversification factor the estimator uses vs realised:")
    print(f"     estimator-implied (1/IDM)  latest {est_div_latest:.3f} / mean {est_div_mean:.3f}")
    print(f"     realised (from subsystem returns) {realised_div:.3f}")
    verdict = ("estimator prices MORE correlation than realised -> IDM too low -> vol suppressed"
               if est_div_mean > realised_div else
               "estimator ~ realised -> IDM not the cause; look elsewhere")
    print(f"     => {verdict}")
    print(f"  realised avg pairwise subsystem correlation {realised_avg_corr:.3f}  ({len(funded)} funded)")
    print(f"\nsaved -> {OUTDIR}/summary.json", flush=True)


if __name__ == "__main__":
    main()
