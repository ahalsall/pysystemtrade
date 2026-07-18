# SOFR (CSI SR3) frozen deferred quarterly band — diagnosis + IB-splice repair

**Status:** SOFR EXCLUDED from live rob_dynamic pending the DB rebuild (below), which is HELD for sign-off.
Everything is prepared + verified; sign-off = one command.

## Diagnosis (confirmed 2026-07-17)
- SOFR = CSI **SR3** = CME 3-Month SOFR future.
- A CONTIGUOUS BAND of quarterly (H/M/U/Z) contracts, **202309 .. 203212**, is frozen at exactly
  **2023-04-14** in the CSI export. Everything else is current: the monthly serials (202310, 202401, ...)
  AND the newer far quarterlies (203303+) all run to today. Only this one band froze.
- **The CSI re-export is a DEAD END.** User re-exported SR3 in UA with "all contracts"; the band still
  stopped at 2023-04-14, and UA's own contract view (e.g. Sep-2026) also stops there. So CSI genuinely
  does not serve these *individual deferred quarterly legs* past 2023-04-14. (The catalog's
  `EndDate 2026-07-06` is the front/continuous SR3, not the deferred legs.) This is a vendor feed
  artifact -- an orphaned deep-history contract set -- not our config and not fixable in UA.
- Effect: roll offset -1000 (intentional) holds a ~2.7yr-deferred quarterly. Post-2023-04-14 those legs
  are frozen -> ~1183-day gap in the back-adjusted series -> NaN variance in the order-time covariance
  -> SOFR auto-dropped by the optimiser.

## The fix: IB-tail splice (verified)
IB has full daily history for every still-listed leg. Read-only probes (sysinit.futures.ib_sofr_probe,
ib_sofr_depth_probe, ib_sofr_overlap_check) confirmed:
- IB serves 202406..203212 with daily bars back to 2020-07-20 (our framework's hardcoded `1 Y` duration
  had hidden it; the raw request returns the full contract life).
- On the freeze date 2023-04-14, **IB close == CSI close to the tick** for every leg -> clean seam.
- IB provides ~832 rows beyond the freeze (2023-04-17 -> today) per leg -> the exact missing tail.

Splice seam-check (`ib_sofr_splice` report): **33 spliceable, all seam diff = 0.0000; 3 unavailable**
(202309/202312/202403 -- expired, IB purged from secdef). The 3 are IMMATERIAL: under -1000 they are only
the *priced* leg back in ~2020-2021 (where CSI is complete); post-2023 we price off the 202603+ legs,
all spliceable. roll_calendar_audit + gap check confirm this at rebuild.

## Mechanism (durable; survives every csi_sync)
The raw UA/Data/PST CSVs are csi-owned AND re-frozen on every sync, so we do NOT write there. Instead:
- **Active repair store** `private/data/futures/ib_repair_tails/SOFR_<YYYYMM>.csv` (post-freeze IB rows).
- **Hook** `_ib_repair_tail` in `sysinit/futures/csi_sync_reingest.py` `stage()` overlays these tails onto
  the staged contract files on EVERY sync -> a re-frozen vendor export can't undo the fix. Generic +
  no-op for any instrument without a repair file (unit-tested).
- `sysinit/futures/ib_sofr_splice.py` populates the store (report = inert cache; --rebuild = activate + reingest).

Keeping to CSI-only-sim-DB: this is a DELIBERATE, DOCUMENTED, seam-verified exception for ONE instrument's
broken tail. CSI stays the historical base; IB supplies only the post-2023-04-14 tail.

## To apply (HELD for sign-off)
    # 1. rebuild SOFR: activate repair store + real reingest(force_bootstrap) via the hooked stage()
    uv run python -m sysinit.futures.ib_sofr_splice --rebuild --use-cache
    # 2. bootstrap drops the last roll -> review
    uv run python -m sysinit.futures.fix_stuck_rolls SOFR         # (roll review)
    # 3. verify the gap is gone
    uv run python -c "from sysproduction.data.prices import diagPrices; a=diagPrices().get_adjusted_prices('SOFR').dropna(); print('adj last', a.index[-1].date(), 'max gap days', int(a.index.to_series().diff().dt.days.max()))"
    # 4. re-include SOFR: delete its entry from private/systems/rob_dynamic/instrument_exclusions.yaml,
    #    regenerate config (-> 117), confirm order-time covariance has finite SOFR variance (0 NaNs).

## Refreshing the tail over time
The deferred legs get ~1 new IB bar/day. Re-run `ib_sofr_splice` (report) periodically to refresh the
cache, then `--rebuild --use-cache` (or let the standard `csi_sync_reingest SOFR` incremental pick it up
via the hook). At the ~2.7yr tenor a day or two of staleness is immaterial.
