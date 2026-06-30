# CSI Data (csidata.com) + "Unfair Advantage" as a Deep-History Futures Source

Research note for using **CSI Data / Unfair Advantage (UA)** as a *deep historical*
data source to complement Interactive Brokers (which only carries ~recent history)
for systematic futures backtesting in pysystemtrade.

> **Caveat:** This is general desk research from CSI's own site plus reputable
> third parties. Pricing and feature details change frequently — **confirm directly
> with CSI** before committing. Points flagged "uncertain" below are not fully
> resolved from public sources.

---

## 1. Data coverage & depth

- **Breadth:** CSI advertises **110+ commodity exchanges worldwide**, thousands of
  futures contracts, plus stocks (US/Canada/UK), ~20k US mutual funds, ~160 FX
  pairs, ~70 crypto cross-rates, and options on indices/futures. Futures come in
  **RTH (floor/spot), ETH (electronic) and Combined** flavours, plus cash/spot
  series for many domestic markets.
  ([UA overview](https://www.csidata.com/?page_id=14))
- **Depth:** CSI claims it "carries most world markets back to the **first day of
  trading**" — i.e. genuinely multi-decade, 50+ years for the oldest US commodity
  markets. How much of that you actually *receive* depends on your plan (see Cost):
  individual annual plans bundle **10 years**, the "Gold" package **30 years**, and
  the Professional Edition is **unlimited**; extra history is buyable per year.
  ([Data Coverage FAQ](https://www.csidata.com/?page_id=450),
  [UA overview](https://www.csidata.com/?page_id=14))
- **Individual contracts vs continuous:** UA provides **both**. You can extract
  **per-delivery-month individual contract histories** *and* have UA build
  continuous series — **back-adjusted**, proportional/ratio-adjusted, perpetual
  (time- or open-interest-weighted), and Gann contracts.
  ([UA overview](https://www.csidata.com/?page_id=14))
- **Data quality:** Strong reputation. An independent study in *Futures Magazine*
  reportedly found CSI's error/omission rate **lower than all competitors tested**,
  and CSI states errors are **hand-checked daily by analysts**. This is the source
  many CTAs/vendors historically standardised on.
  ([Data Coverage FAQ](https://www.csidata.com/?page_id=450))
- **Fit for AFTS-style multi-decade backtests:** **Yes.** Decades of clean,
  per-contract EOD futures across ~global exchanges is exactly what forecast fitting
  for Carver's *Advanced Futures Trading Strategies* needs. EOD only — **no
  intraday/real-time**, which is fine since we use IB for execution, not CSI.

## 2. Access methods

- **Windows-only:** **Confirmed.** UA is an old **32-bit native Windows
  application** (`UAd.exe`); CSI has never shipped a Linux/macOS build. The only
  documented way to obtain CSI data is through the UA rich client.
  ([UA overview](https://www.csidata.com/?page_id=14),
  [UA API FAQ](https://www.csidata.com/?page_id=461))
- **Linux / Wine / VM:** No native option. CSI's own API FAQ notes Wine has been
  *attempted but failed* — specifically the `CopyRetrievedDataToArray` /
  `CopyRetrievedDataToArray2` COM calls (variant safearray handling). Practical
  answer for us: **run UA inside a Windows VM** (or a small dedicated Windows box).
  Headless is not officially supported, but UA can update unattended once configured.
  ([UA API FAQ](https://www.csidata.com/?page_id=461))
- **Automation — two real options:**
  1. **Auto-maintained export portfolios (recommended, no coding).** You define an
     export "portfolio" once (ASCII/CSV, chosen symbols, frequency). Thereafter the
     **export files are refreshed automatically at each daily data-distribution
     update** — UA writes the CSVs for you. UA itself updates in **unattended mode**
     on CSI's release schedule. This is the standard way users get a daily CSV drop.
     ([UA overview](https://www.csidata.com/?page_id=14),
     [Developer doc](https://www.csidata.com/custserv/onlinehelp/HowToGuide/DevDoc.htm))
  2. **API2 (OLE/COM automation).** A documented COM interface (`UAd.exe` server,
     `ua.tlb` type library) with `RetrieveContract()`, `RetrieveSnapshot()`,
     `CopyRetrievedDataToArray()` etc. Samples exist for **C++, C#, VBA/Excel,
     Perl**; **Python works via a COM bridge** (`win32com`) but variant-array
     passing is noted as fiddly. Some command-line launch args exist (e.g. loading a
     saved scanner layout). There is **no REST API / SDK / cloud endpoint**.
     ([UA API FAQ](https://www.csidata.com/?page_id=461),
     [Developer doc](https://www.csidata.com/custserv/onlinehelp/HowToGuide/DevDoc.htm))
  - *Uncertain:* whether full API2 automation is enabled on the cheapest **personal**
    tiers vs requiring Professional — not stated publicly; confirm with CSI.

## 3. Export format

- **Formats:** CSI/QuickTrieve (binary), MetaStock, CSIM, and **ASCII/CSV**. For us,
  **ASCII/CSV** is the relevant one; avoid the Excel path (reported to cause issues).
  ([UA overview](https://www.csidata.com/?page_id=14),
  [Exporting CSI to ASCII](https://www.stockblocks.com/support/csi/ua_exporting_csi.htm))
- **Per-contract files:** Yes — one CSV per delivery month, named **symbol + delivery
  code**, e.g. `AC_2005M.CSV`, `YM_2000Z.CSV` (base symbol, year, month letter).
  Default export path `\ua\Files\...`.
  ([Trading Evolved / CSI ingest writeup](https://weisser-zwerg.dev/posts/trading_evolved_1/))
- **Column layout is configurable.** UA lets you pick the field order; common choices
  are **`DOHLCV`** (Date, Open, High, Low, Close, Volume) or the richer
  **`DNOHLCviVI`** (adds delivery number, contract vs total volume & open interest).
  Set separator = comma and "include century". CSI docs show a default date as
  `YYYYMMDD` (e.g. `20020102`), **but the date/time field is configurable** — which
  matches what we already confirmed locally: CSI can emit ISO timestamps like
  `2023-12-18T06:00:00+0000`.
  ([Exporting CSI to ASCII](https://www.stockblocks.com/support/csi/ua_exporting_csi.htm),
  [Trading Evolved writeup](https://weisser-zwerg.dev/posts/trading_evolved_1/))
- **Match to our pipeline:** Effectively identical to the **barchart** ingestion we
  already run. `sysinit/futures/barchart_futures_contract_prices.py` uses a generic
  `ConfigCsvFuturesPrices(input_date_index_name="Time", input_column_mapping=...)`
  and a `market_map` from short symbols → PST instrument codes, with per-contract
  filenames `SYMBOL+monthletter+yy`. CSI's `Time,Open,High,Low,Close,Volume` +
  `AE→AEX`, `AL→ALUMINUM` slots straight in.

## 4. Cost / licensing (USD, "Personal and Private Use" tier; verify currency of figures)

From CSI's published UA price list ([archived price list](https://www.csidata.com/custserv/onlinehelp/docs/UAPRICEStort5.htm_old)):

| Package | License fee | History bundled | Annual (prepaid) | Monthly | Extra history |
|---|---|---|---|---|---|
| **World Futures** | $135 | up to 10 yr | ~$540/yr ($45/mo) | $56.25/mo | $20/yr |
| **North American Futures** | $60 | up to 10 yr | ~$313/yr ($26.10/mo) | $32.62/mo | $20/yr |
| World Futures Options | $175 | 1 yr | ~$475/yr | $49.50/mo | $200/yr |

- **Professional Edition** (unlimited history): World Futures **$570 license +
  ~$3,072/yr**; "All Market Categories" ~$10,714/yr. Overkill for our needs.
- **History-only / one-off:** CSI sells history-only pulls. A third-party writeup
  reports buying **~20 years of World Futures history-only for ~$350 USD** — likely
  the most cost-effective route for a one-time deep-history seed.
  ([Trading Evolved writeup](https://weisser-zwerg.dev/posts/trading_evolved_1/))
- **Trial:** **$20 trial** (limited symbols, ~18 months history) to validate the
  export format end-to-end before buying.
  ([UA $20 Trial](https://www.csidata.com/?page_id=2662))
- **Licensing / redistribution:** Personal tier is **personal/private use only — no
  redistribution**; commercial/redistribution requires a separate commercial
  agreement. Fine for our own internal backtesting; do **not** republish the data.
  ([License & Terms](https://www.csidata.com/?page_id=824),
  [Commercial Sales](https://www.csidata.com/?page_id=136))

## 5. pysystemtrade / Rob Carver fit

- **Carver historically used CSI.** His blog references CSI Data as a futures source
  and notes he wrote **his own rollover code** because vendor continuous-series roll
  methods didn't match his needs (he trades on **back-adjusted** prices to avoid
  spurious forecast jumps at roll).
  ([Carver: futures rolling](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html))
  This argues for taking **CSI individual-contract** files and building
  multiple/adjusted prices **inside pysystemtrade** rather than importing CSI's
  back-adjusted continuous series.
- **Symbol mapping:** Already half-done. The repo's `market_map`
  (`sysinit/futures/barchart_futures_contract_prices.py`) maps short codes to PST
  instruments. CSI uses its own **Factsheet** symbology, so we'd build an analogous
  `csi_market_map` (CSI symbol → PST instrument), cross-referencing the CSI Factsheet
  / `cdbfacts.adm` commodity-properties file.
- **Rolls / expiry data:** CSI encodes **delivery month in the filename** and (via
  the `DNOHLCviVI` layout) exposes per-contract **volume + open interest**, which is
  what roll-calendar generation needs. Whether CSI exports **explicit expiry/
  first-notice dates** per contract is **uncertain** from public docs — commodity
  properties live in `cdbfacts.adm`, but confirm the export contains usable expiry
  fields. In practice pysystemtrade builds roll calendars from price/volume/OI
  overlap (`build_roll_calendars.py`), so explicit expiry dates are helpful but not
  strictly required.
- **Building multiple/adjusted prices:** Standard PST flow applies — load CSI
  per-contract CSVs → `contract_prices_from_csv_to_db` →
  `build_roll_calendars` → `build_multiple_prices_from_raw_data` →
  `adjustedprices_from_db_multiple_to_db`.

## 6. Recommendation

**CSI is a strong deep-history complement to IB for this setup** — decades of clean,
per-contract EOD futures, in a CSV layout essentially identical to our existing
barchart ingestion, from the vendor Carver himself used. IB stays as the live/recent
and execution source; CSI provides the multi-decade tail for forecast fitting.

**Practical wiring:**
1. Buy a **History-only World (or North American) Futures** pull for the seed (or
   start with the **$20 trial** to validate format), then optionally an annual sub
   for ongoing daily updates.
2. Run **UA in a Windows VM** (or a cheap always-on Windows box). Wine is not viable
   for the COM bits.
3. In UA, create an **ASCII/CSV auto-export portfolio**: layout `DOHLCV` (or
   `DNOHLCviVI` if we want OI for rolls), comma separator, include century,
   per-contract files. Exports then **refresh automatically on each daily update**.
4. **Sync the export folder** to the Linux box (Syncthing / SMB share / rclone /
   Dropbox) so pysystemtrade sees a fresh CSV drop.
5. Add a **CSI variant of the barchart ingester**: a `ConfigCsvFuturesPrices` with
   `input_date_index_name="Time"`, ISO date format, CSI column mapping, plus a
   `csi_market_map`. Reuse `init_db_with_csv_futures_contract_prices` unchanged.
6. Build roll calendars + multiple/adjusted prices with the **existing PST scripts**
   (don't rely on CSI's continuous series).

**Net:** low effort to integrate (the pipeline already exists), modest cost
(~$350 one-off seed, or ~$300–540/yr for ongoing), high payoff for deep backtests.

---

## Sources

- CSI — Unfair Advantage overview: https://www.csidata.com/?page_id=14
- CSI — Data Coverage FAQ: https://www.csidata.com/?page_id=450
- CSI — UA API FAQ (automation / Wine): https://www.csidata.com/?page_id=461
- CSI — UA Developer Document (API2/OLE, file formats): https://www.csidata.com/custserv/onlinehelp/HowToGuide/DevDoc.htm
- CSI — Extracting data (History version): https://www.csidata.com/?p=1285
- CSI — UA price list (archived): https://www.csidata.com/custserv/onlinehelp/docs/UAPRICEStort5.htm_old
- CSI — $20 Trial: https://www.csidata.com/?page_id=2662
- CSI — License Agreement, Terms & Conditions: https://www.csidata.com/?page_id=824
- CSI — Commercial Sales: https://www.csidata.com/?page_id=136
- CSI — UA Users Manual (PDF): https://www.csidata.com/custserv/onlinehelp/docs/uaman.pdf
- Stock Blocks — Exporting CSI database to ASCII/CSV (format details): https://www.stockblocks.com/support/csi/ua_exporting_csi.htm
- Trading Evolved — ingest CSI-Data futures into Zipline (per-contract naming, $350/20yr, Windows-only): https://weisser-zwerg.dev/posts/trading_evolved_1/
- Rob Carver — Systems building: futures rolling (uses CSI, own roll code): https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html
- pysystemtrade (repo): https://github.com/robcarver17/pysystemtrade
- Local: `sysinit/futures/barchart_futures_contract_prices.py`, `sysdata/csv/csv_futures_contract_prices.py`
