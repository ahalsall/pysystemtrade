# Roadmap: taking a pysystemtrade strategy LIVE with Interactive Brokers

Production top-level functions live in `sysproduction/*.py`; Linux wrappers in
`sysproduction/linux/scripts/` (referenced as `$SCRIPT_PATH`).

## 1. Interactive Brokers setup
- **IB Gateway** (not TWS) — lighter/stable. Launch before any Python. Use **IBC** (github.com/IbcAlpha/IBC) for headless auto-restart.
- Dependency: **`ib_async`** (since Apr 2026; was `ib-insync`). Validate with ib_async "recipes" first.
- Gateway: socket **port 4001**; **trusted IP** whitelist incl. `127.0.0.1`; **"Read only API" OFF** to trade.
- Config in `private/private_config.yaml`:
```yaml
broker_account: U123456     # MANDATORY, private only (no default)
ib_ipaddress: 127.0.0.1
ib_port: 4001
ib_idoffset: 100            # unique client-id offset per system
```
- Connection layers (`sysbrokers/IB/`): `connectionIB` (wraps `ib_async.IB`), client objects (`sysbrokers/IB/client/`), data-source objects (`ib_*_data.py`, reached via `sysproduction/data/broker/`). Active client IDs stored in Mongo. Broker mapping CSVs: `sysbrokers/IB/config/ib_config_futures.csv`, `ib_config_spot_FX.csv`; hours `ib_config_trading_hours.yaml` (assumes GMT).
- Sanity check: `connectionIB(999, ib_ipaddress="127.0.0.1", ib_port=4001, account="U123456")`.

## 2. Architecture
- **MongoDB**: order stacks, positions, optimal positions, capital, historic orders, process-control state, client IDs, roll state, limits, overrides, contract meta, spread costs (db `mongo_db`, default `production`). **Parquet**: time-series prices (`parquet_store`). Config: YAML/CSV.
- **dataBlob** (`sysdata.data_blob.dataBlob`): central object wrapping DB + broker; production code goes through it.
- **Process/stack-handler model**: long-running processes registered in Mongo (start/stop/running/PID), each running "methods" on a frequency/max-execution schedule. Cron launches; control config governs when/whether they run.
- **Order stacks** (`sysexecution`), 3 levels: **instrument** (strategy+instrument, adjusted prices) → **contract** (specific contract/spread) → **broker** (submitted to IB). Fills propagate upward; stack handler reconciles broker vs DB positions and locks instrument on a break.

## 3. Production processes (cron-launched)
| run process | purpose |
|---|---|
| `run_stack_handler` | execute orders across 3 stacks; force-roll orders; fills; position-break checks; runs all day |
| `run_capital_update` | poll IB account → total capital → strategy capital |
| `run_daily_price_updates` | update_fx_prices, update_sampled_contracts, update_historical_prices, update_multiple_adjusted_prices |
| `run_systems` | nightly backtest per strategy → optimal positions + pickled state |
| `run_strategy_order_generator` | optimal positions → instrument orders onto stack |
| `run_reports` | costs/liquidity/status/roll/pandl/reconcile/trade reports (emailed) |
| `run_cleaners`, `run_backups` | housekeeping, backups |

Ad-hoc update order: `update_fx_prices` → `update_sampled_contracts` → `update_historical_prices` → `update_multiple_adjusted_prices`; `update_total_capital`/`update_strategy_capital`; `update_system_backtests`; `update_strategy_orders`. `startup.py` clears stale IB client IDs + marks processes close on reboot.

Scheduling layers:
1. **crontab** `sysproduction/linux/crontab` — launches processes (Mon–Fri); start times not critical. Includes `@reboot mongod` and `@reboot startup`.
2. **process control** `syscontrol/control_config.yaml` (override `private/private_control_config.yaml`): `process_configuration_start_time/stop_time/previous_process` (dependency chains: run_systems needs daily prices; order generator needs run_systems), `process_configuration_methods` (per-method frequency/max_executions/run_on_completion_only), `arguments` (kwargs e.g. download_by_zone).

Scripts invoked via `p` wrapper → `python3 run.py <module.function>`.

## 4. Backtest → production
1. **Freeze fitted params**: `systems.diagoutput.systemDiag.yaml_config_with_estimated_parameters(...)` → dump scalars/weights/FDM/IDM/mapping to YAML; merge into production backtest YAML; turn OFF all five `use_*_estimates`.
2. **Register strategy** in two configs (keep old during transition):
   - `private_control_config.yaml`: `run_systems.<strategy>` (object=run class, backtest_config_filename) + `run_strategy_order_generator.<strategy>` (object=order generator).
   - `private_config.yaml`: `strategy_list.<strategy>` (load_backtests, reporting_code) + `strategy_capital_allocation.strategy_weights`.
3. **Default provided classes**: classic = `run_system_classic.py` / `classic_buffered_positions.py` / `report_system_classic.py`; dynamic = `run_dynamic_optimised_system.py` / `dynamic_optimised_positions.py` / `report_system_dynamic_optimised.py`. Custom = subclass run_system + order generator (`examples/production/example_of_custom_run_system.py`).
4. **Capital**: `update_total_capital` then `update_strategy_capital` (required before backtest runs). Risk target = `percentage_vol_target` in strategy YAML.
5. **Linkage**: run_systems → optimal positions + pickled state; run_strategy_order_generator → compares to DB positions → instrument orders; run_stack_handler → executes.

## 5. Dynamic optimisation in production
backtest emits **raw optimal position** (`-raw`) → order generator `orderGeneratorForDynamicPositions` runs the integer dynamic opt OUTSIDE the backtest → instrument orders.
- **`shadow_cost`** set in `private_config.yaml` (NOT backtest YAML — opt happens in order gen). Default 50; start high (~500) and reduce over first days. Wrong-sign positions closed immediately.
- **`ignore_instruments`** in strategy YAML only for duplicated multipliers (SP500 vs SP500_micro).
- **Position limits mandatory** — used by the optimisation. Autopopulate via `interactive_controls`.
- Don't-trade / reduce-only overrides for expensive/illiquid/restricted instruments.

## 6. Rolls & data maintenance
- Rolls interactive: `interactive_update_roll_status`. States: No_Roll, Passive, Force, Force outright, Close, No open, Roll adjusted. `run_stack_handler.generate_force_roll_orders` creates roll orders (state Force/Force-Outright/Close); `_ROLL_PSEUDO_STRATEGY`. Roll report daily. Auto-roll thresholds in config.
- `update_sampled_contracts` (active contracts/expiries); `update_historical_prices` (per-contract daily+intraday `intraday_frequency` default H; spike check `max_price_spike` default 8 → `interactive_manual_check_historical_prices`); `update_fx_prices` (→ `interactive_manual_check_fx_prices`); `update_multiple_adjusted_prices` (rebuild after per-contract).
- Staggered downloads via `arguments...download_by_zone`. Default exec algos need live streaming; switch algo per instrument if none. Timezone: set `GMT_offset_hours` + `private/private_config_trading_hours.yaml` if not GMT.

## 7. Risk controls & monitoring (`interactive_controls`)
- **Trade limits** (per period per instrument/strategy) — enforced in run_stack_handler.
- **Position limits** — enforced in run_strategy_order_generator; **required for dynamic opt**.
- **Overrides** — multiplier 0–1 / reduce-only / no-trade.
- **Capital safety**: update_total_capital refuses >10% account moves (→ `interactive_update_capital_manual`). `production_capital_method`: full/half/fixed.
- **Dashboard**: `cd dashboard; python3 app.py` → localhost:5000. Simple monitor: `cd syscontrol; python3 monitor.py`. Both email on crashed processes + mark close (no auto-respawn). Reports emailable (need email_* keys; Gmail App Password).

## 8. Ordered go-live checklist
1. Linux box; env vars in ~/.profile (MONGO_DATA, PYSYS_CODE, SCRIPT_PATH, ECHO_PATH, MONGO_BACKUP_PATH; add SCRIPT_PATH to PATH).
2. Create dirs (mongo data, parquet, echos, dumps, backups, backtests, reports).
3. Install pysystemtrade + deps (ib_async); install/start MongoDB.
4. Install/launch IB Gateway (4001, whitelist 127.0.0.1, Read-only OFF); IBC for auto-restart.
5. Create private_config.yaml + private_control_config.yaml (broker_account, ib_*, parquet_store, mongo_db, offsystem_backup_directory, base_currency, email). GMT offset if needed.
6. Verify IB connection (ib_async recipes, then connectionIB).
7. Init FX (repocsv_spotfx_prices.py → update_fx_prices); spread costs; instrument/roll config CSVs.
8. Backfill contract prices → roll calendars → multiple → adjusted (docs/data.md).
9. `update_sampled_contracts`; verify via interactive_diagnostics.
10. Produce frozen-param production backtest YAML.
11. Register strategy in private_config + private_control_config.
12. `update_total_capital` → `update_strategy_capital`.
13. Smoke-test `update_system_backtests` (optimal positions generated).
14. Set position limits (mandatory dynamic), trade limits, overrides; dynamic: shadow_cost (high), ignore_instruments.
15. If replacing strategy: `transfer_positions_between_strategies` (sysinit/futures/strategy_transfer.py).
16. Run full `run_reports` sanity check.
17. chmod +x scripts; install crontab (edit header dirs).
18. Logging: `PYSYS_LOGGING_CONFIG=syslogging.logging_prod.yaml` + log server (syslogging/server.py).
19. On (re)boot: start Mongo, launch Gateway, run startup (clears client IDs, marks close).
20. Start dashboard/monitor.

### Gotchas
- broker_account + offsystem_backup_directory have no defaults (private only).
- Production can't read inside backtest YAML — strategy values it needs (shadow_cost) go in private_config.
- Must include run_systems + run_strategy_order_generator strategy blocks in private_control_config.
- Unique ib_idoffset per system; don't release client IDs while IB connected.
- Default exec algos need live streaming data.
- After crash: fix position breaks via interactive_order_stack before resuming, or instruments stay locked.
- Backups contain secrets — encrypt off-site.
