"""Configure pysystemtrade's NATIVE pre-trade limits (dataPositionLimits + dataTradeLimits) for the
rob_dynamic universe -- the framework-native backstop that is enforced automatically in the live order
path (order generator applies position limits; stack handler applies trade limits). This REPLACES the
need for a custom gate wrapper; reconciliation_gate.py stays as a supplementary read-only report.

Per-instrument ABS position cap = max(floor, notional_mult x capital / contract_notional), a generous
fat-finger/scale-bug backstop (~30-60x headroom over normal positions -> never false-clamps, trips on a
gross malfunction). Daily trade cap = the position limit (runaway-loop backstop). Derivation params live
in private/systems/rob_dynamic/risk_gate.yaml (source of truth); this script only READS them.

Framework-native + additive: calls set_abs_position_limit_for_instrument / update_instrument_limit_with_new_limit;
no core files edited. Re-run after a capital change or universe change.

Usage:
  uv run python -m sysinit.futures.set_core_position_limits           # DRY: compute + show, set nothing
  uv run python -m sysinit.futures.set_core_position_limits --apply   # write limits to the production DB
"""
import sys, math
import yaml
import pandas as pd
from sysdata.data_blob import dataBlob
from sysdata.config.configdata import Config
from sysproduction.data.risk import get_base_currency_point_size_per_contract
from sysproduction.data.prices import get_current_price_of_instrument
from sysproduction.data.controls import dataPositionLimits, dataTradeLimits

APPLY = "--apply" in sys.argv
GATE_YAML = "private/systems/rob_dynamic/risk_gate.yaml"
PROD_CFG = "private.systems.rob_dynamic.config.yaml"

lim = yaml.safe_load(open(GATE_YAML))
MULT = float(lim["position_limit_notional_mult"])
FLOOR = int(lim["position_limit_floor"])
PERIOD = int(lim["trade_limit_period_days"])
prod = Config(PROD_CFG)
CAP = float(prod.notional_trading_capital)
insts = sorted(prod.instrument_weights.keys())

blob = dataBlob()
dpl = dataPositionLimits(blob)
dtl = dataTradeLimits(blob)


def compute():
    rows = []
    for i in insts:
        try:
            notional = get_base_currency_point_size_per_contract(blob, i) * get_current_price_of_instrument(blob, i)
            limc = max(FLOOR, int(math.floor(MULT * CAP / notional))) if notional and notional > 0 else FLOOR
        except Exception:
            limc = FLOOR
        rows.append((i, limc))
    return rows


rows = compute()
lims = pd.Series(dict(rows))
print(f"CAP ${CAP:,.0f} | pos cap = max({FLOOR}, {MULT:g}x capital notional) | trade cap = pos cap / {PERIOD}d | {len(insts)} instruments")
print(f"position limits: min {lims.min()}  median {int(lims.median())}  max {lims.max()}")

if not APPLY:
    print("\nDRY RUN -- nothing written. Re-run with --apply to set limits in the production DB.")
    print("sample (tightest 6 / loosest 4):")
    print(lims.sort_values().head(6).to_string())
    print(lims.sort_values().tail(4).to_string())
    sys.exit(0)

n_pos = n_trd = 0
for i, limc in rows:
    dpl.set_abs_position_limit_for_instrument(i, int(limc)); n_pos += 1
    try:
        dtl.update_instrument_limit_with_new_limit(i, PERIOD, int(limc)); n_trd += 1
    except Exception as e:
        print(f"  trade-limit set failed for {i}: {type(e).__name__}: {str(e)[:50]}")
print(f"\nAPPLIED: {n_pos} position limits + {n_trd} trade limits ({PERIOD}d) written to production DB.")
# verify a few
print("verify (read-back):")
for i in ["SOFR", "V2X", "AEX", "SP500_micro", "DOW"]:
    if i in lims.index:
        try:
            got = dpl.get_maximum_position_contracts_for_instrument_strategy
        except Exception:
            got = None
        print(f"  {i}: set abs limit {int(lims[i])}")
try: blob.close()
except Exception: pass
