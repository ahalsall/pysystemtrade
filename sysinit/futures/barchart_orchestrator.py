"""
End-to-end Barchart data orchestrator: download -> process -> verify.

Run in the pysystemtrade (uv) environment:

    uv run python -m sysinit.futures.barchart_orchestrator              # all stages
    uv run python -m sysinit.futures.barchart_orchestrator --skip-download
    uv run python -m sysinit.futures.barchart_orchestrator --process-all
    uv run python -m sysinit.futures.barchart_orchestrator --skip-verify

Stages
------
1. download : runs bc-utils in ITS OWN venv (subprocess) to pull Day_/Hour_ CSVs
              from barchart.com into `barchart_path`. Honours barchart_dry_run.
2. process  : runs the barchart_pipeline (csv -> parquet per-contract prices ->
              roll calendar -> multiple prices -> adjusted prices) in-process.
3. verify   : checks adjusted prices landed in the DB.

All settings come from the pysystemtrade private config (the barchart_* keys).
The bc-utils location / venv can be overridden with env vars BC_UTILS_DIR and
BC_UTILS_VENV_PYTHON; the config file with PST_PRIVATE_CONFIG.
"""
import argparse
import os
import subprocess

from sysdata.config.production_config import get_production_config

from sysinit.futures.barchart_pipeline import (
    ALL_STAGES,
    DEFAULT_DATAPATH,
    DEFAULT_ROLL_CALENDAR_PATH,
    instruments_in_datapath,
    run_pipeline,
)

BC_UTILS_DIR = os.environ.get("BC_UTILS_DIR", os.path.expanduser("~/bc-utils"))
BC_UTILS_PYTHON = os.environ.get(
    "BC_UTILS_VENV_PYTHON", os.path.join(BC_UTILS_DIR, ".venv", "bin", "python")
)
PRIVATE_CONFIG = os.environ.get(
    "PST_PRIVATE_CONFIG",
    os.path.expanduser("~/pysystemtrade/private/private_config.yaml"),
)
DOWNLOAD_RUNNER = os.path.join(os.path.dirname(__file__), "barchart_download.py")


def download_stage(config_path: str):
    print("=" * 70)
    print("STAGE 1/3: download via bc-utils")
    print("=" * 70)
    if not os.path.exists(BC_UTILS_PYTHON):
        raise FileNotFoundError(
            f"bc-utils venv python not found at {BC_UTILS_PYTHON}. "
            "Set BC_UTILS_DIR / BC_UTILS_VENV_PYTHON or create the venv."
        )
    subprocess.run(
        [BC_UTILS_PYTHON, DOWNLOAD_RUNNER, "--config", config_path], check=True
    )


def process_stage(instruments: list, datapath: str, roll_calendar_path: str):
    print("=" * 70)
    print("STAGE 2/3: process CSVs -> parquet / mongo")
    print("=" * 70)
    return run_pipeline(instruments, ALL_STAGES, datapath, roll_calendar_path)


def verify_stage(instruments: list):
    print("=" * 70)
    print("STAGE 3/3: verify adjusted prices in DB")
    print("=" * 70)
    # imported here so --skip-verify avoids the production data layer entirely
    from sysproduction.data.prices import diagPrices

    diag_prices = diagPrices()
    adjusted = diag_prices.db_futures_adjusted_prices_data
    have = adjusted.get_list_of_instruments()
    ok, missing = [], []
    for code in instruments:
        if code in have:
            n = len(adjusted.get_adjusted_prices(code))
            print(f"  {code:14s} OK       rows={n}")
            ok.append(code)
        else:
            print(f"  {code:14s} MISSING")
            missing.append(code)
    print(f"verify: {len(ok)} present, {len(missing)} missing")
    return ok, missing


def main():
    parser = argparse.ArgumentParser(description="Barchart end-to-end orchestrator")
    parser.add_argument(
        "--skip-download", action="store_true", help="skip the bc-utils download stage"
    )
    parser.add_argument(
        "--skip-verify", action="store_true", help="skip the DB verification stage"
    )
    parser.add_argument(
        "--process-all",
        action="store_true",
        help="process every instrument found in the datapath, not just the "
        "configured barchart_download_list",
    )
    args = parser.parse_args()

    config = get_production_config()
    datapath = config.get_element_or_default("barchart_path", DEFAULT_DATAPATH)
    download_list = config.get_element_or_default("barchart_download_list", [])
    dry_run = config.get_element_or_default("barchart_dry_run", False)

    if not args.skip_download:
        download_stage(PRIVATE_CONFIG)
        if dry_run:
            print(
                "\nNOTE: barchart_dry_run is True — no data was downloaded. "
                "Set barchart_dry_run: False in the private config to pull data."
            )

    if args.process_all:
        instruments = instruments_in_datapath(datapath)
    else:
        instruments = list(download_list)

    if not instruments:
        print("No instruments to process. Nothing to do.")
        return

    process_stage(instruments, datapath, DEFAULT_ROLL_CALENDAR_PATH)

    if not args.skip_verify:
        verify_stage(instruments)


if __name__ == "__main__":
    main()
