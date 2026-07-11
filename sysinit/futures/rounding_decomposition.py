"""Isolate how much of the vol shortfall is CONTRACT ROUNDING vs everything else.
The standard rob_system holds FRACTIONAL positions (no integer constraint) -> its realized
vol is the 'achievable without rounding' ceiling, capital-invariant. Compared against the
dynamic-opt (integer) realized vol from the saved capital sweep, the difference = rounding
cost. If the unrounded ceiling is well below the target, micros/capital can't help beyond it."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv, json
import numpy as np
import pandas as pd
from systems.provided.rob_system.run_system import futures_system  # STANDARD (fractional) rob_system
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

VOL_TARGET = float(os.environ.get("VOL_TARGET", 20))
system = futures_system()
system.config.percentage_vol_target = VOL_TARGET
system.config.instrument_weights = {i: 1.0 / len(our) for i in our}
system.config.use_instrument_weight_estimates = True
system.config.notional_trading_capital = 500000  # capital-invariant for fractional; comfortable value
print(f"UNROUNDED reference: standard rob_system, {len(our)} instruments, {VOL_TARGET}% target "
      f"(fractional positions, no integer constraint)", flush=True)
acc = system.accounts.portfolio()
p = acc.percent
unrounded_vol = float(p.ann_std())
unrounded_sr = float(p.sharpe())
print(f"\n  UNROUNDED realized vol: {unrounded_vol:.1f}%  (target {VOL_TARGET}%)  Sharpe {unrounded_sr:.2f}")
print(f"  -> deployment WITHOUT rounding = {unrounded_vol/VOL_TARGET*100:.0f}% of target\n")

# compare against saved dynamic-opt (integer) sweep runs at this vol target
print(f"=== ROUNDING DECOMPOSITION (vol target {VOL_TARGET}%) ===")
print(f"{'capital':>10}{'dynopt_vol':>12}{'unrounded':>11}{'rounding_cost':>15}{'% of gap':>10}")
runs = f"private/backtest_runs"
gap_total = VOL_TARGET - unrounded_vol
for cap in [110000, 300000, 500000, 1000000]:
    lbl = f"capsweep_vt{int(VOL_TARGET)}_{cap}"
    fp = os.path.join(runs, lbl, "stats.json")
    if not os.path.exists(fp):
        continue
    s = json.load(open(fp))
    rv = s["ann_vol_pct"]
    rounding_cost = unrounded_vol - rv
    total_short = VOL_TARGET - rv
    pct_rounding = rounding_cost / total_short * 100 if total_short else 0
    print(f"{cap:>10,}{rv:>11.1f}%{unrounded_vol:>10.1f}%{rounding_cost:>13.1f}pt{pct_rounding:>9.0f}%")
print(f"\nINTERPRETATION: of the {VOL_TARGET}%-target shortfall, the part from ROUNDING is "
      f"(unrounded - dynopt); the RESIDUAL ({VOL_TARGET:.0f}-{unrounded_vol:.1f}={gap_total:.1f}pt) is "
      f"forecast-strength/period/scaling and is NOT fixable by micros or capital.", flush=True)
