"""Daily pre-market refresh for the rob_dynamic paper strategy.

Runs ONCE (systemd one-shot, before the trading day) and exits:
  1. csi_sync_reingest --auto   -> bring the sim DB current from the latest CSI export (incremental)
  2. run_systems (rob_dynamic)  -> recompute + store optimal positions at the live $250k strategy capital
  3. order generator            -> stage instrument orders on the INTERNAL stack (NOT broker-facing)

The separate pst-rob-stackhandler service (canonical run_stack_handler) then works those staged
orders to the broker through the day's liquid windows. This split is deliberate: the ONLY broker-facing
component is the single continuous run_stack_handler (full order-lifecycle management, no double-submit).

Read-only w.r.t. the broker; places nothing at IB. Idempotent per day (run_systems/order-gen max 1).
"""
import os
import sys
import subprocess

os.environ["TZ"] = "UTC"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def step(title, fn):
    print(f"\n===== {title} =====", flush=True)
    try:
        fn()
        print(f"[ok] {title}", flush=True)
        return True
    except Exception as e:
        print(f"[FAIL] {title}: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return False


def csi_sync():
    # incremental sync of whatever the UA export has made current; --auto detects behind instruments
    r = subprocess.run(
        [sys.executable, "-m", "sysinit.futures.csi_sync_reingest", "--auto"],
        cwd=ROOT, env={**os.environ, "TZ": "UTC"}, timeout=3000,
    )
    if r.returncode != 0:
        raise RuntimeError(f"csi_sync exit {r.returncode}")


def run_systems():
    from sysdata.data_blob import dataBlob
    from syscontrol.strategy_tools import strategyRunner
    data = dataBlob(log_name="rob_daily_refresh_systems")
    strategyRunner(data, "rob_dynamic", "run_systems", "run_backtest").run_strategy_method()


def order_gen():
    from sysdata.data_blob import dataBlob
    from syscontrol.strategy_tools import strategyRunner
    data = dataBlob(log_name="rob_daily_refresh_ordergen")
    strategyRunner(
        data, "rob_dynamic", "run_strategy_order_generator", "get_and_place_orders"
    ).run_strategy_method()


def clear_stale_orders():
    # Stack hygiene: clear leftover un-worked instrument orders BEFORE order_gen so stale orders don't
    # accumulate day-to-day when the stack handler didn't run to clean them (its end-of-day
    # safe_stack_removal). Guarded: only clears when NOTHING is in flight (contract+broker stacks empty),
    # so it can never disrupt live execution. Touches only the instrument stack -> no broker/Gateway needed.
    from sysdata.data_blob import dataBlob
    from sysexecution.stack_handler.stack_handler import stackHandler
    sh = stackHandler(dataBlob())
    if sh.contract_stack.get_list_of_order_ids() or sh.broker_stack.get_list_of_order_ids():
        print("  in-flight orders present (contract/broker stack non-empty) -> SKIP hygiene", flush=True)
        return
    inst = sh.instrument_stack
    stale = inst.get_list_of_order_ids()
    for oid in stale:
        inst.deactivate_order(oid)
    inst.remove_all_deactivated_orders_from_stack()
    print(f"  cleared {len(stale)} stale un-worked instrument order(s)", flush=True)


def main():
    ok = True
    ok = step("1/4 CSI incremental sync", csi_sync) and ok
    ok = step("2/4 run_systems (optimal positions @ $250k)", run_systems) and ok
    step("3/4 stack hygiene (clear stale un-worked orders)", clear_stale_orders)  # best-effort; don't fail the run
    ok = step("4/4 order generator (stage instrument orders)", order_gen) and ok
    # report staged orders
    try:
        from sysdata.data_blob import dataBlob
        from sysexecution.stack_handler.stack_handler import stackHandler
        sh = stackHandler(dataBlob())
        n = len(sh.instrument_stack.get_list_of_order_ids())
        print(f"\nstaged instrument orders: {n}", flush=True)
    except Exception as e:
        print(f"stack read err: {e}", flush=True)
    print("\nrob_daily_refresh DONE" + ("" if ok else " (WITH FAILURES)"), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
