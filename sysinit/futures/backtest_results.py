"""Reusable backtest results persistence: full stats + the whole account curve,
saved per run so we can jump back and compare across sessions. Everything lands under
private/backtest_runs/<label>/ : curve.csv (cumulative %-of-capital) + stats.json.

Usage in a backtest script:
    from sysinit.futures.backtest_results import full_stats, save_run
    stats = full_stats(acc, capital, extra=dict(funded=..., universe=..., ...))
    save_run("dynopt_estimated_110k", acc, capital, stats)
"""
import os
import json
import numpy as np
import pandas as pd

RUNS_DIR = "private/backtest_runs"


def _daily_ccy(acc):
    """Daily P&L in base currency from an account curve (acc.as_ts is a PROPERTY)."""
    raw = acc.as_ts
    raw = raw() if callable(raw) else raw
    return pd.Series(raw).replace([np.inf, -np.inf], np.nan).dropna()


def full_stats(acc, capital: float, extra: dict = None) -> dict:
    """Comprehensive, currency-based (finite at low capital) stats dict."""
    d = _daily_ccy(acc)
    mu, sd = d.mean(), d.std()
    cum = d.cumsum()
    dd = cum - cum.cummax()  # currency drawdown
    ddpct = dd / capital * 100
    stats = dict(
        capital=int(capital),
        sharpe=round(float((mu / sd) * np.sqrt(256)) if sd else float("nan"), 3),
        ann_return_pct=round(float(mu * 256 / capital * 100), 2),
        ann_vol_pct=round(float(sd * np.sqrt(256) / capital * 100), 2),
        max_dd_pct=round(float(ddpct.min()), 2),
        avg_dd_pct=round(float(ddpct.mean()), 2),
        median_dd_pct=round(float(ddpct.median()), 2),
        time_in_dd_pct=round(float((ddpct < -0.01).mean() * 100), 1),
        skew=round(float(d.skew()), 3),
        start=str(d.index[0].date()),
        end=str(d.index[-1].date()),
        n_days=int(len(d)),
    )
    if extra:
        stats.update(extra)
    return stats


def save_run(label: str, acc, capital: float, stats: dict = None) -> str:
    """Persist curve (cumulative %-of-capital) + stats.json under RUNS_DIR/<label>/."""
    d = _daily_ccy(acc)
    curve_pct = (d.cumsum() / capital * 100)
    outdir = os.path.join(RUNS_DIR, label)
    os.makedirs(outdir, exist_ok=True)
    curve_pct.to_csv(os.path.join(outdir, "curve.csv"), header=["cum_pct_of_capital"])
    if stats is None:
        stats = full_stats(acc, capital)
    with open(os.path.join(outdir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    return outdir


def load_stats(label: str) -> dict:
    with open(os.path.join(RUNS_DIR, label, "stats.json")) as f:
        return json.load(f)


def compare_runs() -> "pd.DataFrame":
    """Table of all saved runs' stats for cross-comparison."""
    rows = []
    if os.path.isdir(RUNS_DIR):
        for label in sorted(os.listdir(RUNS_DIR)):
            p = os.path.join(RUNS_DIR, label, "stats.json")
            if os.path.exists(p):
                with open(p) as f:
                    rows.append(dict(label=label, **json.load(f)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = compare_runs()
    pd.set_option("display.width", 160)
    print(df.to_string(index=False) if len(df) else "no saved runs yet")
