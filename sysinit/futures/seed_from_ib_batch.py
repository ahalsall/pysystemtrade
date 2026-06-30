"""
Batch-seed per-contract price data from IB for a list of instruments.

Reuses ONE dataBlob / IB connection across all instruments (avoids client-id
churn). For each instrument it asks the broker for its contract dates and pulls
hourly+daily per contract into the DB (parquet), via the stock seeding helpers.

IB only serves recent + forward contracts (no deep/expired history), so this
gives current tradeable contracts + ~1-2yr per-contract history per instrument.
Run pure-IB (clear any prior barchart data for these instruments first) to avoid
roll-chain gaps. Then build roll calendars -> multiple -> adjusted as usual.

Usage:
    uv run python -m sysinit.futures.seed_from_ib_batch SP500_micro US10 BUND ...
"""
import sys

from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysobjects.contracts import futuresContract
from sysinit.futures.seed_price_data_from_IB import seed_price_data_for_contract


def seed_instruments(codes):
    ok, fail = [], []
    with dataBlob(log_name="seed-from-ib-batch") as data:
        broker = dataBroker(data)
        for code in codes:
            print(f"=== seeding {code} ===")
            try:
                contract_dates = broker.get_list_of_contract_dates_for_instrument_code(
                    code, allow_expired=True
                )
                got = 0
                for contract_date in contract_dates:
                    seed_price_data_for_contract(
                        data, futuresContract(code, contract_date[:6])
                    )
                    got += 1
                print(f"  {code}: processed {got} contracts")
                ok.append(code)
            except Exception as error:
                print(f"  !!! FAILED {code}: {type(error).__name__}: {str(error)[:160]}")
                fail.append(code)
    print(f"\nDONE. seeded {len(ok)}, failed {len(fail)}")
    if ok:
        print("  ok:", ok)
    if fail:
        print("  failed:", fail)
    return ok, fail


if __name__ == "__main__":
    codes = sys.argv[1:]
    if not codes:
        raise SystemExit("pass instrument codes as args")
    seed_instruments(codes)
