"""Rebuild-only roll fix for instruments whose multiple/adjusted prices went stale (priced
contract expired, roll never advanced). Regenerates the roll calendar FROM DB CONTRACT PRICES
(no CSI re-ingest — the current contract data is already in the DB), then rebuilds multiple +
adjusted prices. Reuses the CSI pipeline's stage functions.

Validate after each: inspect the regenerated roll calendar (no phantom same-date double rolls,
sane monotonic contracts) and the multiple-prices tail (priced advanced, PRICE non-NaN). The
2026-07-01 lesson: auto-regen can OVER-advance on sparse data — so this is test-one-then-batch.

USAGE:  uv run python -m sysinit.futures.rebuild_stale_rolls EU-BANKS [more codes...]"""
import sys
from sysinit.futures.rollcalendars_from_db_prices_to_csv import build_and_write_roll_calendar
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.csi_pipeline import _dedupe_roll_calendar_csv, DEFAULT_ROLL_CALENDAR_PATH

RCP = DEFAULT_ROLL_CALENDAR_PATH
codes = sys.argv[1:]
if not codes:
    raise SystemExit("pass instrument codes to rebuild")
ok, fail = [], []
for code in codes:
    print("=" * 50, f"\nRebuilding rolls: {code}", flush=True)
    try:
        build_and_write_roll_calendar(code, output_datapath=RCP, write=True, check_before_writing=False)
        _dedupe_roll_calendar_csv(code, RCP)
        process_multiple_prices_single_instrument(
            code, csv_roll_data_path=RCP, ADD_TO_DB=True, ADD_TO_CSV=False)
        process_adjusted_prices_single_instrument(code, ADD_TO_DB=True, ADD_TO_CSV=False)
        ok.append(code)
    except Exception as e:
        import traceback; traceback.print_exc()
        fail.append(code)
        print(f"!!! FAILED {code}: {e}", flush=True)
print(f"\nDONE: {len(ok)} ok {ok}, {len(fail)} failed {fail}", flush=True)
