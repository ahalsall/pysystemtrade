# SOFR (CSI SR3) re-export — precise UA fix for the 2023-04-14 gap

**Status:** SOFR EXCLUDED from live rob_dynamic (data-quality) until this is done. **Fix = UA re-export (below).**
**Confirmed:** the data EXISTS in CSI — this is a UA *export-config* gap, not a CSI data gap.

## Diagnosis (confirmed 2026-07-17)
- SOFR = CSI **SR3** = CME 3-Month SOFR future. Catalog (commodityfactsheet.csv):
  `SR3 ... StartDate 2018-05-07, EndDate 2026-07-06, IsActive=1, LastTotalVolume 2,297,695, DeliveryMonths SSVSSVSSVSSV`
  => CSI has CURRENT, high-volume SR3 data. The data is there.
- Our raw export (private/data/futures/csi/UA/Data/PST/SR3_*.csv) has a hard cutoff at **2023-04-14** for the
  **deferred quarterly IMM contracts**, while the front quarterly (202606), the monthly serials, and far
  forwards DO get the ongoing refresh. Verified in-CSV: SR3_202609.csv trades in size on 2023-04-14 then 0
  rows after; SR3_202606.csv runs to 2026-07-16.
- Effect: with the (intentional) roll offset -1000, SOFR stitches a ~2.7-yr-out quarterly across 2023->2026
  (202603 -> 202606 -> 202609 -> 202612 -> ...). All those quarterlies except 202606 are frozen at 2023-04-14
  -> ~1183-day gap in the back-adjusted series -> NaN variance in the order-time covariance -> auto-dropped.
- ROOT CAUSE: the UA SR3 portfolio is NOT maintaining the deferred quarterly `V` (Mar/Jun/Sep/Dec) contracts
  past the one-time deep-history batch (2023-04-14). The serial `S` months + front quarterly + far forwards
  are maintained; the deferred quarterly chain is not.

## The UA fix (Unfair Advantage, Windows VM)
Goal: make UA re-fetch + maintain the full deferred quarterly IMM chain with current data.

1. **First, confirm in UA (2-min sanity check):** open SR3 contract **Sep-2026 (202609)** and check the chart/
   data extends past 2023-04-14 (the catalog says it should — active to 2026-07-06). If UA SHOWS current data
   for 202609 but our CSV is stale -> it's purely a portfolio/export setting (proceed to step 2). If UA itself
   has no 202609 data past 2023-04-14 -> contact CSI support (unexpected given the active catalog entry).
2. **Fix the SR3 portfolio export settings** (see notes/concepts/csi_export_design.md decision table):
   - **Delivery months = ALL listed contracts** (not "nearest-N" / not a limited set). This is the key one:
     the deferred quarterly chain must be in the maintained set.
   - **History depth = earliest available -> present.**
   - Series type = **individual/actual contracts** (NOT back-adjusted), DOHLCV, comma, 4-digit year,
     Form-Columns off, weekend/holiday fill OFF, one file per contract `SR3_<YYYYMM>.csv`, native currency.
3. **Force a full re-distribution/re-export of SR3** (not just incremental) so the frozen contracts refresh
   to present -- specifically these 29 currently-frozen quarterly contracts:

       202309 202312 202403 202406 202409 202412 202503 202506 202509 202512
       202603 202609 202612 202703 202706 202709 202712 202803 202806 202809
       202812 202903 202906 202909 202912 203003 203006 203009 203012

   (Critical for the current gap: 202603 onward. The export writes them to Z:\ -> our csi landing dir.)
4. Going forward, keep "all delivery months" so the deferred quarterly chain stays current (else this recurs).

## After the export lands (our side)
    uv run python -m sysinit.futures.csi_sync_reingest SOFR --bootstrap   # rebuild continuous series
    uv run python -m sysinit.futures.roll_calendar_audit | grep -i sofr    # expect NOT stale
    uv run python -c "from sysproduction.data.prices import diagPrices; import numpy as np; a=diagPrices().get_adjusted_prices('SOFR'); print('max adj gap days', int(a.index.to_series().diff().dt.days.max()))"  # expect a small normal number, not ~1183
Then RE-INCLUDE SOFR: delete the SOFR entry from private/systems/rob_dynamic/instrument_exclusions.yaml, add
SOFR back to config.yaml's instrument_weights/forecast_weights/forecast_div_multiplier (or regenerate), and
confirm the order-time covariance has a finite SOFR variance (0 NaNs).
