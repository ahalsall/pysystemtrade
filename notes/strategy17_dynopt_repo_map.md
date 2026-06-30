# Repo map: trend+carry & dynamic optimization (Strategy 17 / Strategy 25)

What's already implemented in pysystemtrade for AFTS-style strategies and dynamic
optimisation, with exact paths. Goal: implement Strategy 17 with Strategy 25's
dynamic optimization against our Barchart DB.

## Two "Carver-book" provided systems
- `systems/provided/futures_chapter15/` — *Systematic Trading* ch.15: EWMAC + carry.
  - `basesystem.py` → `futures_system(data, config, trading_rules)`; `estimatedsystem.py` (estimated).
  - `futuresconfig.yaml`: 6 EWMAC (2_8..64_256) + carry; forecast cap 20; capital 250k USD; IDM 1.89.
- **`systems/provided/rob_system/`** — the **AFTS template** (closest to *Advanced Futures Trading Strategies*). USE THIS as the base for Strategy 17 + dynamic opt.
  - `run_system.py` → `futures_system(sim_data=arg_not_supplied, config_filename="systems.provided.rob_system.config.yaml", rules=arg_not_supplied)` — **defaults to dbFuturesSimData()**.
  - Stage list: `Risk()`, `accountForOptimisedStage()`, `optimisedPositions()`, `Portfolios()`, `PositionSizing()`, `myFuturesRawData()`, `ForecastCombine()`, `volAttenForecastScaleCap()`, `rules`.
  - `myFuturesRawData` (rob_system/rawdata.py): smoothed_carry, median_carry_for_asset_class, normalised prices.
  - `volAttenForecastScaleCap` (systems/provided/attenuate_vol/...): config `use_attenuation:` lists rules.
  - vol: `sysquant.estimators.vol.mixed_vol_calc` (35d mixed + 20yr slow, proportion_of_slow_vol 0.35).
  - config: `use_instrument_div_mult_estimates: True`, others False; vol target 25; capital 500k.
  - **Already includes dynamic optimisation** (optimisedPositions + accountForOptimisedStage stages).

## Provided trading rules — `systems/provided/rules/`
ewmac.py `ewmac(price,vol,Lfast,Lslow)`; carry.py `carry(raw_carry,smooth_days=90)` + `relative_carry(...)`;
accel.py `accel(price,vol,Lfast=4)`; breakout.py `breakout(price,lookback=10,smooth)`;
rel_mom.py `relative_momentum(...)`; cs_mr.py `cross_sectional_mean_reversion(...)`; mr_wings.py `mr_wings(price,vol,Lfast=4)`;
factors.py `factor_trading_rule`, `conditioned_factor_trading_rule`.
Framework: `systems/trading_rules.py` (`TradingRule`), `systems/forecasting.py` (`Rules`).
(The AFTS rule family = accel, breakout, rel_mom, cs_mr, mr_wings, relative_carry, factors + ewmac + carry.)

## Dynamic optimization — `systems/provided/dynamic_small_system_optimise/`
- `optimised_positions_stage.py` → `optimisedPositions(SystemStage)`: `get_optimised_position_df()`, `get_optimised_weights_df()`, `get_optimal_positions_with_fixed_contract_values()`, `get_constraints()`, `get_reduce_only_instruments()`, `get_long_only_instruments()`, `get_speed_control()`.
- `optimisation.py` → `objectiveFunctionForGreedy` (contracts_optimal, covariance, per_contract_value, costs, speed_control, previous_positions, constraints), `constraintsForDynamicOpt`, `optimise_positions()`, `tracking_error_against_optimal()`.
- `greedy_algo.py` → `greedy_algo_across_integer_values(obj)` — increments each asset by 1 contract until no improvement.
- `data_for_optimisation.py` → `dataForOptimisation` (weights_optimal_as_np, per_contract_value_as_np, covariance_matrix_as_np).
- `set_up_constraints.py` → `minMaxAndDirectionAndStart`, `calculate_min_max_and_direction_and_start`.
- `buffering.py` → `speedControlForDynamicOpt` (trade_shadow_cost=10, tracking_error_buffer=0.02) + `calculate_adjustment_factor`.
- `accounts_stage.py` → `accountForOptimisedStage` (`optimised_portfolio()`, `pandl_for_optimised_instrument`, `get_optimised_position(code)`).

Config (`small_system` in sysdata/config/defaults.yaml):
```yaml
small_system:
  shadow_cost: 50
  cost_multiplier: 1.0
  tracking_error_buffer: 0.0125
  shrink_instrument_returns_correlation: 0.5
```
Static variant: `systems/provided/static_small_system_optimise/optimise_small_system.py` (`find_best_ordered_set_of_instruments`).

## Production dynamic-opt
- `sysproduction/strategy_code/run_dynamic_optimised_system.py` → `runSystemCarryTrendDynamic(runSystemClassic)`, `dynamic_system(data, config_filename, log, notional_trading_capital, base_currency)`, `futures_system(data, config)`.
- `sysproduction/strategy_code/report_system_dynamic_optimised.py` → `report_system_dynamic(data, backtest)`.
- `sysexecution/strategies/dynamic_optimised_positions.py` → `orderGeneratorForDynamicPositions`.
- `sysproduction/data/optimal_positions.py` → `dataOptimalPositions`.

## Data access for backtests
- `sysdata/sim/db_futures_sim_data.py` → `dbFuturesSimData` (adjusted+multiple via parquet, FX via parquetFxPricesData, instrument via csvFuturesInstrumentData, roll via csvRollParametersData, spread costs via mongoSpreadCostData). **Our Barchart data is read through this — verified.**
- `sysdata/sim/csv_futures_sim_data.py` → `csvFuturesSimData`.

## Other stages
- positionsizing.py `PositionSizing.get_subsystem_position` (= vol_scalar * forecast / avg_abs_forecast).
- portfolio.py `Portfolios.get_notional_position` / `get_actual_position`.
- rawdata.py `RawData`: get_daily_prices, daily_returns_volatility, get_instrument_raw_carry_data, raw_carry.
- forecast_combine.py `ForecastCombine.get_combined_forecast` (weighted sum × FDM).

## Quick usage
```python
# trend+carry base
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system()
system.accounts.portfolio().sharpe()

# AFTS + dynamic opt (defaults to dbFuturesSimData)
from systems.provided.rob_system.run_system import futures_system as rob_futures_system
system = rob_futures_system()
system.optimisedPositions.get_optimised_position_df()
```

## Implementation plan for Strategy 17 + dynamic opt (pending S17 book definition)
1. Base on `rob_system` with `sim_data=dbFuturesSimData()` (our Barchart DB).
2. Configure S17's specific rules + forecast weights + instrument scope in a config YAML.
3. Dynamic opt already wired (optimisedPositions); tune `small_system:` (shadow_cost, tracking_error_buffer).
4. Validate account curve / Sharpe; later freeze params → production (run_dynamic_optimised_system + orderGeneratorForDynamicPositions + IB).

STILL NEEDED: Strategy 17's exact definition (rules/forecasts + weights, instrument scope, fixed vs estimated, vol target/capital).
