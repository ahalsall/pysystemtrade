"""UNIVERSE COMPLETENESS AUDIT — find major market exposures that silently dropped out of our tradeable
106, the way natural gas did (Rob's config references a symbol whose CSI data is DEAD, while fresh data
exists under a different symbol not in the config). Read-only.

Three lenses:
  A. DROPPED — instruments in Rob's 170 config NOT in our tradeable 106, with WHY (no-data / stale-dead /
     roll-stuck) and asset class. This is 'what exposure did we lose'.
  B. FRESH ORPHANS — instruments with FRESH data in our DB that are in NEITHER config. These are the
     'we have the data, just not wired in' candidates (GAS_US, GASOIL, ...). Each is matched by name-root
     to the dead config instrument it could replace.
  C. ASSET-CLASS COVERAGE — per class: how many Rob instruments we trade vs dropped, so a THIN or ZERO
     exposure (like nat gas) jumps out even if individual names look fine.
"""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv as csvmod
import re
import yaml
import pandas as pd
from sysproduction.data.prices import diagPrices

STALE_DAYS = 30
dp = diagPrices()
rob = list(yaml.safe_load(open("systems/provided/rob_system/config.yaml"))["instrument_weights"].keys())
ours = set(yaml.safe_load(open("private/systems/rob_dynamic/config.yaml"))["instrument_weights"].keys())
adj = set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
mp = set(dp.db_futures_multiple_prices_data.get_list_of_instruments())

# asset class from instrument config
acls = {}
try:
    for r in csvmod.DictReader(open("data/futures/csvconfig/instrumentconfig.csv")):
        acls[r["Instrument"]] = r.get("AssetClass", "?")
except Exception:
    pass

# priced-contract freshness
lastp = {}
for c in mp:
    try:
        lastp[c] = pd.Timestamp(dp.db_futures_multiple_prices_data.get_multiple_prices(c)["PRICE"].dropna().index[-1])
    except Exception:
        pass
fresh_ref = max(lastp.values())
def fresh(c):
    return c in lastp and (fresh_ref - lastp[c]).days <= STALE_DAYS
fresh_db = {c for c in lastp if fresh(c)}

def norm(s):  # normalize a symbol to a comparison root
    s = s.upper()
    for suf in ["_MINI", "_MICRO", "-MINI", "-MICRO", "-LAST", "-PEN", "-NEW", "-OZ"]:
        s = s.replace(suf, "")
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"\d+$", "", s))

# ---------- A. DROPPED ----------
dropped = []
for inst in rob:
    if inst in ours:
        continue
    if inst not in adj and inst not in mp:
        why = "NO-DATA"
    elif not fresh(inst):
        why = f"STALE→{lastp.get(inst).date() if inst in lastp else '?'}"
    else:
        why = "FRESH?(check)"
    dropped.append(dict(inst=inst, asset=acls.get(inst, "?"), why=why))
D = pd.DataFrame(dropped)

# ---------- B. FRESH ORPHANS (fresh data, in neither config) ----------
orphans = sorted(fresh_db - set(rob) - ours)
orph_rows = []
dead_cfg = {d["inst"] for d in dropped}  # dropped config instruments (candidates to replace)
for o in orphans:
    n = norm(o)
    # a dropped config instrument sharing the same root -> o could replace it
    repl = [d for d in dead_cfg if norm(d) == n or norm(d).startswith(n) or n.startswith(norm(d))]
    orph_rows.append(dict(orphan=o, asset=acls.get(o, "?"), last=str(lastp[o].date()),
                          could_replace=",".join(sorted(repl)[:3]) if repl else ""))
O = pd.DataFrame(orph_rows)

# ---------- C. ASSET-CLASS COVERAGE ----------
rows = []
classes = sorted(set(acls.get(i, "?") for i in rob))
for cl in classes:
    rob_in = [i for i in rob if acls.get(i, "?") == cl]
    trad = [i for i in rob_in if i in ours]
    drop = [i for i in rob_in if i not in ours]
    # fresh orphans in this class that could add exposure
    orph_cl = [o for o in orphans if acls.get(o, "?") == cl]
    rows.append(dict(asset_class=cl, rob=len(rob_in), tradeable=len(trad), dropped=len(drop),
                     pct_trad=round(100 * len(trad) / len(rob_in)) if rob_in else 0,
                     fresh_orphans=len(orph_cl)))
C = pd.DataFrame(rows).sort_values("pct_trad")

pd.set_option("display.width", 180); pd.set_option("display.max_rows", 200)
print("=" * 90)
print(f"UNIVERSE COMPLETENESS  |  Rob 170 → our {len(ours)} tradeable  |  {len(dropped)} dropped  |  {len(orphans)} fresh orphans")
print("=" * 90)

print("\n[C] ASSET-CLASS COVERAGE (worst first) — thin/zero exposures are the risk:")
print(C.to_string(index=False))

print("\n[B] FRESH ORPHANS — data we HAVE, fresh, but wired into NEITHER config (the GAS_US-type finds):")
print(O.to_string(index=False) if len(O) else "  (none)")

print("\n[A] DROPPED config instruments by asset class + why (STALE=dead data, NO-DATA=never had it):")
for cl in sorted(D.asset.unique()):
    sub = D[D.asset == cl]
    print(f"\n  {cl} ({len(sub)}):")
    for _, r in sub.iterrows():
        print(f"    {r['inst']:<16} {r['why']}")

# save
os.makedirs("private", exist_ok=True)
D.to_csv("private/universe_dropped.csv", index=False)
O.to_csv("private/universe_fresh_orphans.csv", index=False)
C.to_csv("private/universe_class_coverage.csv", index=False)
print("\nsaved -> private/universe_{dropped,fresh_orphans,class_coverage}.csv")
