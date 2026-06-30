"""
Wiring health-check: run Rob's system (rob_system) against our Barchart DB.

This is a PLUMBING test, not a meaningful backtest. It restricts rob_system to
the instruments we currently have processed in the DB, uses a fixed IDM (no
estimation) for speed/robustness on thin data, and walks each stage with
per-step error handling so we can see which integration points are sound as the
barchart build-out accumulates data.

Run:
    uv run python -m sysinit.futures.robsystem_smoketest

As the build-out grows, re-run to graduate from plumbing check to a real
backtest (re-enable IDM estimation and widen the instrument set).
"""
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from systems.provided.rob_system.run_system import futures_system


def _step(name, fn):
    try:
        out = fn()
        length = f"(len={len(out)})" if hasattr(out, "__len__") else ""
        print(f"  PASS  {name} {length}")
        return out
    except Exception as error:
        print(f"  FAIL  {name}: {type(error).__name__}: {str(error)[:200]}")
        return None


def main():
    data = dbFuturesSimData()
    available = set(data.get_instrument_list())

    # rob_system.futures_system builds its own Config from config_filename; build
    # the system, then prune system.config before any stage computation runs.
    system = futures_system(sim_data=data)
    configured = set(system.config.instrument_weights.keys())
    test_instruments = sorted(available & configured)
    print(f"available in DB: {len(available)} | configured in rob_system: {len(configured)}")
    print(f"=> smoke-test instruments ({len(test_instruments)}): {test_instruments}")
    if not test_instruments:
        raise SystemExit("No overlap between our data and rob_system instruments")

    # restrict to our instruments; fixed IDM avoids heavy estimation on thin data
    system.config.instrument_weights = {
        k: system.config.instrument_weights[k] for k in test_instruments
    }
    system.config.forecast_weights = {
        k: system.config.forecast_weights[k] for k in test_instruments
    }
    system.config.use_instrument_div_mult_estimates = False

    inst = test_instruments[0]
    print(f"\nWalking stages (primary instrument = {inst}):")

    _step("system.get_instrument_list", lambda: system.get_instrument_list())
    _step(f"data.daily_prices({inst})", lambda: system.data.daily_prices(inst))
    _step("rawdata.daily_returns_volatility", lambda: system.rawdata.daily_returns_volatility(inst))
    _step("rawdata.normalised_price_for_asset_class", lambda: system.rawdata.normalised_price_for_asset_class(inst))
    _step("rawdata.raw_carry", lambda: system.rawdata.raw_carry(inst))
    _step("rule momentum16 (raw forecast)", lambda: system.rules.get_raw_forecast(inst, "momentum16"))
    _step("rule assettrend16 (asset-rel)", lambda: system.rules.get_raw_forecast(inst, "assettrend16"))
    _step("rule relmomentum40 (asset-rel)", lambda: system.rules.get_raw_forecast(inst, "relmomentum40"))
    _step("rule carry60", lambda: system.rules.get_raw_forecast(inst, "carry60"))
    _step("rule mrinasset1000", lambda: system.rules.get_raw_forecast(inst, "mrinasset1000"))
    _step("rule skewabs365 (factors)", lambda: system.rules.get_raw_forecast(inst, "skewabs365"))
    _step("rule accel32", lambda: system.rules.get_raw_forecast(inst, "accel32"))
    _step("forecastScaleCap.get_capped_forecast(momentum16)", lambda: system.forecastScaleCap.get_capped_forecast(inst, "momentum16"))
    _step("combForecast.get_combined_forecast", lambda: system.combForecast.get_combined_forecast(inst))
    _step("positionSize.get_subsystem_position", lambda: system.positionSize.get_subsystem_position(inst))
    _step("portfolio.get_notional_position", lambda: system.portfolio.get_notional_position(inst))
    _step("portfolio.get_instrument_diversification_multiplier", lambda: system.portfolio.get_instrument_diversification_multiplier())
    _step("optimisedPositions.get_optimised_position_df", lambda: system.optimisedPositions.get_optimised_position_df())
    _step("accounts.optimised_portfolio()", lambda: system.accounts.optimised_portfolio())

    print("\nSmoke-test complete.")


if __name__ == "__main__":
    main()
