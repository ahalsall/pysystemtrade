"""One-shot data-integrity gate for the CSI-only sim DB (run after any re-ingest).
Checks, per instrument: (1) FRESHNESS — how stale the raw price is; (2) DEFLATOR —
does calculate_cost_deflator go inf/nan (the bug that freezes the dynamic optimiser);
(3) NEGATIVES — back-adjusted series crossing zero. Plus COVERAGE vs the CSI map
(flags Barchart-only residue). Exit-style summary: PASS only if 0 stale / 0 broken /
0 residue. Env: STALE_DAYS (default 10), AS_OF (YYYY-MM-DD, default today-ish)."""
import os
import csv
import numpy as np
import pandas as pd
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from syscore.pandas.strategy_functions import calculate_cost_deflator

STALE_DAYS = int(os.environ.get("STALE_DAYS", 10))
AS_OF = pd.Timestamp(os.environ.get("AS_OF", "2026-07-07"))

d = dbFuturesSimData()
csi = {r[1]: r[0] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
       if r and r[0] != "csi_symbol"}
in_db = set(d.get_instrument_list())
residue = sorted(in_db - set(csi))          # in DB but not CSI-mapped (Barchart-only)
missing = sorted(set(csi) - in_db)          # mapped but not ingested

rows = []
for pst in sorted(set(csi) & in_db):
    try:
        p = d.get_raw_price(pst).dropna()
        last = pd.Timestamp(p.index[-1].date())
        stale = (AS_OF - last).days
        defl = calculate_cost_deflator(p)
        broken = bool(np.isinf(defl.iloc[-1]) or np.isnan(defl.iloc[-1]) or np.isinf(defl).any())
        negs = int((p < 0).sum())
        rows.append(dict(pst=pst, csi=csi[pst], last=last.date(), stale=stale,
                         broken=broken, negs=negs))
    except Exception as e:
        rows.append(dict(pst=pst, csi=csi.get(pst, "?"), last="ERR", stale=99999,
                         broken=True, negs=-1))

df = pd.DataFrame(rows)
stale_df = df[df.stale > STALE_DAYS].sort_values("stale", ascending=False)
broken_df = df[df.broken]
neg_df = df[df.negs > 0]

pd.set_option("display.width", 130)
print(f"=== CSI-only DATA-INTEGRITY GATE (as of {AS_OF.date()}, stale>{STALE_DAYS}d) ===")
print(f"instruments: {len(df)} mapped+in-DB | missing (mapped, not ingested): {len(missing)} {missing}")
print(f"Barchart-only RESIDUE in DB (should be 0 after cutover): {len(residue)}")
if residue:
    print("  ", residue)
print(f"\nSTALE (>{STALE_DAYS}d): {len(stale_df)}")
if len(stale_df):
    print(stale_df[["pst", "csi", "last", "stale"]].to_string(index=False))
print(f"\nBROKEN cost-deflator (inf/nan -> FREEZES optimiser): {len(broken_df)}")
if len(broken_df):
    print(broken_df[["pst", "csi", "last", "stale", "negs"]].to_string(index=False))
print(f"\nNEGATIVE raw prices (deflator/vol risk): {len(neg_df)}")
if len(neg_df):
    print(neg_df[["pst", "csi", "negs"]].to_string(index=False))

ok = (len(stale_df) == 0 and len(broken_df) == 0 and len(residue) == 0 and len(missing) == 0)
print(f"\n{'PASS - DB clean, backtests trustworthy' if ok else 'FAIL - fix above before backtesting'}")
df.to_csv("private/data_freshness_audit.csv", index=False)
print("saved -> private/data_freshness_audit.csv")
