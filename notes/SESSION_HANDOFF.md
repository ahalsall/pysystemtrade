# SESSION HANDOFF — pysystemtrade Barchart pipeline & AFTS strategy work

**Purpose:** durable backup so this work can be fully resumed from a fresh session.
**Last updated:** 2026-07-07 (work by Andrew Halsall + Claude).
**Repo:** /home/andrew/pysystemtrade · branch `develop` · fork `ahalsall/pysystemtrade` (origin), upstream `robcarver17/pysystemtrade`.

---

## ⏱ RESUME HERE (2026-07-09 morning)
**✅ OVERNIGHT CAPITAL SWEEP DONE (20% + 25%, clean CSI, 8/8 runs, attribution+curves persisted
in private/backtest_runs/capsweep_vt{20,25}_{cap}/).** `uv run python -m sysinit.futures.backtest_results`
tables all. RESULTS (Sharpe / realized-vol / maxDD / avgDD, funded):
- VT20 (AFTS parity): $110k 0.89/10.8%/-20.5%/-6.5% (81f) · $300k 0.92/13.8%/-38.1%/-9.3% · $500k
  0.92/15.2%/-47.0%/-10.7% · $1M 0.92/16.3%/-56.8%/-11.7% (97f). CLEAN & MONOTONIC.
- VT25: $110k 0.89/13.3%/-40.5%/-9.1% · $300k 0.93/16.9%/-50.2%/-11.1% · $500k 0.83/18.3%/**-76.5%**/-14.6%
  · $1M 0.88/19.6%/-55.7%/-12.7%.
KEY: (1) -76.5% is REAL not contamination (reproduced $500k/25%, avgDD -14.6% also elevated) BUT
specific to $500k/25% — at 20% that point is a normal -47%; it's a discrete-optimiser path
sensitivity, and **20% target is more robust** (monotonic DD, stable SR) = another reason to use
20% (AFTS parity). (2) VOL SHORTFALL confirmed both targets: ~53-54% of target at $110k climbing
to ~78-82% at $1M = the missing-micros gap (task #27). (3) AFTS Table 128: Rob dyn-opt $100k SR
1.06 @ 18.8% vol / $500k 1.22 @ 21.1%; OURS vt20 $110k 0.89 @ 10.8% / $500k 0.92 @ 15.2% -> Rob
deploys ~2x our risk at same capital (micro-rich universe), our SR lower (2022-26 drought in-sample
+ rob_system vs Strategy11 rules), our DD/vol slightly worse (diversification quality + period).
(4) Attribution consistent across all runs = 2020-2025 trend drought in Equity/Bond/Sector/Metals
(recurring losers SP400, US-ENERGY, MSCIWORLD, KR3, GOLD_micro, SMI, ALUMINIUM, BUND); Ags/OilGas/FX
often offset. positions.parquet saved per run for offline window slicing. NEXT: micro decision
(#27, now fully armed with AFTS + this sweep) -> finalize universe -> production (#30). Consider
switching rob_system config default to 20% target (more robust + AFTS parity).

--- (prior night's state) ---
## ⏱ (2026-07-08 night)
**✅ CLEAN CSI-ONLY DB + TRUSTWORTHY BASELINE + AFTS-VALIDATED. Overnight 20% sweep queued.**
State: CSI-only cutover COMPLETE & clean (all core instruments fresh to 2026-07-07, 0
deflator-broken, 0 barchart residue; barchart-buildout timer DISABLED and MUST STAY OFF —
it clobbered the DB at 08:00, see below). Confirmed baseline (full universe 106, $110k, 25%,
estimated weights): **Sharpe 0.89, ann 11.9%, vol 13.3%, skew -0.03, maxDD -40.5%, avgDD -9.1%,
86/106 funded** — reproduced across two clean re-ingests. FAITHFUL-APPLICATION MILESTONE CLOSED:
methodology matches AFTS Strategy 25 exactly (shadow_cost 50, greedy tracking-error, Bσ=0.05τ);
static-selection counts track Rob's report (25/34 vs 28/35); forecast repro ~4% off (data vintage).
**AFTS Table 128 benchmark (Rob dynamic-opt, Strategy 11):** $100k SR 1.06 @ 18.8% vol, avgDD
-9.6%; $500k SR 1.22 @ 21.1%. **Our vs Rob:** avgDD matches (-9.1 vs -9.6); VOL SHORTFALL
(13.3% of 25% vs Rob 18.8% of 20%) = MISSING MICROS (Rob's small-acct universe is micro-rich;
task #27 gates production #30); Sharpe gap (0.89 vs 1.06) = 2022-26 drought in-sample + rules
(rob_system vs Strategy11) + 25 vs 20 target. **-40.5% DD attributed** (2020-2025 drought): Equity
-25 (EUROSTX/SMI/MSCIWORLD) + Bond -11 (BUND/KR10/KR3), offset by Ags/Sector. $500k -76.5% is a
non-monotonic outlier (deeper than $1M) — attribution HUNG on non-PSD-covariance corner case at
$500k, re-verify at 20% first. Persistence infra: sysinit/futures/backtest_results.py -> saved
runs in private/backtest_runs/; `python -m ...backtest_results` tables all. Ref chapter:
private/reference_for_claude/ (AFTS Strategy 25 pdf, read in full). NEXT: overnight 20%-target
capital sweep (`CAPITALS="110000,300000,500000,1000000" uv run python -m sysinit.futures.dynopt_capital_sweep`,
VOL_TARGET=20 default); then micro decision (#27, AFTS-armed) -> finalize universe -> production
paper track (#30). Tasks: #25 QA, #26 SOYMEAL, #27 micros(gates #30), #28 roll truncations,
#29 cutover(keep open till survives tomorrow's dead-timer 08:00), #30 IBKR paper.

--- (contamination incident, now resolved) ---
**🚨🔧 BARCHART TIMER WAS CONTAMINATING CSI — DISABLED; re-ingested clean.** The
"first trustworthy backtest" below was FALSE: the `barchart-buildout` systemd --user timer
(OnCalendar 08:00 daily, set up early in the session for the pre-CSI build-out) fired
**2026-07-08 08:00→09:16**, the morning AFTER the overnight CSI re-ingest, and CLOBBERED the
clean CSI DB — re-added the 75 barchart-only instruments (WHEAT_mini/WHEY…, back to 205) and
overwrote CSI series with STALE barchart data → truncated roll calendars (CORN→2022-09,
SP500→2024-09) → truncated adjusted/multiple. My 07-08 backtests (Sharpe 0.74/0.89, run after
09:16) were on this CONTAMINATED DB → DISCARD. The Phase-2 gate wasn't buggy — it ran before
08:00 when the DB was genuinely clean. CSI CONTRACT DATA IS FINE (CORN contracts overlap richly,
fresh to 2026-07-07). FIX APPLIED: `systemctl --user disable --now barchart-buildout.timer`
(now disabled+inactive, 0 timers) — **MUST STAY DISABLED under CSI-only** (two writers on one
parquet DB = the whole bug). Re-archived contaminated stores (…_bcontam_2026-07-08_1345,
reversible; spotfx+positions preserved), re-ingesting CSI-only from intact staging (147 fresh).
NEXT: on re-ingest done → data_freshness_audit.py must PASS (0 stale/broken/residue) → trustworthy
full-universe backtest + estimated-weights + drawdown attribution (all pending, none valid yet).
Task #29 REOPENED effectively (contamination) — see [[barchart-pipeline-project]].

--- (the below was the contaminated run, retained for context) ---
## ⏱ (SUPERSEDED) 2026-07-08 first-backtest attempt
**✅ CUTOVER DONE → FIRST TRUSTWORTHY BACKTEST (2026-07-08).** CSI-only cutover COMPLETE:
archived 3 futures parquet stores (barchart_archive_2026-07-07_2230, reversible; spotfx +
positions preserved), re-ingested all 147 fresh CSI (0 failed). Gate (data_freshness_audit.py):
0 broken-deflator, 0 barchart-residue, 0 missing; 17 stale = the known truncations (data
genuinely ends early, task #28), auto-excluded now by a DYNAMIC STALENESS GUARD in
dynopt_backtest.py (STALE_DAYS=45, replaces the old hardcoded EXCLUDE/BROKEN; the 4 ex-breakers
CORN/CRUDE_W/SOYBEAN/WHEAT are FRESH+included). 26 negative-price instruments (Brent/COCOA/CRUDE
back-adj zero-cross) — watch, don't break deflator. **FIRST TRUSTWORTHY RESULT** (full universe
106, $110k, 25% vol, data→2026-07-07): Sharpe 0.74, ann 9.0%, vol 12.2%, maxDD -25.2%, 85/106
ever-funded, ALL asset classes. DISCARD all earlier session numbers (-51/-46/-45% DD, Sharpe~1)
— deflator-freeze artifacts. KEY REAL FINDING (opposite of the false narrative): at $110k the
book diversifies broadly but UNDER-INVESTS — realized 12.2% vs 25% target — the genuine
small-capital integer-lumpiness cost (capital-dependent: $1M realizes ~20%). Sharpe 0.74 is a
modest baseline (<Rob's ~1.0) → legit tuning question (equal-1/N vs handcrafted weights,
universe, 2021-25 trend drought), NOT a bug. NEXT (all now trustworthy): clean vol-target sweep,
$110k-vs-$1M, static selection on clean data + Rob diff, drawdown attribution, Sharpe investigation.
Baseline milestone: reproduce a known Rob result (see [[validation-before-strategy-changes]]).

--- superseded debug notes below ---
**✅ ROOT CAUSE FOUND → CSI-ONLY CUTOVER (2026-07-07 night).** ALL dynamic-opt backtest
numbers this session (−51/−46/−45% DD, Sharpe ~1, "small-capital concentration", "need
micros", vol-target sweep) were CORRUPTED by ONE bug and must be discarded. **Root cause:
STALE two-source data** — Barchart (hourly) series under CSI codes, ffill'd flat >180d →
`calculate_cost_deflator` (syscore/pandas/strategy_functions.py) `final_vol=0` → inf cost →
`inf*0=NaN` in optimiser `calculate_costs` → optimiser FREEZES to prior positions ~99% of
days → fake concentrated book. PROOF: excluding the 4 flat-tail breakers (CORN/CRUDE_W/
SOYBEAN/WHEAT) → optimiser errors 7772→3, funded 5→22 of 23, diversified across ALL asset
classes incl. full-size bonds (BOBL/BTP/FED/KR3) at $110k. So the affordability/micro
narrative was FALSE (task #27 deprioritized). **DECISION: CSI-only single-source sim DB**
(purge/silo Barchart). Gate `data_freshness_audit.py` on current DB = FAIL: 75 Barchart-only
residue, 88 stale(>10d), 4 broken-deflator, 27 negative-price. **Checklist: notes/csi_cutover_
validation.md.** User is rebuilding CSI CSVs. NO instrument adds/drops (micro-Treasuries not
in CSI; universe stays 147/150). NEXT (post-rebuild): archive parquet → CSI-only re-ingest →
`data_freshness_audit.py` until PASS → remove the 4 from BROKEN set in dynopt_backtest.py →
first TRUSTWORTHY full-universe backtest + clean vol sweep + static selection + attribution.
Debug artifacts: idm_diagnostic.py (IDM=2.5 fine), cost_nan_check.py, optimiser_input_check.py
(found the inf), dynopt_backtest.py (SELECTION/CAPITAL env, currency metrics, BROKEN set).
Static selection WORKS (static_instrument_selection.py: 26@110k/34@250k/57@1M, tracks Rob's
report). Rob refs: Static_selection_of_instruments + Duplicate_markets_report (github robcarver17/reports).

--- earlier debug notes (superseded by root-cause above) ---
- Static instrument selection WORKS (`static_instrument_selection.py`): our 26 @ $110k, 34 @
  $250k, 57 @ $1M, counts track Rob's published `Static_selection_of_instruments` report
  (25 vs 28, 34 vs 35). Rob reports: Static_selection_of_instruments + Duplicate_markets_report.
- The DYNAMIC OPTIMISER degenerates: on the 26-set it funds only 5-7 instruments and NEVER
  holds equities/sectors/metals/energy, at BOTH $110k AND $1M (near-identical Sharpe 0.97/0.98,
  DD −46%/−45%) — i.e. CAPITAL-INVARIANT, so it's NOT affordability. DOW's upstream optimal is
  ~2.4 contracts (52% wt) yet held 0 at both capitals.
- RULED OUT: IDM (=2.5, correct), per-instrument spreadcosts (all 26 valid), system construction
  (byte-identical to canonical `sysproduction/strategy_code/run_rob_dynamic_system.py`).
- MECHANISM: `optimised_positions_stage.get_optimal_positions_with_fixed_contract_values` wraps
  `optimise_positions()` in try/except that RETURNS previous_positions on ANY exception. The
  greedy throws "Trade costs are zero" (actually `np.isnan(trade_costs)`, optimisation.py:258)
  ~99% of days at $110k (7772 hits) -> positions FREEZE/carry-forward -> degenerate book.
  "All zeros in optimisation" fallback is capital-driven (7772→3 at $1M) but the freeze persists.
- SUSPECTS: (a) my backtest forces equal 1/N weights + use_instrument_weight_estimates=False
  (Rob uses estimated correlation-aware weights) — prime suspect; (b) a NaN in costs/covariance
  input for the never-funded instruments. Diagnostic running: `optimiser_input_check.py` prints
  target_contracts/cost/per_contract_value/variance per instrument (DOW vs FED) to find the NaN.
NEXT: read optimiser_input_check result; then re-run canonically with ESTIMATED weights (no
equal-weight override) as the known-good baseline. Scripts: dynopt_backtest.py (SELECTION+CAPITAL
env, currency metrics), idm_diagnostic.py, cost_nan_check.py, optimiser_input_check.py.

**🎯 LIVE-150 UNIVERSE INGESTED (2026-07-07 midday).** Andrew batch-added the 53 codes to CSI;
all 53 arrived + validated 1:1 (CSI market name vs PST desc), mapped in KNOWN_OVERRIDES +
`csi_symbol_map.csv` (now 147). Imported via `csi_pipeline` (rename + full price/roll/multiple/
adjusted chain): **53/53 succeeded, 0 failed, all in parquet.** Roll validation: **39/53 clean**
(all monotonic+valid). **14 flagged → TASK #28:** TRUNCATED/mid-chain-gap (lose recent history):
BRE(2000) US3(2010) GAS-LAST(2006) US-REALESTATE(2007) EPRA-EUROPE(2010) EU-TECH(2008)
FTSECHINAH(2018) FTSEINDO(2017) OMX(1996) GBPEUR(1999) VNKI(2012); DIVERGES-from-Rob: NIKKEI(34%)
REDWHEAT(18%) SOFR(43%). 39 clean are backtest-ready.
**🔑 KEY BACKTEST FINDING (attribution):** at $500k the greedy-integer dynamic-opt only ever
FUNDS 9 instruments (LEANHOG SOYOIL SOYMEAL PLAT RICE PALLAD LIVECOW SP500_micro NASDAQ_micro) —
expensive full-size contracts round to ZERO. So the -51% DD = concentrated ags/livestock/metals/
micro-equity book, NOT diversified-system failure. At real ~$110k it's worse. **Fix = micro/mini
contracts (TASK #27 audit)** — why Rob's jumbo uses MYM/MNQ/MES/M2K/MGC. NEXT: rerun backtest at
~$110k on the expanded 150 to see if the optimiser now diversifies (affordable contracts across
all asset classes), and to empirically drive the micro audit. Open tasks: #26 SOYMEAL carry,
#27 micro audit, #28 roll review, #25 QA audit.

**🎯 AFTS JUMBO PORTFOLIO CROSS-CHECKED (2026-07-07).** Andrew supplied the jumbo scan
(6 imgs, `private/jumbo portfolio/`, AFTS Tables 172-183 = **102 instruments**). Full
reconciliation in `private/jumbo_reconciliation.csv`: **65 DONE / 29 ADD(live) / 3 COVERED /
2 DEAD / 3 FLAG → 97/102 fully covered.** NOTE: jumbo "Market code" col is Rob's exchange code
(ZN/GBL/SXAP), NOT the CSI SymbolUA — used only to confirm membership. Cross-check FIXED my
first-pass errors: CHEESE(CSC) & HEATOIL(HO2, NY Harbor ULSD deep-1978) were mis-filed DEEP →
are jumbo; GASOILINE switched IRB(ICE)→**RB2**(NYMEX RBOB, jumbo=RB, v156k deeper); RUR/EDOLLAR
were SKIP → jumbo-but-dead (EDOLLAR=CSI ED 1981-2023 = 42yr STIR, research-deep). Findings:
jumbo has **EU sectors(8) but NO US sectors** (my 9 US-sector picks = Rob-cfg extras, not jumbo);
jumbo uses minis/last-day (WTI-mini QM→covered by full CRUDE_W=CL2; EUR-full→covered by
EUR_micro=M6E; EU-Utils-600→proxy EU-DJ-UTIL=DEW). **FLAG/verify in UA:** USIRS10(N1U)+
USIRS5ERIS(LIW) = obscure swaps, no clean CSI (likely omit); SGD(SND)=no CSI USD/SGD (unavailable).
**JUMBO LIVE-ADD (29 CSI codes, batch-add now):** `TU T3 TN BTS KTB M2K EMD SCP DED DJS DJH DJI
DJE DJY DJV FT5 II2 JNM FVS RP BR5 ETH BZN HH RB2 HO2 ER CSC KW2`. Slot math: 94 done + 29 jumbo
= 123 → **27 slots** for best non-jumbo extras (top: SOFR/SR3, EURIBOR/FEI, FED/FF modern STIRs
replacing dead Eurodollar; MSCIWORLD/MWO; real-estate REI/SPR/JRE/EPR; then US/EU sector extras).
Superseded `private/csi_gap_confirmed.csv` (pre-jumbo CORE/BLOCK/DEEP/SKIP; still valid for the
non-jumbo extras pool). Deep-history symbol convention: US20=US, US10=TY, US5=FV, SILVER=SI2,
GOLD=GC2 (2-letter/#2, NOT Globex). Evidence: `private/csi_gap_candidates.txt`.

**🎯 FIRST DYNAMIC-OPT BACKTEST — SUCCESS (2026-07-06 night).** rob_system template
(trend+carry → forecast → position sizing → **dynamic optimisation**, dbFuturesSimData, USD,
$500k, Rob's fitted forecast weights/scalars) on **66 CSI deep-history instruments** (CSI∩data∩
Rob-config, minus 3 truncated: GAS_US_mini/YENEUR/FEEDCOW). Over **1996→2026 (30yr)**: **Sharpe 1.00,
ann return 19.9%, ann vol 19.9%, skew −0.69, avg DD −11.8%, max DD −51.1%; dynamic-opt holds 32 of 66
on the last date** (sparse/capital-efficient — working as designed). Script:
`sysinit/futures/dynopt_backtest.py`; curve: `private/dynopt_backtest_curve.csv`. NOTE: account-curve
`.percent` values are already in PERCENTAGE POINTS (don't re-apply `%` formatting). NEXT on backtest:
rerun at OUR capital (~USD 110k) for realistic held-count; add the 25 CSI instruments not in Rob's
config (need forecast weights); compare vs equal-weight / non-dynamic; per-instrument P&L attribution.

**CSI Batch 1+2 INGESTED: 94 instruments of deep history** (most 20–30yr). Map 100% resolved
(`csi_symbol_map.csv`, 94 verified via KNOWN_OVERRIDES in build_csi_symbol_map.py). Roll validation
(`validate_roll_calendars.py`: monotonic+valid+truncation + vs-Rob): **77/94 clean.**
FIXED: SOYMEAL/SOYOIL monotonicity (dedupe self-heal), **GAS_US** (NG2, 30yr, for thin GAS_US_mini),
**USDKRW** quarterly→monthly (config-vs-data mismatch), **SOYMEAL** -90→-45 offset (liquidity 47→79%).
Seasonal divergences ASSESSED via liquidity check: RICE/LEANHOG/LIVECOW/SOYOIL our roll is *more*
liquid than Rob → ACCEPT (Rob's blog: "no one true set of stitching dates"; his shipped calendars
are approximate). KOSPI_mini/GOLD_micro = rank-metric artifact (many contracts).

**TRUNCATIONS — root-caused (2026-07-06): mostly DATA issues, NOT config patches** (user's caution):
- **FTSE100**: FIXED via **FFI** (ICE, full 1996-2026, 30yr, vs-Rob 100%, clean). FTK ignored.
- **NASDAQ**: FIXED via **NQ** (liquid e-mini, symbol-linked to 1996; 30yr, vs-Rob 97%, clean). ND3 ignored.
- **US20-new (TWE)**: PERSISTENT — whole-DB rebuild STILL missing 2024-25 quarters though catalog says
  TWE active to 2026 → UA/CSI-specific export issue for TWE; flag to CSI (not fixable our end).
- **FEEDCOW/NOK**: unchanged after full rebuild → CONFIRMED fundamental thinness (vol 300/245), accept.
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
1. Remaining truncations: FTSE100(FFI)+NASDAQ(NQ) DONE. **US20-new(TWE)**: flag to CSI (persistent
   missing 2024-25 quarters even after full rebuild). FEEDCOW/NOK: accept as thin. YENEUR: §5.5.
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

### ✅ VOL/SHARPE GAP vs ROB — FULLY AUDITED & CLOSED (2026-07-11)
Question: why does our rob_system deploy ~15.2% vol / SR 0.92 vs Rob AFTS Table128 (~18.8-21.1% vol, SR 1.06-1.22)?
Method: corrected fractional decomposition (sysinit/futures/gap_decomposition.py) + scaling audit (scaling_diagnostic.py).
CORRECTION found first: futures_system() from rob_system INCLUDES optimisedPositions (it's the dynamic-opt system),
so the earlier "unrounded ceiling" (rounding_decomposition.py) was actually dynamic-opt@$500k — coincidentally 15.2%,
matching the TRUE fractional (Account stage, no optimiser), so that conclusion held by luck. Note added to that file.

FINDINGS (fractional, 20% target, 106 instruments):
- V0 full rob_system: 15.2%/SR0.92 FULL; 15.9%/1.05 on 1996-2021; V3 trend+carry+atten: 16.8%/0.94 FULL, 17.5%/1.05 96-21.
- Vol attenuation HELPS (remove it -> SR 0.92->0.75). Keep it. NOT the culprit.
- Relative-value/skew rules dampen vol ~1.5pt at ~neutral SR (they ADD diversification the capped IDM can't monetize).
- Scaling audit: avg |combined forecast| 9.3/10 (FULL strength, not weak); avg SUBSYSTEM vol 23.2% (>target, per-inst fine);
  IDM last 2.50 = AT dm_max cap 2.5 (mean 2.27); portfolio/subsystem vol ratio = 0.66.

VERDICT (both benign):
1. SHARPE gap = PERIOD. On 1996-2021 (Rob's era) we hit SR 1.05 ~= his 1.06. Full-period 0.92 dragged by 2022-26 drought
   (post-dates his book). No defect.
2. VOL gap = IDM CAP (2.5) on a highly-diversified book. NOT weak forecasts, NOT bad scaling — every instrument
   over-deploys alone (23.2%); the 106-instrument book is so diversified the "correct" IDM would be ~3.8 but is capped
   at 2.5 to protect against correlation breakdown in crises. The lower vol is a DELIBERATE, PRUDENT risk control = GOOD.
   The relative-value-rule dampening is the SAME mechanism (more diversification than the cap will lever).

LEVERS if higher realized vol wanted (small-account absolute return): raise the vol TARGET (not the cap) — realized vol
scales ~linearly with target while IDM cap + attenuation stay intact/protective; target ~26% -> ~20% realized. Removing/
raising the IDM cap is the WRONG lever (reintroduces the correlation-breakdown tail risk the cap exists to prevent).
RECOMMENDATION: leave it. Risk-adjusted return (Sharpe) is what compounds and it matches Rob. 15.2% = system being prudent.
Scripts: gap_decomposition.py, scaling_diagnostic.py (+ private/scaling_diagnostic.csv, private/gap_decomp.log).

### Gap audit — LEVER EXPERIMENTS refine the verdict (2026-07-12); IDM-cap hypothesis REFUTED
Ran fractional full-stats experiments (sysinit/futures/gap_experiments.py) on the two deployment levers.
Results (vol/ret/DD in true %; addDD = additive/pysystemtrade-native cumsum-of-%-returns DD;
compDD = compounded equity DD, %-of-account peak-to-trough, bounded -100% -- the "real" drawdown):
  BASE 20%/cap2.5 : vol 15.2 ret 14.0 SR 0.92 addDD -47.1 compDD -38.8 skew -0.31 IDM 2.50 | SR96-21 1.05
  EXP1 26%/cap2.5 : vol 18.9 ret 16.2 SR 0.86 addDD -74.9 compDD -54.6 skew -0.43 IDM 2.50 | SR96-21 1.02
  EXP2 20%/NO cap : vol 15.5 ret 14.1 SR 0.91 addDD -54.8 compDD -43.5 skew -0.28 IDM 2.84 | SR96-21 1.06
  EXP3 26%/NO cap : vol 19.2 ret 16.4 SR 0.86 addDD -76.5 compDD -55.5 skew -0.43 IDM 2.84 | SR96-21 1.02
compDD is ~8-20pt shallower than addDD (bounded, %-of-equity). BASE real max DD = -38.8% (survivable for a
15%-vol trend system over 30y; in line with Rob's AFTS strategies). Ordering/verdict identical under compDD:
BASE has best Sharpe AND shallowest DD. Daily return curves saved -> private/gap_curves/{BASE,EXP1,EXP2,EXP3}.csv
(so future DD/stat questions need NO rebuild). Earlier addDD numbers had a cosmetic x100 (fixed).

REFINEMENT: the earlier "IDM cap (2.5) suppresses deployment; correct IDM ~3.8" was WRONG — removing the
cap raises IDM only 2.50->2.84 and vol only 15.2->15.5% (Sharpe flat). The cap is barely binding. The real
constraint is the IDM ESTIMATOR being (correctly) conservative about a genuinely diversified 106-inst book
(uncapped it only wants 2.84 -> 15.5%). Methodology working as designed, not throttled.
Raising the vol target to reach Rob's headline vol is a BAD TRADE: 20->26% target gets vol ~19% but Sharpe
0.92->0.86, real (compounded) DD -38.8%->-54.6%, skew worse. Best risk-adjusted point = BASE (EXP2 ties).
FINAL: leave target 20% + cap 2.5. 15.2%/0.92 is the system being correct. Gap fully closed & benign.
Scripts: gap_experiments.py (+ private/gap_experiments.csv/.log).

### PRODUCTION TRACK #30 STARTED (2026-07-12); decisions: $250k/20% paper, IB intraday recorder in parallel
Beta production paper trading of CSI-driven rob_dynamic. Two user decisions this session:
 - Paper run capital/vol: $250k / 20% vol (middle ground: exercises a good chunk of the universe, our validated vol target).
 - IB intraday capture: stand up a minimal siloed recorder NOW in parallel (perishable tape argument).

PHASE A instrument-alignment audit DONE (sysinit/futures/phase_a_instrument_audit.py -> private/phase_a_audit.csv):
 106 CSI-universe instruments; 0 BLOCKED (ALL have IB contract mappings + specs -> whole universe IB-tradeable).
 74 READY; 32 REVIEW = ~30 flagged STALE(-1mo) (quarterly EU/US sector indices + Euro bonds; roll-calendar/rebuild
 timing, SAME cluster as task #28) + 2 false positives (EURIBOR/SOFR forward-dating is normal for STIR futures).
 Currency mix 67 USD/25 EUR/rest CHF/JPY/KRW/CNH/SGD -> from CAD base every trade has an FX leg.
 Phase A follow-up: rebuild-and-recheck the ~30 -1mo instruments (also closes #28); whitelist EURIBOR/SOFR.

PHASE B backtest at $250k/20% RUNNING (CAPITALS=250000 VOL_TARGET=20 dynopt_capital_sweep -> capsweep_vt20_250000/
 {stats.json, positions.parquet, attribution}). Validates production integer position sizing at our capital.
Next: Phase C paper fills (order gen -> stack handler, liquid window, TZ=UTC); Phase D daily automation + reconciliation.

PROD INFRA MAP (from Explore): strategy=rob_dynamic; run_systems -> optimal positions (Mongo);
 run_strategy_order_generator (orderGeneratorForDynamicPositions) -> instrument orders; run_stack_handler ->
 broker orders + fills; config gen = sysinit/futures/make_rob_dynamic_config.py -> private/systems/rob_dynamic/config.yaml.
 2026-07-01 paper fill used a 10-subset at $500k/25% on shallow IB-seeded data; now we have CSI deep history.
 ISOLATION: run_systems reads only parquet sim stores; IB fills -> Mongo positions, NOT price stores. The one
 contamination vector = seeding scripts (IB/barchart) writing into the sim parquet -> keep disabled. NOTE:
 pysystemtrade's native run_daily_prices_updates fetches IB intraday INTO the sim contract-price store -> do NOT
 run it under CSI-only; our recorder writes to a SEPARATE store instead.

IB INTRADAY RECORDER (task #31, sysinit/futures/ib_intraday_capture.py): siloed store private/data/parquet_ib_intraday/
 (asserts != sim path). Reuses IB client get_prices_at_frequency_for_contract_object at Frequency.Hour; merges per
 contract; 10s pacing sleep. DRY-RUN default (validated: 74 instruments mapped to current contracts, isolation OK);
 IB_LIVE=1 with Gateway up to fetch. intraday_frequency default in pysystemtrade = H (hourly). TODO: live Gateway test.

### IB GATEWAY WIRING VALIDATED (2026-07-13, off-hours) — recorder works, reconciliation gap found
Gateway up (paper DU1739659, port 4002). Ran read-only preliminary checks (sysinit/futures/ib_preliminary_checks.py):
 - CONNECTION OK (client id 104, market-data farms OK). Paper account value ~$1.27M base ccy.
 - 4 STALE OPEN POSITIONS from the 2026-07-01 fill still live: JPY -1 (20260914), AUD -1 (20260914),
   SP500_micro +1 (20260918), GOLD_micro -1 (20260827). Flatten or manage in the first Phase C cycle.
 - 8 POSITION BREAKS (broker vs DB) = EXPIRY-MAPPING GAP: broker reports exact expiries (YYYYMMDD) but DB holds
   month-codes (YYYYMM00) and the current contracts' expiry dates aren't populated in the CSI-rebuilt DB
   ("expiry not found in database"). => PHASE C PREREQUISITE: populate current-contract expiries (contract
   sampling / update_sampled_contracts) so broker<->DB reconciliation matches cleanly. Not a data-corruption
   issue; the CSI rebuild just didn't carry IB exact expiries for the current front contracts.

IB INTRADAY RECORDER LIVE-VALIDATED (task #31): CAPTURE_LIMIT=3 IB_LIVE=1 fetched hourly bars (AEX 307,
 ALUMINIUM 160, AUD 160) and wrote to the SILOED store private/data/parquet_ib_intraday/ (Hour@<inst>#<contract>.parquet);
 sim store untouched. Recorder wiring done; remaining = schedule as background daily append + EOD-close cross-check.
 Fixes: class parquetFuturesContractPriceData, futuresContract(inst,date), CAPTURE_LIMIT env.

### EXPIRY-MAPPING RECONCILIATION GAP FIXED (2026-07-13, off-hours)
Root cause understood: reconciliation calls get_actual_expiry(instrument, contract_date) against the mongo CONTRACT
db; the CSI-rebuilt db had the current contracts unsampled (no IB expiry) -> ContractNotFound -> phantom break.
Fix = contract sampling (sysinit/futures/fix_contract_expiries.py, non-interactive wrapper of
update_active_contracts_for_instrument; writes ONLY to the contract db, never prices/sim). Gateway up.
Validated on the 4 open-position instruments (SP500_micro GOLD_micro JPY AUD): sampling pulled real IB expiries
(e.g. SP500_micro/20260900 -> 2026-09-18 = broker's 20260918; expired June contracts auto-retired from sampling).
Re-ran reconciliation preview -> "none (broker == DB)". 8 breaks -> 0. Gap fixed.
REMAINING: run full-universe sampling (fix_contract_expiries.py with no args -> all multiple-prices instruments)
so the whole Phase C tradeable universe is reconcilable; deferred until the IB recorder finishes (avoid concurrent
IB pacing). This is also part of the normal daily run_daily_fx_and_contract_updates process.

### ROLL-CALENDAR CLEANUP — ROOT-CAUSED (2026-07-13); comprehensive audit
Ran sysinit/futures/roll_calendar_audit.py (read-only) over the 106 universe -> private/roll_calendar_audit.csv.
Findings:
 - "104 truncated" flag was SPURIOUS: audit read the SEED calendars in data/futures/roll_calendars_csv/ (stale 2021);
   the CSI pipeline writes real calendars to private/data/futures/roll_calendars_csv/. Multiple prices (the sim source)
   are current for the healthy set. Ignore the truncation flag.
 - SOYMEAL (#26): RESOLVED. priced 20260900 / carry 20260800 -> carry computable; NOT stale; the -90->-45 RollOffset
   change did NOT break carry. 0 CARRY=PRICE across the whole universe. Close #26.
 - 30 STALE instruments (= Phase A REVIEW set, = task #28 cluster): multiple prices stuck on an EXPIRED priced
   contract (e.g. EU-BANKS priced 20260600 whose data ended 2026-06-19 -> PRICE NaN for ~3 weeks; Sep 20260900 has
   current data but sits as forward). ROOT CAUSE (definitive): these 30 have their LAST contract = 20260900 (Sep) and
   NO Dec-2026+ contract. pysystemtrade priced = SECOND-TO-LAST contract, so with data ending at Sep the priced is
   stuck at Jun. Healthy instruments run far forward (BUND->Dec26, AUD->Sep27, JPY->Dec27). Staged CSI files for the
   30 end at Day_<sym>_20260900.csv -> the CSI EXPORT only went out to Sep. NOT fixable by rebuild (tested EU-BANKS:
   no Jun->Sep roll can generate without a Dec forward). FIX = CSI RE-EXPORT of the 30 with deeper forward coverage
   (>= Dec-2026 + Mar-2027), then re-ingest via csi_pipeline. List: private/stale_reexport_list.txt (PST->CSI syms).
 - Interim: the 30 stay in the Phase A REVIEW set, EXCLUDED from Phase C's 74-READY paper universe until re-exported.
Scripts: roll_calendar_audit.py, rebuild_stale_rolls.py (rebuild-only driver; confirmed rebuild alone can't fix the
 coverage gap). EU-BANKS was test-rebuilt (harmless; same stale state, will be fixed by re-export).

### CSI STALE ROLLS: ingest-gap vs export-gap SPLIT + daily sync workflow (2026-07-13)
The 30 stale instruments split into two causes (checked raw UA export UA/Data/PST/<CSISYM>_<YYYYMM>.csv vs staged/DB):
 - INGEST-GAP (2): BOBL(EBM), KR10(KT0) — raw HAD the Dec-2026 contract (202612); we'd only STAGED to Sep (202609).
   FIXED by re-ingest -> now priced 20260900 / fwd 20261200, data current to 07-10. (MUMMY, LIVECOW also auto-synced.)
 - EXPORT-GAP (28): raw UA itself stops at Sep-2026 (202609) though DATA is fresh to 2026-07-10 — just no Dec forward.
   pysystemtrade priced = SECOND-TO-LAST contract, so no Dec -> stuck on expired June. All EU/US SECTOR INDICES +
   peripheral bonds: BON BTS CON SCP DJA DEB DJS DED DEW DJH DJI DJE DJV JPX RSV SEK ESM EMD SPD SPE SPF SPH SPI SPM
   SPR SPS SPT SPU. USER TO CHECK in UA: why these sector-index symbols don't list the Dec-2026+ contract (forward-
   months/deferred setting, or CSI doesn't carry the deferred quarter for these yet). Then re-export -> csi_sync_reingest.

DAILY SYNC WORKFLOW (sysinit/futures/csi_sync_reingest.py) — the ongoing CSI->sim maintenance tool:
  --diff : per-instrument compare raw export vs parquet DB on 2 triggers: NEW-CONTRACT (raw front > DB) and
           NEW-ROWS (raw data date > DB adjusted last date). Ran it: 143 instruments behind (most just 07-07->07-10
           = whole DB 3 days stale; a few deeply-stale non-universe: BRE ends 2000, EPRA-EUROPE 2010, BOVESPA 2023).
  <codes>: stage changed raw -> re-ingest contract prices -> rebuild roll calendar/multiple/adjusted -> validate.
  --auto : diff then re-ingest the flagged set.
 Efficiency TODO (deferred by user): mtime pre-filter (only diff raw files changed since last sync) + incremental
 append for NEW-ROWS. Current tool mirrors production's nightly full rebuild; correct but ~1-2min diff + ~10s/inst.
 RAN NOW: sync refresh on the 78 HEALTHY instruments (106 universe minus 28 export-gap) to bring sim to 07-10.

PHASE B RESULT (capsweep_vt20_250000): $250k/20% -> Sharpe 0.84, ann 11.5%, REALIZED vol 13.6% (integer rounding at
 $250k vs 15.2% fractional), maxDD -32.0%, avg DD -10.0%, skew -0.24, funded 91/106, held-today 14. Production sizing
 validated at our capital. (Ran on all 106 incl the stale-tailed 28; ~3wk NaN tail negligible over 30y — rerun on
 the 78 healthy after the refresh for a clean Phase C baseline.)

### 4-HOUR CHECK (2026-07-13 03:23 PDT) — Dec forward contracts did NOT arrive; diagnosed
Healthy-universe sync refresh: DONE 78/78, sim DB now current to 2026-07-10 (verified BUND/SP500_micro/BOBL).
The 28 sector indices: the UA re-build DID run on them this time (fresh mtimes Jul 12 22:53 - Jul 13 00:33, vs old
Jul 6-7) BUT still produce NO contract beyond Sep-2026 (202609). So NOT a portfolio-membership problem.
DIAGNOSIS = CSI contract-activation timing, not a fixable export setting:
 - Control BOBL(EBM) Dec-2026 (202612) got its FIRST data row only 2026-07-09 (1 row) -> Dec-2026 quarterly
   contracts are only just now activating.
 - Thin sector indices activate deferred contracts LATE: DEB(EU-BANKS) Sep contract's first data was 2026-03-23
   (~5.5mo lead); extrapolating, DEB's Dec likely won't have data until ~Sep-2026.
 => CSI genuinely has no Dec-2026 data for these 28 yet, so pysystemtrade can't roll them (priced=second-to-last
    needs a Dec forward). They can't be fixed until CSI's Dec contract activates (likely weeks).
ACTION: none ingestible now. The 28 stay EXCLUDED from Phase C's healthy universe. Re-run
 `csi_sync_reingest.py --diff` after a future CSI download to auto-detect when Dec arrives (shows as NEW-CONTRACT).
USER TO OPTIONALLY CONFIRM on CSI side: does the factsheet for e.g. DEB list a Dec-2026 contract at all? If listed
 but empty = data lag (wait); if not listed = exchange hasn't activated the deferred sector-index quarter yet.
Healthy universe for Phase C = 78 (106 - 28). Consider rerunning Phase B on the clean 78 for a Phase-C baseline.

### LIQUIDITY SCREEN built + run (2026-07-13) — reliable on volume, blocked on risk-$ by data-scale bug
sysinit/futures/liquidity_screen.py uses pysystemtrade's OWN thresholds (constants.py): PASS = >=100 contracts/day
AND >=$1.5M/day RISK (risk_$m = daily_price_stdev x sqrt(256) x point_size_base x avg_daily_contracts /1e6).
Fixed a volume bug first: best_vol must scan CURRENTLY-LIQUID contracts (front +/-window), not cds[-5:] which for
deep forward curves are far-dated illiquid contracts (made SILVER look like 7 lots/day etc).
RESULT (contracts/day = RELIABLE): 104/106 clear >=100 lots; only BONO(47) & CH10(28) fail, both already-excluded
export-gap. So raw liquidity across the tradeable universe is fine (incl US-TECH once volume fixed).
RESULT (risk-$ = NOT TRUSTWORTHY): corrupted by CSI PRICE-SCALE BUGS. SILVER contract price=6016.50 vs real ~$36/oz
(~167x inflated -> risk $117,387M/day absurd); CNH looks deflated ($47/contract). GOLD_micro/PALLAD/PLAT/BUND/MES
are correct. => risk-$ FAILs (STEEL, CNH, +stale) are a mix of real + corrupted; can't certify until scales fixed.
-> Task #32: CSI data-scale audit + IB cross-check. Impact: %vol is scale-invariant (fractional backtest ~ok) but
integer optimizer notional/rounding + any live $-sizing are distorted for mis-scaled instruments. Screen output:
private/liquidity_screen.csv.
NOTE the CarryOffset question (thin-deferred carry) is downstream of this: once scales are trusted + the risk screen
runs clean, decide live-vs-research membership and which survivors need CarryOffset=-1.

### SCALE AUDIT first pass (2026-07-13, sysinit/futures/scale_audit.py) — 4 real scale bugs found
Computes front-contract price, implied notional (price x USD point size), annual %vol per instrument; flags
notional outside $3k-$600k or vol outside 2-90%. -> private/scale_audit.csv. 11 flagged = 4 REAL + 7 false-pos.
REAL scale bugs (all unit-convention mismatches; confirm vs IB then fix config/mapping):
  SILVER  notional $6.02M  (price 6016 vs real ~$36/oz)      ~33x
  JPY     notional $7.77M  (per-yen vs per-100-yen)          ~100x
  COTTON  notional $4.08M  (cents vs dollars)                ~100x
  CNH     notional $2,041  (deflated)                        ~50x low
FALSE POSITIVES (correct, heuristic bands too tight): FED/EURIBOR/SOFR/US2/BTP3/SHATZ (STIR/short-bond <2% vol is
  real); V2X (vol future legit small notional). US-TECH/SP400 sane (not scale-broken).
IMPACT: %vol scale-invariant -> fractional backtest ~ok; but integer optimizer notional/rounding + live order sizing
  mis-size these 4 (JPY/COTTON at 100x notional -> round to ~0 contracts -> effectively dropped). FIX before live.
NEXT: IB cross-check (Gateway up) to confirm real prices, then fix per-instrument (priceMagnifier in ib_config /
  Pointsize in instrumentconfig / csi_symbol_map). Part of task #32.

### SCALE BUGS FIXED via coordinating price-scale config (2026-07-13); 3/4 done, CNH pending IB
Root cause (verified): pysystemtrade stored price must satisfy stored = real_price x priceMagnifier (since
Pointsize = IBMultiplier/priceMagnifier). CSI quotes some instruments in cents/x100 while their stock Pointsize
expects the base unit -> notional 100x off. Confirmed: CORN(mag100,Pointsize50,cents) OK; COTTON/SILVER/JPY
(mag1, dollar-Pointsize) got cents from CSI -> 100x. BUND fine (CSI gives natural). Not a config we changed (git:
stock Pointsizes). So it's a CSI-convention mismatch -> needs a per-instrument CSI scale config (user's insight).
SOLUTION: private/data/futures/csi_price_scale.csv (instrument,scale,reason) -- COTTON/SILVER/JPY = 0.01. Applied
at INGEST via ConfigCsvFuturesPrices.apply_multiplier (scales OPEN/HIGH/LOW/FINAL only, NOT volume). Wired into
BOTH csi_pipeline.csi_config_for() (single source of truth) and csi_sync_reingest (imports it) so daily syncs +
full rebuilds stay correct. VERIFIED (no Gateway needed, notional self-check): COTTON front 78.67->0.7802
notional $3.9M->$39,010; SILVER/JPY re-ingested; scale_audit flagged 11->8 (COTTON/SILVER/JPY cleared; remaining
= CNH + 7 false-positives STIR/short-bond low-vol + V2X small-notional which are CORRECT).
CNH DEFERRED: notional $2,041 (~50x too LOW), FX convention ambiguous (SGX USD/CNH, possible inversion) -> do NOT
guess; calibrate vs IB. Gateway was DOWN this session (port 4002 refused) so couldn't calibrate CNH or IB-verify.
TOOL for when Gateway up: sysinit/futures/ib_csi_calibration.py -- fetches IB daily close+volume per contract,
compares to CSI (price_ratio -> the scale correction; volume_ratio = the requested IB-vs-CSI volume check). Run it
on CNH + a full-universe sweep to catch any unflagged small-notional 100x errors + confirm COTTON/SILVER/JPY.
Note: %vol is scale-invariant so the fractional backtest was always ~unaffected; this fixes integer-optimizer
notional/rounding + live order sizing. Task #32 tracks the remainder.

### ALL 4 SCALE BUGS FIXED + IB-CONFIRMED (2026-07-13, Gateway up)
Ran ib_csi_calibration.py (fetches IB daily close+vol per contract vs CSI). CONFIRMED the 3 prior fixes against
IB ground truth: COTTON CSI 0.8154 = IB 0.8154; SILVER 60.83 ~ IB 58.38; JPY 0.0063 ~ IB 0.0062 (all px_ratio ~1.0);
controls CORN/WHEAT/SUGAR/BUND/SP500_micro all match. So the coordinating-config approach is validated end-to-end.
CNH RESOLVED: CSI 0.1481 vs IB 6.7562 = pure INVERSION (CSI quotes USD-per-CNH; IB/pysystemtrade want CNH-per-USD).
 Inversion also fixes CNH's RETURN DIRECTION (was sign-flipped), not just notional. Fixed via apply_inverse.
 BUT found + fixed a REAL pysystemtrade BUG: sysdata/csv/csv_futures_contract_prices.py apply_inverse rebound
 column_series without writing back (line ~102) -> inversion was silently a no-op. Fixed (assign back to
 instrpricedata[col_name]; also makes apply_multiplier robust). CNH now: price 0.148->6.7527, notional 2041->$93,071.
Coordinating config now has scale+inverse columns: private/data/futures/csi_price_scale.csv
 COTTON/SILVER/JPY scale 0.01; CNH inverse. Applied at ingest via csi_pipeline.csi_config_for (used by both
 full rebuild + daily sync). scale_audit: 11->7 flagged, all 7 remaining are FALSE POSITIVES (STIR/short-bond
 <2% vol = correct: FED/EURIBOR/SOFR/US2/BTP3/SHATZ; V2X small notional = correct vol future). ZERO real scale bugs.
NOTE: CNH CSI data is THIN (only 3 contract files, IB vol 103k vs CSI 631) -> flag for liquidity/coverage review,
 but the scale/direction is now correct. Full-universe IB calibration sweep launched (private/ib_calibration_full.log)
 to catch any unflagged residuals + the IB-vs-CSI volume consistency check (contract choice caveat: uses forward
 contract which is far-dated/thin, so volume ratios there are not apples-to-apples for liquidity).

### FULL-UNIVERSE IB CALIBRATION SWEEP done (2026-07-13) — universe clean except MSCIWORLD
ib_csi_calibration.py swept all 106 vs IB (private/ib_calibration_full.log / ib_csi_calibration.csv).
COTTON/SILVER/JPY/CNH all now OK vs IB (CNH 6.7527 vs 6.7561 ratio 1.0005 = inversion fix confirmed). Only ONE
genuine scale discrepancy remains across the whole universe: MSCIWORLD CSI 16010 vs IB 4935 (ratio 0.308, ~3.24x).
NOT a clean 100x (so not the cents pattern) AND IB's compared contract (20261200) had 0 volume -> IB price may be a
stale/thin-contract quote. DO NOT auto-fix -> verify against a LIQUID MSCIWORLD contract (real MSCI World index
~3900; 16010/4~4000 hints CSI may be a x4 or different-denomination variant). Added to task #32.
Benign (5-11% price/date diffs, NOT scale bugs): BRENT-LAST 1.07, GASOILINE 1.06, HEATOIL 1.065, KOSPI_mini 0.90.
VOLUME check caveat: sweep used the forward contract (often far-dated/thin on IB) so CSI_vol vs IB_vol isn't
apples-to-apples for liquidity EXCEPT it flagged CNH as thin in CSI (631 vs IB 103k). A proper vol-consistency pass
should compare the FRONT liquid contract.
NET: 4/4 original scale bugs fixed + IB-confirmed; zero remaining ~100x errors; MSCIWORLD (3.24x) + CNH-thinness are
the only open data-quality items.

### MSCIWORLD verified vs LIQUID contract (2026-07-13) — index-VARIANT mismatch, NOT a scale bug
Compared CSI vs IB on the liquid Sep contract (CSI vol 13,696): ratio consistently 0.308 (same as Dec) -> not a
contract artifact. DIAGNOSIS: CSI MSCIWORLD ~15,835 = MSCI World NET TOTAL RETURN index; IB MXWO ~4,879 = MSCI World
PRICE index (what our config points to: MXWO/EUREX/mult10). 3.24x ratio ~= 56yr compounded dividends (both base 100
Dec-1969, ~2%/yr) -> confirms TR-vs-price, NOT a units error. A scale multiplier would be WRONG (ratio drifts with
dividends). Price RETURNS of TR vs price futures are ~identical -> backtest signal ~unaffected; but notional (158k vs
49k), carry, and the tradeable contract differ. DECISION NEEDED (instrument-config, not a patch): (a) remap CSI to
the PRICE-index MSCI World future to match IB MXWO, OR (b) repoint config/IB symbol to the Net-TR future if that's
what's liquid/tradeable for us. NB CSI vol 13,696 >> IB MXWO vol 188 -> TR variant may be the liquid one; check which
MSCI World future actually fills at IB. Left UNCHANGED pending that decision. Task #32.

### MSCIWORLD RESOLVED (2026-07-13) — repointed IB symbol to the liquid NETR future (M1WO)
Queried IB (reqMatchingSymbols/reqContractDetails). Two USD MSCI World quarterly futures on EUREX:
  M1WO (FMWO) = MSCI World NETR (Net Total Return) USD, px ~15,740, mult 10, quarterly vol ~4,644/day
  MXWO (FMWP) = MSCI World PRICE index USD, px ~4,879, mult 10, quarterly vol ~209/day  <- our OLD config (thin!)
CSI's MSCIWORLD data (~15,835) = the NETR future, and NETR is ~22x more liquid. So it was never a scale bug --
our ib_config just pointed at the wrong (thin price-index) symbol. FIX (one field): ib_config_futures.csv
MSCIWORLD IBSymbol MXWO -> M1WO (EUREX/USD/mult10/mag1/IgnoreWeekly TRUE keeps quarterly, skips daily TRF).
Pointsize 10 already correct for NETR level (notional ~$160k). VERIFIED: ib_csi_calibration MSCIWORLD now
CSI 16010 = IB 16010, ratio 1.0000 OK. Backtest was already on NETR (CSI data) so this aligns execution to it.
=> All scale-audit items now resolved. Only residual: CNH thin in CSI (coverage), scale correct.

### CNH REPLACEMENT PLAN (2026-07-13) — switch to HKEX USD/CNH (deep CSI + liquid IB, same exposure)
Root of CNH thinness: our CSI symbol CY = CME "Chinese Renminbi (Offshore)", StartDate 2026-02-23 (brand new, 3
contracts, vol ~360). AND venue mismatch: data=CME(CY) but ib_config executes SGX(UC). CSI has NO SGX USD/CNH.
BEST REPLACEMENT (same offshore USD/CNH exposure) = HKEX USD/CNH, which CSI carries deep + IB has liquid:
  CSI catalog: HUC (HKEX USD/CNH Combined, start 2014-12, LastVol 92,150) or HCU (RTH, start 2013-02, 88,388).
  IB: CNH-HK = CNH/HKFE mult 100000 -> ~1,563/day (passes liquidity screen ~$9M/day risk). (SGX UC is most liquid
  at ~25k/day but CSI has NO SGX CNH data, so can't use it.) HKEX quotes CNH-per-USD (6.77) = right convention,
  NO inversion needed (unlike CME CY which we patched with apply_inverse).
ACTION (user): add CSI symbol HUC (HKEX USD/CNH) to UA export. THEN (me): ingest HUC; repoint csi_symbol_map
  HUC->CNH (replacing CY->CNH); repoint ib_config CNH row to CNH,CNH,HKFE,CNH,100000,1,FALSE (from UC/SGX); REMOVE
  the CNH inverse row from private/data/futures/csi_price_scale.csv (HKEX not inverted); re-ingest + verify
  ib_csi_calibration CNH ~ratio 1.0 with deep history + real volume; re-run liquidity_screen (should PASS).
Alternative if HUC unavailable: keep CNH research-only (thin) or drop from live universe.

### UNIVERSE ALIGNMENT AUDIT status (2026-07-13) — 3/4 dimensions clean; variant/venue pass recommended
Q: are we confident in liquidity + contract size + right-instrument across UA(CSI) and IB for the whole universe?
CLEARED:
 - PRICE/SCALE: full 106 IB calibration sweep clean (only MSCIWORLD+CNH needed fixing, both done).
 - CONTRACT-SIZE config integrity: Pointsize x priceMagnifier == IBMultiplier for ALL 122; config ccy == IB ccy
   for all; every instrument has an IB mapping. (stock config, consistent by construction.)
 - LIQUIDITY (re-run post scale-fix, clean risk-$): 102/106 PASS Rob thresholds (>=100 contracts & >=$1.5M risk).
   FAILs: CNH ($1.39M, being replaced by HKEX), BONO/CH10 (already in excluded export-gap 28), STEEL (336 contracts
   $0.65M risk = genuine live-vs-research flag, healthy otherwise). SILVER etc now sane post scale-fix.
REMAINING GAP: VARIANT/VENUE correctness -- NOT systematically verified. MSCIWORLD (NETR vs price) & CNH (CME vs
 SGX) prove these hide when config is consistent + notional in-band + prices coincidentally align. Recommend a
 UA<->IB variant/venue audit: per instrument compare CSI catalog (commodityfactsheet.csv via csi_symbol_map: Name,
 Exchange, ContractSize, Units, Currency) vs IB reqContractDetails (longName, exchange, multiplier, currency);
 flag underlying/venue/size mismatches. Needs Gateway (~15min). This is the definitive closer before live.

### VARIANT/VENUE AUDIT done (2026-07-13) — found real issues; audit was worth it
sysinit/futures/variant_venue_audit.py: per-instrument CSI catalog (commodityfactsheet.csv via csi_symbol_map)
vs IB reqContractDetails. 122 instruments, 14 real flags (after CBT=CBOT false-positive fix). -> private/variant_venue_audit.csv
GENUINE ISSUES (decisions/fixes needed):
 - FTSEINDO: WRONG INDEX -- CSI=MSCI Indonesia(EUREX), IB=FTSE Indonesia(SGX). Different index+venue. HIGH PRIORITY.
 - DAX: POINTVAL csi 25 vs cfg 1 -- CSI=full DAX(EUR25/pt), config Pointsize=1(micro EUR1/pt). Same index so returns
   fine but notional/sizing 25x off unless we deliberately trade micro-DAX. CONFIRM (major instrument).
 - FTSECHINAH: CSI "FTSE China 50"(CME) vs IB "FTSE China H50"(SGX). venue + maybe different index. REVIEW.
 - EURIBOR: CSI ICE vs IB EUREX (same 3M rate, diff exchange). align venue.
 - BRENT-LAST: CSI CLEAR(ICE) vs IB NYMEX (two different Brent-last listings). REVIEW.
 - CNH: CME/SGX + size 500k/100k -> already being replaced by HKEX (task #33).
CAN'T VERIFY (CSI symbol not in commodityfactsheet.csv): FTSECHINAA, FTSETAIWAN, IRON, MSCISING (all SGX) -> check
 csi_symbol_map vs catalog SymbolUA (maybe different catalog vintage).
BENIGN: JPY/SILVER/COTTON point-value = the cents/x100 conventions already fixed via csi_price_scale (notionals
 correct); NIFTY (NSE<->SGX GIFT migration) + COTTON venue (ICE<->NYMEX IB naming) almost certainly same product.
CONCLUSION: answered the user's Q -- we were NOT fully confident; the audit surfaced ~5 genuine variant/venue
 issues (esp FTSEINDO wrong-index, DAX point-value) that scale/contract-size/liquidity/price checks all passed.

### FTSEINDO + DAX resolved (2026-07-13, from variant/venue audit)
DAX: NOT a bug -- confirmed FINE. pysystemtrade sets the IB contract multiplier from config (ib_instruments.py:92),
 so our IBMultiplier=1 resolves DAX to FDXS = MICRO-DAX (EUR1/pt, ~EUR25k notional). Verified: IB multiplier=1 ->
 tradingClass FDXS only; multiplier=25 -> FDAX (full). Micro-DAX is right for our capital; CSI DAX-index data serves
 it (same index all sizes). The audit POINTVAL(25 vs 1) flag is a FALSE POSITIVE for deliberately-smaller contracts.
 -> POINTVAL flag class is unreliable when we trade micro/mini vs the catalog's full-size point value.
FTSEINDO: DROPPED (unfixable + marginal). CSI data (MIN) = MSCI Indonesia (EUREX, thin, catalog LastVol 130) but
 ib_config (WIIDN/SGX) = FTSE Indonesia -> signal on one index, execution on another = wrong exposure. IB FTSE
 Indonesia (WIIDN) vol ~50/day = FAILS 100-contract floor; IB MSCI Indonesia (MID/HKFE) doesn't resolve to a
 tradeable contract. No liquid aligned option either way. REMOVED FTSEINDO row (MIN,FTSEINDO) from csi_symbol_map.csv
 -> excluded from universe (parquet data remains, unselected; reversible via git). Universe now 1 fewer.

### Remaining variant/venue items RESOLVED (2026-07-13) — audit complete
INDONESIA: no viable exposure exists. Only tradeable Indonesia future = SGX FTSE Indonesia (WIIDN) ~50/day (fails
 liquidity); IB MSCI Indonesia (MID/HKFE, EUREX) not tradeable. Single-country Indonesia equity futures inherently
 too thin -> FTSEINDO drop is FINAL; Indonesia only reachable indirectly via broad EM/Asia index if wanted.
EURIBOR: FIXED. Our config pointed to EUREX EURIBOR (EU3) which trades ~5-200/day (effectively dead); the liquid
 EURIBOR is ICE (I/ICEEU, ~5k-25k/day), which is ALSO CSI's data venue (FEI=ICE-EU-FIN). Same rate (px_ratio .999),
 same multiplier 2500. Repointed ib_config EURIBOR EU3/EUREX -> I/ICEEU. Verified: resolves to ICE, IB_vol 25,211,
 ratio 0.9991 OK. Now execution+data both ICE + liquid.
FTSECHINAH: NO ACTION. Same index (FTSE China 50 = H50); SGX execution (XIN0I) liquid ~2,054/day. CME(CSI data
 source) vs SGX(execution) is same index, prices align (sweep didn't flag). Low risk.
BRENT-LAST: NO ACTION. CSI BZN symbol=BZ (exch labeled CLEAR) = IB BZ/NYMEX = same NYMEX Brent-Last contract;
 8% price diff is a thin far-month date artifact, not instrument mismatch.
4 NO-CATALOG (FTSECHINAA/FTSETAIWAN/IRON/MSCISING, all SGX): commodityfactsheet.csv just lacks these SymbolUA rows
 (incomplete catalog); full price sweep already matched them to IB (ratio ~1.0) -> correct instruments, no action.
NET: variant/venue audit fully worked through. Real fixes: FTSEINDO dropped, EURIBOR->ICE. DAX confirmed fine.
 Everything else benign. Only CNH->HKEX remains (task #33, awaiting HUC export). Universe alignment now COMPLETE
 across scale, contract-size, liquidity, and variant/venue.

### CNH -> HKEX USD/CNH DONE (2026-07-13) — task #33 complete
HUC exported (53 contracts, 2014-2027, deep). Executed the switch:
 - csi_symbol_map: CY(CME) -> HUC (HKEX USD/CNH deep).
 - ib_config: CNH,UC,SGX -> CNH,CNH,HKFE (execute HKEX, the venue matching the data).
 - csi_price_scale: REMOVED the CNH inverse row (HUC quotes CNY/USD ~6.53, already correct convention).
 - Cleared old CME-CY data (3 staged + parquet contract/multiple/adjusted) then re-ingested HUC clean.
VERIFIED: ib_csi_calibration CNH ratio 1.0000 (CSI 6.7077 = IB 6.7077, both HKEX, no inversion); 53 contracts
 20141200..20271200; front px 6.5708 notional ~$90,565; adj fresh to 2026-07-13. CNH now coherent: deep HKEX data
 + liquid HKEX execution + right convention + correct notional. Old thin/mismatched CME-CY (3 contracts, inverted)
 fully replaced. This closes the last data-alignment item -> universe fully aligned across scale/size/liquidity/
 variant-venue with CNH now a proper live instrument.

### 28 SECTOR-INDEX GAP: diagnosed as UA export config, NOT contract timing (2026-07-13)
Re-checked: all 28 still export only to Sep-2026 (202609) even after fresh 07-13 downloads. IB check settles it:
the Dec-2026 (+Mar-2027, +more) contracts EXIST and are LISTED for all of them (EU-BANKS/SX7E, US-TECH/SIXT,
SP400/EMD, EU-OIL/SXEP, US-ENERGY/IXE -- Sep26/Dec26/Mar27 all listed; CME ones out to Sep-2027), AND HAVE DATA:
IB shows 60-63 daily settlement bars back to ~2026-04-15 for the Dec-2026 contract (recent vol ~0 = deferred/thin,
but pysystemtrade only needs price data to roll, not volume). => The gap is CSI/UA not EXPORTING the deferred
contracts for these 28 symbols (only pulling the front), NOT the exchange/timing.
WHAT WE NEED: in Unfair Advantage, increase the number of forward/deferred contracts (delivery months) downloaded
for these 28 symbols (>= Dec-2026 + Mar-2027). They have deep history but the forward extent is capped at the front.
THEN (me, automatic): csi_sync_reingest --diff flags NEW-CONTRACT -> re-ingest -> roll advances Jun->Sep (like
BOBL/KR10) -> 28 rejoin healthy universe. No code change, just the data.
STRATEGIC: several of the 28 are thin (US-TECH ~940/day; BONO/CH10 fail liquidity screen) -> decide live-worthy vs
research-only before investing in their forward data. Separate from the data fix.
