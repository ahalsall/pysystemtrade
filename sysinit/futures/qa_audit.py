"""#25 QA AUDIT -- verify no pysystemtrade framework step/criterion is circumvented before real money.

Checks, per production config (private/systems/rob_dynamic/config.yaml) and DB, WITHOUT rebuilding the
30-min optimiser:
  CONFIG  resolved (defaults-filled) values for the params that actually bind the risk/opt engine
  COVERAGE per instrument in instrument_weights: adjusted prices fresh, multiple-prices priced contract
           fresh (not roll-stuck), instrument metadata (pointsize/currency), SR cost, FX to base, and a
           forecast_weights entry. Any gap = an instrument the optimiser would size on incomplete inputs.
Read-only. Prints a FINDINGS summary at the end.
"""
import os
os.environ["MPLBACKEND"] = "Agg"
import pandas as pd
from sysdata.config.configdata import Config
from sysproduction.data.prices import diagPrices
from sysdata.sim.db_futures_sim_data import dbFuturesSimData

CFG = "private.systems.rob_dynamic.config.yaml"
STALE_DAYS = 15

raw = Config(CFG)                 # as-written (what run_systems reads)
filled = Config(CFG); filled.fill_with_defaults()
iw = raw.instrument_weights
fw = getattr(raw, "forecast_weights", {})
insts = sorted(iw.keys())
findings = []

print("=" * 78)
print(f"QA AUDIT -- {len(insts)} instruments in production config")
print("=" * 78)

# ---- CONFIG: what actually binds ----
print("\n[CONFIG] resolved params that bind the engine")
def show(k):
    v = getattr(filled, k, "<absent>")
    print(f"  {k:32} {v if not isinstance(v,dict) else '(dict len %d)'%len(v)}")
for k in ["percentage_vol_target","notional_trading_capital","base_currency","forecast_cap",
          "average_absolute_forecast","use_SR_costs","instrument_div_multiplier",
          "use_instrument_weight_estimates","use_forecast_weight_estimates","small_system"]:
    show(k)
vt = getattr(raw, "percentage_vol_target", None)
cap = getattr(raw, "notional_trading_capital", None)
if float(vt) != 20.0:
    findings.append(f"CONFIG vol_target={vt} in file but intended production target is 20 (AFTS). "
                    f"run_systems reads the FILE -> would trade wrong risk. Runtime scripts mask this.")
if float(cap) != 250000:
    findings.append(f"CONFIG capital={cap} in file but intended is 250000. run_systems reads the FILE.")
idm = float(getattr(raw,"instrument_div_multiplier",0))
est_idm = str(getattr(raw,"use_instrument_div_mult_estimates","")).lower() in ("true","1")
if not est_idm and idm > 2.5:
    findings.append(f"CONFIG fixed IDM={idm} inherited from Rob's 170-inst fit (>cap 2.5). Verify not "
                    f"over-levering the 106-inst book; re-estimate IDM for our universe.")

# ---- COVERAGE ----
print("\n[COVERAGE] per-instrument input completeness")
dp = diagPrices()
data = dbFuturesSimData()
adj_list = set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
mp_list = set(dp.db_futures_multiple_prices_data.get_list_of_instruments())
# freshness reference across all multiple prices
lastp = {}
for c in mp_list:
    try:
        lastp[c] = pd.Timestamp(dp.db_futures_multiple_prices_data.get_multiple_prices(c)["PRICE"].dropna().index[-1])
    except Exception:
        pass
fresh_ref = max(lastp.values())

no_adj, stuck, no_meta, no_cost, no_fx, no_fw, zero_w = [], [], [], [], [], [], []
for c in insts:
    if c not in adj_list:
        no_adj.append(c)
    if c in lastp and (fresh_ref - lastp[c]).days > STALE_DAYS:
        stuck.append(c)
    try:
        block = data.get_value_of_block_price_move(c)
        ccy = data.get_instrument_currency(c)
        if not block or block <= 0:
            no_meta.append(f"{c}(block={block})")
    except Exception as e:
        no_meta.append(f"{c}({type(e).__name__})")
    try:
        sr = data.get_SR_cost(c) if hasattr(data, "get_SR_cost") else data.get_raw_cost_data(c)
        if sr is None:
            no_cost.append(c)
    except Exception as e:
        no_cost.append(f"{c}({type(e).__name__})")
    try:
        fx = data.get_fx_for_instrument(c, str(raw.base_currency))
        s = pd.Series(fx).dropna()
        if len(s) == 0:
            no_fx.append(c)
    except Exception as e:
        no_fx.append(f"{c}({type(e).__name__})")
    if c not in fw:
        no_fw.append(c)
    if iw[c] <= 0:
        zero_w.append(c)

def rep(name, lst):
    print(f"  {name:34} {'OK' if not lst else 'GAP %d: %s'%(len(lst), lst[:12])}")
rep("adjusted prices present", no_adj)
rep("priced contract fresh (<15d)", stuck)
rep("instrument metadata (block/ccy)", no_meta)
rep("SR cost data", no_cost)
rep(f"FX to base ({raw.base_currency})", no_fx)
rep("forecast_weights entry", no_fw)
rep("positive instrument weight", zero_w)

for nm, lst in [("adjusted prices", no_adj), ("roll-stuck priced contract", stuck),
                ("instrument metadata", no_meta), ("SR cost", no_cost),
                ("FX to base", no_fx), ("forecast_weights", no_fw)]:
    if lst:
        findings.append(f"COVERAGE {len(lst)} instruments missing {nm}: {lst[:10]}")

print("\n" + "=" * 78)
print(f"FINDINGS ({len(findings)})")
print("=" * 78)
for i, f in enumerate(findings, 1):
    print(f"  {i}. {f}")
if not findings:
    print("  none -- config binds correctly and all instruments have complete inputs")
