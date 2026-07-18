"""SOFR (SR3) data repair via IB-tail splice.

CSI orphaned the deferred quarterly band 202309..203212 at 2023-04-14 (a vendor feed
artifact -- serial months + newer far quarterlies stay current, only this band froze).
IB has full daily history for every still-listed leg (202406+); expired legs IB purged
from secdef and can't be filled. This tool splices IB's post-freeze daily tail onto each
frozen contract so the normal CSI reingest rebuilds a CURRENT continuous series.

DELIBERATE, DOCUMENTED exception to the CSI-only-sim-DB rule, scoped to ONE instrument's
broken tail. CSI stays the historical base (deep pre-2020 history IB lacks); IB supplies
only 2023-04-17 -> today. Seam-verified: IB close on the freeze date must equal CSI's to
within SEAM_TOL, else the contract is skipped + flagged.

DURABILITY: the raw UA/Data/PST CSVs are csi-owned AND re-frozen on every csi_sync, so the
splice is NOT written there. Instead the post-freeze tails are stored in an ACTIVE repair
store (IB_REPAIR) that csi_sync_reingest.stage() overlays on EVERY sync -- so a re-frozen
vendor export can't undo the fix. See the _ib_repair_tail hook in csi_sync_reingest.py.

TWO-PHASE, sign-off respecting:
  report  -> pull IB, seam-check, write tails to an INACTIVE cache (hook can't see it). Inert.
  --rebuild -> ACTIVATE (copy cache -> IB_REPAIR) then call the real reingest(force_bootstrap):
               hooked stage() overlays the tails -> ingest -> bootstrap. This is the DB rebuild.

Usage:
  uv run python -m sysinit.futures.ib_sofr_splice            # REPORT: pull+cache+seam-check, nothing active
  uv run python -m sysinit.futures.ib_sofr_splice --rebuild  # HELD: activate repair store + reingest+bootstrap
  uv run python -m sysinit.futures.ib_sofr_splice --rebuild --use-cache   # rebuild from cached tails, no IB
"""
import os
import sys
import glob
import re
import shutil
import pandas as pd
from ib_async import IB, Future

PST = "SOFR"
CSI_SYM = "SR3"
UA_DIR = "private/data/futures/csi/UA/Data/PST"
CACHE = "private/data/futures/sofr_ib_repair"           # INACTIVE staging (hook does NOT read this)
IB_REPAIR = "private/data/futures/ib_repair_tails"      # ACTIVE store read by csi_sync_reingest.stage()
FREEZE_DATE = pd.Timestamp("2023-04-14")
SEAM_TOL = 0.03
IB_PORT = 4002
IB_CLIENTID = 79
COLS = ["date", "o", "h", "l", "c", "v"]

REBUILD = "--rebuild" in sys.argv
USE_CACHE = "--use-cache" in sys.argv


def read_ohlcv(path):
    return pd.read_csv(path, header=None, names=COLS, parse_dates=["date"]).sort_values("date").reset_index(drop=True)


def fmt_body(df):
    return "\n".join(
        f"{r['date'].strftime('%Y-%m-%d')},{r['o']:.8f},{r['h']:.8f},{r['l']:.8f},{r['c']:.8f},{int(round(r['v']))}"
        for _, r in df.iterrows()) + "\n"


def frozen_contracts():
    out = []
    for path in sorted(glob.glob(f"{UA_DIR}/{CSI_SYM}_*.csv")):
        m = re.search(rf"{CSI_SYM}_(\d{{6}})\.csv$", path)
        if not m:
            continue
        last = pd.read_csv(path, header=None, usecols=[0], names=["d"], parse_dates=["d"])["d"].max()
        if last == FREEZE_DATE:
            out.append(m.group(1))
    return out


def ib_tail(ib, ym):
    """IB daily rows with date >= FREEZE_DATE (incl. the seam row), or None if IB can't serve. Cached."""
    cache = f"{CACHE}/{PST}_{ym}.csv"
    if USE_CACHE and os.path.exists(cache):
        return read_ohlcv(cache)
    if ib is None:
        return None
    c = Future(symbol="SOFR3", lastTradeDateOrContractMonth=ym, multiplier="2500",
               exchange="CME", currency="USD", includeExpired=True)
    try:
        q = ib.qualifyContracts(c)
    except Exception:
        return None
    if not q or not getattr(q[0], "conId", 0):
        return None
    bars = ib.reqHistoricalData(q[0], endDateTime="", durationStr="8 Y", barSizeSetting="1 day",
                                whatToShow="TRADES", useRTH=False, formatDate=1)
    if not bars:
        return None
    df = pd.DataFrame([{"date": pd.Timestamp(b.date), "o": b.open, "h": b.high, "l": b.low,
                        "c": b.close, "v": b.volume} for b in bars])
    df = df[df["date"] >= FREEZE_DATE].sort_values("date").reset_index(drop=True)
    os.makedirs(CACHE, exist_ok=True)
    open(cache, "w").write(fmt_body(df))
    return df


def build_plan(ib):
    frozen = frozen_contracts()
    rows, ok_yms = [], []
    for ym in frozen:
        csi = read_ohlcv(f"{UA_DIR}/{CSI_SYM}_{ym}.csv")
        csi_last = csi["date"].max()
        csi_close = float(csi.iloc[-1]["c"])
        tail = ib_tail(ib, ym)
        if tail is None:
            rows.append((ym, len(csi), None, None, None, "UNAVAILABLE (expired/no-secdef)")); continue
        seam = tail[tail["date"] == csi_last]
        if len(seam) == 0:
            rows.append((ym, len(csi), 0, None, None, "SKIP (IB lacks freeze date)")); continue
        diff = abs(float(seam.iloc[0]["c"]) - csi_close)
        new = tail[tail["date"] > csi_last]
        if diff > SEAM_TOL:
            rows.append((ym, len(csi), len(new), diff, None, f"FLAG seam {diff:.3f}>{SEAM_TOL}")); continue
        ok_yms.append(ym)
        rows.append((ym, len(csi), len(new), diff, new["date"].max().date(), "ok"))
    return rows, ok_yms, frozen


def report(rows):
    print(f"\n{'contract':>9} | {'csi':>5} | {'ib_tail':>7} | {'seam':>7} | {'new_last':>10} | status")
    print("-" * 74)
    sp = un = fl = 0
    for ym, csi_n, tail_n, diff, newlast, status in rows:
        d = f"{diff:.4f}" if diff is not None else "--"
        t = str(tail_n) if tail_n is not None else "--"
        nl = str(newlast) if newlast else "--"
        print(f"{ym:>9} | {csi_n:>5} | {t:>7} | {d:>7} | {nl:>10} | {status}")
        if status == "ok": sp += 1
        elif status.startswith("UNAVAILABLE"): un += 1
        else: fl += 1
    print("-" * 74)
    print(f"spliceable: {sp}   unavailable(expired): {un}   flagged/skip: {fl}")
    return sp


def activate(ok_yms):
    """Promote cached tails -> ACTIVE IB_REPAIR store (what stage() overlays). Idempotent."""
    os.makedirs(IB_REPAIR, exist_ok=True)
    n = 0
    for ym in ok_yms:
        src = f"{CACHE}/{PST}_{ym}.csv"
        if os.path.exists(src):
            shutil.copy2(src, f"{IB_REPAIR}/{PST}_{ym}.csv"); n += 1
    return n


def do_rebuild():
    """Call the REAL reingest with force_bootstrap; the hooked stage() overlays IB_REPAIR automatically."""
    from sysdata.data_blob import dataBlob
    from sysproduction.data.prices import diagPrices
    from sysinit.futures.csi_sync_reingest import reingest
    data = dataBlob(); dp = diagPrices(data)
    tag = reingest(PST, data, dp, force_bootstrap=True)
    print(f"  reingest outcome: {tag}")


def main():
    os.makedirs(CACHE, exist_ok=True)
    ib = None
    if not (USE_CACHE and all(os.path.exists(f"{CACHE}/{PST}_{ym}.csv") for ym in frozen_contracts())):
        ib = IB(); ib.connect("127.0.0.1", IB_PORT, clientId=IB_CLIENTID, timeout=15)
    try:
        rows, ok_yms, frozen = build_plan(ib)
    finally:
        if ib is not None:
            ib.disconnect()
    report(rows)

    if not REBUILD:
        print(f"\nREPORT ONLY. Tails cached (INACTIVE) in {CACHE}/ . Repair store {IB_REPAIR}/ untouched -> hook is a no-op.")
        print("On sign-off:  uv run python -m sysinit.futures.ib_sofr_splice --rebuild --use-cache")
        return

    n = activate(ok_yms)
    print(f"\n--rebuild: ACTIVATED {n} repair tails -> {IB_REPAIR}/ . Running real reingest(force_bootstrap) ...")
    do_rebuild()
    print("\nDONE. Verify: roll_calendar_audit | grep SOFR ; adjusted-price max gap normal. Then re-include SOFR.")


if __name__ == "__main__":
    main()
