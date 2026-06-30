"""
Generate the production strategy config for our rob_system-equivalent dynamic system.

Takes systems/provided/rob_system/config.yaml (Rob's full 170-instrument fitted
config) and restricts instrument_weights + forecast_weights to the instruments we
actually have data for in the DB, so the production backtest can run today. Re-run
this as the barchart build-out accumulates more instruments to widen the set.

Output: private/systems/rob_dynamic/config.yaml (gitignored).

Notes:
- use_instrument_div_mult_estimates -> False (fixed IDM) for speed/robustness on
  limited data; revisit (re-estimate) once history is deep.
- base_currency left as USD for now (proven to work; we have USD-pair FX). CAD base
  is the production target per the Canada research but needs CAD FX rates loaded.
"""
import os
import yaml

from sysdata.sim.db_futures_sim_data import dbFuturesSimData

ROB_CFG = "systems/provided/rob_system/config.yaml"
OUT_DIR = "private/systems/rob_dynamic"
OUT = os.path.join(OUT_DIR, "config.yaml")


def main():
    cfg = yaml.safe_load(open(ROB_CFG))
    available = set(dbFuturesSimData().get_instrument_list())
    configured = set(cfg["instrument_weights"].keys())
    use = sorted(available & configured)
    if not use:
        raise SystemExit("No overlap between DB instruments and rob_system config")

    cfg["instrument_weights"] = {k: cfg["instrument_weights"][k] for k in use}
    cfg["forecast_weights"] = {k: cfg["forecast_weights"][k] for k in use}
    cfg["use_instrument_div_mult_estimates"] = False
    # base_currency stays as in rob_system (USD) for now; CAD is the production target.

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    print(f"wrote {OUT} with {len(use)} instruments")
    print("instruments:", use)


if __name__ == "__main__":
    main()
