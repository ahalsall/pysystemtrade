"""Liquidity screen using pysystemtrade's OWN definition (sysproduction/reporting/data/constants.py):
   PASS requires BOTH:
     avg daily volume  >= 100 contracts        (MIN_VOLUME_CONTRACTS_DAILY)
     risk-$ volume      >= $1.5 million/day     (MIN_VOLUME_RISK_DAILY)
   where risk_$m = annual_risk_per_contract x avg_daily_contracts / 1e6,
         annual_risk_per_contract = daily_price_stdev x sqrt(256) x point_size_in_USD.
This normalizes across asset classes (a bond and a sector index with equal lot-counts carry
very different risk). Computed from our CSI data. Splits healthy(78) vs export-gap(28)."""
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

MIN_CONTRACTS = 100
MIN_RISK_M = 1.5
EXPORT_GAP = set("BONO BTP3 CH10 DJSTX-SMALL EU-AUTO EU-BANKS EU-BASIC EU-DIV30 EU-DJ-UTIL EU-HEALTH "
                 "EU-INSURE EU-OIL EU-TRAVEL NIKKEI400 R1000 SEK SMI-MID SP400 US-DISCRETE US-ENERGY "
                 "US-FINANCE US-HEALTH US-INDUSTRY US-MATERIAL US-PROPERTY US-STAPLES US-TECH US-UTILS".split())

data = dataBlob()
dp = diagPrices(data)
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
cutoff = fresh - pd.Timedelta(days=35)  # ~30 calendar days of recent volume


ref_m = fresh.year * 12 + fresh.month
def best_vol(inst):
    cds = sorted(str(c) for c in dp.contract_dates_with_price_data_for_instrument_code(inst))
    # scan CURRENTLY-LIQUID contracts (front +/- window), NOT the last-by-date (which for deep
    # forward curves are far-dated illiquid contracts). max recent-30d volume across them.
    near = [cd for cd in cds if -3 <= (int(cd[:4]) * 12 + int(cd[4:6]) - ref_m) <= 18]
    vols = []
    for cd in (near or cds[-5:]):
        try:
            dv = dp.get_merged_prices_for_contract_object(futuresContract(inst, cd)).daily_volumes()
            recent = dv[dv.index >= cutoff]
            v = float(recent.mean()) if len(recent) else np.nan
            if not np.isnan(v):
                vols.append(v)
        except Exception:
            pass
    return max(vols) if vols else np.nan


rows = []
for inst in our:
    try:
        vol = best_vol(inst)
        dstd = get_current_daily_stdev_for_instrument(data, inst)
        psize = get_base_currency_point_size_per_contract(data, inst)
        arpc = dstd * ROOT_BDAYS_INYEAR * psize
        riskm = arpc * vol / 1e6
        passes = (vol >= MIN_CONTRACTS) and (riskm >= MIN_RISK_M)
        rows.append(dict(inst=inst, contracts=round(vol, 0), risk_m=round(riskm, 2),
                         healthy=inst not in EXPORT_GAP, passes=passes))
    except Exception as e:
        rows.append(dict(inst=inst, contracts=np.nan, risk_m=np.nan,
                         healthy=inst not in EXPORT_GAP, passes=False))

df = pd.DataFrame(rows).set_index("inst").sort_values("risk_m", ascending=False)
df.to_csv("private/liquidity_screen.csv")
npass = int(df["passes"].sum()); nfail = int((~df["passes"]).sum())
print(f"LIQUIDITY SCREEN ({len(our)} instruments) — pysystemtrade thresholds: "
      f">={MIN_CONTRACTS} contracts/day AND >=${MIN_RISK_M}M risk/day\n", flush=True)
print(f"PASS {npass} / FAIL {nfail}\n", flush=True)
print("=== FAIL (below threshold — live-tradeability concern) ===")
fail = df[~df["passes"]]
print(fail.assign(why=[("contracts" if r.contracts < MIN_CONTRACTS else "") +
                       (" risk" if (not np.isnan(r.risk_m) and r.risk_m < MIN_RISK_M) else "") +
                       (" nodata" if np.isnan(r.contracts) else "")
                       for r in fail.itertuples()])[["contracts", "risk_m", "healthy", "why"]].to_string())
print(f"\n=== bottom of the PASS list (marginal) ===")
print(df[df["passes"]].tail(10)[["contracts", "risk_m", "healthy"]].to_string())
print(f"\nFAILs among the 78 HEALTHY (drop candidates): "
      f"{sorted(df[(~df['passes']) & (df['healthy'])].index.tolist())}")
print("saved -> private/liquidity_screen.csv", flush=True)
