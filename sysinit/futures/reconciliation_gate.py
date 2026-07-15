"""#30 RECONCILIATION SAFETY GATE -- pre-trade tripwire between the generated book and live orders.

Given the target book (private/target_book_250k.csv) and current broker holdings, it computes for the
TARGET positions -- using pysystemtrade's OWN risk primitives (point size, price, daily stdev) so it
can't drift from the framework -- per-instrument notional, annualised risk % of capital, implied order
size, and order/position vs ADV; plus portfolio gross leverage; plus broker-vs-DB reconciliation breaks.
Each is checked against hand-tuned caps in private/systems/rob_dynamic/risk_gate.yaml.

Verdict per row: PASS / WARN / BLOCK. Any BLOCK -> overall FAIL and NON-ZERO EXIT, so a launcher can
refuse to place orders. This is the standing guard that catches a regressed scale bug, a leverage
blowup, a fat-finger, or a position that drifted from the broker -- before anything is sent.

Read-only; places nothing.  Usage: uv run python -m sysinit.futures.reconciliation_gate
"""
import os
import sys
os.environ["MPLBACKEND"] = "Agg"
import yaml
import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from sysdata.data_blob import dataBlob
from sysproduction.data.prices import diagPrices, get_current_price_of_instrument
from sysproduction.data.risk import get_base_currency_point_size_per_contract
from sysproduction.reporting.data.risk import get_current_daily_stdev_for_instrument
from sysobjects.contracts import futuresContract

ROOT_BDAYS = np.sqrt(256)
GATE_YAML = "private/systems/rob_dynamic/risk_gate.yaml"
BOOK_CSV = "private/target_book_250k.csv"
PROD_CFG = "private.systems.rob_dynamic.config.yaml"

lim = yaml.safe_load(open(GATE_YAML))
prod = Config(PROD_CFG)
CAPITAL = float(prod.notional_trading_capital)
VOL = float(prod.percentage_vol_target)

tgt = pd.read_csv(BOOK_CSV, index_col=0)["target_contracts"].astype(int)
tgt = tgt[tgt != 0]

blob = dataBlob()
dp = diagPrices()

# ---- broker holdings + reconciliation breaks (best-effort; broker may be down) ----
cur = pd.Series(dtype=int)
breaks = []
broker_ok = False
try:
    from sysproduction.data.broker import dataBroker
    brk = dataBroker(blob)
    pos = brk.get_all_current_contract_positions()
    df = pos.as_pd_df() if hasattr(pos, "as_pd_df") else pos
    if len(df):
        cur = df.groupby("instrument_code")["position"].sum().astype(int)
    try:
        breaks = brk.get_list_of_breaks_between_broker_and_db_contract_positions()
    except Exception as e:
        breaks = [f"(break-check unavailable: {type(e).__name__})"]
    broker_ok = True
except Exception as e:
    print(f"NOTE: broker unavailable ({type(e).__name__}: {str(e)[:50]}) -- reconciliation checks skipped, "
          f"risk/leverage checks still run on the target book.")

# ---- ADV on the priced contract (recent avg daily volume) ----
def adv(inst):
    try:
        pc = str(dp.db_futures_multiple_prices_data.get_multiple_prices(inst)["PRICE_CONTRACT"].iloc[-1])
        vols = dp.get_merged_prices_for_contract_object(futuresContract(inst, pc)).daily_volumes()
        v = pd.Series(vols).replace(0, np.nan).dropna()
        return float(v.tail(20).mean()) if len(v) else np.nan
    except Exception:
        return np.nan

# ---- per-instrument metrics on TARGET positions (framework primitives) ----
insts = sorted(set(tgt.index) | set(cur.index))
rows = []
for inst in insts:
    t = int(tgt.get(inst, 0)); c = int(cur.get(inst, 0)); order = t - c
    try:
        psb = get_base_currency_point_size_per_contract(blob, inst)   # base-ccy notional per point
        px = get_current_price_of_instrument(blob, inst)
        dstd = get_current_daily_stdev_for_instrument(blob, inst)      # daily PRICE stdev
        notional = t * psb * px
        ann_risk_ccy = dstd * ROOT_BDAYS * psb                        # per-contract annual risk (base ccy)
        risk_perc = 100 * ann_risk_ccy * t / CAPITAL
        notl_perc = 100 * notional / CAPITAL
        a = adv(inst)
        ordadv = 100 * abs(order) / a if a and a > 0 else np.nan
        posadv = 100 * abs(t) / a if a and a > 0 else np.nan
        rows.append(dict(inst=inst, cur=c, tgt=t, order=order,
                         notional_perc=round(notl_perc, 1), risk_perc=round(risk_perc, 2),
                         adv=round(a) if a == a else np.nan,
                         ord_adv=round(ordadv, 2) if ordadv == ordadv else np.nan,
                         pos_adv=round(posadv, 1) if posadv == posadv else np.nan))
    except Exception as e:
        rows.append(dict(inst=inst, cur=c, tgt=t, order=order, err=f"{type(e).__name__}:{str(e)[:30]}"))

R = pd.DataFrame(rows).set_index("inst")

# ---- apply caps -> per-row verdict ----
blocks, warns = [], []
def flag(cond_block, cond_warn, msg, inst):
    if cond_block: blocks.append(f"{inst}: {msg}")
    elif cond_warn: warns.append(f"{inst}: {msg}")

for inst, r in R.iterrows():
    if "err" in r and isinstance(r.get("err"), str):
        warns.append(f"{inst}: metric error {r['err']}"); continue
    flag(r.risk_perc > lim["max_instrument_risk_perc"], r.risk_perc > lim["warn_instrument_risk_perc"],
         f"annual risk {r.risk_perc}% capital", inst)
    flag(abs(r.notional_perc) > lim["max_instrument_notional_perc"], abs(r.notional_perc) > lim["warn_instrument_notional_perc"],
         f"notional {r.notional_perc}% capital", inst)
    flag(abs(r.order) > lim["max_single_order_contracts"], False,
         f"order {r.order} > max_single_order_contracts", inst)
    if r.get("ord_adv") == r.get("ord_adv"):
        flag(False, r.ord_adv > lim["max_order_perc_adv"], f"order {r.ord_adv}% of ADV", inst)
    if r.get("pos_adv") == r.get("pos_adv"):
        flag(False, r.pos_adv > lim["max_position_perc_adv"], f"position {r.pos_adv}% of ADV", inst)

gross_lev = float(R["notional_perc"].abs().sum() / 100) if "notional_perc" in R else float("nan")
if gross_lev > lim["max_gross_leverage"]:
    blocks.append(f"PORTFOLIO gross leverage {gross_lev:.2f}x > max {lim['max_gross_leverage']}")
elif gross_lev > lim["warn_gross_leverage"]:
    warns.append(f"PORTFOLIO gross leverage {gross_lev:.2f}x > warn {lim['warn_gross_leverage']}")

if breaks:
    real_breaks = [b for b in breaks if not str(b).startswith("(")]
    if real_breaks and lim.get("block_on_reconciliation_break"):
        blocks.append(f"RECONCILIATION {len(real_breaks)} broker/DB position break(s): {real_breaks[:6]}")
    elif real_breaks:
        warns.append(f"RECONCILIATION {len(real_breaks)} broker/DB break(s) (WARN in beta): {real_breaks[:6]}")

# ---- report ----
pd.set_option("display.width", 170)
print("=" * 88)
print(f"RECONCILIATION SAFETY GATE  |  ${CAPITAL:,.0f} @ {VOL:.0f}% vol  |  {len(tgt)} target positions"
      f"  |  broker {'connected' if broker_ok else 'OFFLINE'}")
print("=" * 88)
cols = [c for c in ["cur","tgt","order","notional_perc","risk_perc","adv","ord_adv","pos_adv"] if c in R.columns]
print(R[cols].to_string())
print(f"\nPORTFOLIO gross leverage (sum|notional|/capital): {gross_lev:.2f}x   "
      f"[warn {lim['warn_gross_leverage']} / max {lim['max_gross_leverage']}]")
print(f"total target annual risk (undiversified sum): {R['risk_perc'].abs().sum():.1f}% of capital "
      f"(diversified realised is far lower; informational)")

print("\n" + "-" * 88)
if warns:
    print(f"WARN ({len(warns)}):")
    for w in warns: print(f"  ⚠ {w}")
if blocks:
    print(f"\nBLOCK ({len(blocks)}):")
    for b in blocks: print(f"  ✖ {b}")
verdict = "FAIL" if blocks else ("PASS-WITH-WARNINGS" if warns else "PASS")
print("\n" + "=" * 88)
print(f"GATE VERDICT: {verdict}" + ("  -> DO NOT TRADE" if blocks else "  -> cleared to place orders"))
print("=" * 88)
try: blob.close()
except Exception: pass
sys.exit(1 if blocks else 0)
