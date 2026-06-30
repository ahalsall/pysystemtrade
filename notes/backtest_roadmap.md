# pysystemtrade Backtest Reference (build & run a backtest)

How to construct/run a backtest, point it at a custom price database, configure it,
write/use trading rules, run estimated systems, and replicate AFTS-style strategies +
dynamic optimisation. Paths are absolute.

## 1. Constructing a `System`

`System` lives in `systems/basesystem.py`.

```python
from systems.basesystem import System
system = System(list_of_stages, data, config)   # config optional
```

- Arg 1: list of **stage instances** — order does not matter (each registers under a fixed attr name).
- Arg 2: a `data` object (`simData` subclass).
- Arg 3 (optional): a `Config`.

Missing upstream stages only error when a downstream method needs them.

### Standard stages

| # | attr | class / file | key output methods | produces |
|---|------|--------------|--------------------|----------|
| 1 | `rawdata` | `RawData` — systems/rawdata.py | `get_daily_prices`, `daily_returns_volatility`, `daily_annualised_roll` | price/vol/carry inputs |
| 2 | `rules` | `Rules` — systems/forecasting.py | `get_raw_forecast(code, rule)` | raw forecasts |
| 3 | `forecastScaleCap` | `ForecastScaleCap` — systems/forecast_scale_cap.py | `get_capped_forecast` | scaled (avg abs 10) + capped (±20) |
| 4 | `combForecast` | `ForecastCombine` — systems/forecast_combine.py | `get_combined_forecast(code)` | weighted + FDM combined forecast |
| 5 | `positionSize` | `PositionSizing` — systems/positionsizing.py | `get_subsystem_position(code)`, `get_daily_cash_vol_target` | subsystem position |
| 6 | `portfolio` | `Portfolios` — systems/portfolio.py | `get_notional_position(code)`, `get_buffers_for_position` | final notional position |
| 7 | `accounts` | `Account` — systems/accounts/accounts_stage.py | `portfolio()`, `pandl_for_*` | P&L / account curves |

Happy path:
```python
system.rules.get_raw_forecast("SOFR", "ewmac64_256")
system.forecastScaleCap.get_capped_forecast("SOFR", "carry")
system.combForecast.get_combined_forecast("SOFR")
system.positionSize.get_subsystem_position("SOFR")
system.portfolio.get_notional_position("SOFR")
system.accounts.portfolio()        # accountCurveGroup
```
`system.get_instrument_list()` = instruments traded (from `instrument_weights`, else `instruments`, else all-with-data minus dupes/ignored).

## 2. Pointing a System at data

### CSV: `csvFuturesSimData` (sysdata/sim/csv_futures_sim_data.py)
```python
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
data = csvFuturesSimData()
data = csvFuturesSimData(csv_data_paths=dict(
    csvFuturesAdjustedPricesData="private.barchart.adjusted"))  # DOTTED package paths, not OS paths
```
Keys: `csvFuturesInstrumentData`, `csvFuturesMultiplePricesData`, `csvFuturesAdjustedPricesData`, `csvFxPricesData`, `csvRollParametersData`.
File formats: adjusted `CODE.csv` (DATETIME,PRICE); multiple `CODE.csv` (DATETIME,PRICE,CARRY,FORWARD,*_CONTRACT); FX `ccy1ccy2fx.csv` (DATETIME,FXRATE). NEVER mix adjusted + multiple in one dir (same filenames).

### Database: `dbFuturesSimData` (sysdata/sim/db_futures_sim_data.py)
Mongo (static) + Parquet (time series). Populate via `sysinit/futures/repocsv_*` scripts. Class→storage mapping in the `use_sim_classes` dict in that file. **This is what we already use for our Barchart data — verified working.**

### Passing in
```python
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system(data=my_data, config=my_config)
```
`futures_system(data=None, config=None, trading_rules=None)` defaults to csv + chapter15 YAML.

## 3. Config

`Config` (sysdata/config/configdata.py); defaults `sysdata/config/defaults.yaml`.
```python
from sysdata.config.configdata import Config
Config(dict(...))
Config("systems.provided.futures_chapter15.futuresconfig.yaml")
Config(["file.yaml", override_dict])   # later overrides earlier
```
Lookup priority: **config object → private/private_config.yaml → defaults.yaml** (defaults merged once placed in a System). `trading_rules` are NOT defaulted (no rules → exception). Editing nested dicts: change one key, don't reassign the dict (wipes defaults).

Key params:
- Trading rules: `trading_rules: {name: {function, data:[...], other_args:{...}, forecast_scalar}}`
- Scaling: `use_forecast_scale_estimates`, `forecast_scalars`, `forecast_cap: 20.0`
- Combine: `use_forecast_weight_estimates`, `use_forecast_div_mult_estimates`, `forecast_weights`, `forecast_div_multiplier`, `rule_variations`
- Portfolio: `use_instrument_weight_estimates`, `use_instrument_div_mult_estimates`, `instrument_weights`, `instrument_div_multiplier`, `instruments`
- Buffering: `buffer_method: position|forecast|none`, `buffer_size: 0.10`, `buffer_trade_to_edge`
- Capital/vol: `percentage_vol_target`, `notional_trading_capital`, `base_currency`
- Costs: `use_SR_costs`, instrument cost fields from `instrument_config.csv`
- Vol calc: `volatility_calculation: {func, days, min_periods, vol_floor, ...}`
- Date range: `start_date`
- Save estimated→fixed: `systems.diagoutput.systemDiag(system).yaml_config_with_estimated_parameters(...)`

## 4. Trading rules

A rule = function + positional data inputs + other_args kwargs; returns Tx1 Series.
- `TradingRule` (systems/trading_rules.py): `rule` may be callable / dotted-string / 3-tuple / dict / TradingRule.
- `Rules` (systems/forecasting.py): empty `Rules()` pulls `config.trading_rules`.
- Data strings reference `rawdata.*`/`data.*` methods (never downstream → recursion). other_args: no underscore → rule kwarg; `_x` → first data method; `__x` → second.

Provided rules — `systems/provided/rules/`:
| file | function | signature |
|------|----------|-----------|
| ewmac.py | `ewmac` | `(price, vol, Lfast, Lslow)` |
| carry.py | `carry` | `(raw_carry, smooth_days=90)` |
| carry.py | `relative_carry` | `(smoothed_carry, median_carry_for_asset_class)` |
| accel.py | `accel` | `(price, vol, Lfast=4)` |
| breakout.py | `breakout` | `(price, lookback=10, smooth=None)` |
| rel_mom.py | `relative_momentum` | `(norm_price, norm_price_asset_class, horizon=250, ewma_span)` |
| cs_mr.py | `cross_sectional_mean_reversion` | `(norm_price, norm_price_asset_class, horizon=250, ewma_span)` |
| mr_wings.py | `mr_wings` | `(price, vol, Lfast=4)` |
| factors.py | `factor_trading_rule`, `conditioned_factor_trading_rule` | `(demean_factor_value, smooth=90)` |

NOTE: docs reference `systems.futures.rules.ewmac` which DOES NOT EXIST — canonical is `systems.provided.rules.ewmac`.

## 5. Estimated vs fixed

Flags: `use_forecast_scale_estimates`, `use_forecast_weight_estimates`, `use_forecast_div_mult_estimates`, `use_instrument_weight_estimates`, `use_instrument_div_mult_estimates`.
Pre-baked estimated system: `systems/provided/futures_chapter15/estimatedsystem.py` + `futuresestimateconfig.yaml`.
Estimated runs need: a list of `instruments` (not `instrument_weights`), `rule_variations`, and an `Account()` stage. Optimisation config under `forecast_weight_estimate`/`instrument_weight_estimate` (method: handcraft recommended; frequency W; date_method expanding). Save to fixed YAML then turn flags off.

## 6. AFTS replication & dynamic optimisation

- **`futures_chapter15`** = *Systematic Trading* ch.15 (EWMAC + carry; vol target 20, cap 250k).
- **`rob_system`** (`systems/provided/rob_system/`) = the **AFTS template**. Full rule family + dynamic opt + vol attenuation + grouped handcrafted weights.
  - Constructor: `systems/provided/rob_system/run_system.py` → `futures_system(sim_data=arg_not_supplied, config_filename="systems.provided.rob_system.config.yaml", rules=arg_not_supplied)` — **defaults to dbFuturesSimData()**.
  - Stages: `Risk()`, `accountForOptimisedStage()`, `optimisedPositions()`, `Portfolios()`, `PositionSizing()`, `myFuturesRawData()`, `ForecastCombine()`, `volAttenForecastScaleCap()`, `rules`.
  - `volAttenForecastScaleCap` (systems/provided/attenuate_vol/...) with config `use_attenuation:` listing rules.
  - `myFuturesRawData` (systems/provided/rob_system/rawdata.py) adds `smoothed_carry`, `median_carry_for_asset_class`, normalised prices.
  - vol: `sysquant.estimators.vol.mixed_vol_calc` (35d mixed, 20yr slow, proportion_of_slow_vol 0.35).
  - config: `use_instrument_div_mult_estimates: True`, others False; vol target 25; capital 500k.
  - To use our Barchart CSVs instead of DB: pass `sim_data=csvFuturesSimData(csv_data_paths=...)`.

### Dynamic optimisation ("Mr Greedy")
`systems/provided/dynamic_small_system_optimise/`
- `optimised_positions_stage.py` → `optimisedPositions` stage (`get_optimised_position_df`, `get_optimised_weights_df`, `get_constraints`, `get_speed_control`).
- `optimisation.py` → `objectiveFunctionForGreedy`, `constraintsForDynamicOpt` (reduce_only_keys, no_trade_keys, long_only_keys), `optimise_positions`, `tracking_error_against_optimal`.
- `greedy_algo.py` → `greedy_algo_across_integer_values` (integer-contract greedy minimising tracking error).
- `buffering.py` → `speedControlForDynamicOpt` (trade_shadow_cost, tracking_error_buffer).
- `accounts_stage.py` → `accountForOptimisedStage` (`optimised_portfolio`, `get_optimised_position`).

Config (`small_system` block in defaults.yaml):
```yaml
small_system:
  shadow_cost: 50
  cost_multiplier: 1.0
  tracking_error_buffer: 0.0125
  shrink_instrument_returns_correlation: 0.5
```
Production wrappers: `sysproduction/strategy_code/run_dynamic_optimised_system.py` (`dynamic_system`, `runSystemCarryTrendDynamic`), `sysexecution/strategies/dynamic_optimised_positions.py` (`orderGeneratorForDynamicPositions`). Static variant: `systems/provided/static_small_system_optimise/`.

## 7. Minimal first backtest
```python
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system()
system.accounts.portfolio().sharpe()
system.accounts.portfolio().curve().plot()
```
Caching: after a config change, recreate the system (`futures_system(config=system.config)`) or `system.cache.delete_all_items()`.

## Key file map
- Core: systems/basesystem.py
- Stages: systems/{rawdata,forecasting,forecast_scale_cap,forecast_combine,positionsizing,portfolio}.py, systems/accounts/accounts_stage.py
- Rules: systems/trading_rules.py, systems/provided/rules/
- Config: sysdata/config/{configdata.py,defaults.yaml}
- Data: sysdata/sim/{csv_futures_sim_data,db_futures_sim_data}.py
- Chapter15: systems/provided/futures_chapter15/
- AFTS/dynamic: systems/provided/rob_system/, systems/provided/dynamic_small_system_optimise/
- Examples: examples/introduction/{asimpletradingrule,simplesystem,prebakedsystems}.py
