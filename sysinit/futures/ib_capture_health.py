"""Capture-health check for the siloed IB intraday store -- so Gateway-down days can't silently open
permanent gaps. Reads ONLY the local parquet silo (private/data/parquet_ib_intraday/); no Gateway/DB
needed, so it always runs. For every instrument in the live production universe it reports the last
captured bar and staleness, and -- crucially -- flags anything approaching IB's ~30-day hourly lookback
horizon, beyond which the missing tape can NEVER be back-filled.

Verdicts (days since last captured bar):
  FRESH  < WARN_DAYS (default 7)          -- healthy
  WARN   WARN_DAYS..DANGER_DAYS           -- capture likely not running; investigate
  DANGER >= DANGER_DAYS (default 23)      -- < ~1wk of IB lookback left to recover; act now
  MISSING                                 -- in universe but never captured

Writes a snapshot to private/ib_capture_health.csv and exits NON-ZERO if any DANGER/MISSING.
Usage: uv run python -m sysinit.futures.ib_capture_health
Schedulable weekly (needs no Gateway): pst-ib-capture-health.timer.
"""
import os
import sys
import glob
import datetime
import numpy as np
import pandas as pd

STORE = "private/data/parquet_ib_intraday/futures_contract_prices"
PROD_CFG = "private/systems/rob_dynamic/config.yaml"
OUT = "private/ib_capture_health.csv"
IB_LOOKBACK_DAYS = int(os.environ.get("IB_LOOKBACK_DAYS", 30))   # IB hourly history horizon
WARN_DAYS = int(os.environ.get("WARN_DAYS", 7))
DANGER_DAYS = int(os.environ.get("DANGER_DAYS", IB_LOOKBACK_DAYS - 7))
FREQ = os.environ.get("CAPTURE_FREQ", "Hour")
# Instruments IB serves NO intraday Trades data for (daily works; mapping verified OK in #32).
# Reported as EXCLUDED (non-alarming), not MISSING. Auto-recovers to FRESH if a future liquid
# contract does return intraday. Override with CAPTURE_EXCLUDE="COTTON,FOO".
NO_INTRADAY_IB = set(os.environ.get("CAPTURE_EXCLUDE", "COTTON").replace(",", " ").split())


def load_universe():
    import yaml
    if os.path.exists(PROD_CFG):
        iw = yaml.safe_load(open(PROD_CFG)).get("instrument_weights", {})
        if iw:
            return sorted(iw.keys())
    raise SystemExit(f"no universe ({PROD_CFG} instrument_weights missing)")


def last_bar_per_instrument():
    """Max bar timestamp + bar count across all contract files for each instrument in the silo."""
    out = {}
    for f in glob.glob(os.path.join(STORE, f"{FREQ}@*.parquet")):
        inst = os.path.basename(f).split("@")[1].split("#")[0]
        try:
            df = pd.read_parquet(f)
            idx = pd.to_datetime(df.index)
            last = idx.max()
            rec = out.setdefault(inst, dict(last=last, first=idx.min(), n=len(df), files=0))
            rec["files"] += 1
            rec["n"] = max(rec["n"], len(df))
            if last > rec["last"]:
                rec["last"] = last
            if idx.min() < rec["first"]:
                rec["first"] = idx.min()
        except Exception:
            continue
    return out


universe = load_universe()
data = last_bar_per_instrument()
now = pd.Timestamp(datetime.datetime.utcnow())

rows = []
for inst in universe:
    rec = data.get(inst)
    if rec is None:
        v = "EXCLUDED" if inst in NO_INTRADAY_IB else "MISSING"
        rows.append(dict(instrument=inst, verdict=v, days_stale=np.nan,
                         last_bar="", n_bars=0, days_to_permanent_gap=np.nan))
        continue
    stale = (now - rec["last"]).total_seconds() / 86400
    verdict = "DANGER" if stale >= DANGER_DAYS else ("WARN" if stale >= WARN_DAYS else "FRESH")
    rows.append(dict(instrument=inst, verdict=verdict, days_stale=round(stale, 1),
                     last_bar=str(rec["last"]), n_bars=rec["n"],
                     days_to_permanent_gap=round(IB_LOOKBACK_DAYS - stale, 1)))

df = pd.DataFrame(rows).sort_values(["verdict", "days_stale"], ascending=[True, False])
df.to_csv(OUT, index=False)

counts = df["verdict"].value_counts().to_dict()
print("=" * 84)
print(f"IB INTRADAY CAPTURE HEALTH  |  {len(universe)} universe  |  now {now:%Y-%m-%d %H:%M}UTC  |  "
      f"WARN>{WARN_DAYS}d DANGER>{DANGER_DAYS}d (IB lookback {IB_LOOKBACK_DAYS}d)")
print("=" * 84)
print("summary:", ", ".join(f"{k} {counts.get(k,0)}" for k in ["FRESH", "WARN", "DANGER", "MISSING", "EXCLUDED"]))
excluded = df[df["verdict"] == "EXCLUDED"]["instrument"].tolist()
if excluded:
    print(f"excluded (IB has no intraday Trades data; benign): {excluded}")

problems = df[df["verdict"].isin(["WARN", "DANGER", "MISSING"])]
if len(problems):
    print(f"\nNEEDS ATTENTION ({len(problems)}):")
    for _, r in problems.iterrows():
        if r["verdict"] == "MISSING":
            print(f"  MISSING {r['instrument']:<14} never captured")
        else:
            print(f"  {r['verdict']:7} {r['instrument']:<14} stale {r['days_stale']}d "
                  f"(last {r['last_bar'][:16]}, {r['days_to_permanent_gap']}d to permanent gap)")
else:
    print("\nall instruments FRESH -- capture is healthy")
print(f"\nsnapshot -> {OUT}")

# freshest few for context
fresh = df[df["verdict"] == "FRESH"].sort_values("days_stale").head(3)
if len(fresh):
    print("freshest:", ", ".join(f"{r.instrument}({r.days_stale}d)" for _, r in fresh.iterrows()))

sys.exit(1 if (counts.get("DANGER", 0) or counts.get("MISSING", 0)) else 0)
