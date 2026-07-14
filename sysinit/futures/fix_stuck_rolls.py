"""Un-stick instruments whose multiple prices are frozen on an expired PRICED contract because the
batch roll-calendar generator (build_roll_calendars.adjust_to_price_series) DROPS its last row --
leaving priced = second-to-last contract. Fine when there's a deep forward chain; for instruments
whose data ends at the current front, it strands the priced on the just-expired contract.

Per Rob's data.md ("you can add extra rolls ... if there would have been rolls since then"), the fix
is to append the missing recent roll (current=stuck priced, next=current front) to the roll calendar,
then rebuild multiple+adjusted. No forward/deferred contract needed -- the FRONT becomes priced and
its live prices flow into the forecast. Roll date placed inside the current+next price overlap.

USAGE: uv run python -m sysinit.futures.fix_stuck_rolls [INSTR ...]   (default: auto-detect stuck)"""
import os
import sys
import csv
import pandas as pd
from sysproduction.data.prices import diagPrices
from syscore.fileutils import get_resolved_pathname
from sysobjects.contracts import futuresContract
from sysinit.futures.csi_pipeline import DEFAULT_ROLL_CALENDAR_PATH, _dedupe_roll_calendar_csv
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import process_multiple_prices_single_instrument
from sysinit.futures.adjustedprices_from_db_multiple_to_db import process_adjusted_prices_single_instrument

dp = diagPrices()
roll = {r["Instrument"]: r for r in csv.DictReader(open("data/futures/csvconfig/rollconfig.csv"))}
RCP_DIR = get_resolved_pathname(DEFAULT_ROLL_CALENDAR_PATH)


def stuck_instruments():
    """priced-contract PRICE stale (>15d) while a fresher FORWARD contract exists = stuck roll."""
    out = []
    insts = set(dp.db_futures_multiple_prices_data.get_list_of_instruments())
    fresh = None
    lastp = {}
    for c in insts:
        try:
            lastp[c] = pd.Timestamp(dp.db_futures_multiple_prices_data.get_multiple_prices(c)["PRICE"].dropna().index[-1])
        except Exception:
            pass
    fresh = max(lastp.values())
    for c, lp in lastp.items():
        if (fresh - lp).days > 15:
            out.append(c)
    return sorted(out)


def fix(inst):
    mp = dp.db_futures_multiple_prices_data.get_multiple_prices(inst)
    priced = str(mp["PRICE_CONTRACT"].iloc[-1])       # stuck (expired) contract
    nxt = str(mp["FORWARD_CONTRACT"].iloc[-1])         # the current front we want priced
    # matching-price overlap of priced & next
    cp = dp.get_merged_prices_for_contract_object(futuresContract(inst, priced))["FINAL"].dropna()
    npx = dp.get_merged_prices_for_contract_object(futuresContract(inst, nxt))["FINAL"].dropna()
    ov = cp.index.intersection(npx.index)
    if len(ov) == 0:
        return f"{inst}: NO overlap between {priced}/{nxt} -> skip"
    roff = abs(int(roll.get(inst, {}).get("RollOffsetDays", -10)))
    ideal = cp.index[-1] - pd.Timedelta(days=roff)     # ~RollOffset before the priced contract's last data
    roll_date = ov[ov <= ideal][-1] if (ov <= ideal).any() else ov[-1]  # snap into the overlap
    carry = nxt  # CarryOffset=+1 pattern used by these (carry = next)
    rc_path = os.path.join(RCP_DIR, f"{inst}.csv")
    with open(rc_path, "a") as f:
        f.write(f"{roll_date.strftime('%Y-%m-%d')},{priced},{nxt},{carry}\n")
    _dedupe_roll_calendar_csv(inst, DEFAULT_ROLL_CALENDAR_PATH)
    process_multiple_prices_single_instrument(inst, csv_roll_data_path=DEFAULT_ROLL_CALENDAR_PATH,
                                              ADD_TO_DB=True, ADD_TO_CSV=False)
    process_adjusted_prices_single_instrument(inst, ADD_TO_DB=True, ADD_TO_CSV=False)
    # verify
    mp2 = dp.db_futures_multiple_prices_data.get_multiple_prices(inst)
    newpriced = str(mp2["PRICE_CONTRACT"].iloc[-1])
    lastreal = mp2["PRICE"].dropna().index[-1].date()
    ok = newpriced == nxt
    return f"{inst}: roll {roll_date.date()} {priced}->{nxt} | priced now {newpriced} PRICE fresh {lastreal} {'OK' if ok else 'STILL STUCK'}"


targets = sys.argv[1:] or stuck_instruments()
print(f"Fixing {len(targets)} stuck instruments\n", flush=True)
ok = 0
for inst in targets:
    try:
        msg = fix(inst)
        print("  " + msg, flush=True)
        if "OK" in msg:
            ok += 1
    except Exception as e:
        print(f"  {inst}: ERR {type(e).__name__}: {str(e)[:60]}", flush=True)
print(f"\n{ok}/{len(targets)} un-stuck", flush=True)
