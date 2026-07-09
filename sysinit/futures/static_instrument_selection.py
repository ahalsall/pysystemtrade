"""Run Rob's STATIC instrument selection (greedy, affordability + diversification +
cost aware, dedup via config duplicate_instruments) on OUR universe/data, across
capital levels. Compares to Rob's published Static_selection_of_instruments report.
This is the correct pre-step the naive equal-weight backtest skipped.

Output: for each capital, the ordered + sorted selected instrument set, and a diff
vs Rob's published list (where known)."""
import os
os.environ["MPLBACKEND"] = "Agg"
import csv
import pandas as pd
from systems.provided.rob_system.run_system import futures_system
from systems.provided.static_small_system_optimise.optimise_small_system import (
    find_best_ordered_set_of_instruments, get_correlation_matrix,
)
from sysproduction.data.prices import diagPrices
from sysdata.sim.db_futures_sim_data import dbFuturesSimData

# clean CSI universe = csi n data n config, minus DYNAMIC-STALENESS (same guard as
# dynopt_backtest): drop instruments whose raw price ends >45d before the freshest.
# futures_system() loads the full 170 config incl. never-ingested codes -> restrict first.
_dp = diagPrices()
_data = (set(_dp.db_futures_adjusted_prices_data.get_list_of_instruments())
         & set(_dp.db_futures_multiple_prices_data.get_list_of_instruments()))
_csi = set(r[1] for r in csv.reader(open("private/data/futures/csi_symbol_map.csv"))
           if r and r[0] != "csi_symbol")
_simd = dbFuturesSimData()
_cfg = set(futures_system().config.instrument_weights.keys())
_cands = _csi & _data & _cfg
_last = {}
for _c in _cands:
    try:
        _last[_c] = pd.Timestamp(_simd.get_raw_price(_c).dropna().index[-1].date())
    except Exception:
        _last[_c] = pd.Timestamp("1900-01-01")
_fresh = max(_last.values())
_UNIVERSE = sorted(c for c in _cands if (_fresh - _last[c]).days <= 45)
print(f"static-selection universe: {len(_UNIVERSE)} clean instruments (of {len(_cands)} cands)")


def our_system():
    system = futures_system()
    w = 1.0 / len(_UNIVERSE)
    system.config.instrument_weights = {i: w for i in _UNIVERSE}
    system.config.use_instrument_weight_estimates = False
    return system

# Rob's published lists (Static_selection_of_instruments report) for diffing
ROB = {
    100000: set("BITCOIN CAD COPPER-micro CORN DOW EU-AUTO EU-BANKS EU-OIL EU-REALESTATE "
                "EURO600 EUR_micro GBP IRON KOSDAQ KOSPI_mini KR10 KRWUSD_mini LEANHOG MUMMY "
                "OAT REDWHEAT RICE RUBBER SOYOIL SP500_micro TOPIX V2X ZAR".split()),
    250000: set("BITCOIN BRE CAD COPPER-micro DOW EU-AUTO EU-BANKS EU-DJ-UTIL EU-OIL EUROSTX "
                "EUR_micro FTSECHINAA GAS_US_mini GOLD_micro IRON KOSDAQ KOSPI_mini KRWUSD_mini "
                "LEANHOG LIVECOW MSCIASIA MUMMY MXP NASDAQ_micro OAT RICE RUBBER SEK SMI SOYMEAL "
                "SOYOIL US10 WHEAT YENEUR ZAR".split()),
}

# (capital, est_number_of_instruments) — est only sizes max_weight/IDM; greedy picks the count
LEVELS = [(100000, 16), (110000, 16), (250000, 22), (1000000, 36)]

print("Computing correlation matrix (capital-irrelevant, shared)...", flush=True)
corr = get_correlation_matrix(our_system())
print("corr matrix ready\n", flush=True)

summary = []
for capital, est in LEVELS:
    system = our_system()
    sel = find_best_ordered_set_of_instruments(
        system, corr_matrix=corr,
        max_instrument_weight=1.0 / est,
        notional_starting_IDM=est ** 0.25,
        capital=capital,
    )
    ss = sorted(sel)
    print(f"\n===== CAPITAL ${capital:,} -> {len(ss)} instruments =====", flush=True)
    print("  ordered:", sel, flush=True)
    print("  sorted :", ss, flush=True)
    if capital in ROB:
        ours, rob = set(ss), ROB[capital]
        print(f"  vs Rob's published ({len(rob)}): overlap {len(ours & rob)}", flush=True)
        print(f"    we-pick-not-Rob: {sorted(ours - rob)}", flush=True)
        print(f"    Rob-picks-not-us: {sorted(rob - ours)}", flush=True)
    summary.append((capital, len(ss), " ".join(ss)))

print("\n=== SUMMARY ===", flush=True)
for cap, n, lst in summary:
    print(f"  ${cap:>9,}: {n:>2} instruments", flush=True)
with open("/home/andrew/pysystemtrade/private/static_selection_ours.txt", "w") as f:
    for cap, n, lst in summary:
        f.write(f"# ${cap:,}  ({n} instruments)\n{lst}\n\n")
print("saved -> private/static_selection_ours.txt", flush=True)
