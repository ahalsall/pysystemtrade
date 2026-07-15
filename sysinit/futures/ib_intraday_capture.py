"""SILOED IB intraday price recorder (parallel track — NOT part of the CSI sim DB).

WHY: CSI is EOD-only. Granular intraday history is effectively un-buyable retroactively
(IB serves only ~months of minute bars back, with pacing limits), so the ONLY way to have
intraday tape later is to start accumulating NOW. This captures hourly bars forward for the
production universe as a second, independent data source for (a) future medium/higher-freq
research and (b) cross-checking the CSI sim prices.

HARD ISOLATION: writes ONLY to private/data/parquet_ib_intraday/, a store the simulation
NEVER reads. pysystemtrade's native run_daily_prices_updates would write IB bars into the
sim's futures_contract_prices store (the contamination vector we avoid) — this does not.

USAGE:
  dry-run (no Gateway, prints the capture plan):   uv run python -m sysinit.futures.ib_intraday_capture
  live    (Gateway up, fetches + appends hourly):  IB_LIVE=1 uv run python -m sysinit.futures.ib_intraday_capture
Run live during a Gateway session (like the paper fills). Safe to re-run daily: it merges."""
import os
import csv
import time
import pandas as pd

SILOED_PATH = "private/data/parquet_ib_intraday"
SIM_PATH = "private/data/parquet"  # the CSI sim store — MUST stay untouched
assert os.path.abspath(SILOED_PATH) != os.path.abspath(SIM_PATH), "siloed store must differ from sim store"

from sysproduction.data.prices import diagPrices
IB_LIVE = os.environ.get("IB_LIVE", "0") == "1"
FREQ_NAME = os.environ.get("CAPTURE_FREQ", "Hour")  # Hour (default) | Minute for a small subset

# Universe = the LIVE production universe (rob_dynamic instrument_weights = our tradeable set, single
# source of truth). Auto-widens as the generator adds instruments. Env CAPTURE_UNIVERSE overrides;
# phase_a_audit READY set is the legacy fallback.
def load_universe():
    env = os.environ.get("CAPTURE_UNIVERSE")
    if env:
        return sorted(set(env.replace(",", " ").split()))
    prod = "private/systems/rob_dynamic/config.yaml"
    if os.path.exists(prod):
        import yaml
        iw = yaml.safe_load(open(prod)).get("instrument_weights", {})
        if iw:
            return sorted(iw.keys())
    fp = "private/phase_a_audit.csv"
    if os.path.exists(fp):
        rows = list(csv.DictReader(open(fp)))
        ready = [r["instrument"] for r in rows if r["verdict"] == "READY"]
        return ready or [r["instrument"] for r in rows]
    raise SystemExit("no universe source (production config instrument_weights or phase_a_audit.csv)")

dp = diagPrices()
universe = load_universe()
_limit = os.environ.get("CAPTURE_LIMIT")
if _limit:
    universe = universe[:int(_limit)]

# current priced contract per instrument (from sim multiple prices) = the liquid contract to record
plan = []
for c in universe:
    try:
        mp = dp.db_futures_multiple_prices_data.get_multiple_prices(c)
        plan.append((c, str(mp["PRICE_CONTRACT"].iloc[-1])))
    except Exception as e:
        plan.append((c, f"ERR:{e}"))

print(f"IB INTRADAY CAPTURE ({'LIVE' if IB_LIVE else 'DRY-RUN'}), freq={FREQ_NAME}, "
      f"{len(plan)} instruments -> {SILOED_PATH}/\n", flush=True)

if not IB_LIVE:
    print("Capture plan (instrument -> current contract):")
    for c, ct in plan[:12]:
        print(f"  {c:<16} {ct}")
    print(f"  ... ({len(plan)} total)")
    print("\nDRY-RUN only — no IB connection, nothing written. Set IB_LIVE=1 with the Gateway up to fetch.")
    print("Isolation check: writes would go ONLY to", os.path.abspath(SILOED_PATH),
          "\n                 sim store", os.path.abspath(SIM_PATH), "is never touched.")
    raise SystemExit(0)

# ---- LIVE path (Gateway required) ----
from syscore.dateutils import Frequency
from sysobjects.contracts import futuresContract
from sysdata.parquet.parquet_access import ParquetAccess
from sysdata.parquet.parquet_futures_per_contract_prices import parquetFuturesContractPriceData
from sysproduction.data.broker import dataBroker

freq = getattr(Frequency, FREQ_NAME)
os.makedirs(SILOED_PATH, exist_ok=True)
siloed = parquetFuturesContractPriceData(ParquetAccess(SILOED_PATH))
broker = dataBroker()
ok = fail = 0
for c, ct in plan:
    if ct.startswith("ERR"):
        fail += 1; continue
    try:
        contract = futuresContract(c, ct)
        bars = broker.get_prices_at_frequency_for_contract_object(contract, freq)
        if bars is None or len(bars) == 0:
            print(f"  {c} {ct}: no bars"); fail += 1; continue
        # merge with anything already recorded, write to the SILOED store only
        try:
            existing = siloed.get_prices_at_frequency_for_contract_object(contract, freq)
            merged = existing.add_rows_to_existing_data(bars) if len(existing) else bars
        except Exception:
            merged = bars
        siloed.write_prices_at_frequency_for_contract_object(
            contract, merged, frequency=freq, ignore_duplication=True)
        print(f"  {c} {ct}: +{len(bars)} bars -> siloed store ({len(merged)} total)", flush=True)
        ok += 1
        time.sleep(10)  # respect IB historical-data pacing limits
    except Exception as e:
        print(f"  {c} {ct}: FAIL {e}", flush=True); fail += 1

print(f"\nCaptured {ok} instruments, {fail} failed/empty. Siloed store: {SILOED_PATH}/", flush=True)
