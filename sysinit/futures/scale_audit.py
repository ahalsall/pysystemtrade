"""Price-scale sanity audit (first pass, no Gateway). For each instrument computes the current
FRONT-contract price, implied notional (price x USD point size), and annualised %vol, then flags
scale outliers -- the SILVER-type bug (price 167x too big -> notional ~$6M) and the CNH-type
(deflated). Real futures notionals cluster ~$5k-$500k; %vol has sane per-asset bands. Flags are
heuristic -> confirm the flagged ones against IB (task #32)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import numpy as np
import pandas as pd
from sysdata.data_blob import dataBlob
from sysproduction.data.prices import diagPrices
from sysobjects.contracts import futuresContract
from sysproduction.reporting.data.risk import get_current_daily_stdev_for_instrument
from sysproduction.data.risk import get_base_currency_point_size_per_contract
from syscore.dateutils import ROOT_BDAYS_INYEAR
from sysdata.config.configdata import Config
from sysdata.sim.db_futures_sim_data import dbFuturesSimData

NOTIONAL_LO, NOTIONAL_HI = 3_000, 600_000     # sane futures notional band (USD)
VOL_LO, VOL_HI = 2.0, 90.0                     # sane annual %vol band
spec = {r["Instrument"]: r for r in csv.DictReader(open("data/futures/csvconfig/instrumentconfig.csv"))}

data = dataBlob(); dp = diagPrices(data)
adj = dp.db_futures_adjusted_prices_data; mpd = dp.db_futures_multiple_prices_data
data_inst = set(adj.get_list_of_instruments()) & set(mpd.get_list_of_instruments())
csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv")) if r and r[0] != "csi_symbol")
cfg = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
d = dbFuturesSimData()
last = {}
for c in csi & data_inst & cfg:
    try: last[c] = pd.Timestamp(d.get_raw_price(c).dropna().index[-1].date())
    except Exception: last[c] = pd.Timestamp("1900")
fresh = max(last.values()); our = sorted(c for c in csi & data_inst & cfg if (fresh - last[c]).days <= 45)
ref_m = fresh.year * 12 + fresh.month


def front_price(inst):
    cds = sorted(str(c) for c in dp.contract_dates_with_price_data_for_instrument_code(inst))
    near = [cd for cd in cds if -3 <= (int(cd[:4]) * 12 + int(cd[4:6]) - ref_m) <= 18] or cds[-3:]
    best_v, price = -1, np.nan
    for cd in near:
        try:
            p = dp.get_merged_prices_for_contract_object(futuresContract(inst, cd))
            v = float(p.daily_volumes().tail(20).mean())
            fp = p["FINAL"].dropna()
            if v > best_v and len(fp):
                best_v, price = v, float(fp.iloc[-1])
        except Exception:
            pass
    return price


rows = []
for inst in our:
    try:
        price = front_price(inst)
        psize = get_base_currency_point_size_per_contract(data, inst)
        notional = price * psize
        dstd = get_current_daily_stdev_for_instrument(data, inst)
        volpct = dstd / price * ROOT_BDAYS_INYEAR * 100 if price else np.nan
        flags = []
        if not np.isnan(notional) and (notional < NOTIONAL_LO or notional > NOTIONAL_HI):
            flags.append(f"NOTIONAL(${notional:,.0f})")
        if not np.isnan(volpct) and (volpct < VOL_LO or volpct > VOL_HI):
            flags.append(f"VOL({volpct:.0f}%)")
        rows.append(dict(inst=inst, asset=spec.get(inst, {}).get("AssetClass", "?"),
                         price=round(price, 2), pt_usd=round(psize, 2), notional=round(notional, 0),
                         volpct=round(volpct, 1), flag=" ".join(flags)))
    except Exception as e:
        rows.append(dict(inst=inst, asset="?", price=np.nan, pt_usd=np.nan, notional=np.nan,
                         volpct=np.nan, flag=f"ERR:{type(e).__name__}"))

df = pd.DataFrame(rows).set_index("inst").sort_values("notional", ascending=False)
df.to_csv("private/scale_audit.csv")
flagged = df[df["flag"] != ""]
print(f"SCALE AUDIT ({len(our)} instruments). Sane bands: notional ${NOTIONAL_LO:,}-${NOTIONAL_HI:,}, "
      f"vol {VOL_LO}-{VOL_HI}%\n", flush=True)
print(f"=== {len(flagged)} FLAGGED for review / IB cross-check ===")
print(flagged[["asset", "price", "pt_usd", "notional", "volpct", "flag"]].to_string())
print(f"\n=== highest notional (top 8, sanity) ===")
print(df.head(8)[["asset", "price", "pt_usd", "notional", "volpct"]].to_string())
print(f"\n=== lowest notional (bottom 8) ===")
print(df.tail(8)[["asset", "price", "pt_usd", "notional", "volpct"]].to_string())
print("\nsaved -> private/scale_audit.csv", flush=True)
