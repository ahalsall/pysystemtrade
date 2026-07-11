"""Correlation-proxy micro screen (Andrew's strategy): for each expensive instrument we
hold, find the cheapest highly-correlated 'handle' the optimiser could use to express its
exposure. A handle = an instrument whose underlying has an affordable CSI micro/mini. Uses
the optimiser's OWN correlation matrix (6-mo weekly), so no new ingestion needed to screen.

Output: (1) which of our instruments have their OWN same-underlying CSI micro; (2) for the
expensive/no-own-micro ones, the best correlated instrument that HAS a micro (the proxy);
(3) ORPHANS = expensive exposures with neither an own micro nor a correlated micro proxy."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv, re
import numpy as np
import pandas as pd
from systems.provided.rob_system.run_system import futures_system
from systems.provided.static_small_system_optimise.optimise_small_system import get_correlation_matrix
from sysproduction.data.prices import diagPrices
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysdata.config.configdata import Config
from sysinit.futures.csi_catalog_map import load_catalog, load_pst_index

dp = diagPrices()
data_inst = (set(dp.db_futures_adjusted_prices_data.get_list_of_instruments())
             & set(dp.db_futures_multiple_prices_data.get_list_of_instruments()))
p2c = {r[1]: r[0] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv")) if r and r[0] != "csi_symbol"}
cfg = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
d = dbFuturesSimData()
last = {}
for c in set(p2c) & data_inst & cfg:
    try: last[c] = pd.Timestamp(d.get_raw_price(c).dropna().index[-1].date())
    except Exception: last[c] = pd.Timestamp("1900")
fresh = max(last.values()); our = sorted(c for c in set(p2c) & data_inst & cfg if (fresh - last[c]).days <= 45)
pidx = load_pst_index(); cat = load_catalog(); bycsi = {c["symbol"]: c for c in cat}

# which of OUR instruments have a same-underlying CSI micro (smaller contract, active, liquid)
def toks(s): return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()) - {"index","mini","micro","e","futures","the","and","us","usd"}
smalls = [c for c in cat if re.search(r"micro|mini|emini", c["name"], re.I) and c["active"] and c["volume"] > 200]
held_csi = set(p2c[c] for c in our)
has_micro = {}
for c in our:
    cc = bycsi.get(p2c[c]);
    if not cc: continue
    ht = toks(cc["name"]); sz = cc["contract_size"] or 1e12
    hit = None
    for s in smalls:
        if s["symbol"] in held_csi: continue
        if len(ht & toks(s["name"])) >= 2 and (s["contract_size"] or 1e12) < sz * 0.9:
            # guard: same number-family (Sugar 11 != 16 etc) and not a sector<->broad mismatch handled by token overlap
            hit = (s["symbol"], s["name"][:26], round(sz / (s["contract_size"] or 1), 1)); break
    if hit: has_micro[c] = hit

print("Building system + correlation matrix (heavy)...", flush=True)
system = futures_system()
system.config.instrument_weights = {i: 1.0 / len(our) for i in our}
system.config.use_instrument_weight_estimates = False
corr = get_correlation_matrix(system)
cm = pd.DataFrame(corr.as_pd().values, index=corr.columns, columns=corr.columns) if hasattr(corr, "as_pd") else \
     pd.DataFrame(corr.values, index=corr.columns, columns=corr.columns)
cm = cm.reindex(index=our, columns=our)
print(f"corr matrix {cm.shape}\n", flush=True)

CORR_MIN = 0.70
own = set(has_micro)
rows = []
for c in our:
    if c in own:
        rows.append(dict(instrument=c, asset=pidx.get(c, {}).get("asset_class", "?"),
                         status="OWN-MICRO", proxy=has_micro[c][0], detail=has_micro[c][1], corr=1.0))
        continue
    # find best correlated instrument that HAS a micro
    corrs = cm[c].drop(c, errors="ignore").dropna()
    cands = [(o, corrs[o]) for o in corrs.index if o in own]
    cands = [(o, r) for o, r in cands if abs(r) >= CORR_MIN]
    cands.sort(key=lambda x: -abs(x[1]))
    if cands:
        o, r = cands[0]
        rows.append(dict(instrument=c, asset=pidx.get(c, {}).get("asset_class", "?"),
                         status="PROXY", proxy=f"{o}->{has_micro[o][0]}", detail=f"via {o}", corr=round(float(r), 2)))
    else:
        rows.append(dict(instrument=c, asset=pidx.get(c, {}).get("asset_class", "?"),
                         status="ORPHAN", proxy="", detail="no own micro, no correlated micro", corr=np.nan))

df = pd.DataFrame(rows).set_index("instrument")
df.to_csv("private/micro_proxy_screen.csv")
from collections import Counter
print("=== coverage summary ===")
print(dict(Counter(df["status"])))
print(f"\n=== OWN same-underlying micro available ({(df.status=='OWN-MICRO').sum()}) ===")
print(df[df.status == "OWN-MICRO"][["asset", "proxy", "detail"]].to_string())
print(f"\n=== reachable via CORRELATED micro proxy (|corr|>={CORR_MIN}) ({(df.status=='PROXY').sum()}) ===")
print(df[df.status == "PROXY"].sort_values("corr", ascending=False)[["asset", "proxy", "corr"]].to_string())
print(f"\n=== ORPHANS: expensive exposures with NO cheap handle ({(df.status=='ORPHAN').sum()}) ===")
print(df[df.status == "ORPHAN"].groupby("asset").size().to_string())
print("  orphan instruments:", sorted(df[df.status == "ORPHAN"].index.tolist()))
print("\nsaved -> private/micro_proxy_screen.csv", flush=True)
