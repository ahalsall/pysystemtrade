"""
Build & audit the CSI -> PST instrument symbol map (CSI_SYMBOL_MAP).

We have ~500 instruments to map from CSI symbols to PST codes, and it must be
trustworthy against BOTH PST config and IB. Rather than hand-type, we cross-
reference CSI market specs against the two local Rosetta stones:
  - sysbrokers/IB/config/ib_config_futures.csv : Instrument <-> IBSymbol <->
        IBExchange <-> IBCurrency <-> IBMultiplier
  - data/futures/csvconfig/instrumentconfig.csv: Instrument <-> Description <->
        Pointsize <-> Currency <-> AssetClass <-> Region

Matching uses several corroborating keys so a match is only "HIGH" confidence
when independent signals agree:
  - CSI exchange-symbol  == IBSymbol            (strong, if present)
  - CSI name             ~= PST Description      (fuzzy)
  - CSI currency         == PST/IB currency      (corroborating)
  - CSI point value      == Pointsize/IBMultiplier (corroborating)

Outputs (nothing is trusted blindly):
  - a proposed CSI_SYMBOL_MAP (CSV + python-dict snippet) for HIGH matches
  - an AUDIT csv with score + evidence + runner-up for every CSI market
  - lists of ambiguous / unmatched CSI markets and unmatched PST instruments

The CSI specs loader is best-effort until we see a real symbol.specs.txt; it is
isolated in load_csi_specs() and easy to adjust. Until then:
  # works NOW without any CSI file — dump the PST-side reference for manual work:
  uv run python -m sysinit.futures.build_csi_symbol_map --dump-pst-reference
  # once you have specs files:
  uv run python -m sysinit.futures.build_csi_symbol_map --specs <dir-or-file> \
      --out private/data/futures/csi_symbol_map.csv --audit private/data/futures/csi_map_audit.csv
"""
import argparse
import csv
import os
import re
from difflib import SequenceMatcher

IB_CONFIG = "sysbrokers/IB/config/ib_config_futures.csv"
INSTR_CONFIG = "data/futures/csvconfig/instrumentconfig.csv"

# seed / known-good overrides — always win, and let us encode manual audit results
KNOWN_OVERRIDES = {
    "AE": "AEX",
    "AL": "ALUMINIUM",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _norm_tokens(s: str) -> set:
    return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def load_pst_index() -> dict:
    """PST instrument -> merged record from ib_config + instrumentconfig."""
    idx = {}
    with open(IB_CONFIG) as f:
        for r in csv.DictReader(f):
            idx[r["Instrument"]] = {
                "instrument": r["Instrument"],
                "ib_symbol": r.get("IBSymbol", ""),
                "ib_exchange": r.get("IBExchange", ""),
                "ib_currency": r.get("IBCurrency", ""),
                "ib_multiplier": r.get("IBMultiplier", ""),
            }
    with open(INSTR_CONFIG) as f:
        for r in csv.DictReader(f):
            rec = idx.setdefault(r["Instrument"], {"instrument": r["Instrument"]})
            rec["description"] = r.get("Description", "")
            rec["pointsize"] = r.get("Pointsize", "")
            rec["currency"] = r.get("Currency", "")
            rec["asset_class"] = r.get("AssetClass", "")
            rec["region"] = r.get("Region", "")
    return idx


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def score_match(csi: dict, pst: dict) -> tuple:
    """Return (score, evidence dict). Higher = better. Requires corroboration
    for a confident match (see confidence() )."""
    ev = {}
    score = 0.0

    # name / description fuzzy (0..4)
    csi_name = csi.get("name", "")
    pst_desc = pst.get("description", "")
    if csi_name and pst_desc:
        ratio = SequenceMatcher(None, _norm(csi_name), _norm(pst_desc)).ratio()
        toks = _norm_tokens(csi_name) & _norm_tokens(pst_desc)
        tok_bonus = min(len(toks) * 0.15, 0.6)
        name_score = ratio * 4 + tok_bonus
        score += name_score
        ev["name"] = f"{ratio:.2f}/{sorted(toks)[:4]}"

    # exchange symbol == IBSymbol (strong, +5)
    ex_sym = csi.get("exchange_symbol", "")
    if ex_sym and pst.get("ib_symbol"):
        if _norm(ex_sym) == _norm(pst["ib_symbol"]):
            score += 5
            ev["exch_sym"] = f"{ex_sym}==IB:{pst['ib_symbol']}"

    # currency match (+2)
    cur = (csi.get("currency", "") or "").upper()
    pcur = (pst.get("currency", "") or pst.get("ib_currency", "") or "").upper()
    if cur and pcur:
        if cur == pcur:
            score += 2
            ev["ccy"] = cur
        else:
            score -= 1.5  # currency mismatch is a strong negative
            ev["ccy_mismatch"] = f"{cur}!={pcur}"

    # point value match (+3)
    pv = _num(csi.get("point_value"))
    ppv = _num(pst.get("pointsize")) or _num(pst.get("ib_multiplier"))
    if pv is not None and ppv is not None and pv > 0 and ppv > 0:
        if abs(pv - ppv) / max(pv, ppv) < 0.001:
            score += 3
            ev["pointvalue"] = f"{pv:g}"

    return score, ev


def confidence(best_score, runner_score, ev) -> str:
    strong = ("exch_sym" in ev) + (("ccy" in ev) and ("pointvalue" in ev))
    name_ok = "name" in ev and float(ev["name"].split("/")[0]) >= 0.6
    margin = best_score - runner_score
    if "ccy_mismatch" in ev:
        return "LOW"
    if best_score >= 6 and margin >= 1.5 and (strong or name_ok):
        return "HIGH"
    if best_score >= 4 and margin >= 0.8:
        return "MEDIUM"
    return "LOW"


def match_all(csi_records: list, pst_index: dict) -> list:
    results = []
    pst_list = list(pst_index.values())
    for csi in csi_records:
        sym = csi.get("csi_symbol", "")
        if sym in KNOWN_OVERRIDES:
            results.append(dict(csi_symbol=sym, pst=KNOWN_OVERRIDES[sym],
                                score=99, confidence="OVERRIDE", evidence="seed",
                                runner_up=""))
            continue
        scored = sorted(
            ((score_match(csi, p), p) for p in pst_list),
            key=lambda x: x[0][0], reverse=True,
        )
        (best_s, best_ev), best_p = scored[0]
        runner_s = scored[1][0][0] if len(scored) > 1 else 0.0
        conf = confidence(best_s, runner_s, best_ev)
        results.append(dict(
            csi_symbol=sym, csi_name=csi.get("name", ""),
            pst=best_p["instrument"], score=round(best_s, 2), confidence=conf,
            evidence=";".join(f"{k}={v}" for k, v in best_ev.items()),
            runner_up=f"{scored[1][1]['instrument']}({runner_s:.1f})" if len(scored) > 1 else "",
        ))
    return results


# --------------------------------------------------------------------------
# CSI specs loader — BEST-EFFORT until we see a real symbol.specs.txt.
# Handles (a) a normalized CSV with columns
#   csi_symbol,name,exchange,exchange_symbol,currency,point_value
# and (b) key:value spec blocks. Adjust _SPEC_KEYS once we have real files.
# --------------------------------------------------------------------------
_SPEC_KEYS = {
    "csi_symbol": ["csi symbol", "symbol", "csisymbol", "sym"],
    "name": ["name", "description", "title", "market"],
    "exchange": ["exchange", "exch"],
    "exchange_symbol": ["exchange symbol", "exchangesymbol", "trading symbol"],
    "currency": ["currency", "ccy", "denomination"],
    "point_value": ["big point value", "point value", "contract value", "pointvalue"],
}


def _normkey(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _spec_field(key_variants, kv):
    """kv has normalized keys; match variants after normalizing them too."""
    for k in key_variants:
        nk = _normkey(k)
        if nk in kv:
            return kv[nk]
    return ""


def load_csi_specs(path: str) -> list:
    files = []
    if os.path.isdir(path):
        for fn in os.listdir(path):
            if fn.lower().endswith((".txt", ".csv", ".specs")):
                files.append(os.path.join(path, fn))
    else:
        files = [path]

    records = []
    for fp in files:
        with open(fp, errors="replace") as f:
            head = f.readline()
            f.seek(0)
            if "," in head and any(h in head.lower() for h in ("symbol", "name")):
                # normalized CSV
                for r in csv.DictReader(f):
                    low = {_normkey(k): (v or "").strip() for k, v in r.items()}
                    records.append({
                        field: _spec_field(variants, low)
                        for field, variants in _SPEC_KEYS.items()
                    })
            else:
                # key:value block(s)
                kv = {}
                for line in f:
                    m = re.match(r"\s*([A-Za-z][A-Za-z ./]+?)\s*[:=]\s*(.+)", line)
                    if m:
                        kv[_normkey(m.group(1))] = m.group(2).strip()
                if kv:
                    records.append({
                        field: _spec_field(variants, kv)
                        for field, variants in _SPEC_KEYS.items()
                    })
    return [r for r in records if r.get("csi_symbol")]


def dump_pst_reference(pst_index, out):
    cols = ["instrument", "description", "asset_class", "region", "currency",
            "pointsize", "ib_symbol", "ib_exchange", "ib_currency", "ib_multiplier"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for rec in sorted(pst_index.values(), key=lambda r: r["instrument"]):
            w.writerow(rec)
    print(f"wrote PST reference ({len(pst_index)} instruments) -> {out}")


def main():
    p = argparse.ArgumentParser(description="Build/audit CSI->PST symbol map")
    p.add_argument("--specs", help="CSI specs dir or file (symbol.specs.txt / normalized CSV)")
    p.add_argument("--out", default="private/data/futures/csi_symbol_map.csv",
                   help="output map CSV (HIGH+OVERRIDE matches)")
    p.add_argument("--audit", default="private/data/futures/csi_map_audit.csv",
                   help="full audit CSV (every CSI market, all confidences)")
    p.add_argument("--dump-pst-reference", metavar="OUT", nargs="?",
                   const="private/data/futures/pst_instrument_reference.csv",
                   help="just dump the PST-side reference table and exit")
    args = p.parse_args()

    pst_index = load_pst_index()
    print(f"PST index: {len(pst_index)} instruments "
          f"({sum('description' in r for r in pst_index.values())} with description)")

    if args.dump_pst_reference:
        dump_pst_reference(pst_index, args.dump_pst_reference)
        return

    if not args.specs:
        p.error("need --specs (or use --dump-pst-reference)")

    csi_records = load_csi_specs(args.specs)
    print(f"loaded {len(csi_records)} CSI market records")
    if csi_records[:1]:
        print("  sample parsed record:", csi_records[0])

    results = match_all(csi_records, pst_index)
    by_conf = {}
    for r in results:
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
    print("confidence breakdown:", by_conf)

    # full audit
    os.makedirs(os.path.dirname(args.audit), exist_ok=True)
    with open(args.audit, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["csi_symbol", "csi_name", "pst", "score",
                                          "confidence", "evidence", "runner_up"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    print(f"wrote audit -> {args.audit}")

    # trusted map = HIGH + OVERRIDE
    trusted = [r for r in results if r["confidence"] in ("HIGH", "OVERRIDE")]
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["csi_symbol", "pst_code", "confidence", "evidence"])
        for r in sorted(trusted, key=lambda r: r["csi_symbol"]):
            w.writerow([r["csi_symbol"], r["pst"], r["confidence"], r.get("evidence", "")])
    print(f"wrote trusted map ({len(trusted)}) -> {args.out}")

    matched_pst = {r["pst"] for r in trusted}
    unmatched_pst = sorted(set(pst_index) - matched_pst)
    ambiguous = [r["csi_symbol"] for r in results if r["confidence"] in ("MEDIUM", "LOW")]
    print(f"\nNEEDS MANUAL AUDIT: {len(ambiguous)} CSI markets (MEDIUM/LOW) — see audit csv")
    print(f"PST instruments with NO trusted CSI match: {len(unmatched_pst)}")


if __name__ == "__main__":
    main()
