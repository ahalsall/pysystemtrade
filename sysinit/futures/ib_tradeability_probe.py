"""
IB-Canada tradeability probe → generates the `trading_restrictions` list.

Answers: "of the instruments in our (broad) sim/research universe, which can we
ACTUALLY trade on IB from Canada?" The COMPLEMENT (untradeable) is what goes into
`exclude_instrument_lists.trading_restrictions` in private_config.yaml, so the
dynamic optimiser never targets a market we can't fill (see
notes/concepts/instrument_universe.md — restrictions become reduce_only box
constraints inside the optimisation, so risk is redistributed to tradeable markets).

Tradeability signals, cheapest → strongest (all except market-data need no subs):
  1. in ib_config_futures.csv         — config gate (no IB connection needed)
  2. get_brokers_instrument_with_metadata(code)      — IB knows the instrument
  3. get_list_of_contract_dates_for_instrument_code  — has a current contract chain
  4. get_actual_expiry_date_for_single_contract(c)   — a real contract resolves
  5. (optional, --check-market-data)  recent bid/ask ticks — we hold the data sub

Special case: LME (ALUMINIUM_LME etc.) — IB *resolves* these (synthetic OTC) but
they are NOT tradeable for a Canadian account, so they are hard-coded region-blocked.

Usage:
  # offline: config-only classification (LME + not-in-ib-config), no Gateway needed
  uv run python -m sysinit.futures.ib_tradeability_probe --no-connect

  # full probe (needs IB Gateway up); default universe = ib_config instruments
  uv run python -m sysinit.futures.ib_tradeability_probe

  # probe a specific universe (dotted datapath OR file path, one code per line),
  # also flags codes not in ib_config as untradeable; optionally check data subs
  uv run python -m sysinit.futures.ib_tradeability_probe \
      --universe-file private.data.futures.research_universe --check-market-data \
      --out private/trading_restrictions.yaml
"""
import argparse
import csv
import datetime
import os

from syscore.fileutils import get_resolved_pathname

IB_CONFIG = "sysbrokers/IB/config/ib_config_futures.csv"

# IB returns synthetic LME contracts, but they are not tradeable from Canada.
# Region-blocked regardless of what IB resolution says.
REGION_BLOCKED = {
    "ALUMINIUM_LME", "COPPER_LME", "LEAD_LME", "NICKEL_LME", "TIN_LME", "ZINC_LME",
}


def load_ib_config_instruments() -> dict:
    """instrument_code -> IBExchange, from the IB futures config."""
    with open(IB_CONFIG) as stream:
        return {r["Instrument"]: r.get("IBExchange", "") for r in csv.DictReader(stream)}


def load_universe(universe_file: str) -> list:
    """Read instrument codes from a dotted datapath dir OR a plain text file
    (one code per line). If a dir, expects a single-column file of codes."""
    if os.path.isfile(universe_file):
        path = universe_file
    else:
        # allow a dotted datapath to a file, or a dir holding a codes file
        resolved = get_resolved_pathname(universe_file)
        path = resolved if os.path.isfile(resolved) else None
        if path is None:
            raise FileNotFoundError(f"universe-file not found: {universe_file}")
    with open(path) as stream:
        return [
            line.strip()
            for line in stream
            if line.strip() and not line.lstrip().startswith("#")
        ]


def classify_offline(codes, ib_instruments) -> dict:
    """Config-only pass: mark not-in-ib-config and LME. Returns dict code->record."""
    results = {}
    for code in codes:
        if code in REGION_BLOCKED:
            results[code] = dict(status="UNTRADEABLE", reason="region-blocked (LME, Canada)")
        elif code not in ib_instruments:
            results[code] = dict(status="UNTRADEABLE", reason="not in ib_config")
        else:
            results[code] = dict(status="PENDING", reason="", exchange=ib_instruments[code])
    return results


def probe_ib(results, check_market_data: bool):
    """For PENDING codes, hit IB to confirm a real tradeable contract resolves."""
    # imported here so --no-connect avoids the broker/IB stack entirely
    from sysdata.data_blob import dataBlob
    from sysproduction.data.broker import dataBroker
    from sysobjects.contracts import futuresContract

    pending = [c for c, r in results.items() if r["status"] == "PENDING"]
    if not pending:
        return results

    with dataBlob(log_name="ib-tradeability-probe") as data:
        broker = dataBroker(data)
        for code in pending:
            rec = results[code]
            try:
                # signal 2: IB knows the instrument
                broker.get_brokers_instrument_with_metadata(code)
                # signal 3: current (non-expired) contract chain
                dates = broker.get_list_of_contract_dates_for_instrument_code(
                    code, allow_expired=False
                )
                if not dates:
                    rec.update(status="UNTRADEABLE", reason="no current contracts at IB")
                    print(f"  {code:16s} UNTRADEABLE  no current contracts")
                    continue
                # signal 4: a specific contract fully resolves (expiry from IB)
                contract = futuresContract(code, str(dates[0])[:6])
                expiry = broker.get_actual_expiry_date_for_single_contract(contract)
                rec.update(status="TRADEABLE", reason="", expiry=str(expiry),
                           n_contracts=len(dates))
                # signal 5 (optional): do we actually have market data?
                if check_market_data:
                    try:
                        ticks = broker.get_recent_bid_ask_tick_data_for_contract_object(
                            contract
                        )
                        has = ticks is not None and len(ticks) > 0
                        rec["market_data"] = "OK" if has else "NONE"
                    except Exception as md_err:
                        rec["market_data"] = f"NONE ({type(md_err).__name__})"
                md = f"  data={rec.get('market_data')}" if check_market_data else ""
                print(f"  {code:16s} TRADEABLE    expiry={rec.get('expiry')} "
                      f"contracts={len(dates)}{md}")
            except Exception as error:
                rec.update(status="UNTRADEABLE",
                           reason=f"{type(error).__name__}: {str(error)[:120]}")
                print(f"  {code:16s} UNTRADEABLE  {rec['reason']}")
    return results


def emit_yaml(results) -> str:
    untradeable = sorted(c for c, r in results.items() if r["status"] == "UNTRADEABLE")
    today = datetime.date.today().isoformat()
    lines = [
        f"# generated by ib_tradeability_probe on {today}",
        "# paste into private_config.yaml — untradeable markets become reduce_only",
        "exclude_instrument_lists:",
        "  trading_restrictions:",
    ]
    for code in untradeable:
        reason = results[code]["reason"]
        lines.append(f"    - {code}  # {reason}")
    return "\n".join(lines) + "\n"


def summarise(results):
    by = {}
    for r in results.values():
        by.setdefault(r["status"], 0)
        by[r["status"]] += 1
    print("\n" + "=" * 60)
    print("SUMMARY:", ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
    md = [c for c, r in results.items() if r.get("market_data", "").startswith("NONE")]
    if md:
        print(f"TRADEABLE but NO market data ({len(md)}): {sorted(md)}")


def main():
    p = argparse.ArgumentParser(description="IB-Canada tradeability probe")
    p.add_argument("--universe-file",
                   help="dotted datapath or file of instrument codes to probe "
                        "(default: all instruments in ib_config)")
    p.add_argument("--instruments", help="comma-separated codes (overrides universe-file)")
    p.add_argument("--no-connect", action="store_true",
                   help="config-only classification (LME + not-in-ib-config); no Gateway")
    p.add_argument("--check-market-data", action="store_true",
                   help="also probe recent bid/ask ticks (needs data subscriptions)")
    p.add_argument("--out", help="write the trading_restrictions YAML snippet here")
    p.add_argument("--limit", type=int, help="probe only the first N (testing)")
    args = p.parse_args()

    ib_instruments = load_ib_config_instruments()

    if args.instruments:
        codes = [c.strip() for c in args.instruments.split(",") if c.strip()]
    elif args.universe_file:
        codes = load_universe(args.universe_file)
    else:
        codes = sorted(ib_instruments)
    if args.limit:
        codes = codes[: args.limit]

    print(f"Probing {len(codes)} instruments (ib_config has {len(ib_instruments)})")
    results = classify_offline(codes, ib_instruments)
    if not args.no_connect:
        results = probe_ib(results, check_market_data=args.check_market_data)
    else:
        # offline: nothing stays PENDING — treat as TRADEABLE (config-passed)
        for r in results.values():
            if r["status"] == "PENDING":
                r["status"] = "TRADEABLE"

    summarise(results)
    yaml_snippet = emit_yaml(results)
    if args.out:
        out = get_resolved_pathname(args.out) if "." in args.out and "/" not in args.out else args.out
        with open(out, "w") as stream:
            stream.write(yaml_snippet)
        print(f"\nwrote trading_restrictions snippet -> {out}")
    else:
        print("\n" + yaml_snippet)


if __name__ == "__main__":
    main()
