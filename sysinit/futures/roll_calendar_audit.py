"""Comprehensive roll-calendar / roll-config audit across our universe. Read-only (CSVs + parquet,
no IB, no system build). For each instrument reports and flags:
  cal_end        : last date in roll_calendars_csv/<inst>.csv
  adj_end/mp_end : last date of adjusted / multiple prices
  TRUNCATED      : roll calendar ends >180d before the price data (multiple prices can't extend past it)
  priced/carry   : current PRICE_CONTRACT vs CARRY_CONTRACT from multiple prices
  CARRY=PRICE    : carry contract equals priced -> carry forecast not computable
  STALE          : priced-contract month is behind the freshest data month
  diverged       : our rollconfig row differs from Rob's committed baseline (HEAD~ vs working)
Highlights the instruments needing a roll-calendar regen / config review before Phase C."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import subprocess
import pandas as pd
from sysproduction.data.prices import diagPrices
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysdata.config.configdata import Config

dp = diagPrices()
adj = dp.db_futures_adjusted_prices_data
mpd = dp.db_futures_multiple_prices_data
data_inst = set(adj.get_list_of_instruments()) & set(mpd.get_list_of_instruments())
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv")) if r and r[0] != "csi_symbol")
cfg = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
d = dbFuturesSimData()
last = {}
for c in csi & data_inst & cfg:
    try: last[c] = pd.Timestamp(d.get_raw_price(c).dropna().index[-1].date())
    except Exception: last[c] = pd.Timestamp("1900")
fresh = max(last.values()); our = sorted(c for c in csi & data_inst & cfg if (fresh - last[c]).days <= 45)
today_m = fresh.year * 12 + fresh.month

# roll config
roll = {r["Instrument"]: r for r in csv.DictReader(open("data/futures/csvconfig/rollconfig.csv"))}
# instruments whose rollconfig row we changed vs committed baseline
diverged = set()
try:
    base = subprocess.run(["git", "show", "HEAD:data/futures/csvconfig/rollconfig.csv"],
                          capture_output=True, text=True).stdout
    base_rows = {r["Instrument"]: r for r in csv.DictReader(base.splitlines())}
    for k, v in roll.items():
        if k in base_rows and v != base_rows[k]:
            diverged.add(k)
except Exception:
    pass

def cal_info(c):
    fp = f"data/futures/roll_calendars_csv/{c}.csv"
    if not os.path.exists(fp): return (None, None)
    try:
        df = pd.read_csv(fp)
        end = pd.to_datetime(df["DATE_TIME"].iloc[-1])
        return (end, str(df["current_contract"].iloc[-1]))
    except Exception:
        return (None, None)

rows = []
for c in our:
    rc = roll.get(c, {})
    cal_end, cal_priced = cal_info(c)
    try:
        ae = pd.Timestamp(adj.get_adjusted_prices(c).dropna().index[-1].date())
    except Exception:
        ae = None
    try:
        mp = mpd.get_multiple_prices(c); me = pd.Timestamp(mp.index[-1].date())
        pc = str(mp["PRICE_CONTRACT"].iloc[-1]); cc = str(mp["CARRY_CONTRACT"].iloc[-1])
    except Exception:
        me = pc = cc = None
    trunc = (cal_end is not None and ae is not None and (ae - cal_end).days > 180)
    carry_eq = (pc is not None and pc == cc)
    stale = False
    if pc:
        stale = (int(pc[:4]) * 12 + int(pc[4:6])) < today_m
    flags = []
    if trunc: flags.append(f"TRUNC(cal->{cal_end.date() if cal_end is not None else '?'})")
    if carry_eq: flags.append("CARRY=PRICE")
    if stale: flags.append("STALE")
    if c in diverged: flags.append("diverged")
    rows.append(dict(inst=c, cal_end=str(cal_end.date()) if cal_end is not None else "MISSING",
                     adj_end=str(ae.date()) if ae is not None else "?",
                     priced=pc, carry=cc, cycle=rc.get("HoldRollCycle", "?"),
                     rolloff=rc.get("RollOffsetDays", "?"), carryoff=rc.get("CarryOffset", "?"),
                     flags=" ".join(flags)))

df = pd.DataFrame(rows).set_index("inst")
df.to_csv("private/roll_calendar_audit.csv")
prob = df[df["flags"] != ""]
print(f"ROLL AUDIT: {len(our)} instruments, freshest data {fresh.date()}. Divergences from Rob: "
      f"{sorted(diverged & set(our))}\n", flush=True)
print(f"=== {len(prob)} FLAGGED (of {len(our)}) ===")
print(prob[["cal_end", "adj_end", "priced", "carry", "cycle", "rolloff", "flags"]].to_string() if len(prob)
      else "  (none)")
print(f"\ncounts: TRUNCATED={df['flags'].str.contains('TRUNC').sum()} "
      f"CARRY=PRICE={df['flags'].str.contains('CARRY=PRICE').sum()} "
      f"STALE={df['flags'].str.contains('STALE').sum()} diverged={df['flags'].str.contains('diverged').sum()}")
print("saved -> private/roll_calendar_audit.csv", flush=True)
