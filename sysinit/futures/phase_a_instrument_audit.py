"""Phase A production-readiness audit: of our validated CSI universe, which instruments are
genuinely paper-tradeable via IBKR. Read-only. Checks per instrument:
  ib      : has an IBKR contract mapping (ib_config_futures.csv, IBSymbol present)
  spec    : has PST instrument spec (instrumentconfig.csv: Pointsize, Currency)
  spread  : has a spread-cost estimate (spreadcosts.csv, SpreadCost > 0)
  ccy     : trading currency (flag non-USD -> CAD-base FX awareness)
  roll    : sim's CURRENT priced contract (from multiple prices) is a plausible near month,
            not slipped forward/stale (the 2026-07-01 failure mode). Indicator only -- the
            authoritative production roll state lives in the live roll status, not the sim DB.
Verdict: READY (all ok) / REVIEW (spread/roll/ccy flag) / BLOCKED (no IB map or no spec)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import pandas as pd
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

# load config maps
def load(path, key):
    out = {}
    for r in csv.DictReader(open(path)):
        out[r[key]] = r
    return out
ib = load("sysbrokers/IB/config/ib_config_futures.csv", "Instrument")
spec = load("data/futures/csvconfig/instrumentconfig.csv", "Instrument")
spread = load("data/futures/csvconfig/spreadcosts.csv", "Instrument")
today_m = fresh.year * 12 + fresh.month  # months, referenced to freshest data date

rows = []
for c in our:
    ibr = ib.get(c); spr = spec.get(c); sp = spread.get(c)
    ib_ok = bool(ibr and ibr.get("IBSymbol"))
    spec_ok = bool(spr and spr.get("Pointsize"))
    try: spread_val = float(sp["SpreadCost"]) if sp else None
    except Exception: spread_val = None
    ccy = (spr or {}).get("Currency", "?")
    # multiplier consistency: Pointsize vs IBMultiplier*priceMagnifier
    mult_flag = ""
    try:
        ps = float(spr["Pointsize"]); ibm = float(ibr["IBMultiplier"]); pm = float(ibr.get("priceMagnifier", 1) or 1)
        eff = ibm / pm
        if abs(eff - ps) / max(ps, 1e-9) > 0.02:
            mult_flag = f"mult {ps}!={eff:g}"
    except Exception:
        pass
    # sim roll indicator
    roll_flag = ""
    try:
        mp = dp.db_futures_multiple_prices_data.get_multiple_prices(c)
        pc = str(mp["PRICE_CONTRACT"].iloc[-1])  # YYYYMMDD
        cm = int(pc[:4]) * 12 + int(pc[4:6])
        ahead = cm - today_m
        if ahead < 0: roll_flag = f"STALE({ahead}mo)"
        elif ahead > 14: roll_flag = f"FWD(+{ahead}mo)"
    except Exception:
        roll_flag = "no-mp"
    # verdict
    if not ib_ok or not spec_ok:
        verdict = "BLOCKED"
    elif mult_flag or roll_flag or not spread_val:
        verdict = "REVIEW"
    else:
        verdict = "READY"
    rows.append(dict(instrument=c, verdict=verdict, ib=ib_ok, spec=spec_ok,
                     ccy=ccy, spread=spread_val, mult=mult_flag, roll=roll_flag,
                     ibsym=(ibr or {}).get("IBSymbol", ""), ibexch=(ibr or {}).get("IBExchange", "")))

df = pd.DataFrame(rows).set_index("instrument")
df.to_csv("private/phase_a_audit.csv")
from collections import Counter
print(f"PHASE A AUDIT: {len(our)} CSI-universe instruments (freshest data {fresh.date()})\n", flush=True)
print("verdict:", dict(Counter(df["verdict"])), flush=True)
print(f"currency mix: {dict(Counter(df['ccy']))}", flush=True)
print(f"\n=== BLOCKED (no IB map or no spec -> cannot trade) ===")
b = df[df.verdict == "BLOCKED"]
print(b[["ib", "spec", "ccy"]].to_string() if len(b) else "  (none)")
print(f"\n=== REVIEW (tradeable but flagged) ===")
rv = df[df.verdict == "REVIEW"]
print(rv[["ccy", "spread", "mult", "roll", "ibsym"]].to_string() if len(rv) else "  (none)")
print(f"\n=== READY count: {(df.verdict=='READY').sum()} ===")
print("  " + " ".join(sorted(df[df.verdict == "READY"].index.tolist())))
print("\nsaved -> private/phase_a_audit.csv", flush=True)
