"""
Generate/refresh the production strategy config for our rob_system-equivalent dynamic system.

CONTRACT (important): this script owns ONLY the instrument-derived blocks --
    instrument_weights, forecast_weights, forecast_div_multiplier
-- which it rebuilds from Rob's fitted rob_system config, restricted to the instruments we
actually trade. EVERYTHING ELSE (percentage_vol_target, notional_trading_capital, base_currency,
use_instrument_div_mult_estimates, forecast_scalars, trading_rules, risk_overlay, ...) is STATIC
and HAND-TUNED in the yaml -- so when this runs to widen/narrow the universe it PRESERVES those
values by using the existing output yaml as its base. It never writes a config *value*; the yaml
is the single source of truth for tuning.

First run (no output yaml yet) bootstraps the base from rob_system -- so the static params start
at Rob's defaults (25% vol, $500k, fixed IDM) and MUST be reviewed/hand-set once before production.

Output: private/systems/rob_dynamic/config.yaml (gitignored).

Usage:
  uv run python -m sysinit.futures.make_rob_dynamic_config              # universe = all DB instruments
  uv run python -m sysinit.futures.make_rob_dynamic_config AEX AUD ...  # explicit universe
"""
import os
import sys
import yaml

from sysdata.sim.db_futures_sim_data import dbFuturesSimData

ROB_CFG = "systems/provided/rob_system/config.yaml"
OUT_DIR = "private/systems/rob_dynamic"
OUT = os.path.join(OUT_DIR, "config.yaml")
ADDITIONS = os.path.join(OUT_DIR, "instrument_additions.yaml")  # instruments beyond Rob's set (inherit a donor's fit)
EXCLUSIONS = os.path.join(OUT_DIR, "instrument_exclusions.yaml")  # instruments removed on data-quality grounds (each with a reason + reopen condition)

# the ONLY blocks this script regenerates; every other key is preserved from the existing yaml
INSTRUMENT_DERIVED_KEYS = ["instrument_weights", "forecast_weights", "forecast_div_multiplier"]
# static params we surface each run so an unintended overwrite can't slip by unnoticed
STATIC_PARAMS_TO_REPORT = [
    "percentage_vol_target", "notional_trading_capital", "base_currency",
    "use_instrument_div_mult_estimates", "instrument_div_multiplier",
]


def main():
    rob = yaml.safe_load(open(ROB_CFG))
    configured = set(rob["instrument_weights"].keys())

    if len(sys.argv) > 1:
        requested = set(",".join(sys.argv[1:]).replace(",", " ").split())
        use = sorted(requested & configured)
        missing = sorted(requested - configured)
        if missing:
            print(f"NOTE: not in rob_system config (skipped): {missing}")
    else:
        available = set(dbFuturesSimData().get_instrument_list())
        use = sorted(available & configured)
    if not use:
        raise SystemExit("No overlap between DB instruments and rob_system config")

    # BASE: preserve hand-tuned static params by starting from the existing custom yaml.
    # Only on first-ever run (no file) do we bootstrap from rob_system -- and we shout about it.
    if os.path.exists(OUT):
        cfg = yaml.safe_load(open(OUT))
        print(f"base = existing {OUT} (static params PRESERVED)")
    else:
        cfg = dict(rob)
        print(f"base = rob_system BOOTSTRAP (no existing yaml) -- REVIEW static params before production!")

    # regenerate ONLY the instrument-derived blocks, restricted to our universe, from rob's fit
    for key in INSTRUMENT_DERIVED_KEYS:
        if key in rob:
            cfg[key] = {k: rob[key][k] for k in use if k in rob[key]}

    # merge in our additions (markets beyond Rob's set; each inherits a donor's fitted params so it
    # survives regeneration). See private/systems/rob_dynamic/instrument_additions.yaml.
    added = []
    if os.path.exists(ADDITIONS):
        for new_inst, spec in (yaml.safe_load(open(ADDITIONS)) or {}).items():
            donor = (spec or {}).get("inherit_from")
            if donor not in rob["instrument_weights"]:
                print(f"NOTE: addition {new_inst}: donor '{donor}' not in rob config -- skipped")
                continue
            for key in INSTRUMENT_DERIVED_KEYS:
                if donor in rob.get(key, {}):
                    cfg[key][new_inst] = rob[key][donor]
            added.append(new_inst)
    if added:
        print(f"additions merged ({len(added)}, inherit donor fit): {sorted(added)}")

    # remove EXCLUSIONS (data-quality removals) from every instrument-derived block, so they stay out
    # across regenerations. Each entry documents a reason + reopen condition. See instrument_exclusions.yaml.
    excluded = []
    if os.path.exists(EXCLUSIONS):
        for inst, spec in (yaml.safe_load(open(EXCLUSIONS)) or {}).items():
            hit = False
            for key in INSTRUMENT_DERIVED_KEYS:
                if inst in cfg.get(key, {}):
                    del cfg[key][inst]; hit = True
            if hit:
                excluded.append(inst)
    if excluded:
        print(f"exclusions applied ({len(excluded)}, data-quality): {sorted(excluded)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    print(f"wrote {OUT} with {len(cfg['instrument_weights'])} instruments ({len(use)} from rob + {len(added)} additions)")
    print("static params (hand-tuned, preserved):")
    for k in STATIC_PARAMS_TO_REPORT:
        print(f"  {k:34} {cfg.get(k, '<absent -> framework default>')}")
    print("instruments:", use)


if __name__ == "__main__":
    main()
