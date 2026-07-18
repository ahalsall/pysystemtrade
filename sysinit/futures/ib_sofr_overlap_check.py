"""READ-ONLY: verify IB's SOFR contract data matches CSI's in the pre-freeze overlap
window (so an IB tail would stitch cleanly onto the CSI history -- same contract, same
units, same prices). Compares closes on shared dates. Nothing written.

Usage: uv run python -m sysinit.futures.ib_sofr_overlap_check
"""
import pandas as pd
from ib_async import IB, Future

CSI_DIR = "private/data/futures/csi/UA/Data/PST"
CONTRACTS = ["202609", "202612", "202703"]

ib = IB()
ib.connect("127.0.0.1", 4002, clientId=78, timeout=15)

for ym in CONTRACTS:
    csi = pd.read_csv(f"{CSI_DIR}/SR3_{ym}.csv", header=None,
                      names=["date", "o", "h", "l", "c", "v"], parse_dates=["date"]).set_index("date")
    c = Future(symbol="SOFR3", lastTradeDateOrContractMonth=ym,
               multiplier="2500", exchange="CME", currency="USD")
    [q] = ib.qualifyContracts(c)
    bars = ib.reqHistoricalData(q, endDateTime="", durationStr="6 Y", barSizeSetting="1 day",
                                whatToShow="TRADES", useRTH=False, formatDate=1)
    ibdf = pd.DataFrame([{"date": pd.Timestamp(b.date), "c": b.close} for b in bars]).set_index("date")

    shared = csi.index.intersection(ibdf.index)
    if len(shared) == 0:
        print(f"{ym}: NO shared dates?!"); continue
    diff = (csi.loc[shared, "c"] - ibdf.loc[shared, "c"]).abs()
    print(f"\n=== SR3_{ym} ===")
    print(f"  CSI:  {csi.index.min().date()} -> {csi.index.max().date()}  ({len(csi)} rows)")
    print(f"  IB:   {ibdf.index.min().date()} -> {ibdf.index.max().date()}  ({len(ibdf)} rows)")
    print(f"  shared dates: {len(shared)}   max |close diff|: {diff.max():.4f}   mean: {diff.mean():.5f}")
    tail = csi.index.max()
    print(f"  CSI last close {tail.date()}: {csi.loc[tail,'c']:.4f}   IB same date: "
          f"{ibdf.loc[tail,'c']:.4f}" if tail in ibdf.index else f"  (IB has no {tail.date()})")
    beyond = ibdf.index[ibdf.index > tail]
    print(f"  IB rows BEYOND CSI freeze ({tail.date()}): {len(beyond)}  "
          f"-> {beyond.min().date()} .. {beyond.max().date()}" if len(beyond) else "  IB no rows beyond")

ib.disconnect()
print("\n(read-only; nothing written)")
