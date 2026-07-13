"""Selective CSI re-ingest workflow.

After Unfair Advantage syncs fresh data into the raw CSI export dir (private/data/futures/csi/,
incl. UA/Data/PST/), this keeps the sim DB in step WITHOUT a full rebuild:
  1. stage only the target instruments' raw contract files into csi_ingest
     (<CSISYM>_<YYYYMM>.csv  ->  Day_<PST>_<YYYYMM>00.csv, prepending the CSI header)
  2. re-ingest contract prices + rebuild roll calendar -> multiple -> adjusted for each
  3. validate: report new priced contract + last non-NaN adjusted date

--auto detects instruments whose raw export has a NEWER front contract than the DB (the
roll-advancing / forward-coverage case, e.g. a new Dec contract appeared) and re-ingests those.

USAGE:
  uv run python -m sysinit.futures.csi_sync_reingest BOBL KR10     # explicit
  uv run python -m sysinit.futures.csi_sync_reingest --auto        # detect & fix all stale
  uv run python -m sysinit.futures.csi_sync_reingest --auto --dry  # just report what it would do
"""
import os
import re
import sys
import glob
import csv as _csv

from syscore.fileutils import get_resolved_pathname
from sysinit.futures.csi_pipeline import (
    CSI_CONFIG, CSI_HEADER, DEFAULT_ROLL_CALENDAR_PATH,
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
    flag what needs re-ingesting. Two independent triggers:
      NEW-CONTRACT : raw has a newer front contract than the DB (roll-advancing / forward coverage)
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


def reingest(pst):
    csi_sym = PST2CSI.get(pst)
    if not csi_sym:
        print(f"  {pst}: no CSI symbol mapping", flush=True); return False
    if not raw_files(csi_sym):
        print(f"  {pst} ({csi_sym}): no raw files in {UA_DIR}", flush=True); return False
    staged = stage(pst, csi_sym)
    init_db_with_split_freq_csv_prices_for_code(pst, get_resolved_pathname("private.data.futures.csi_ingest"),
                                                csv_config=CSI_CONFIG)
    build_and_write_roll_calendar(pst, output_datapath=RCP, write=True, check_before_writing=False)
    _dedupe_roll_calendar_csv(pst, RCP)
    process_multiple_prices_single_instrument(pst, csv_roll_data_path=RCP, ADD_TO_DB=True, ADD_TO_CSV=False)
    process_adjusted_prices_single_instrument(pst, ADD_TO_DB=True, ADD_TO_CSV=False)
    print(f"  {pst}: staged {staged} contract files, re-ingested + rebuilt", flush=True)
    return True


def validate(pst):
    from sysproduction.data.prices import diagPrices
    dp = diagPrices()
    mp = dp.db_futures_multiple_prices_data.get_multiple_prices(pst)
    adj = dp.db_futures_adjusted_prices_data.get_adjusted_prices(pst).dropna()
    print(f"    {pst}: priced={mp['PRICE_CONTRACT'].iloc[-1]} fwd={mp['FORWARD_CONTRACT'].iloc[-1]} "
          f"| adj last non-NaN {adj.index[-1].date()}", flush=True)


def main():
    args = [a for a in sys.argv[1:]]
    dry = "--dry" in args
    args = [a for a in args if not a.startswith("--")]
    if "--auto" in sys.argv or "--diff" in sys.argv:
        det = diff()
        print(f"DIFF: {len(det)} instrument(s) need re-ingest (raw CSI ahead of DB):")
        for d in det:
            print(f"  {d['pst']:<14} {d['reasons']}")
        codes = [d["pst"] for d in det]
        if "--diff" in sys.argv:
            print(f"\n(diff-only; {len(codes)} would be re-ingested) codes: {codes}")
            return
    else:
        codes = args
    if not codes:
        print("nothing to do"); return
    if dry:
        print("dry-run: would re-ingest", codes); return
    print(f"\nRe-ingesting {len(codes)}: {codes}\n", flush=True)
    done = [c for c in codes if reingest(c)]
    print("\nvalidation:", flush=True)
    for c in done:
        try: validate(c)
        except Exception as e: print(f"    {c}: validate err {e}")
    print(f"\nDONE: {len(done)}/{len(codes)} re-ingested", flush=True)


if __name__ == "__main__":
    main()
