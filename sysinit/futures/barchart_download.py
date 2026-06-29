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

import yaml
from bcutils.bc_utils import create_bc_session, get_barchart_downloads


def main():
    parser = argparse.ArgumentParser(description="Barchart download runner")
    parser.add_argument("--config", required=True, help="path to yaml config")
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

    get_barchart_downloads(
        session,
        instr_list=cfg["barchart_download_list"],
        save_dir=cfg["barchart_path"],
        start_year=cfg.get("barchart_start_year", 1950),
        end_year=cfg.get("barchart_end_year", 2025),
        do_daily=cfg.get("barchart_do_daily", True),
        dry_run=cfg.get("barchart_dry_run", False),
    )


if __name__ == "__main__":
    main()
