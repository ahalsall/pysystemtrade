"""
Market-hours calendar / report for our instrument universe.

Leverages pysystemtrade's existing IB-sourced trading-hours data (holiday- and
early-close-aware) rather than maintaining a calendar by hand. For each
instrument it shows:
  - whether it's tradeable RIGHT NOW (is_contract_okay_to_trade)
  - the upcoming daily sessions (open/close) for its priced contract
  - flags for EARLY CLOSE (session shorter than the instrument's normal day) and
    HOLIDAY (a weekday inside the window with no session at all)

Requires IB Gateway running (hours come live from IB; read-only is fine).

Usage:
  uv run python -m sysinit.futures.market_hours_calendar                  # strategy config instruments
  uv run python -m sysinit.futures.market_hours_calendar SP500_micro GOLD_micro BUND
  uv run python -m sysinit.futures.market_hours_calendar --all            # all instruments with price data
"""
import sys
import csv
import datetime
from collections import defaultdict

from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysproduction.data.prices import diagPrices
from sysobjects.contracts import futuresContract

IB_CONFIG = "sysbrokers/IB/config/ib_config_futures.csv"
ROB_CFG = "private/systems/rob_dynamic/config.yaml"


def _exchange_map():
    try:
        return {r["Instrument"]: r["IBExchange"] for r in csv.DictReader(open(IB_CONFIG))}
    except Exception:
        return {}


def _default_universe(data):
    # strategy config instruments if available, else instruments with adjusted prices
    try:
        import yaml

        cfg = yaml.safe_load(open(ROB_CFG))
        return sorted(cfg["instrument_weights"].keys())
    except Exception:
        return sorted(diagPrices(data).db_futures_adjusted_prices_data.get_list_of_instruments())


def _sessions_by_day(hours):
    by_day = defaultdict(list)
    for h in hours:
        by_day[h.opening_time.date()].append((h.opening_time, h.closing_time))
    return by_day


def _duration_hours(sessions):
    return sum((c - o).total_seconds() for o, c in sessions) / 3600.0


def report(codes, data):
    broker = dataBroker(data)
    contracts = dataContracts(data)
    exch = _exchange_map()

    open_now, closed_now, errors = [], [], []
    print(f"Market-hours calendar  (generated {datetime.datetime.now():%Y-%m-%d %H:%M} local)\n")
    for code in codes:
        try:
            pc = contracts.get_priced_contract_id(code)
            fc = futuresContract(code, pc)
            hours = broker.get_trading_hours_for_contract(fc)
            # status + next-open derived from the SAME hours object + datetime.now()
            # (consistent with PST's tradingHours.okay_to_trade_now, which uses naive now)
            okay = hours.okay_to_trade_now()
        except Exception as e:
            print(f"  {code:14s} ERROR {type(e).__name__}: {str(e)[:80]}")
            errors.append(code)
            continue

        now = datetime.datetime.now()
        all_sessions = sorted((h.opening_time, h.closing_time) for h in hours)
        if okay:
            current = next(((o, c) for o, c in all_sessions if o <= now <= c), None)
            next_event = f"closes {current[1]:%b-%d %H:%M}" if current else "-"
        else:
            future_opens = [o for o, c in all_sessions if o > now]
            next_event = f"opens {min(future_opens):%b-%d %H:%M}" if future_opens else "-"

        status = "OPEN " if okay else "CLOSED"
        (open_now if okay else closed_now).append(code)
        print(f"{code:14s} [{exch.get(code,'?'):8s}] {pc}  NOW: {status}  NEXT: {next_event}")

        by_day = _sessions_by_day(hours)
        if by_day:
            normal = max(_duration_hours(s) for s in by_day.values())
            days = sorted(by_day)
            # detect holiday weekdays inside the window
            cur = days[0]
            while cur <= days[-1]:
                if cur.weekday() < 5 and cur not in by_day:
                    print(f"    {cur:%Y-%m-%d %a}  --- HOLIDAY (no session) ---")
                cur += datetime.timedelta(days=1)
            for d in days:
                sess = by_day[d]
                span = " ".join(f"{o:%H:%M}-{c:%H:%M}" for o, c in sess)
                flag = "  <-- EARLY CLOSE" if _duration_hours(sess) < 0.9 * normal else ""
                print(f"    {d:%Y-%m-%d %a}  {span}{flag}")
        print()

    print("=" * 60)
    print(f"OPEN now ({len(open_now)}): {open_now}")
    print(f"CLOSED now ({len(closed_now)}): {closed_now}")
    if errors:
        print(f"errors ({len(errors)}): {errors}")
    print("(times as provided by IB/PST; 'NOW' uses is_contract_okay_to_trade)")


def main():
    args = sys.argv[1:]
    with dataBlob(log_name="market-hours-calendar") as data:
        if "--all" in args:
            codes = sorted(diagPrices(data).db_futures_adjusted_prices_data.get_list_of_instruments())
        else:
            explicit = [a for a in args if not a.startswith("--")]
            codes = explicit if explicit else _default_universe(data)
        report(codes, data)


if __name__ == "__main__":
    main()
