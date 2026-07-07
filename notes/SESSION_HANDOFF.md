# SESSION HANDOFF — pysystemtrade Barchart pipeline & AFTS strategy work

**Purpose:** durable backup so this work can be fully resumed from a fresh session.
**Last updated:** 2026-07-01 (work by Andrew Halsall + Claude).
**Repo:** /home/andrew/pysystemtrade · branch `develop` · fork `ahalsall/pysystemtrade` (origin), upstream `robcarver17/pysystemtrade`.

---

## ⏱ RESUME HERE (2026-07-06)
**CSI Batch 1+2 INGESTED: 94 instruments of deep history** (most 20–30yr). Map 100% resolved
(`csi_symbol_map.csv`, 94 verified via KNOWN_OVERRIDES in build_csi_symbol_map.py). Roll validation
(`validate_roll_calendars.py`: monotonic+valid+truncation + vs-Rob): **77/94 clean.**
FIXED: SOYMEAL/SOYOIL monotonicity (dedupe self-heal), **GAS_US** (NG2, 30yr, for thin GAS_US_mini),
**USDKRW** quarterly→monthly (config-vs-data mismatch), **SOYMEAL** -90→-45 offset (liquidity 47→79%).
Seasonal divergences ASSESSED via liquidity check: RICE/LEANHOG/LIVECOW/SOYOIL our roll is *more*
liquid than Rob → ACCEPT (Rob's blog: "no one true set of stitching dates"; his shipped calendars
are approximate). KOSPI_mini/GOLD_micro = rank-metric artifact (many contracts).

**TRUNCATIONS — root-caused (2026-07-06): mostly DATA issues, NOT config patches** (user's caution):
- **FTSE100**: FTK had only 2018+ w/gaps → user found **FFI** (ICE, full history, GBP, exch Z);
  mapped FFI→FTSE100, FTK in IGNORE_CSI_SYMBOLS. Re-export FFI (overwrites limited FTK data).
- **US20-new** (missing 2024-25 quarters), **FEEDCOW** (scattered quarter gaps 2016+) → incomplete
  export; RE-EXPORT / verify CSI coverage.
- **NASDAQ** (full-size ND3 delisted ~2015) → market structure; 1996-2015 valid, ADD E-mini NQ for current.
- **NOK** thin minor cross (~3mo windows, 5-day overlaps) → accept. **GAS_US_mini** thin (use GAS_US).
  **YENEUR** Dec-2000 CSI gap (§5.5). Principle: don't patch roll config to mask incomplete data.
**CATALOG (2026-07-06):** user supplied `private/commodityfactsheet.csv` (2604 CSI markets:
SymbolUA, Name, Exchange, Currency, ContractSize, **LastTotalVolume**, Start/End). Built
`csi_catalog_map.py` (reverse PST→CSI lookup, volume-ranked) — BUT it agrees with our 94 spec-verified
only ~37/95 (name matching too coarse for same-family: soy meal/oil, EU sector vs main index, micros).
So it's an **AUDIT-FIRST LOOKUP** (candidates+volume+coverage dates), NOT a blind auto-mapper; real map
stays in KNOWN_OVERRIDES. Wins: FFI→FTSE100 (deep, 1984), NQ→NASDAQ (liquid), confirmed TWE (US20-new)
data exists → incomplete export. Pre-registered CYN→BRENT, FFI→FTSE100, NQ→NASDAQ; FTK/ND3 in
IGNORE_CSI_SYMBOLS. **COVERAGE REPORT** (`private/csi_coverage_report.csv`, reliable): 65/95 verified
are ≥20yr (grains→1949, metals 1963-75, FX 1972, gold 1975); flagged THIN: FEEDCOW/NOK/SEK/RICE/OATIES,
US20-new(vol0)/NASDAQ_mini(vol0)/BRENT-CYN. ~179 more deep candidates in the tentative set → prioritize
next exports by depth+volume.
UA shopping lists: `private/csi_batch1_shopping_list.txt`, `csi_batch2_shopping_list.txt`.
Prior milestones: 07-01 pipeline validated end-to-end; 07-06am systemd timer replaced Barchart cron.

Also today: instrument-universe framework (notes/concepts/instrument_universe.md — research 501
vs live tradeable, self-scaling, exclude_instrument_lists); **IB tradeability probe**
(`ib_tradeability_probe.py`) run → 483 tradeable / 101 untradeable → `private/trading_restrictions.yaml`;
**CSI→PST symbol-map builder** (`build_csi_symbol_map.py`) finalized against real `.Specs.txt`.

**Key facts for resuming CSI work:**
- Real UA export = headerless, date-only (`2023-10-23,719.30,...`), nested under `UA/Data/PST/`,
  CSI symbols like `AEX`/`ALI` (NOT AE/AL). `csi_pipeline` handles it (date fmt `%Y-%m-%d`,
  `--rename` walks subdirs + prepends header). Windows needs `EnableLinkedConnections=1` so
  admin-UA sees mapped Z:.
- UA export settings are in notes/concepts/csi_export_design.md (individual contracts, DOHLCV +
  contract-volume `v`, specs file ON, all continuation/adjust features OFF — PST does its own).

**NEXT STEPS (in order):**
1. RE-EXPORT the data-issue truncations (better/complete sources, NOT config patches):
   FTSE100 via **FFI** (already mapped); US20-new + FEEDCOW (fuller CSI pull); add **E-mini Nasdaq NQ**.
   Then `build_csi_symbol_map` → `--rename` → `--instruments all` → `validate_roll_calendars`.
2. YENEUR RY Dec-2000 CSI follow-up (bridge/accept/synthesize from legs — §5.5).
3. Batch 3 → full research universe (~501) in UA; same flow. Map auto-resolves knowns (94 pinned +
   CYN/FFI pre-registered); pin any new residue in KNOWN_OVERRIDES.
4. First-notice/delivery-timing audit for physically-settled names (§5.3 checklist).
5. Once universe is broad: run duplicate-markets + cost/liquidity reports on OUR data to populate
   duplicate_instruments (§4 of instrument_universe.md) + trading_restrictions + bad_markets.
4. Nightly cron: UA scheduled export (auto-login) → `--rename` → process → validate.
5. Dup-date check on CSI+barchart/IB tail-merge (saw 23:00 vs 00:00 mix).
6. Pipeline flow now = 3 cmds (map build → --rename loads csi_symbol_map.csv → --instruments all).
QA audit = task #25 (roll process circumvention now partially discharged via validate_roll_calendars).

---

## 0. Mission / goals
1. Wire Barchart futures data into pysystemtrade for backtesting. ✅ done & verified.
2. Automate barchart.com → CSV → parquet/mongo build-out within Barchart's daily download limit. ✅ done, cron live.
3. Reproduce **AFTS Strategy 17** and apply **Strategy 25 dynamic optimization**, backtested on our Barchart data. ⏳ researched; blocked on S17 book definition.
4. Eventually go to production / live trading via Interactive Brokers. 🔜 roadmap captured (notes/production_ib_roadmap.md).

**Knowledge base (notes/concepts/):** portfolio_and_dynopt, rob_reports, costs_and_capital, rob_system_allocation (allocation by family + realized rule Sharpe), canada_tax_brokerage (NOT tax advice). Canada research key findings: futures gains = capital (50% incl) OR business income (100%, risk for active traders); s.39(4) election EXCLUDES commodity futures; outright futures NOT allowed in RRSP/TFSA (IB bars them; futures-ETF is the only sheltered exposure); IB entity = Interactive Brokers Canada Inc (CIRO), **CIPF covers futures (US SIPC does not)**; NO Canadian tax-free spread-bet equivalent (so only the "real futures via IB, taxable" half of Carver's playbook applies); must report to CRA in CAD regardless of IB base setting; **recommendation: CAD base currency, hold USD balances, convert in blocks via IDEALPRO**. Confirm all with a CPA.

**IB Canada / market data (notes/concepts/ib_canada_instruments_and_data.md):** nearly all our exchanges tradeable by a Canada-resident IB individual EXCEPT **LME** (IB's LME access is synthetic OTC, excluded for Canada) → drop the 6 LMEOTC instruments (ALUMINIUM_LME, COPPER_LME, LEAD_LME, NICKEL_LME, TIN_LME, ZINC_LME) from the LIVE set (they have COMEX equivalents anyway; still OK for backtest research). Market data: IB historical likely needs the same per-exchange subscription as streaming (the "free historical" idea was NOT confirmed) — but we can develop/backtest/pick instruments with ZERO IB subs by using our Barchart data; subscribe to streaming only at go-live, only for executed exchanges (US futures bundle ~$5-10/mo + Eurex Core ~€1/mo; ICE pricier; fees largely WAIVED once monthly commissions exceed ~$5-30; keep non-professional status). Our 200 cost-screened instruments span ~22 IB exchanges, ~75% on 7 majors (CME/EUREX/CBOT/NYMEX/COMEX/ICEEU/NYBOT). DECISION: trade-data architecture could keep Barchart as the price source + IB for execution, or subscribe to IB bundles (which also give historical) for executed exchanges.

**Data sources (3-tier strategy):** IB = current/execution + ~1-4yr recent (live); Barchart/bc-utils = mid (daily-only build-out, cron); **CSI Data (Unfair Advantage)** = DEEP history (decades/50+yr, per-contract, 110+ exchanges, lowest error rate) for forecast fitting — see notes/concepts/csi_data.md. CSI export CSV format (Time/Date,O,H,L,Close,V) ~= our barchart pipeline → low-effort wiring (CSI config FINAL="Close" + CSI-symbol→PST rename; csi/test data + `csi` user already present). CSI is Windows-only (Unfair Advantage); run in a Windows VM with auto-export portfolios (ASCII) or OLE/COM API2 (Python via win32com) to a synced folder our pipeline ingests; ~$135 license + ~$540/yr personal (no redistribution). Confirm: API2 on personal tier, expiry/first-notice fields, current pricing.

**Bigger vision (added 2026-06-30):** this is NOT just "run Rob's code." Goal = full understanding to refine/expand/test other instruments & strategies and trade REAL CAPITAL. Spans: strategy theory (why rules work), code mechanics, futures microstructure, portfolio theory, market psychology, brokerage security/best-practices, and **tax strategy from CANADA (not Rob's UK)** — which affects tradable instruments, costs, and opportunities. Sanity-check & refine, don't blindly replicate. See memory `project-vision-and-scope`. Planned: a `notes/concepts/` knowledge base built incrementally.

User context: Andrew (andrew.halsall@gmail.com), trading from **Canada**, initial capital **CAD ~150,000** (flexible to scale up if justified; ≈ USD ~110k → ~28-32 instruments per Rob's static selection; needs micros for high-value underlyings, available via IB). Has a Barchart **Premier** account (250 downloads/day). Has Rob Carver's *Advanced Futures Trading Strategies* (AFTS) book. AFTS supplementary site (JS-rendered, WebFetch gets only the shell): https://www.systematicmoney.org/afts-asdrqoi234as . Concept index: https://qoppac.blogspot.com/p/pysystemtrade.html .

---

## 1. Environment & infrastructure (all set up)
- **Python/deps:** project uses `uv`. Run via `uv run ...`. Tests need the dev extra: `uv run --extra dev pytest <path>`.
- **MongoDB:** v8.0.12 running on 127.0.0.1:27017, db `production` (already had spread_costs + now FX, prices).
- **Parquet store:** `/home/andrew/pysystemtrade/private/data/parquet` (layout: `futures_contract_prices/{Day@|Hour@|}INSTR#YYYYMM00.parquet`, `futures_adjusted_prices/INSTR.parquet`, `futures_multiple_prices/INSTR.parquet`, `spotfx_prices/`).
- **Config:** `private/private_config.yaml` (GITIGNORED — holds Barchart credentials + parquet/mongo/barchart_* keys). NOT in git.
- **SSH/git auth:** generated `~/.ssh/id_ed25519`, added to GitHub; `origin` is SSH (`git@github.com:ahalsall/pysystemtrade.git`); github.com in known_hosts. Pushes work without prompts.
- **Spot FX:** 12 provided FX series loaded into parquet (backtest prerequisite for non-USD instruments).
- **Scheduling (2026-07-06):** Barchart build-out moved from `cron` → **systemd USER timer**
  `barchart-buildout.timer` (OnCalendar 08:00, `Persistent=true` → catches up after overnight suspend;
  plain cron silently missed 07-03..07-06 on this mobile laptop). Units in `~/.config/systemd/user/`
  (`barchart-buildout.{service,timer}`). The future CSI nightly ingest should use the same pattern.
  Optional hardening: `sudo loginctl enable-linger andrew` (boot-before-login). Production → always-on box.

### Workflow rule (IMPORTANT)
- This environment has **NO TTY**: interactive scripts (`input()`), `sudo`, and git credential prompts will hang/fail. Run interactive / long-running / live-data / real-DB-writing work in Andrew's OWN terminal.
- Run non-interactive things through Claude (Bash) for fast fix-and-rerun loops.

---

## 2. Barchart data pipeline (BUILT & VERIFIED)
Flow: barchart.com → [bc-utils] → split-freq CSVs → [our pipeline] → parquet/mongo → backtest.

### bc-utils (the downloader)
- Cloned at `~/bc-utils` with its OWN venv `~/bc-utils/.venv` (editable install). Kept separate so PST `pyproject.toml` stays clean for upstream syncs (PST env lacks requests/bs4).
- By bug-or-feature (same author who contributes to PST). Writes `Day_INSTR_YYYYMM00.csv` / `Hour_INSTR_YYYYMM00.csv`.
- **GOTCHAS (hard-won):**
  - `barchart_end_year` is EXCLUSIVE (`range(start,end)`): use end=2026 to get 2025.
  - Current bc-utils close column is **"Latest"** (older batches "Close").
  - No native daily-only mode (`do_daily=True`=both, False=hourly-only). We added one.
  - Skips already-downloaded files; delete CSV to force re-download.
  - The split-freq loader MERGES existing DB hourly into a daily contract's Mixed series → stale `Hour@INSTR#...` parquet contaminates daily-only results. Wipe instrument parquet + roll calendar before reprocessing at a different frequency.
  - MIXED-FORMAT GOTCHA (hit on 1st cron run 2026-06-30): the old test-batch CSVs use header "Close", new bc-utils downloads use "Latest"; pipeline config maps FINAL="Latest" → old files fail with KeyError 'Latest'. FIXED via one-time header migration: `cd private/data/futures/barchart && sed -i '1s/,Close,/,Latest,/' *.csv` (rewrites header only, preserves data; no-op on Latest files). All 488 files now "Latest". If format drifts again, re-run or make loader column-robust.

### First build-out cron run (2026-06-30 08:00, ~51 min)
Login OK; built full contract lists (552/instrument monthly); downloaded exactly **225** daily contracts and hit the self-imposed cap cleanly. Process stage: 15 succeeded / 120 failed — dominant failure was the 'Latest' mixed-format issue above (~83), rest are expected thin-data ("can't find valid starting contract" ~19, "empty roll calendar" ~10). Verify: 27 instruments with adjusted prices. After the header migration + reprocess, the 'Latest' failures should clear; remaining failures resolve as build-out accumulates contracts.

### Our committed scripts (in `sysinit/futures/`)
- `barchart_pipeline.py` — non-interactive 4-stage processor (contract prices→roll calendar→multiple→adjusted). Defines its OWN `BARCHART_CONFIG` (FINAL="Latest", date `%Y-%m-%dT%H:%M:%S` NO %z). Datapaths are DOTTED package paths (`private.data.futures.barchart`); a leading `./` resolves WRONG. CLI: `--instruments`, `--all`, `--stages`, `--datapath`, `--roll-calendar-path`.
- `barchart_download.py` — standalone download runner, run BY the bc-utils venv. Reads barchart_* keys from a yaml config. Flags `--config`, `--check-login`. Supports `barchart_daily_only`, `barchart_max_downloads` (cap → returns EXCEED), `barchart_download_list_file`.
- `barchart_orchestrator.py` — run in PST env: download (subprocess to bc-utils venv) → process → verify. Flags `--skip-download`, `--skip-verify`, `--process-all`. Env overrides: BC_UTILS_DIR, BC_UTILS_VENV_PYTHON, PST_PRIVATE_CONFIG.
- `barchart_buildout_instruments.txt` — 224 instruments (Rob's full list ∩ bc-utils CONTRACT_MAP = downloadable).

### Verified end-to-end
AEX, 2024, daily-only: 12 contracts downloaded → 242 clean daily adjusted rows (2024-01-16→12-20, 0 intraday dupes) → backtest read OK (forecasts/positions/account curve). Cap tested live (max=5 → stopped at exactly 5).

---

## 3. Build-out strategy (LIVE via cron)
- Goal: build out all 224 downloadable instruments, full history, daily-only, within 250/day limit.
- `private/private_config.yaml` barchart keys: credentials; `barchart_path: /home/andrew/pysystemtrade/private/data/futures/barchart`; `barchart_download_list_file: .../sysinit/futures/barchart_buildout_instruments.txt`; `barchart_start_year: 1980`; `barchart_end_year: 2026`; `barchart_dry_run: False`; `barchart_do_daily: True`; `barchart_daily_only: True`; `barchart_max_downloads: 225`.
  - NOTE: during the live cap test these were temporarily narrowed; current state may show test scope (AEX/2024) if not reset — CHECK and reset to the build-out values above for production build-out.
- **System crontab (live):**
  `0 8 * * * /home/andrew/.local/bin/uv run --directory /home/andrew/pysystemtrade python -m sysinit.futures.barchart_orchestrator --process-all >> /home/andrew/pysystemtrade/private/logs/barchart_buildout.log 2>&1`
- Each run: ≤225 daily downloads (newest-first, breadth across instruments), stop at cap, process all CSVs, verify. skip-existing → resumes next day. Early runs will show many per-instrument processing failures (insufficient contracts) — expected; they succeed as history accumulates.
- Pause: comment the crontab line. Log: `private/logs/barchart_buildout.log`.
- 357 of Rob's instruments (minis/micros, -ICE/-SGX/-MEFF variants, exotics) are NOT in bc-utils CONTRACT_MAP — can't be pulled this way.
- **LME removed from build-out (2026-06-30):** build-out list now **218 active** (was 224); the 6 `*_LME` are kept as COMMENTED research-only lines in `barchart_buildout_instruments.txt` (untradeable from Canada; redundant with COMEX; uncomment to pull for research). Existing LME data in the DB is retained for research.
- **IB WIRING TESTED & PASSED (2026-06-30):** IB Gateway installed (~/Jts, downloaded installer ~/Downloads/ibgateway-stable.sh) + PAPER account logged in. private_config has broker_account: DU1739659, ib_port: 4002 (paper; live Gateway=4001). Two tests passed: (1) raw ib_async (sysinit/futures/ib_conn_test.py [host port clientid], delayed data) → connected, account visible, qualified MESU6, pulled price; (2) pysystemtrade production stack: dataBlob→dataBroker→connectionIB pulled GBPUSD historical FX (259 rows). API was Read-Only initially (order writes blocked, data works). Gateway logs out ~daily; need IBC for unattended. ib_async 2.1.0.
- **ORDER PLACEMENT TESTED (2026-06-30):** with Read-Only API DISABLED, ran sysinit/futures/ib_order_test.py — submitted BUY 1 MES LIMIT ~30% below market → status Submitted/active (write works), then cancelled cleanly; account left FLAT. Notice 10349 (TIF defaulted to DAY by order preset) is harmless. Full filling round-trip DONE: sysinit/futures/ib_roundtrip_test.py — BUY 1 MES @7557.0 then SELL @7556.75, ended FLAT; commission $0.62/side, realized PnL −$2.49. Complete broker chain (order→fill→position→close→flat) proven on paper. NOTE: Read-Only API currently DISABLED — re-enable in Gateway for safety when doing data-only work. Production order path (pysystemtrade stacks via run_stack_handler) is a separate larger test, not yet done.
- **TENSION (from Rob's reports repo, see notes/concepts/rob_reports.md):** Rob's capital-efficient static instrument selection leans heavily on micro/mini contracts at low capital — exactly the ones bc-utils can't download. Affects our instrument strategy + intersects Canada availability. OPEN QUESTION: Andrew's intended trading capital (drives the selected instrument set: ~8 @ $10k → ~53 @ $1M).
- **Rob's public output as reference:** github.com/robcarver17/reports holds his live production diagnostics (Static_selection_of_instruments, Remove_markets_report, Costs/Slippage, Minimum_capital, Trading_rule_p&l, Dynamic_Optimisation, Strategy_report). Raw base: raw.githubusercontent.com/robcarver17/reports/master/<file>. pysystemtrade_examples repo = runnable blog code by topic.

### Scheduled session monitor
- CronCreate job `0aecc192` (session-only, in-memory) fires **Jun 30 09:33** to read the build-out log and report. Dies if this Claude session closes — if so, just ask "check the build-out log".

---

## 4. TARGET = Rob's actual system (rob_system); S17 = milestone (RESEARCHED)
See `notes/strategy17_dynopt_repo_map.md`, `notes/backtest_roadmap.md`.
- **REAL GOAL (per Andrew):** recreate Rob Carver's ACTUAL live system, not just AFTS S17. That system **IS `systems/provided/rob_system/`** — Rob develops+runs pysystemtrade live and this is his real config. S17 is a simpler validation milestone / subset on the way.
- **Rob's system = book's final fully-combined strategy + Strategy 25 dynamic optimization** (a superset of S17). ~40 rules across 9 families: momentum(4-64), normmom(2-64), assettrend(2-64) [all ewmac variants], breakout(10-320), carry(10/30/60/125), relcarry, relmomentum(10-80), mrinasset1000 (cross-sectional MR), skew abs/rv×180/365 (factors/neg_skew), accel(16/32/64). Config: 170 instruments (FIXED fitted instrument_weights + per-instrument fixed forecast_weights), IDM 2.75, vol target 25%, capital 500k USD, risk_overlay, vol attenuation (use_attenuation list), dynamic opt in stage list, use_instrument_div_mult_estimates True (others fixed).
- `run_system.py::futures_system(sim_data=..., config_filename="systems.provided.rob_system.config.yaml")` — defaults to dbFuturesSimData(); pass our `dbFuturesSimData()` (reads our Barchart data).
- **GATING:** rob_system is data-hungry (170 instruments, asset-class-relative rules, skew needs long history). Our build-out just started → meaningful run needs build-out to accumulate. Can validate WIRING now on the few instruments we have by restricting the instrument list. His fitted weights are on HIS data; for ours we either reuse as-is or re-estimate.
- **WIRING SMOKE-TEST PASSED (2026-06-30):** ran rob_system against `dbFuturesSimData()` on the 8 instruments we have that are also in his config (AEX, ALUMINIUM, BITCOIN, BRE, CAC, CNH, ETHANOL, ETHEREUM). EVERY stage passed end-to-end: data/rawdata (incl asset-class-relative normalised price + raw carry), every rule family (momentum, assettrend, relmomentum, carry, mrinasset1000, skew/factors, accel), scale/cap, combined forecast, subsystem/notional position, IDM, **optimisedPositions (dynamic opt)**, accounts.optimised_portfolio() (249 pts). Method: build `futures_system(sim_data=data)` (it takes config_filename NOT config), then prune `system.config.instrument_weights`/`forecast_weights` to available instruments + set `use_instrument_div_mult_estimates=False`, before any stage call. Script committed: `sysinit/futures/robsystem_smoketest.py` (`uv run python -m sysinit.futures.robsystem_smoketest`) — re-run as build-out grows. Plumbing only — thin test-batch data, not a meaningful backtest.
- Optional external corroboration: Rob's blog qoppac.blogspot.com (NOT fetched — Andrew rejected web pulls of book/strategy content earlier; ask before web research).
- Dynamic optimization (Strategy 25) already implemented: `systems/provided/dynamic_small_system_optimise/` (greedy integer optimizer). Config `small_system:` in defaults.yaml (shadow_cost, tracking_error_buffer, cost_multiplier, shrink_instrument_returns_correlation).
- Production dynamic-opt: `sysproduction/strategy_code/run_dynamic_optimised_system.py`, `sysexecution/strategies/dynamic_optimised_positions.py`.
- Doc caveat: `systems.futures.rules.ewmac` does NOT exist — use `systems.provided.rules.ewmac`.
- **BLOCKED ON:** Strategy 17's exact book definition — which rules/forecasts + weights, instrument scope, fixed vs estimated, vol target/capital. Once provided: build S17 config on rob_system + dbFuturesSimData, run, validate Sharpe/curve, then tune dynamic-opt.

---

## 5b. Production strategy wiring (IN PROGRESS, 2026-06-30)
Strategy `rob_dynamic` = our rob_system + dynamic optimisation in production.
- **Custom run class** (full rob_system stages in production): `sysproduction/strategy_code/run_rob_dynamic_system.py` → `runRobDynamicSystem` (the stock `runSystemCarryTrendDynamic` uses plain RawData and CAN'T run rob_system's asset-relative/skew/vol-atten rules — so we mirror the documented custom-run pattern with myFuturesRawData + volAttenForecastScaleCap + dynamic-opt stages).
- **Config generator** (re-run as build-out grows): `sysinit/futures/make_rob_dynamic_config.py` → writes `private/systems/rob_dynamic/config.yaml` (rob_system config restricted to instruments we have data for; currently 18; base USD for now—CAD pending CAD FX rates; use_instrument_div_mult_estimates False).
- **Registered** (both gitignored): `private/private_config.yaml` → strategy_list.rob_dynamic (load_backtests object=runRobDynamicSystem, reporting=report_system_dynamic) + strategy_capital_allocation (rob_dynamic 100%). `private/private_control_config.yaml` → run_systems.rob_dynamic (backtest_config_filename=private.systems.rob_dynamic.config.yaml) + run_strategy_order_generator.rob_dynamic (orderGeneratorForDynamicPositions).
- **Capital:** set initial TOTAL capital 150000 (base ccy nominal) via dataCapital.create_initial_capital; update_strategy_capital allocated it (rob_dynamic in strategies-with-capital). Margin allocation errored (needs IB margin data; non-fatal for backtest).
- **DRY-RUN PASSED (2026-06-30):** ran the production backtest non-interactively via `strategyRunner(data,'rob_dynamic','run_systems','run_backtest').run_strategy_method()` (the stock `update_system_backtests()` is interactive/no-TTY). Full rob_system built + ran on 18 instruments; stored backtest state to `private/backtests/rob_dynamic/` (had to `mkdir -p private/backtests` first) and wrote RAW optimal positions for all 18 to mongo (verified via dataOptimalPositions). No orders placed. Warnings (divide-by-zero on a thin instrument; "no rules cheap enough for ETHANOL") are thin-data artifacts, non-fatal. The integer dynamic-opt + orders happen later in run_strategy_order_generator (NOT run).
- **ORDER GENERATOR RAN ON PAPER (2026-06-30):** `strategyRunner(data,'rob_dynamic','run_strategy_order_generator','get_and_place_orders').run_strategy_method()` (method name = `name_of_main_generator_method` = "get_and_place_orders"). Produces INSTRUMENT orders on the internal mongo/parquet stack only — does NOT submit to broker (that's run_stack_handler). Works off DB positions, not the broker; missing position limits default to NO_LIMIT.
  - FIRST attempt on all 18 instruments FAILED: "Negative covariance when optimising!" — DATA MATURITY issue: ETHANOL has zero variance (flat prices) and instruments span non-overlapping windows (some Oct-Dec 2024, some Oct-Dec 2025 → no overlap), so the covariance is degenerate. NOT a wiring bug.
  - To demo: cleared optimal positions (rm private/data/parquet/optimal_positions/*), restricted config to 8 overlapping non-degenerate instruments (AEX, ALUMINIUM, BITCOIN, BRE, BRENT-LAST, CAC, CHEESE, ETHEREUM), re-ran backtest + order generator → SUCCESS: dynamic opt selected a sparse integer set: CAC -1, BITCOIN -1, ALUMINIUM +1, BRE +7 (others optimized to 0). Then cleared the instrument stack (clean state).
  - So the FULL production chain (backtest→optimal positions→dynamic-opt integer order generation→instrument stack) is PROVEN on paper. The current private config is the restricted 8-set; re-run make_rob_dynamic_config to expand (will fail order-gen until build-out gives overlapping history across instruments).
- **STACK HANDLER instrument→contract PROVEN (2026-06-30):** `stackHandler(data).spawn_children_from_new_instrument_orders()` spawned contract orders from the instrument orders with parent/child linkage (BRE/20251100 +7, CAC/20241200 -1, BITCOIN/20241200 -1, ALUMINIUM/20251100 +1). Stacks then cleared.
- **ALL-IB PRODUCTION DATA WORKS (2026-06-30) — covariance fixed, current contracts:** pure-IB seed of a 12-instrument liquid set (SP500_micro, NASDAQ_micro, US10, US2, BUND, GOLD_micro, SILVER, CRUDE_W, CORN, JPY, AUD, VIX) via `sysinit.futures.seed_from_ib_batch`, then barchart_pipeline roll/multiple/adjusted → continuous adjusted series ending TODAY + CURRENT/future priced contracts (no gaps, not expired). Regenerated config via `make_rob_dynamic_config <list>` (now accepts explicit list). Re-ran production backtest + order generator → NO "negative covariance" (clean contemporaneous data); dynamic opt selected 6: US2 -2, SP500_micro +1, GOLD_micro -1, VIX -4, CORN -3, JPY -2. Stack handler spawned contract orders on CURRENT contracts (US2/20260900, SP500_micro/20261200, etc.) → BROKER-READY. Stacks cleared.
- **ONLY remaining step for a real paper fill:** disable Read-Only API in Gateway, then run the order generator + stackHandler.create_broker_orders_from_contract_orders → submit to IB paper. (Re-seed/rebuild first so contracts/prices are fresh.) Note: per-contract IB depth ~1yr (shallow → CSI for deep history); some roll picks went far-forward (e.g. CORN 2027-12) — refine roll config later.
- (Superseded) earlier broker-submission blocker was expired contracts from historical barchart data:
- **REAL BROKER SUBMISSION BLOCKED BY DATA CURRENCY (key finding):** our priced contracts are EXPIRED (2024/2025) because our data is historical backfill; IB only trades the CURRENT front month, so `create_broker_orders_from_contract_orders` would be rejected regardless of read-only. The stack handler's broker-submit+fill machinery itself is effectively already proven by the raw ib_async round-trip. To do a genuine strategy-driven paper execution we need CURRENT front-month contract+price data from IB via the production data-maintenance flow (update_sampled_contracts → update_historical_prices → update_multiple_adjusted_prices → roll status), NOT historical barchart. Plus read-only OFF. This is the real remaining gap to live paper trading.
- **STILL NOT DONE:** current-data production flow for ≥1 instrument → real paper execution via run_stack_handler; mandatory position limits + shadow_cost; re-estimate as data matures; CAD base (needs CAD FX); IBC for unattended.

### IB historical depth (measured 2026-06-30) — see notes/concepts/ib_historical_depth.md
IB gives ~3-4yr CONTINUOUS futures history (MES 3yr, GC 3.75yr) + current/forward contracts only (NO expired contracts retained); historical EOD bars returned on paper with no special subscription. So IB can BOOTSTRAP usable full-coverage NOW: current front month (fixes expired-contract execution blocker) + ~3-4yr continuous (fixes dynamic-opt covariance degeneracy + recent forecasts) across all instruments — without waiting for barchart. But shallow vs AFTS 50yr / rob 20yr, and not per-contract/deep-carry. ARCHITECTURE: IB for current+recent (bootstrap via sysinit/futures/seed_price_data_from_IB.py) + barchart for deep history. This is the recommended way to get the covariance/execution working immediately. Confirm depth/subscription on LIVE account.

## 5. Production / IB (roadmap only; not started)
Full roadmap + ordered go-live checklist in `notes/production_ib_roadmap.md`. Headlines: IB Gateway (port 4001) + `ib_async` + IBC; Mongo+parquet via dataBlob; 3-level order stack; daily cron processes (run_systems → run_strategy_order_generator → run_stack_handler); freeze params for production; mandatory position limits + shadow_cost (in private_config) for dynamic opt.

---

## 6. Git state (as of handoff)
- Branch `develop`, in sync with `origin/develop` (before committing `notes/`).
- Our commits on top of upstream merge `a4b41547`:
  - `0f3c70c8` build-out strategy (cap + list-file)
  - `18ead3f8` bc-utils Latest format + daily-only
  - `464e8966` --check-login flag
  - `2614f0af` download + orchestrator
  - `88a62975` pipeline runner
  - `812944dd` uv.lock gitignore
- `private/` is gitignored (credentials, parquet, CSVs, logs never committed).
- `notes/` being committed alongside this handoff.

---

## 7. How to resume in a fresh session
1. Read this file + the 3 roadmaps in `notes/` + memory (`MEMORY.md` index points to barchart-pipeline-project, run-python-and-tests).
2. Check git: `git -C /home/andrew/pysystemtrade log --oneline -8`, `git status -sb`.
3. Check build-out progress: `tail` `private/logs/barchart_buildout.log`; count instruments with adjusted prices: `uv run python -c "from sysproduction.data.prices import diagPrices; print(len(diagPrices().db_futures_adjusted_prices_data.get_list_of_instruments()))"`.
4. Confirm cron still installed: `crontab -l | grep barchart`.
5. If reset needed, the build-out config values are in §3.
6. Next action: get Strategy 17 definition → implement on rob_system + dbFuturesSimData → backtest.

### Paper broker submission attempt (2026-06-30) — gated by streaming data
With Read-Only OFF, ran create_broker_orders_from_contract_orders for the 6 all-IB orders. RESULT: nothing submitted — `liquidity_size_contract_order` (sysexecution/stack_handler/create_broker_orders_from_contract_orders.py:188) calls data_broker.get_largest_offside_liquid_size_for_contract_order_by_leg, which with DELAYED data (no streaming subscription on paper) returns 0 → every order "Cut down ... to 0 because of liquidity" → missing_order, no broker order. IB warning 10167 "market data not subscribed, displaying delayed". No config toggle; hard gate. => Production order SUBMISSION requires LIVE STREAMING market data (the go-live data sub from notes/concepts/ib_canada_instruments_and_data.md: US futures bundle ~$5-10/mo, often commission-waived). Raw ib_async round-trip filled earlier because it bypassed this liquidity sizing. Stacks cleared. To complete a real paper fill: add a streaming market-data subscription in IB Account Management (works on paper), then re-run. (Alternative for a mechanics-only demo: monkeypatch the liquidity size — bypasses a production safety check, paper only.)

### Market-hours calendar helper (2026-06-30)
`sysinit/futures/market_hours_calendar.py` — uv run python -m sysinit.futures.market_hours_calendar [codes...|--all]. Uses PST's IB-sourced (holiday-aware) trading hours: per instrument shows OPEN/CLOSED now (is_contract_okay_to_trade), upcoming daily sessions, and flags EARLY CLOSE (short session) / HOLIDAY (missing weekday). Needs Gateway up (read-only fine). Verified: correctly flagged 2026-07-03 early close (pre-July-4); 10/12 open mid-afternoon, BUND+CORN closed. PST DOES gate order creation on hours (create_broker_orders -> is_contract_okay_to_trade; best algo switches to market near close). So earlier zero-liquidity submission = missing streaming sub + some markets in CME maintenance break.

### Paper submission — after data sub + session fix (2026-07-01 ~05:2x UTC)
Progress: (1) market-data sub ACTIVE (dataType LIVE); (2) "competing live session" (Error 10197) fixed by logging out mobile app/other sessions + RESTARTING the paper Gateway -> live bid/ask/sizes flow (MES 7530.5/7530.75). BUT orders still not created: create_broker_orders -> preprocess_contract_order line 108-116: market_closed = not is_contract_okay_to_trade -> silently returns missing_order. PST trading hours for these contracts = a single liquid window ~15:00-20:00 (next session tomorrow); at 22:1x UTC we're OUTSIDE it -> okay_to_trade False for all (front AND back contract same hours). PST only trades the liquid session (not thin overnight). TZ=UTC didn't change it. So remaining gates: (a) TIMING - run during the liquid window (~15:00-20:00 UTC weekday, avoid Jul-3 early close); (b) ROLL QUIRK - priced contracts are far-forward (SP500_micro Dec-2026, CORN Dec-2027) = thin back-months, should be FRONT month (roll config to fix). For a mechanics-only paper fill NOW: monkeypatch is_contract_okay_to_trade->True (liquidity check still uses real live data). Stacks currently hold 6 contract orders (18-23) + 6 instrument (22-27).

### Roll fix needed before production fill (2026-07-01) — production-correct route chosen
Decision: comply with PST/Rob roll rules (no bypass); wait for a proper liquid-hours window to test.
Diagnosis: auto-generated roll calendars OVER-ADVANCED on sparse IB data. CORN example: roll calendar has a premature final roll Dec-2026->Dec-2027 dated 2026-06-30 (should roll ~mid-Oct 2026 per RollOffset=-60); phantom-row then makes Dec-2027 the priced contract. Correct current hold = Dec-2026. Affects single-month seasonal holds most (CORN=Z, WHEAT=Z, CRUDE_W=Z, SOYBEAN=X); quarterly (SP500_micro/US2=HMUZ) more robust. This is the known "auto roll calendar is a best-guess, needs human review" situation (docs/data.md). FIX: review/correct roll calendars to respect RollOffsetDays -> rebuild multiple/adjusted -> priced contract = correct liquid month -> then run submission in liquid window. Roll-strategy research in flight -> notes/concepts/roll_cycles_and_liquid_contracts.md (will confirm the PST-sanctioned correction method: edit roll calendar CSV vs interactive_update_roll_status vs regenerate). HoldRollCycle/PricedRollCycle per instrument already inspected (CORN Z/HKNUZ, etc). No bypass of is_contract_okay_to_trade (auto-mode classifier blocked it anyway).

### Roll research landed (notes/concepts/roll_cycles_and_liquid_contracts.md) + CONVERGENCE
Confirms: HoldRollCycle config is CORRECT (don't change it); the too-far-forward roll is a SPARSE-DATA symptom. Sanctioned fix (docs §5.2): denser individual-contract prices for held+carry months, and/or hand-edit the roll calendar CSV then rebuild multiple/adjusted + visually validate. Annual-hold seasonals (CORN/WHEAT/SOYBEAN=X, CRUDE_W=Z) are UNFIXABLE on ~1yr IB data (only ~1 held contract/yr) -> genuinely NEED CSI deep history. Frequent-roll (SP500_micro/US2 HMUZ, GOLD_micro GJMQVZ, SILVER HKNUZ, JPY/AUD/VIX) can be hand-corrected on IB data. CONVERGENCE: proper rolls -> need CSI deep history -> so CSI wiring is the natural enabler for a guideline-compliant production run. Top real-money risk flagged: first-notice/delivery on physically-settled contracts via RollOffsetDays (verify per instrument). Also: reuse Rob's fitted weights only after data is adequate.

### Quick-A done (2026-07-01, end of session) — rolls corrected for 10-subset; run in-window TOMORROW
Did the sanctioned CSV roll correction: removed the premature 2026-06-30 roll rows from SP500_micro, NASDAQ_micro, US10, BUND, GOLD_micro, SILVER, JPY, AUD, VIX (US2 was already correct); rebuilt multiple+adjusted (stages multiple,adjusted only — NOT roll, which would re-add them). Priced contracts now correct current liquid months: most 20260900 (Sep-2026), GOLD_micro 20260800, VIX 20260900 (slightly forward for a monthly — RE-CHECK tomorrow). Config regenerated for 10-subset (dropped CORN, CRUDE_W annual-Z seasonals — need CSI deep history). 
TOMORROW ("proper A" + CSI): (1) re-verify rolls incl VIX + GOLD near-roll; (2) run in a LIQUID WINDOW (~15:00-20:00 UTC weekday, avoid Jul-3 early close) with Read-Only OFF + no competing IB session (mobile app!) — order generator -> stack handler -> broker -> paper fills; (3) start CSI deep-history wiring (needs Windows VM + shared folder; ask Claude for setup guidance) to enable seasonals + proper rolls across the universe.
EARMARKED: task #25 QA audit — before live, verify no required PST steps were circumvented by our manual workarounds (capital init, stack clears, hand-edited rolls, direct strategyRunner calls, IB seeding, etc.).

### ✅ PRODUCTION PAPER FILL ACHIEVED (2026-07-01 ~15:14 UTC / 08:14 PDT)
The full production chain executed end-to-end with REAL PAPER FILLS, no bypass:
IB data -> backtest (rob_dynamic 10-subset, roll-corrected) -> optimal positions -> dynamic-opt order generator -> stack handler (instrument->contract->broker) -> IB paper -> FILLS -> DB positions reconciled.
KEY ENABLERS: (1) ran the whole flow with TZ=UTC (PST assumes GMT; machine is PDT -> without this is_contract_okay_to_trade is 7h wrong). This is the LEGITIMATE fix, not a bypass. (2) In the liquid window (15:00-20:00 UTC = 08:00-13:00 PDT for US instruments). (3) Read-Only OFF + no competing IB session (mobile app killed) so live bid/ask (liquidity check) flows. (4) Roll-corrected priced contracts (current liquid months).
FILLS: SP500_micro +1 @7563.0 (Sep-2026), GOLD_micro -1 @4096.7 (Aug-2026), JPY -1 @0.006194 (Sep-2026), AUD -1 (Sep-2026). The "original-best" algo fills passively/incrementally -> it filled 1 lot of each in our ~30s window; remaining target qty + VIX would fill with a continuously-running run_stack_handler. Residual working orders cleared; 4 paper positions left OPEN (can flatten anytime or manage in next cycle).
OPERATIONAL NOTES for production: always run production processes with TZ=UTC (or set machine to UTC); run_stack_handler must run continuously (as the daily process) to complete fills, not one-shot. Build-out cron's --process-all overlaps IB-managed subset -> separate the two pipelines (earmarked). Task #25 QA audit still stands before live money.

### CSI setup STARTED (2026-07-01)
Ingester built + validated: sysinit/futures/csi_pipeline.py (CSI_CONFIG FINAL="Close", CSI_SYMBOL_MAP CSI-sym->PST, --rename <CSISYM>_<YYYYMM>.csv -> Day_<PST>_<YYYYMM00>.csv, reuses split-freq loader + roll/multiple/adjusted). Validated on sample CSI data (AE->AEX parsed 259 daily rows). PERMISSION MODEL: raw CSI lands in private/data/futures/csi/ (owned by `csi` user, read-only to andrew); ingester stages renamed files to private/data/futures/csi_ingest/ (andrew-writable). VM/shared-folder + UA export guide: notes/concepts/csi_setup_guide.md. TODO: full CSI_SYMBOL_MAP for universe (verify spellings e.g. ALUMINIUM), confirm UA export header/date format, pick shared-folder mechanism (Samba recommended), nightly cron (respect barchart_process_exclude separation), deep-backfill seasonals to fix rolls. Also: build-out catch-up run kicked this morning (background, protected by barchart_process_exclude); nightly cron intact.
