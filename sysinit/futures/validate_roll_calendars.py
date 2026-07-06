"""
Validate generated (CSI) roll calendars against pysystemtrade's own guidance.

Rob's docs say roll-calendar building is "careful craftsmanship, not a batch
process": generate -> CHECK (monotonic + valid) -> review. Our CSI ingest runs it
batched with checks off, so this pass restores the checks AND adds the single best
sanity check available: cross-checking the HELD-CONTRACT sequence against Rob's
shipped roll calendars (data/futures/roll_calendars_csv), where they overlap.

Per instrument it reports:
  - monotonic : date index strictly increasing (rollCalendar.check_if_date_index_monotonic)
  - valid     : both current & next contract have prices on every roll date
                (rollCalendar.check_dates_are_valid_for_prices)
  - vs_rob    : % of overlapping days where WE hold the same contract Rob's shipped
                calendar holds (identical daily forward-fill transform on both)

Low vs_rob or valid=False flags an instrument for manual review (the craftsmanship
step). Nothing here writes data.

Usage:
  uv run python -m sysinit.futures.validate_roll_calendars --instruments all
  uv run python -m sysinit.futures.validate_roll_calendars --instruments WHEAT,GAS_US_mini
"""
import argparse

import pandas as pd

from syscore.fileutils import get_resolved_pathname
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysproduction.data.prices import diagPrices
from sysinit.futures.csi_pipeline import instruments_in_datapath, DEFAULT_DATAPATH

OURS = "private.data.futures.roll_calendars_csv"
SHIPPED = "data.futures.roll_calendars_csv"
AGREE_FLAG = 0.80  # below this % held-contract agreement -> review


def _held_daily(cal: pd.DataFrame) -> pd.Series:
    """Daily forward-filled series of the held (current) contract. Normalizes the
    index to date (shipped calendars carry a time component; ours don't) so the two
    are comparable, and tolerates NaN/duplicate/unsorted rows."""
    s = cal["current_contract"].dropna().map(lambda v: str(int(float(v))))
    s.index = pd.to_datetime(cal.index[cal["current_contract"].notna()]).normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(idx, method="ffill")


def _cross_check(our_cal, shipped_cal) -> tuple:
    a, b = _held_daily(our_cal), _held_daily(shipped_cal)
    lo, hi = max(a.index.min(), b.index.min()), min(a.index.max(), b.index.max())
    if lo >= hi:
        return None, None
    common = a.loc[lo:hi].index.intersection(b.loc[lo:hi].index)
    if len(common) == 0:
        return None, None
    agree = (a.loc[common] == b.loc[common]).mean()
    return agree, f"{lo.date()}..{hi.date()}"


def validate(codes: list) -> list:
    dp = diagPrices()
    prices_data = dp.db_futures_contract_price_data
    ours = csvRollCalendarData(get_resolved_pathname(OURS))
    shipped = csvRollCalendarData(get_resolved_pathname(SHIPPED))
    shipped_codes = set(shipped.get_list_of_instruments())

    results = []
    for code in codes:
        row = dict(code=code, mono="", valid="", rolls="", vs_rob="", note="")
        try:
            cal = ours.get_roll_calendar(code)
            prices = prices_data.get_merged_prices_for_instrument(code).final_prices()
            row["mono"] = "Y" if cal.check_if_date_index_monotonic() else "N"
            row["valid"] = "Y" if cal.check_dates_are_valid_for_prices(prices) else "N"
            row["rolls"] = len(cal)
            # truncation check: a single missing mid-chain contract breaks the roll
            # and silently discards all history after it (passes monotonic+valid).
            # Compare the calendar end to the actual DATA end (latest price across all
            # contracts), NOT the latest contract date -- far-forward-listed contracts
            # (NG ~8yr, STIR ~10yr) have their data at the present, so using contract
            # dates false-positives; data end does not.
            price_dates = [s.index.max() for s in prices.values() if len(s) > 0]
            if price_dates:
                data_end_yr = max(price_dates).year
                cal_end_yr = cal.index.max().year
                if data_end_yr - cal_end_yr >= 3:
                    row["note"] = (f"TRUNCATED: rolls end {cal_end_yr}, data to "
                                   f"{data_end_yr} (mid-chain gap)")
        except Exception as e:
            row["note"] = f"{type(e).__name__}: {str(e)[:50]}"
            results.append(row)
            continue

        if code in shipped_codes:
            try:
                agree, overlap = _cross_check(cal, shipped.get_roll_calendar(code))
                if agree is None:
                    row["vs_rob"] = "no-overlap"
                else:
                    row["vs_rob"] = f"{agree*100:.0f}%"
                    if agree < AGREE_FLAG and not row["note"]:
                        row["note"] = f"DIVERGES from Rob ({overlap})"
            except Exception as e:
                row["vs_rob"] = f"err:{type(e).__name__}"
        else:
            row["vs_rob"] = "not-shipped"

        if row["valid"] == "N" and not row["note"]:
            row["note"] = "INVALID (missing prices on a roll date)"
        if row["mono"] == "N" and not row["note"]:
            row["note"] = "NOT MONOTONIC"
        results.append(row)
    return results


def main():
    p = argparse.ArgumentParser(description="Validate roll calendars + cross-check vs Rob's")
    p.add_argument("--instruments", default="all",
                   help="comma-separated codes, or 'all' (CSI-staged instruments)")
    args = p.parse_args()

    if args.instruments.strip().lower() == "all":
        codes = instruments_in_datapath(DEFAULT_DATAPATH)
    else:
        codes = [c.strip() for c in args.instruments.split(",") if c.strip()]

    results = validate(sorted(codes))
    print(f"\n{'instrument':<15}{'mono':>5}{'valid':>6}{'rolls':>7}{'vs_rob':>9}  note")
    print("-" * 78)
    flagged = []
    for r in sorted(results, key=lambda r: (r["note"] == "", r["code"])):
        print(f"{r['code']:<15}{r['mono']:>5}{r['valid']:>6}{str(r['rolls']):>7}"
              f"{r['vs_rob']:>9}  {r['note']}")
        if r["note"]:
            flagged.append(r["code"])
    ok = sum(1 for r in results if not r["note"])
    print(f"\n{ok}/{len(results)} clean; {len(flagged)} need review: {flagged}")


if __name__ == "__main__":
    main()
