"""Preliminary IB Gateway wiring checks — all READ-ONLY, safe off-hours (no orders).
Validates: connection, paper account identity + capital, current broker positions, and
position breaks vs the DB (a reconciliation preview). Run with Gateway up."""
import os
os.environ.setdefault("TZ", "UTC")
from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker

data = dataBlob()
try:
    b = dataBroker(data)
    print("=== IB GATEWAY PRELIMINARY CHECKS (read-only) ===\n", flush=True)
    print("connection: attempting broker account query...", flush=True)
    acct = b.get_broker_account()
    print(f"  paper account: {acct}", flush=True)
    try:
        cap = b.get_total_capital_value_in_base_currency()
        print(f"  total capital (base ccy): {cap:,.2f}", flush=True)
    except Exception as e:
        print(f"  capital query: {e}", flush=True)

    print("\ncurrent broker contract positions:", flush=True)
    try:
        pos = b.get_all_current_contract_positions()
        plist = pos.as_pd_df() if hasattr(pos, "as_pd_df") else pos
        if hasattr(plist, "empty") and plist.empty:
            print("  (flat — no open positions)")
        else:
            print(plist if not hasattr(plist, "to_string") else plist.to_string())
    except Exception as e:
        print(f"  positions query: {e}", flush=True)

    print("\nposition breaks (broker vs DB) — reconciliation preview:", flush=True)
    try:
        breaks = b.get_list_of_breaks_between_broker_and_db_contract_positions()
        print(f"  {len(breaks)} break(s): {breaks}" if breaks else "  none (broker == DB)")
    except Exception as e:
        print(f"  breaks query: {e}", flush=True)
    print("\n=== checks complete ===", flush=True)
finally:
    try:
        data.close()
    except Exception:
        pass
