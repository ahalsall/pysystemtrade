"""READ-ONLY probe: does IB have data for the frozen SOFR (SR3) deferred quarterly
contracts past the CSI cutoff (2023-04-14)? Pulls DAILY bars for a set of quarterly
contracts and prints the date range + row count. Does NOT write anything -- no merge.

Usage: uv run python -m sysinit.futures.ib_sofr_probe
"""
import pandas as pd
from syscore.dateutils import Frequency
from sysobjects.contracts import futuresContract
from sysproduction.data.broker import dataBroker

INSTR = "SOFR"
# the deferred quarterly IMM legs that are frozen at 2023-04-14 in CSI, plus a couple
# of current/near ones as a live-connection sanity check
CONTRACTS = [
    "20230600", "20230900",              # around/after the CSI freeze
    "20240300", "20240900",
    "20250300", "20250900",
    "20260300", "20260600", "20260900", "20261200",
    "20270300", "20270900",
    "20280300", "20280900",
]

pd.set_option("display.width", 140)
broker = dataBroker()
print(f"{'contract':>12} | {'rows':>6} | {'first':>10} | {'last':>10}")
print("-" * 50)
for ct in CONTRACTS:
    try:
        contract = futuresContract(INSTR, ct)
        bars = broker.get_prices_at_frequency_for_contract_object(contract, Frequency.Day)
        if bars is None or len(bars) == 0:
            print(f"{ct:>12} | {'0':>6} | {'--':>10} | {'--':>10}   (no data)")
            continue
        idx = bars.index
        print(f"{ct:>12} | {len(bars):>6} | {str(idx.min().date()):>10} | {str(idx.max().date()):>10}")
    except Exception as e:
        print(f"{ct:>12} |  ERROR: {type(e).__name__}: {str(e)[:80]}")
print("\n(read-only; nothing written)")
