"""
Non-interactive barchart data pipeline runner.

Runs the full chain needed to make barchart split-frequency CSV data usable for
backtesting, for one or many instruments:

    1. contract prices : split-freq CSVs  -> parquet (per-contract Hour/Day/Mixed)
    2. roll calendar    : db prices        -> roll_calendars_csv/<INSTR>.csv
    3. multiple prices  : db prices + cal  -> db multiple prices
    4. adjusted prices  : db multiple      -> db adjusted prices

Unlike the stock sysinit scripts this takes no interactive input, so it can be
run unattended / through tooling. Each instrument is processed independently;
a failure in one instrument is reported and skipped, not fatal.

Examples
--------
    # one instrument, all stages
    python -m sysinit.futures.barchart_pipeline --instruments FTSE100

    # several instruments
    python -m sysinit.futures.barchart_pipeline --instruments CRUDE_W,CORN,BUND

    # every instrument found in the barchart datapath
    python -m sysinit.futures.barchart_pipeline --all

    # only re-run the later stages (prices already loaded)
    python -m sysinit.futures.barchart_pipeline --all --stages roll,multiple,adjusted
"""
import argparse
import os
import re
import traceback

from syscore.constants import arg_not_supplied
from syscore.fileutils import get_resolved_pathname

from sysinit.futures.contract_prices_from_split_freq_csv_to_db import (
    BARCHART_CONFIG,
    init_db_with_split_freq_csv_prices_for_code,
)
from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)

# NB these are dotted "package" paths, not filesystem paths: the csv data
# classes resolve them via resolve_path_and_filename_for_package(). A leading
# "./" path resolves WRONG (the "." is treated as root), so don't use one.
DEFAULT_DATAPATH = "private.data.futures.barchart"
DEFAULT_ROLL_CALENDAR_PATH = "private.data.futures.roll_calendars_csv"

ALL_STAGES = ["prices", "roll", "multiple", "adjusted"]

_FILENAME_RE = re.compile(r"(Day|Hour)_(.+)_\d{8}\.csv")


def instruments_in_datapath(datapath: str) -> list:
    """Unique instrument codes present as split-freq csv files in datapath."""
    resolved = get_resolved_pathname(datapath)
    found = set()
    for filename in os.listdir(resolved):
        match = _FILENAME_RE.match(filename)
        if match:
            found.add(match.group(2))
    return sorted(found)


def run_pipeline_for_instrument(
    instrument_code: str,
    stages: list,
    datapath: str,
    roll_calendar_path: str,
):
    if "prices" in stages:
        print(f"[{instrument_code}] stage 1/4: loading contract prices to parquet")
        init_db_with_split_freq_csv_prices_for_code(
            instrument_code, datapath, csv_config=BARCHART_CONFIG
        )

    if "roll" in stages:
        print(f"[{instrument_code}] stage 2/4: building roll calendar")
        build_and_write_roll_calendar(
            instrument_code,
            output_datapath=roll_calendar_path,
            write=True,
            check_before_writing=False,
        )

    if "multiple" in stages:
        print(f"[{instrument_code}] stage 3/4: building multiple prices")
        process_multiple_prices_single_instrument(
            instrument_code,
            csv_roll_data_path=roll_calendar_path,
            ADD_TO_DB=True,
            ADD_TO_CSV=False,
        )

    if "adjusted" in stages:
        print(f"[{instrument_code}] stage 4/4: building adjusted prices")
        process_adjusted_prices_single_instrument(
            instrument_code,
            ADD_TO_DB=True,
            ADD_TO_CSV=False,
        )


def run_pipeline(
    instruments: list,
    stages: list,
    datapath: str,
    roll_calendar_path: str,
):
    succeeded, failed = [], []
    for instrument_code in instruments:
        print("=" * 70)
        print(f"Processing {instrument_code}")
        print("=" * 70)
        try:
            run_pipeline_for_instrument(
                instrument_code, stages, datapath, roll_calendar_path
            )
            succeeded.append(instrument_code)
        except Exception as error:
            print(f"!!! FAILED {instrument_code}: {error}")
            traceback.print_exc()
            failed.append((instrument_code, str(error)))

    print("\n" + "=" * 70)
    print(f"DONE. {len(succeeded)} succeeded, {len(failed)} failed.")
    if succeeded:
        print(f"  succeeded: {succeeded}")
    if failed:
        print("  failed:")
        for code, err in failed:
            print(f"    {code}: {err}")
    return succeeded, failed


def main():
    parser = argparse.ArgumentParser(description="Non-interactive barchart pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--instruments",
        help="comma-separated instrument codes, e.g. FTSE100,CRUDE_W",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="process every instrument found in the datapath",
    )
    parser.add_argument(
        "--stages",
        default=",".join(ALL_STAGES),
        help=f"comma-separated subset of {ALL_STAGES} (default: all)",
    )
    parser.add_argument("--datapath", default=DEFAULT_DATAPATH)
    parser.add_argument("--roll-calendar-path", default=DEFAULT_ROLL_CALENDAR_PATH)
    args = parser.parse_args()

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    bad = [s for s in stages if s not in ALL_STAGES]
    if bad:
        parser.error(f"unknown stage(s) {bad}; valid stages are {ALL_STAGES}")

    if args.all:
        instruments = instruments_in_datapath(args.datapath)
    else:
        instruments = [c.strip() for c in args.instruments.split(",") if c.strip()]

    print(f"Instruments: {instruments}")
    print(f"Stages: {stages}")
    run_pipeline(instruments, stages, args.datapath, args.roll_calendar_path)


if __name__ == "__main__":
    main()
