"""Non-interactive contract sampling to populate current-contract EXPIRIES from IB, fixing the
broker<->DB reconciliation breaks (broker reports exact expiry YYYYMMDD; DB holds month-code
YYYYMM00 with no expiry -> ContractNotFound -> phantom break).

Wraps update_active_contracts_for_instrument (the guts of update_sampled_contracts, which is
interactive). Writes ONLY to the mongo CONTRACT database (metadata + expiries + sampling status)
— never touches prices / the CSI sim DB. Gateway must be up.

USAGE:
  validate on specific instruments:  uv run python -m sysinit.futures.fix_contract_expiries SP500_micro GOLD_micro JPY AUD
  full universe (multiple-prices):   uv run python -m sysinit.futures.fix_contract_expiries
"""
import os
import sys
os.environ.setdefault("TZ", "UTC")
from sysdata.data_blob import dataBlob
from sysproduction.update_sampled_contracts import update_active_contracts_for_instrument
from sysproduction.data.prices import diagPrices

codes = sys.argv[1:]
ok = fail = 0
with dataBlob(log_name="fix-expiries") as data:
    list_of_codes = codes if codes else diagPrices(data).get_list_of_instruments_in_multiple_prices()
    print(f"CONTRACT SAMPLING (expiry populate): {len(list_of_codes)} instrument(s)\n", flush=True)
    for c in list_of_codes:
        try:
            update_active_contracts_for_instrument(c, data)
            print(f"  OK   {c}", flush=True)
            ok += 1
        except Exception as e:
            print(f"  FAIL {c}: {type(e).__name__}: {e}", flush=True)
            fail += 1
print(f"\ndone: {ok} sampled, {fail} failed", flush=True)
