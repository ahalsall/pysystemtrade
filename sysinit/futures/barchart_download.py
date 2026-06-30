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


def _patch_download(daily_only: bool, max_downloads: int):
    """Wrap bc-utils' per-contract download to add daily-only and a per-run cap.

    bc-utils has no native daily-only switch (do_daily=True fetches BOTH daily
    and hourly, False fetches hourly only) and no self-imposed download cap (it
    only stops when the server reports the 250/day limit). We wrap
    save_prices_for_contract so that:

    * daily_only -> any Hour_* path returns EXISTS (skipped, no network/pause);
    * once `max_downloads` actual downloads have happened this run, further
      contracts return EXCEED, which makes bc-utils stop cleanly. This leaves
      headroom under the server limit; skip-existing means the next run resumes.
    """
    original = bc_utils.save_prices_for_contract
    state = {"downloaded": 0}

    def wrapper(session, contract, save_path, *args, **kwargs):
        if daily_only and os.path.basename(save_path).startswith("Hour"):
            return HistoricalDataResult.EXISTS
        if max_downloads and state["downloaded"] >= max_downloads:
            logging.info(
                f"Self-imposed cap of {max_downloads} downloads reached - stopping"
            )
            return HistoricalDataResult.EXCEED
        result = original(session, contract, save_path, *args, **kwargs)
        if result == HistoricalDataResult.OK:
            state["downloaded"] += 1
        return result

    bc_utils.save_prices_for_contract = wrapper


def _resolve_instrument_list(cfg: dict) -> list:
    """Instrument codes from a list file (if configured) or the inline list."""
    list_file = cfg.get("barchart_download_list_file")
    if list_file:
        with open(os.path.expanduser(list_file), "r") as stream:
            return [
                line.strip()
                for line in stream
                if line.strip() and not line.lstrip().startswith("#")
            ]
    return cfg.get("barchart_download_list", [])


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
    max_downloads = cfg.get("barchart_max_downloads", 0)
    if daily_only:
        print("Daily-only mode: hourly downloads will be skipped.")
    if max_downloads:
        print(f"Per-run download cap: {max_downloads}")
    if daily_only or max_downloads:
        _patch_download(daily_only, max_downloads)

    # daily-only needs do_daily=True so bc-utils iterates the daily resolution;
    # with do_daily=False it would only try hourly, which we skip -> nothing.
    do_daily = True if daily_only else cfg.get("barchart_do_daily", True)

    instr_list = _resolve_instrument_list(cfg)
    print(f"Instruments to download: {len(instr_list)}")

    get_barchart_downloads(
        session,
        instr_list=instr_list,
        save_dir=cfg["barchart_path"],
        start_year=cfg.get("barchart_start_year", 1950),
        end_year=cfg.get("barchart_end_year", 2025),
        do_daily=do_daily,
        dry_run=cfg.get("barchart_dry_run", False),
    )


if __name__ == "__main__":
    main()
