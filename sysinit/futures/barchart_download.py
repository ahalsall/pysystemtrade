"""
Standalone Barchart download runner.

This is executed by the *bc-utils* virtualenv python (which has requests /
beautifulsoup4), NOT the pysystemtrade environment. It therefore imports only
bcutils + stdlib, and reads its settings from a plain yaml config file (the
barchart_* keys in the pysystemtrade private config).

Invoked by barchart_orchestrator.py as:
    <bc-utils venv python> barchart_download.py --config <private_config.yaml>
"""
import argparse
import logging
import os

import yaml
from bcutils import bc_utils
from bcutils.bc_utils import (
    HistoricalDataResult,
    create_bc_session,
    get_barchart_downloads,
)


def _patch_skip_hourly():
    """Make bc-utils skip hourly downloads (daily-only mode).

    bc-utils has no native daily-only switch: do_daily=True fetches BOTH daily
    and hourly, do_daily=False fetches hourly only. We wrap its per-contract
    download so any Hour_* path is treated as already-present (EXISTS), which
    bc-utils skips without a network call or pause. Daily (Day_*) downloads run
    normally. This avoids forking bc-utils.
    """
    original = bc_utils.save_prices_for_contract

    def wrapper(session, contract, save_path, *args, **kwargs):
        if os.path.basename(save_path).startswith("Hour"):
            return HistoricalDataResult.EXISTS
        return original(session, contract, save_path, *args, **kwargs)

    bc_utils.save_prices_for_contract = wrapper


def main():
    # bc-utils reports progress (logins, downloads, skips, errors) via logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Barchart download runner")
    parser.add_argument("--config", required=True, help="path to yaml config")
    parser.add_argument(
        "--check-login",
        action="store_true",
        help="just log in to confirm credentials, then exit (no downloads)",
    )
    args = parser.parse_args()

    with open(args.config, "r") as stream:
        cfg = yaml.safe_load(stream)

    required = ["barchart_username", "barchart_password", "barchart_path"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise SystemExit(f"Missing required config keys: {missing}")
    if "CHANGE_ME" in str(cfg["barchart_username"]):
        raise SystemExit(
            "Barchart credentials are still placeholders; set barchart_username "
            "/ barchart_password in the private config."
        )

    session = create_bc_session(
        config_obj=dict(
            barchart_username=cfg["barchart_username"],
            barchart_password=cfg["barchart_password"],
        )
    )

    if args.check_login:
        print("LOGIN OK — Barchart session created; credentials are valid.")
        return

    daily_only = cfg.get("barchart_daily_only", False)
    if daily_only:
        print("Daily-only mode: hourly downloads will be skipped.")
        _patch_skip_hourly()

    # daily-only needs do_daily=True so bc-utils iterates the daily resolution;
    # with do_daily=False it would only try hourly, which we skip -> nothing.
    do_daily = True if daily_only else cfg.get("barchart_do_daily", True)

    get_barchart_downloads(
        session,
        instr_list=cfg["barchart_download_list"],
        save_dir=cfg["barchart_path"],
        start_year=cfg.get("barchart_start_year", 1950),
        end_year=cfg.get("barchart_end_year", 2025),
        do_daily=do_daily,
        dry_run=cfg.get("barchart_dry_run", False),
    )


if __name__ == "__main__":
    main()
