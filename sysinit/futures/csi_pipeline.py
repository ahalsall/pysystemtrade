"""
CSI Data (Unfair Advantage) ingestion pipeline — deep-history source.

CSI/UA exports per-contract EOD CSVs named `<CSISYM>_<YYYYMM>.csv` (e.g.
AE_202411.csv) with columns Time,Open,High,Low,Close,Volume (ISO+tz timestamps) —
structurally identical to our barchart split-freq CSVs, just `Close` not `Latest`
and CSI symbol codes. CSI is daily/EOD, so files are ingested as Day_ frequency.

This module:
  1. renames CSI exports `<CSISYM>_<YYYYMM>.csv` -> `Day_<PSTCODE>_<YYYYMM00>.csv`
     into the CSI datapath, using CSI_SYMBOL_MAP;
  2. loads per-contract prices via the split-freq loader with CSI_CONFIG;
  3. builds roll calendar -> multiple -> adjusted (same stages as barchart_pipeline).

Wire UA (Windows VM) to auto-export into a synced folder, point --export-dir at it.
See notes/concepts/csi_setup_guide.md for the VM + shared-folder setup.

Usage:
  # rename raw CSI exports into the datapath, then process
  uv run python -m sysinit.futures.csi_pipeline --export-dir <raw_csi_dir> --rename
  uv run python -m sysinit.futures.csi_pipeline --instruments AEX,ALUMINUM
"""
import argparse
import os
import re

from sysdata.csv.csv_futures_contract_prices import ConfigCsvFuturesPrices
from syscore.fileutils import get_resolved_pathname
from sysinit.futures.contract_prices_from_split_freq_csv_to_db import (
    init_db_with_split_freq_csv_prices_for_code,
)
from sysinit.futures.rollcalendars_from_db_prices_to_csv import build_and_write_roll_calendar
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)

# CSI exports EOD; "Close" is the settle/close column, ISO timestamps (no %z needed).
CSI_CONFIG = ConfigCsvFuturesPrices(
    input_date_index_name="Time",
    input_skiprows=0,
    input_skipfooter=0,
    input_date_format="%Y-%m-%dT%H:%M:%S",
    input_column_mapping=dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    ),
)

# Raw CSI exports land in private/data/futures/csi/ (owned by the dedicated `csi`
# user that runs Unfair Advantage — read-only for us). We stage renamed files in an
# andrew-writable dir and process from there.
DEFAULT_EXPORT_DIR = "private.data.futures.csi"
DEFAULT_DATAPATH = "private.data.futures.csi_ingest"
DEFAULT_ROLL_CALENDAR_PATH = "private.data.futures.roll_calendars_csv"

# CSI symbol -> PST instrument code. SEED — extend to the full universe from CSI's
# symbol list (Unfair Advantage market list). Same code style as the legacy
# barchart market_map (sysinit/futures/barchart_futures_contract_prices.py).
CSI_SYMBOL_MAP = {
    "AE": "AEX",
    "AL": "ALUMINIUM",  # PST spelling is British (ALUMINIUM), CSI file used ALUMINUM
}

_CSI_RE = re.compile(r"^([A-Z0-9]+)_(\d{6})\.csv$")
# UA writes ISO timestamps with a timezone offset (e.g. 2024-08-19T05:00:00+0000).
# Strip the offset so timestamps are tz-naive: matches CSI_CONFIG's
# %Y-%m-%dT%H:%M:%S and the barchart data. A tz-aware index breaks PST's daily
# conversion downstream (same lesson as the barchart %z gotcha).
_TZ_OFFSET_RE = re.compile(r"(\dT\d{2}:\d{2}:\d{2})[+-]\d{4}")


def rename_csi_exports(export_dir: str, target_datapath: str):
    """Rename raw CSI `<SYM>_<YYYYMM>.csv` -> `Day_<PST>_<YYYYMM00>.csv` in datapath."""
    src = get_resolved_pathname(export_dir)
    dst = get_resolved_pathname(target_datapath)
    os.makedirs(dst, exist_ok=True)
    renamed, skipped = 0, []
    for fn in os.listdir(src):
        m = _CSI_RE.match(fn)
        if not m:
            continue
        sym, yyyymm = m.group(1), m.group(2)
        pst = CSI_SYMBOL_MAP.get(sym)
        if pst is None:
            skipped.append(sym)
            continue
        out = f"Day_{pst}_{yyyymm}00.csv"
        with open(os.path.join(src, fn)) as f_in:
            content = f_in.read()
        content = _TZ_OFFSET_RE.sub(r"\1", content)  # tz-aware -> tz-naive
        with open(os.path.join(dst, out), "w") as f_out:
            f_out.write(content)
        renamed += 1
    print(f"renamed {renamed} CSI files into {dst}")
    if skipped:
        print(f"  no CSI_SYMBOL_MAP entry for (skipped): {sorted(set(skipped))}")


def run_pipeline(instruments, datapath, roll_calendar_path):
    ok, fail = [], []
    for code in instruments:
        print("=" * 60, f"\nProcessing {code}")
        try:
            init_db_with_split_freq_csv_prices_for_code(code, datapath, csv_config=CSI_CONFIG)
            build_and_write_roll_calendar(code, output_datapath=roll_calendar_path,
                                          write=True, check_before_writing=False)
            process_multiple_prices_single_instrument(
                code, csv_roll_data_path=roll_calendar_path, ADD_TO_DB=True, ADD_TO_CSV=False)
            process_adjusted_prices_single_instrument(code, ADD_TO_DB=True, ADD_TO_CSV=False)
            ok.append(code)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"!!! FAILED {code}: {e}")
            fail.append(code)
    print(f"\nDONE. {len(ok)} succeeded, {len(fail)} failed.")
    if ok: print("  succeeded:", ok)
    if fail: print("  failed:", fail)


def main():
    p = argparse.ArgumentParser(description="CSI ingestion pipeline")
    p.add_argument("--export-dir", help="raw CSI export dir (with <SYM>_<YYYYMM>.csv)")
    p.add_argument("--rename", action="store_true", help="rename CSI exports into datapath")
    p.add_argument("--instruments", help="comma-separated PST codes to process")
    p.add_argument("--datapath", default=DEFAULT_DATAPATH)
    p.add_argument("--roll-calendar-path", default=DEFAULT_ROLL_CALENDAR_PATH)
    args = p.parse_args()

    if args.rename:
        if not args.export_dir:
            p.error("--rename requires --export-dir")
        rename_csi_exports(args.export_dir, args.datapath)

    if args.instruments:
        instruments = [c.strip() for c in args.instruments.split(",") if c.strip()]
        run_pipeline(instruments, args.datapath, args.roll_calendar_path)


if __name__ == "__main__":
    main()
