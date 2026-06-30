"""
Production run class for our rob_system-equivalent dynamically-optimised strategy.

The stock production runner (run_dynamic_optimised_system.runSystemCarryTrendDynamic)
builds its system with plain RawData + ForecastScaleCap, which CANNOT run rob_system's
asset-class-relative rules (assettrend/relmomentum/mrinasset), skew (factors), relative
carry, or vol attenuation. This custom runner mirrors the documented custom-run-system
pattern (examples/production/example_of_custom_run_system.py) but wires rob_system's
stages — myFuturesRawData + volAttenForecastScaleCap — so production == our research
system, with dynamic optimisation on top.

Registered in private_control_config.yaml (run_systems block) and private_config.yaml
(strategy_list.load_backtests) by the dotted path to runRobDynamicSystem.
"""
from syscore.constants import arg_not_supplied

from sysdata.config.configdata import Config
from sysdata.data_blob import dataBlob

from sysproduction.data.sim_data import get_sim_data_object_for_production
from sysproduction.strategy_code.run_dynamic_optimised_system import (
    runSystemCarryTrendDynamic,
)

from syslogging.logger import get_logger

from systems.basesystem import System
from systems.forecasting import Rules
from systems.forecast_combine import ForecastCombine
from systems.positionsizing import PositionSizing
from systems.portfolio import Portfolios
from systems.risk import Risk
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
    optimisedPositions,
)
from systems.provided.dynamic_small_system_optimise.accounts_stage import (
    accountForOptimisedStage,
)
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import (
    volAttenForecastScaleCap,
)


class runRobDynamicSystem(runSystemCarryTrendDynamic):
    # DO NOT CHANGE THE NAME OF THIS FUNCTION; IT IS HARDCODED INTO CONFIGURATION FILES
    # BECAUSE IT IS ALSO USED TO LOAD BACKTESTS
    def system_method(
        self,
        notional_trading_capital: float = arg_not_supplied,
        base_currency: str = arg_not_supplied,
    ) -> System:
        return rob_dynamic_system(
            self.data,
            self.backtest_config_filename,
            log=self.data.log,
            notional_trading_capital=notional_trading_capital,
            base_currency=base_currency,
        )


def rob_dynamic_system(
    data: dataBlob,
    config_filename: str,
    log=get_logger("futures_system"),
    notional_trading_capital: float = arg_not_supplied,
    base_currency: str = arg_not_supplied,
) -> System:
    sim_data = get_sim_data_object_for_production(data)
    config = Config(config_filename)

    if notional_trading_capital is not arg_not_supplied:
        config.notional_trading_capital = notional_trading_capital
    if base_currency is not arg_not_supplied:
        config.base_currency = base_currency

    system = futures_system(data=sim_data, config=config)
    system._log = log
    return system


def futures_system(data, config) -> System:
    # same stage list as systems/provided/rob_system/run_system.py, plus the
    # dynamic-optimisation stages (Risk, accountForOptimisedStage, optimisedPositions)
    return System(
        [
            Risk(),
            accountForOptimisedStage(),
            optimisedPositions(),
            Portfolios(),
            PositionSizing(),
            myFuturesRawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )
