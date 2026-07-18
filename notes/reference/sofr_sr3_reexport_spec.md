# SOFR (CSI SR3) re-export spec — fix the 2023-04-14 data gap

**Status:** SOFR is EXCLUDED from the live rob_dynamic universe (data-quality) until this is done.
**Reopen condition:** complete this re-export + `csi_sync_reingest SOFR` -> continuous series -> re-include SOFR.

## The problem (diagnosed 2026-07-17)
SOFR maps to CSI symbol **SR3** (CME 3-month SOFR future, IMM quarterly Mar/Jun/Sep/Dec, roll offset −1000
= intentional, holds a contract ~2.7 yrs out). Our SR3 raw export has a hard **cutoff at 2023-04-14** in the
**deferred quarterly chain**: those contracts' CSVs exist with deep history (2013–2018 start) but the data
STOPS at 2023-04-14. Result: the back-adjusted series can't be stitched past April-2023 (a 1183-day gap),
which produces a NaN variance for SOFR in the order-time covariance -> the optimizer auto-drops it.

It is NOT missing whole contracts and NOT a roll-config or pysystemtrade bug — it is **data-within-CSV**
missing for the deferred quarterly IMM contracts. Two separate captures are visible:
- a one-time DEEP-HISTORY batch snapshotted **2023-04-14** (the frozen quarterly chain), and
- an ongoing export since ~2023 that only refreshes a rolling subset: the FRONT quarterly (202606),
  MONTHLY serials (202604/05/07/08/10/11, 202510/11) and a few far forwards (203106/112, 203303/306/312/406).
The ongoing export is NOT pulling the intermediate deferred quarterly chain — so SOFR can't roll through it.

## Exactly what to re-export (UA / Unfair Advantage), SR3
Re-export these **29 quarterly IMM contracts** with data through the present (they are currently frozen
at 2023-04-14):

    202309 202312 202403 202406 202409 202412 202503 202506 202509 202512
    202603 202609 202612 202703 202706 202709 202712 202803 202806 202809
    202812 202903 202906 202909 202912 203003 203006 203009 203012

Critical for the CURRENT gap (2023→2026, the roll chain SOFR must stitch): 202603 onward
(202603, 202609, 202612, 202703, 202706, 202709, 202712, 202803, 202806, 202809, 202812, 202903, 202906,
202909, 202912). The earlier ones (202309–202512) were held in 2021–2025 under the −1000 roll; refresh them
too for a fully clean series.

**Root cause to fix in the UA export config:** the ongoing SR3 export is set to pull the front quarterly +
monthly serials, but NOT the full DEFERRED quarterly chain. Extend the SR3 export's contract set to include
ALL quarterly IMM months (Mar/Jun/Sep/Dec) out to the tenor the −1000 roll needs (~3 yrs of deferred
quarterlies), so the deferred chain stays current going forward — otherwise this gap will recur.

## After re-export (our side)
    uv run python -m sysinit.futures.csi_sync_reingest SOFR --bootstrap   # rebuild the continuous series
    uv run python -m sysinit.futures.roll_calendar_audit                  # confirm SOFR no longer STALE
    # verify no gap:
    uv run python -c "from sysproduction.data.prices import diagPrices; a=diagPrices().get_adjusted_prices('SOFR'); import numpy as np; g=a.index.to_series().diff().dt.days.max(); print('max gap days', g)"
Then RE-INCLUDE SOFR: remove it from private/systems/rob_dynamic/instrument_exclusions.yaml and regenerate /
edit the config back to include it.

## Verify the fix worked (order-time covariance clean)
    uv run python -m sysinit.futures.factsheet ... (not this) -- instead check the covariance has no NaN:
    # (the diagnostic used to pin this: build get_data_for_objective_instance and check dfo.covariance_matrix
    #  for NaNs; SOFR should have a finite variance and correlations once the series is continuous.)
