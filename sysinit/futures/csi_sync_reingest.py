"""Selective CSI sync — INCREMENTAL, roll-calendar-free.

After Unfair Advantage syncs fresh data into the raw CSI export dir (private/data/futures/csi/,
incl. UA/Data/PST/), this keeps the sim DB in step WITHOUT regenerating roll calendars.

WHY (the whole point of the 2026-07-15 redesign): the old version re-ran
build_and_write_roll_calendar per instrument on every sync -- i.e. the BATCH roll-calendar
generation that data.md:271 explicitly warns is "careful craftsmanship, not suited to a batch
process", and which drops the calendar's last row (adjust_to_price_series) -> strands the priced
contract -> the roll-stuck bug, needing fix_stuck_rolls to patch every time. Rob is blunt in his
rolling blog: "I don't think you can fully automate the process of rolling... it needs a lot of
human judgement." So this tool now mirrors pysystemtrade's PRODUCTION daily path
(update_multiple_adjusted_prices_for_instrument): read the current PRICE/FORWARD/CARRY contracts
from the last row of existing multiple prices, fetch fresh prices for JUST those contracts, and
APPEND -- no roll calendar involved. update_with_multiple_prices_no_roll refuses (raises) rather
than corrupt if a roll is detected. Rolling itself stays a SEPARATE, deliberate step
(sysinit.futures.fix_stuck_rolls, run on review) -- never batched into the daily sync.

Per instrument:
  - HAS existing multiple prices  -> ingest fresh contract prices, then INCREMENTAL append
                                     (multiple + adjusted) via the framework. No roll calendar.
  - FIRST ingest (no multiple pr) -> BOOTSTRAP: build the roll calendar ONCE (legit single-
                                     instrument use) + multiple + adjusted. Flagged for a roll review.
  - roll detected in source data  -> reported as ROLL-NEEDED (run fix_stuck_rolls); NOT auto-rebuilt.

USAGE:
  uv run python -m sysinit.futures.csi_sync_reingest BOBL KR10     # explicit
  uv run python -m sysinit.futures.csi_sync_reingest --auto        # detect & sync all behind
  uv run python -m sysinit.futures.csi_sync_reingest --diff        # just report what's behind
  uv run python -m sysinit.futures.csi_sync_reingest --auto --dry  # report the plan, do nothing
"""
import os
import re
import sys
import glob
import csv as _csv

from syscore.fileutils import get_resolved_pathname
from sysinit.futures.csi_pipeline import (
    CSI_CONFIG, CSI_HEADER, DEFAULT_ROLL_CALENDAR_PATH, PRICE_SCALE, csi_config_for as _config_for,
    init_db_with_split_freq_csv_prices_for_code, build_and_write_roll_calendar,
    process_multiple_prices_single_instrument, process_adjusted_prices_single_instrument,
    _dedupe_roll_calendar_csv,
)

UA_DIR = "private/data/futures/csi/UA/Data/PST"
STAGED = get_resolved_pathname("private.data.futures.csi_ingest")
RCP = DEFAULT_ROLL_CALENDAR_PATH
PST2CSI = {r[1]: r[0] for r in _csv.reader(open("private/data/futures/csi_symbol_map.csv"))
           if r and r[0] != "csi_symbol"}


def raw_files(csi_sym):
    return {re.search(r"_(\d{6})\.csv$", f).group(1): f
            for f in glob.glob(f"{UA_DIR}/{csi_sym}_*.csv") if re.search(r"_(\d{6})\.csv$", f)}


def staged_months(pst):
    return {re.search(r"_(\d{6})00\.csv$", f).group(1)
            for f in glob.glob(f"{STAGED}/Day_{pst}_*.csv") if re.search(r"_(\d{6})00\.csv$", f)}


def raw_last_date(csi_sym, yyyymm):
    """Last data date in a raw contract file (cheap: read last non-empty line)."""
    try:
        rows = [ln for ln in open(f"{UA_DIR}/{csi_sym}_{yyyymm}.csv").read().splitlines() if ln.strip()]
        return rows[-1].split(",")[0] if rows and not rows[-1].lower().startswith("time,") else None
    except Exception:
        return None


# cache of DB adjusted last-date per instrument, filled once per run
_DB_ADJ = {}
def db_adj_last(pst, dp):
    if pst not in _DB_ADJ:
        try:
            _DB_ADJ[pst] = str(dp.db_futures_adjusted_prices_data.get_adjusted_prices(pst).dropna().index[-1].date())
        except Exception:
            _DB_ADJ[pst] = None
    return _DB_ADJ[pst]


def stage(pst, csi_sym):
    """Stage all raw contract files for one instrument into csi_ingest (idempotent)."""
    os.makedirs(STAGED, exist_ok=True)
    n = 0
    for yyyymm, src in raw_files(csi_sym).items():
        dst = os.path.join(STAGED, f"Day_{pst}_{yyyymm}00.csv")
        body = open(src).read()
        header = "" if body.lstrip().lower().startswith("time,") else CSI_HEADER
        open(dst, "w").write(header + body)
        n += 1
    return n


def diff():
    """Full daily diff: for every mapped instrument, compare the raw CSI export to the DB and
    flag what needs syncing. Two independent triggers:
      NEW-CONTRACT : raw has a newer front contract than the DB (a roll may be due -- review)
      NEW-ROWS     : raw's newest contract has data beyond the DB's adjusted last date (daily refresh)
    Returns list of dicts. Cheap: last-line reads for raw, one adjusted read per instrument."""
    from sysproduction.data.prices import diagPrices
    dp = diagPrices()
    out = []
    for pst, csi_sym in sorted(PST2CSI.items()):
        rf = raw_files(csi_sym)
        if not rf:
            continue
        raw_new = max(rf)
        db_c = db_state_contract(pst, dp)
        rld = raw_last_date(csi_sym, raw_new)
        dbld = db_adj_last(pst, dp)
        reasons = []
        if db_c is None or raw_new > db_c:
            reasons.append(f"NEW-CONTRACT({db_c}->{raw_new})")
        if rld and dbld and rld > dbld:
            reasons.append(f"NEW-ROWS({dbld}->{rld})")
        if reasons:
            out.append(dict(pst=pst, csi=csi_sym, raw_contract=raw_new, db_contract=db_c,
                            raw_last=rld, db_last=dbld, reasons=" ".join(reasons)))
    return out


_DB_C = {}
def db_state_contract(pst, dp):
    """Newest contract with price data in the DB (cheap-ish, cached)."""
    if pst not in _DB_C:
        try:
            cs = sorted(str(c) for c in dp.contract_dates_with_price_data_for_instrument_code(pst))
            _DB_C[pst] = cs[-1][:6] if cs else None
        except Exception:
            _DB_C[pst] = None
    return _DB_C[pst]


def has_multiple_prices(pst, dp):
    """True if the instrument already has a multiple-prices series (so we can append incrementally)."""
    try:
        mp = dp.get_multiple_prices(pst)
        return mp is not None and len(mp) > 0
    except Exception:
        return False


def _bootstrap(pst):
    """FIRST-ingest only: build the roll calendar ONCE (the legitimate single-instrument use of
    build_and_write_roll_calendar) + multiple + adjusted. The batch generator drops the last roll,
    so a fix_stuck_rolls review must follow -- reported by main()."""
    build_and_write_roll_calendar(pst, output_datapath=RCP, write=True, check_before_writing=False)
    _dedupe_roll_calendar_csv(pst, RCP)
    process_multiple_prices_single_instrument(pst, csv_roll_data_path=RCP, ADD_TO_DB=True, ADD_TO_CSV=False)
    process_adjusted_prices_single_instrument(pst, ADD_TO_DB=True, ADD_TO_CSV=False)


def reingest(pst, data, dp, force_bootstrap=False):
    """Sync one instrument. Returns an outcome tag: incremental | bootstrap | roll-needed | skipped-*.

    force_bootstrap (--bootstrap): deliberate from-scratch rebuild -- for a stale/gapped instrument
    whose DB is years behind the raw data, where the incremental append can't bridge the gap. This is
    the legitimate single-instrument use of build_and_write_roll_calendar (data.md sanctions it for
    from-scratch/craftsmanship); the batch gen drops the last roll, so a fix_stuck_rolls review follows.
    """
    from sysproduction.update_multiple_adjusted_prices import update_multiple_adjusted_prices_for_instrument
    csi_sym = PST2CSI.get(pst)
    if not csi_sym:
        print(f"  {pst}: no CSI symbol mapping", flush=True); return "skipped-no-map"
    if not raw_files(csi_sym):
        print(f"  {pst} ({csi_sym}): no raw files in {UA_DIR}", flush=True); return "skipped-no-raw"
    # 1. ingest fresh CSI contract prices into the per-contract store (append; scale/inverse applied)
    staged = stage(pst, csi_sym)
    init_db_with_split_freq_csv_prices_for_code(
        pst, get_resolved_pathname("private.data.futures.csi_ingest"), csv_config=_config_for(pst))
    # 2. extend multiple + adjusted
    if force_bootstrap or not has_multiple_prices(pst, dp):
        _bootstrap(pst)
        why = "forced" if force_bootstrap else "first ingest"
        print(f"  {pst}: +{staged} contract files -> BOOTSTRAP ({why}; roll calendar built once)", flush=True)
        return "bootstrap"
    try:
        update_multiple_adjusted_prices_for_instrument(pst, data)  # INCREMENTAL, no roll calendar
        print(f"  {pst}: +{staged} contract files -> incremental append (no roll calendar)", flush=True)
        return "incremental"
    except Exception as e:
        msg = str(e)
        if "roll" in msg.lower():
            print(f"  {pst}: ROLL-NEEDED -- roll present in source but not registered; "
                  f"run fix_stuck_rolls to advance (append not done)", flush=True)
            return "roll-needed"
        print(f"  {pst}: incremental FAILED ({type(e).__name__}: {msg[:70]})", flush=True)
        return "error"


def validate(pst, dp):
    mp = dp.db_futures_multiple_prices_data.get_multiple_prices(pst)
    adj = dp.db_futures_adjusted_prices_data.get_adjusted_prices(pst).dropna()
    print(f"    {pst}: priced={mp['PRICE_CONTRACT'].iloc[-1]} fwd={mp['FORWARD_CONTRACT'].iloc[-1]} "
          f"| adj last non-NaN {adj.index[-1].date()}", flush=True)


def main():
    from sysdata.data_blob import dataBlob
    from sysproduction.data.prices import diagPrices
    args = [a for a in sys.argv[1:]]
    dry = "--dry" in args
    force_bootstrap = "--bootstrap" in args
    args = [a for a in args if not a.startswith("--")]
    if "--auto" in sys.argv or "--diff" in sys.argv:
        det = diff()
        print(f"DIFF: {len(det)} instrument(s) behind (raw CSI ahead of DB):")
        for d in det:
            print(f"  {d['pst']:<14} {d['reasons']}")
        codes = [d["pst"] for d in det]
        if "--diff" in sys.argv:
            print(f"\n(diff-only; {len(codes)} would be synced) codes: {codes}")
            return
    else:
        codes = args
    if not codes:
        print("nothing to do"); return
    if dry:
        print("dry-run: would sync", codes); return

    mode = "FORCED BOOTSTRAP (from-scratch rebuild)" if force_bootstrap \
        else "incremental append; no roll-calendar regeneration"
    print(f"\nSyncing {len(codes)} ({mode}): {codes}\n", flush=True)
    data = dataBlob()
    dp = diagPrices(data)
    outcomes = {}
    done = []
    for c in codes:
        tag = reingest(c, data, dp, force_bootstrap=force_bootstrap)
        outcomes.setdefault(tag, []).append(c)
        if tag in ("incremental", "bootstrap"):
            done.append(c)

    print("\nvalidation:", flush=True)
    for c in done:
        try:
            validate(c, dp)
        except Exception as e:
            print(f"    {c}: validate err {e}")

    print("\nSUMMARY:", flush=True)
    for tag, cs in sorted(outcomes.items()):
        print(f"  {tag:<14} {len(cs)}: {cs}", flush=True)
    roll_review = outcomes.get("bootstrap", []) + outcomes.get("roll-needed", [])
    if roll_review:
        print(f"\n>>> ROLL REVIEW NEEDED for {len(roll_review)} instrument(s) (bootstrap drops the last roll,"
              f" or a roll is due). Run the deliberate roll step:", flush=True)
        print(f"    uv run python -m sysinit.futures.fix_stuck_rolls {' '.join(roll_review)}", flush=True)


if __name__ == "__main__":
    main()
