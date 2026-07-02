# CSI / Unfair Advantage export design — optimal settings for pysystemtrade

Designed from what PST needs downstream, NOT from the earlier ad-hoc sample exports.

## Anchor principle
pysystemtrade ingests **raw per-delivery-month contract prices (OHLCV)** and builds its
OWN roll calendars (volume-based) and OWN Panama back-adjustment. Therefore we want UA to
emit the *rawest* data with *maximum* history and turn OFF all of UA's continuation/adjust
features (they would double-adjust or destroy the per-contract structure PST relies on).

## Decision table (UA option → setting → why)
| UA option | Setting | Why for PST |
|---|---|---|
| Series type: individual vs back-adjusted/computed/perpetual | **Individual / actual contracts** | PST builds its own rolls + Panama; a back-adjusted series would double-adjust and remove per-contract structure |
| Roll Trigger (vol / OI / date / days-before-expiry) | **N/A — not used** | only applies to back-adjusted series; PST rolls itself via volume-based roll calendars |
| Detrend method (close-close / ratio / add-subtract) | **None / N/A** | PST does difference (Panama) adjustment itself |
| ASCII layout | **DOHLCV** (Date,Open,High,Low,Close,Volume) | matches CSI_CONFIG columns; UA note: this order avoids extra prompts |
| ASCII separator | **comma** | CSV |
| Include century (4-digit year) | **yes** | unambiguous dates |
| "Form Columns" (fixed-width pad) | **unchecked** | clean delimited CSV, no padding |
| Weekend/holiday insert+fill | **OFF** | no synthetic zero-volume bars; PST wants real observations only |
| Open Interest field | **omit for now** | PST's futuresContractPrices is OHLCV; OI has nowhere to live yet (revisit if we ever use OI for roll/liquidity) |
| History depth | **earliest available → present** | deep history is the entire reason we're using CSI |
| Delivery months | **all listed contracts** | full roll chains; PST's calendar selects the liquid month |
| Prices | **unadjusted, native currency** | raw traded prices; PST config holds point value / FX |
| File structure | **one file per contract** | matches `<SYM>_<YYYYMM>.csv` → our --rename regex |
| Filename | **`<Symbol>_<YYYYMM>.csv`** (UA per-month default) | our rename maps CSI sym→PST code, delivery month→YYYYMM00 |
| Frequency | **daily EOD** | CSI is EOD; ingested as Day_ frequency |
| Update mode | **incremental daily maintenance** | UA auto-maintains portfolio files each distribution; nightly cron ingests |
| Output directory | **Z:\** | the Samba share → `private/data/futures/csi` (lands as user csi) |

## Genuine judgment calls (decide together)
1. **Date-only vs ISO datetime column.** The earlier samples used ISO datetime with a tz
   offset (`2024-08-19T05:00:00+0000`, header `Time`). For EOD data the time component is
   cosmetic and the offset shifts with DST (05:00 vs 06:00) — noise. Two clean options:
   - (a) **Keep ISO datetime** — already validated; --rename strips the tz offset → tz-naive
     `%Y-%m-%dT%H:%M:%S`. Zero further code change.
   - (b) **Date-only `YYYYMMDD`** — cleanest for EOD; would need CSI_CONFIG date format +
     column-name tweak. Arguably more "correct" but churns config.
   LEAN: (a) keep ISO datetime (works, consistent with the tz-strip fix). Low risk.
2. **Weekend/holiday padding: OFF** (recommended). Confirm UA's insert-weekends checkbox is off.
3. **Open Interest: omit** now; revisit only if we extend PST to use OI.
4. **History depth / delivery months: confirm "all available"** — some UA portfolios default
   to a limited date range or nearest-N contracts; we want everything.

## Sequencing
1. Set the export template per the table above.
2. Small test export (AE→AEX, AL→ALUMINIUM) to Z:\ → validate full chain on host.
3. Build the full **CSI_SYMBOL_MAP** (CSI symbol → PST code) for the research universe (501).
4. Export the universe; schedule UA daily; add nightly `csi_pipeline --rename` + process cron.

## Sources
- https://www.csidata.com/custserv/onlinehelp/OnlineManual/backadjustedoverview.htm (series/roll/detrend)
- https://www.stockblocks.com/support/csi/ua_exporting_csi.htm (DOHLCV, separator, century, Form Columns, date format)
- https://www.csidata.com/custserv/onlinehelp/docs/uaman.pdf (UA users manual)
