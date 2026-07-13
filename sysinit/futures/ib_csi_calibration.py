"""Calibrate CSI stored prices/volumes against IB ground truth (Gateway up; off-hours OK -- uses
historical daily bars, not live quotes). For each instrument: pick the current front contract,
fetch IB's recent daily close + avg volume, compare to CSI's stored values.

pysystemtrade Pointsizes are calibrated to IB's price convention, so CSI stored SHOULD equal IB
stored. price_ratio = IB/CSI: ~1.0 = consistent; ~0.01 = CSI is 100x too big (cents vs dollars);
etc. The ratio becomes the per-instrument CSI scale correction (the 'coordinating config').
Also reports volume_ratio (the requested IB-vs-CSI volume consistency check). READ-ONLY."""
import os
os.environ.setdefault("TZ", "UTC")
import sys
import numpy as np
import pandas as pd
from sysdata.data_blob import dataBlob
from sysproduction.data.prices import diagPrices
from sysproduction.data.broker import dataBroker
from sysobjects.contracts import futuresContract
from syscore.dateutils import DAILY_PRICE_FREQ

INSTR = sys.argv[1:] or ["COTTON", "SILVER", "JPY", "CNH", "CORN", "WHEAT", "SOYBEAN", "SUGAR11", "BUND", "SP500_micro"]
data = dataBlob(); dp = diagPrices(data); broker = dataBroker(data)


def front_contract(inst):
    cds = sorted(str(c) for c in dp.contract_dates_with_price_data_for_instrument_code(inst))
    ref = 0
    try:
        mp = dp.db_futures_multiple_prices_data.get_multiple_prices(inst)
        # prefer the current forward (liquid) contract label
        ref = str(mp["FORWARD_CONTRACT"].iloc[-1])
    except Exception:
        pass
    return ref if ref in cds else (cds[-2] if len(cds) >= 2 else cds[-1])


print(f"{'inst':<12}{'contract':<10}{'CSI_px':>12}{'IB_px':>12}{'px_ratio':>10}{'CSI_vol':>10}{'IB_vol':>10}{'v_ratio':>9}  verdict", flush=True)
rows = []
for inst in INSTR:
    try:
        cd = front_contract(inst)
        c = futuresContract(inst, cd)
        csi = dp.get_merged_prices_for_contract_object(c)
        csi_px = float(csi["FINAL"].dropna().iloc[-1]); csi_vol = float(csi.daily_volumes().tail(20).mean())
        ib = broker.get_prices_at_frequency_for_contract_object(c, DAILY_PRICE_FREQ)
        ib_px = float(ib["FINAL"].dropna().iloc[-1]); ib_vol = float(ib.daily_volumes().tail(20).mean())
        pr = ib_px / csi_px if csi_px else np.nan
        vr = ib_vol / csi_vol if csi_vol else np.nan
        # verdict on price scale
        if 0.95 <= pr <= 1.05: verdict = "OK"
        elif 0.009 <= pr <= 0.011: verdict = "CSI x100 -> scale 0.01"
        elif 90 <= pr <= 110: verdict = "CSI /100 -> scale 100"
        else: verdict = f"MISMATCH x{1/pr:.3g}" if pr else "?"
        print(f"{inst:<12}{cd:<10}{csi_px:>12.4f}{ib_px:>12.4f}{pr:>10.4f}{csi_vol:>10,.0f}{ib_vol:>10,.0f}{vr:>9.2f}  {verdict}", flush=True)
        rows.append(dict(inst=inst, contract=cd, csi_px=csi_px, ib_px=ib_px, px_ratio=pr,
                         csi_vol=csi_vol, ib_vol=ib_vol, vol_ratio=vr, verdict=verdict))
        import time; time.sleep(8)
    except Exception as e:
        print(f"{inst:<12}{'?':<10} ERR {type(e).__name__}: {str(e)[:50]}", flush=True)
try:
    data.close()
except Exception:
    pass
pd.DataFrame(rows).to_csv("private/ib_csi_calibration.csv", index=False)
print("\nsaved -> private/ib_csi_calibration.csv", flush=True)
