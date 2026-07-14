"""Phase C prep: build the rob_dynamic PRODUCTION system (private/systems/rob_dynamic/config.yaml,
Rob's fitted weights restricted to our 78 tradeable) at $250k/20%, extract TODAY's optimal integer
positions, and compare to current broker holdings to show the INTENDED ORDERS. Read-only / inspect
only -- places nothing. (The real order generator does target - current_strategy_position; here we
show target + current broker holdings + implied orders.)"""
import os
os.environ["MPLBACKEND"] = "Agg"
os.environ.setdefault("TZ", "UTC")
import pandas as pd
from sysdata.config.configdata import Config
from systems.basesystem import System
from systems.risk import Risk
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import optimisedPositions
from systems.provided.dynamic_small_system_optimise.accounts_stage import accountForOptimisedStage
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.forecast_combine import ForecastCombine
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import volAttenForecastScaleCap
from systems.forecasting import Rules
from sysdata.sim.db_futures_sim_data import dbFuturesSimData

CAPITAL = float(os.environ.get("CAPITAL", 250000))
VOL = float(os.environ.get("VOL_TARGET", 20))
config = Config("private.systems.rob_dynamic.config.yaml")
config.notional_trading_capital = CAPITAL
config.percentage_vol_target = VOL
config.base_currency = "USD"

print(f"Building rob_dynamic production system @ ${CAPITAL:,.0f} / {VOL:.0f}% vol "
      f"({len(config.instrument_weights)} instruments)...", flush=True)
system = System([Risk(), accountForOptimisedStage(), optimisedPositions(), Portfolios(),
                 PositionSizing(), myFuturesRawData(), ForecastCombine(),
                 volAttenForecastScaleCap(), Rules()], dbFuturesSimData(), config)

posdf = system.optimisedPositions.get_optimised_position_df()
today = posdf.iloc[-1]
asof = posdf.index[-1].date()
tgt = today.round().astype(int)
tgt = tgt[tgt != 0].sort_values()
print(f"\n=== TARGET BOOK (optimal integer positions as of {asof}) ===", flush=True)
print(tgt.to_string())
print(f"\n{len(tgt)} instruments held / {len(today)} in universe | gross {int(tgt.abs().sum())} contracts", flush=True)

# current broker holdings (aggregate to instrument level) -> implied orders
print("\n=== current broker holdings + IMPLIED ORDERS (target - current) ===", flush=True)
try:
    from sysdata.data_blob import dataBlob
    from sysproduction.data.broker import dataBroker
    db = dataBlob()
    pos = dataBroker(db).get_all_current_contract_positions()
    df = pos.as_pd_df() if hasattr(pos, "as_pd_df") else pos
    cur = df.groupby("instrument_code")["position"].sum() if len(df) else pd.Series(dtype=float)
    print("current broker positions:", dict(cur.astype(int)) if len(cur) else "(flat)")
    allinst = sorted(set(tgt.index) | set(cur.index))
    orders = {i: int(tgt.get(i, 0) - cur.get(i, 0)) for i in allinst}
    orders = {i: q for i, q in orders.items() if q != 0}
    print(f"\nIMPLIED ORDERS ({len(orders)}):")
    for i in sorted(orders, key=lambda x: -abs(orders[x])):
        print(f"  {i:<14} {'BUY ' if orders[i] > 0 else 'SELL'} {abs(orders[i])}")
    try: db.close()
    except Exception: pass
except Exception as e:
    print(f"  broker fetch skipped: {type(e).__name__}: {str(e)[:60]}")
    print("  (target book above IS the intended positions; orders = target minus current holdings)")

tgt.to_csv("private/target_book_250k.csv", header=["target_contracts"])
print("\nsaved target book -> private/target_book_250k.csv", flush=True)
