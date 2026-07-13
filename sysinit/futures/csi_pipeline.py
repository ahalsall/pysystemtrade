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
import csv
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
    input_date_format="%Y-%m-%d",
    input_column_mapping=dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    ),
)

# UA's real export is HEADERLESS and date-only: `2023-10-23,719.30,...,2`.
# --rename prepends this header so CSI_CONFIG (name-based mapping) can parse it.
CSI_HEADER = "Time,Open,High,Low,Close,Volume\n"

# Raw CSI exports land in private/data/futures/csi/ (owned by the dedicated `csi`
# user that runs Unfair Advantage — read-only for us). We stage renamed files in an
# andrew-writable dir and process from there.
DEFAULT_EXPORT_DIR = "private.data.futures.csi"
DEFAULT_DATAPATH = "private.data.futures.csi_ingest"
DEFAULT_ROLL_CALENDAR_PATH = "private.data.futures.roll_calendars_csv"
# built by sysinit.futures.build_csi_symbol_map (csi_symbol,pst_code,...)
DEFAULT_MAP_FILE = "private/data/futures/csi_symbol_map.csv"

# CSI symbol -> PST instrument code. SEED — extend to the full universe from CSI's
# symbol list (Unfair Advantage market list). Same code style as the legacy
# barchart market_map (sysinit/futures/barchart_futures_contract_prices.py).
CSI_SYMBOL_MAP = {
    "AEX": "AEX",        # CSI AEX (Euronext AEX Index, EUR x200) -> PST AEX
    "ALI": "ALUMINIUM",  # CSI ALI (COMEX Aluminum, USD 25t) -> PST ALUMINIUM (IB sym ALI/COMEX)
}

_CSI_RE = re.compile(r"^([A-Z0-9]+)_(\d{6})\.csv$")
# UA writes ISO timestamps with a timezone offset (e.g. 2024-08-19T05:00:00+0000).
# Strip the offset so timestamps are tz-naive: matches CSI_CONFIG's
# %Y-%m-%dT%H:%M:%S and the barchart data. A tz-aware index breaks PST's daily
# conversion downstream (same lesson as the barchart %z gotcha).
_TZ_OFFSET_RE = re.compile(r"(\dT\d{2}:\d{2}:\d{2})[+-]\d{4}")
# staged file: Day_<PST>_<YYYYMM00>.csv  (PST codes may contain underscores)
_STAGED_RE = re.compile(r"^Day_(.+)_\d{8}\.csv$")


def load_symbol_map(map_file: str = DEFAULT_MAP_FILE) -> dict:
    """Merge the builder's csi_symbol_map.csv (csi_symbol,pst_code,...) over the
    inline seed; CSV wins. Falls back to just the seed if the file is absent."""
    merged = dict(CSI_SYMBOL_MAP)
    if map_file and os.path.exists(map_file):
        with open(map_file) as f:
            for r in csv.DictReader(f):
                sym = (r.get("csi_symbol") or "").strip()
                pst = (r.get("pst_code") or "").strip()
                if sym and pst:
                    merged[sym] = pst
        print(f"symbol map: {len(merged)} entries (seed + {map_file})")
    else:
        print(f"symbol map: file not found ({map_file}); using inline seed ({len(merged)})")
    return merged


def instruments_in_datapath(datapath: str) -> list:
    """Distinct PST codes among staged Day_<PST>_<YYYYMM00>.csv files."""
    d = get_resolved_pathname(datapath)
    codes = set()
    for fn in os.listdir(d):
        m = _STAGED_RE.match(fn)
        if m:
            codes.add(m.group(1))
    return sorted(codes)


def _dedupe_roll_calendar_csv(code: str, roll_calendar_path: str):
    """Drop degenerate duplicate-date roll rows (keep LAST, preserving the forward
    chain) so the calendar is strictly monotonic. These appear when the earliest
    held contract is clamped to the start, giving two rolls on the same first date."""
    import pandas as pd
    path = os.path.join(get_resolved_pathname(roll_calendar_path), f"{code}.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    datecol = df.columns[0]
    before = len(df)
    df = df.drop_duplicates(subset=datecol, keep="last")
    if len(df) < before:
        df.to_csv(path, index=False)
        print(f"  [{code}] deduped roll calendar: {before} -> {len(df)} rows "
              f"(removed {before - len(df)} duplicate-date rows)")


def rename_csi_exports(export_dir: str, target_datapath: str, symbol_map: dict = None):
    """Stage raw CSI `<SYM>_<YYYYMM>.csv` (headerless, date-only) found anywhere
    under export_dir into datapath as `Day_<PST>_<YYYYMM00>.csv`, prepending the
    column header and stripping any tz offset. Walks subdirectories because UA
    writes into nested folders (e.g. UA/Data/PST/). `.Specs.txt` files are ignored
    (they don't match the contract-file pattern)."""
    if symbol_map is None:
        symbol_map = CSI_SYMBOL_MAP
    src = get_resolved_pathname(export_dir)
    dst = get_resolved_pathname(target_datapath)
    os.makedirs(dst, exist_ok=True)
    renamed, skipped = 0, []
    for root, _dirs, files in os.walk(src):
        if os.path.abspath(root) == os.path.abspath(dst):
            continue  # never re-ingest our own staged output
        for fn in files:
            m = _CSI_RE.match(fn)
            if not m:
                continue
            sym, yyyymm = m.group(1), m.group(2)
            pst = symbol_map.get(sym)
            if pst is None:
                skipped.append(sym)
                continue
            out = f"Day_{pst}_{yyyymm}00.csv"
            with open(os.path.join(root, fn)) as f_in:
                content = f_in.read()
            content = _TZ_OFFSET_RE.sub(r"\1", content)  # tz-aware -> tz-naive (no-op if date-only)
            if not content.lstrip().lower().startswith("time,"):
                content = CSI_HEADER + content  # UA exports are headerless
            with open(os.path.join(dst, out), "w") as f_out:
                f_out.write(content)
            renamed += 1
    print(f"renamed {renamed} CSI files into {dst}")
    if skipped:
        print(f"  no CSI_SYMBOL_MAP entry for (skipped): {sorted(set(skipped))}")


import csv as _csv_mod
def _load_price_scale():
    """Coordinating CSI price-scale config: per-instrument multiplier applied at INGEST so stored
    price matches pysystemtrade's convention (stored = real_price x priceMagnifier). CSI quotes
    some instruments in cents/x100 while their Pointsize expects the base unit -> notional 100x off.
    Single source of truth used by BOTH run_pipeline and csi_sync_reingest. Calibrate entries vs IB."""
    fp = "private/data/futures/csi_price_scale.csv"
    if not os.path.exists(fp):
        return {}
    out = {}
    for r in _csv_mod.DictReader(open(fp)):
        out[r["instrument"]] = dict(
            scale=float(r.get("scale") or 1.0),
            inverse=str(r.get("inverse", "0")).strip() in ("1", "True", "true"))
    return out
PRICE_SCALE = _load_price_scale()


def csi_config_for(code):
    cfg = PRICE_SCALE.get(code)
    if not cfg or (cfg["scale"] == 1.0 and not cfg["inverse"]):
        return CSI_CONFIG
    return ConfigCsvFuturesPrices(
        input_date_index_name="Time", input_skiprows=0, input_skipfooter=0, input_date_format="%Y-%m-%d",
        input_column_mapping=dict(OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"),
        apply_multiplier=cfg["scale"], apply_inverse=cfg["inverse"])


def run_pipeline(instruments, datapath, roll_calendar_path):
    ok, fail = [], []
    for code in instruments:
        print("=" * 60, f"\nProcessing {code}")
        try:
            init_db_with_split_freq_csv_prices_for_code(code, datapath, csv_config=csi_config_for(code))
            build_and_write_roll_calendar(code, output_datapath=roll_calendar_path,
                                          write=True, check_before_writing=False)
            _dedupe_roll_calendar_csv(code, roll_calendar_path)
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
    p.add_argument("--instruments", help="comma-separated PST codes, or 'all' to "
                   "process every instrument staged in the datapath")
    p.add_argument("--datapath", default=DEFAULT_DATAPATH)
    p.add_argument("--roll-calendar-path", default=DEFAULT_ROLL_CALENDAR_PATH)
    p.add_argument("--map-file", default=DEFAULT_MAP_FILE,
                   help="CSI->PST map CSV from build_csi_symbol_map (merged over seed)")
    args = p.parse_args()

    if args.rename:
        if not args.export_dir:
            p.error("--rename requires --export-dir")
        symbol_map = load_symbol_map(args.map_file)
        rename_csi_exports(args.export_dir, args.datapath, symbol_map)

    if args.instruments:
        if args.instruments.strip().lower() == "all":
            instruments = instruments_in_datapath(args.datapath)
            print(f"processing all {len(instruments)} staged instruments")
        else:
            instruments = [c.strip() for c in args.instruments.split(",") if c.strip()]
        run_pipeline(instruments, args.datapath, args.roll_calendar_path)


if __name__ == "__main__":
    main()
