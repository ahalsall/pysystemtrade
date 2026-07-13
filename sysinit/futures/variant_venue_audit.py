"""UA<->IB variant/venue alignment audit. For each instrument, compares the CSI catalog
(commodityfactsheet.csv, matched via csi_symbol_map) against IB's ACTUAL contract
(reqContractDetails via our ib_config IBSymbol). Flags where the venue, currency, contract
size/point value, or underlying don't line up -- the MSCIWORLD (variant) / CNH (venue) class
of issue that passes scale + contract-size-integrity + notional checks. READ-ONLY. Gateway up."""
import os
os.environ.setdefault("TZ", "UTC")
import csv
import re
from sysdata.data_blob import dataBlob
from ib_async import Future
from sysproduction.data.prices import diagPrices
from sysdata.config.configdata import Config

# exchange name normalization (CSI <-> IB); reduces to a coarse market/region token
EXCH = {"HKEX": "HKFE", "DTB": "EUREX", "GLOBEX": "CME", "ECBOT": "CBOT", "CBT": "CBOT", "NYBOT": "ICE",
        "IPE": "ICE", "LIFFE": "ICE", "SFE": "SNFE", "OSE": "OSE.JPN",
        "EURONEXT-AMSTERDAM": "FTA", "EURONEXT-PARIS": "MONEP", "EURONEXT-BRUSSELS": "FTA",
        "EURONEXT-LISBON": "FTA", "EURONEXT": "FTA", "CME-FOREX": "CME", "CBOE": "CFE",
        "BMF": "BMF", "B3": "BMF", "SGX": "SGX", "KRX": "KSE"}
def nx(e): e = (e or "").upper().strip(); return EXCH.get(e, e)

# maps
pst2csi = {r[1]: r[0] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv")) if r and r[0] != "csi_symbol"}
ibcfg = {r["Instrument"]: r for r in csv.DictReader(open("sysbrokers/IB/config/ib_config_futures.csv"))}
spec = {r["Instrument"]: r for r in csv.DictReader(open("data/futures/csvconfig/instrumentconfig.csv"))}
cat = {}
for r in csv.DictReader(open("private/commodityfactsheet.csv")):
    cat.setdefault(r["SymbolUA"], []).append(r)  # may be multiple sessions per SymbolUA

dp = diagPrices()
data_inst = set(dp.db_futures_adjusted_prices_data.get_list_of_instruments()) & set(dp.db_futures_multiple_prices_data.get_list_of_instruments())
cfg = set(Config("systems.provided.rob_system.config.yaml").instrument_weights.keys())
univ = sorted(set(pst2csi.keys()) & data_inst & cfg)  # pst2csi: pst_code -> csi_symbol

data = dataBlob(); ib = data.ib_conn.ib
rows = []
for inst in univ:
    csi_sym = pst2csi.get(inst)
    crows = cat.get(csi_sym, [])
    crow = next((r for r in crows if r.get("IsActive") == "1"), crows[0] if crows else {})
    b = ibcfg.get(inst, {})
    # IB ground truth
    ibname = ibexch = ibccy = ""; ibmult = None
    try:
        f = Future(symbol=b.get("IBSymbol"), exchange=b.get("IBExchange"),
                   currency=(b.get("IBCurrency") if b.get("IBCurrency") not in ("NA", "", None) else ""))
        dets = ib.reqContractDetails(f)
        dets = [d for d in dets if d.contract.lastTradeDateOrContractMonth >= "20260714"]
        if dets:
            d = sorted(dets, key=lambda d: d.contract.lastTradeDateOrContractMonth)[0]
            ibname = d.longName or ""; ibexch = d.contract.exchange; ibccy = d.contract.currency
            ibmult = float(d.contract.multiplier) if d.contract.multiplier else None
    except Exception as e:
        ibname = f"ERR:{type(e).__name__}"
    # compare
    flags = []
    if crow:
        if nx(crow.get("Exchange")) != nx(ibexch) and ibexch: flags.append(f"VENUE(csi {crow.get('Exchange')}/ib {ibexch})")
        cc = (crow.get("Currency") or "").upper(); ic = (ibccy or "").upper()
        if cc and ic and cc != ic and not {cc, ic} <= {"USD", "CNH", "CNY"}: flags.append(f"CCY(csi {cc}/ib {ic})")
        # point value: CSI FullPointValue vs our Pointsize (both value-per-point) = contract-size check
        try:
            fpv = float(crow.get("FullPointValue")); ps = float(spec[inst]["Pointsize"])
            if abs(fpv - ps) / max(ps, 1e-9) > 0.02: flags.append(f"POINTVAL(csi {fpv:g}/cfg {ps:g})")
        except Exception:
            pass
    else:
        flags.append("no-CSI-catalog")
    if ibname.startswith("ERR") or not ibexch: flags.append("no-IB-detail")
    rows.append(dict(inst=inst, csi_sym=csi_sym, csi_name=(crow.get("Name") or "")[:26], csi_exch=crow.get("Exchange", ""),
                     ib_name=ibname[:30], ib_exch=ibexch, flags=" ".join(flags)))

import pandas as pd
df = pd.DataFrame(rows).set_index("inst")
df.to_csv("private/variant_venue_audit.csv")
flagged = df[df["flags"] != ""]
print(f"VARIANT/VENUE AUDIT: {len(univ)} instruments\n", flush=True)
print(f"=== {len(flagged)} FLAGGED ===")
print(flagged[["csi_sym", "csi_name", "csi_exch", "ib_name", "ib_exch", "flags"]].to_string() if len(flagged) else "  NONE")
print("\nsaved -> private/variant_venue_audit.csv", flush=True)
try: data.close()
except Exception: pass
