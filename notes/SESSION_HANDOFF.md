# SESSION HANDOFF — pysystemtrade Barchart pipeline & AFTS strategy work

**Purpose:** durable backup so this work can be fully resumed from a fresh session.
**Last updated:** 2026-06-29 (work by Andrew Halsall + Claude).
**Repo:** /home/andrew/pysystemtrade · branch `develop` · fork `ahalsall/pysystemtrade` (origin), upstream `robcarver17/pysystemtrade`.

---

## 0. Mission / goals
1. Wire Barchart futures data into pysystemtrade for backtesting. ✅ done & verified.
2. Automate barchart.com → CSV → parquet/mongo build-out within Barchart's daily download limit. ✅ done, cron live.
3. Reproduce **AFTS Strategy 17** and apply **Strategy 25 dynamic optimization**, backtested on our Barchart data. ⏳ researched; blocked on S17 book definition.
4. Eventually go to production / live trading via Interactive Brokers. 🔜 roadmap captured (notes/production_ib_roadmap.md).

**Knowledge base (notes/concepts/):** portfolio_and_dynopt, rob_reports, costs_and_capital, rob_system_allocation (allocation by family + realized rule Sharpe), canada_tax_brokerage (NOT tax advice). Canada research key findings: futures gains = capital (50% incl) OR business income (100%, risk for active traders); s.39(4) election EXCLUDES commodity futures; outright futures NOT allowed in RRSP/TFSA (IB bars them; futures-ETF is the only sheltered exposure); IB entity = Interactive Brokers Canada Inc (CIRO), **CIPF covers futures (US SIPC does not)**; NO Canadian tax-free spread-bet equivalent (so only the "real futures via IB, taxable" half of Carver's playbook applies); must report to CRA in CAD regardless of IB base setting; **recommendation: CAD base currency, hold USD balances, convert in blocks via IDEALPRO**. Confirm all with a CPA.

**IB Canada / market data (notes/concepts/ib_canada_instruments_and_data.md):** nearly all our exchanges tradeable by a Canada-resident IB individual EXCEPT **LME** (IB's LME access is synthetic OTC, excluded for Canada) → drop the 6 LMEOTC instruments (ALUMINIUM_LME, COPPER_LME, LEAD_LME, NICKEL_LME, TIN_LME, ZINC_LME) from the LIVE set (they have COMEX equivalents anyway; still OK for backtest research). Market data: IB historical likely needs the same per-exchange subscription as streaming (the "free historical" idea was NOT confirmed) — but we can develop/backtest/pick instruments with ZERO IB subs by using our Barchart data; subscribe to streaming only at go-live, only for executed exchanges (US futures bundle ~$5-10/mo + Eurex Core ~€1/mo; ICE pricier; fees largely WAIVED once monthly commissions exceed ~$5-30; keep non-professional status). Our 200 cost-screened instruments span ~22 IB exchanges, ~75% on 7 majors (CME/EUREX/CBOT/NYMEX/COMEX/ICEEU/NYBOT). DECISION: trade-data architecture could keep Barchart as the price source + IB for execution, or subscribe to IB bundles (which also give historical) for executed exchanges.

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
- **ORDER PLACEMENT TESTED (2026-06-30):** with Read-Only API DISABLED, ran sysinit/futures/ib_order_test.py — submitted BUY 1 MES LIMIT ~30% below market → status Submitted/active (write works), then cancelled cleanly; account left FLAT. Notice 10349 (TIF defaulted to DAY by order preset) is harmless. Full filling round-trip (market buy+sell to close) NOT yet done. Re-enable Read-Only when doing data-only testing.
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
