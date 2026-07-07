"""
Catalog-driven CSI symbol selection (the whole-universe shopping list).

Given CSI's full factsheet (private/commodityfactsheet.csv — every CSI market with
SymbolUA, Name, Exchange, Currency, ContractSize, LastTotalVolume, Start/End dates),
find for EACH PST instrument the best + MOST-LIQUID matching CSI market. Volume is the
tie-breaker among same-underlying candidates, so we pick NQ over dead ND3, FFI over
FTK, ICE Brent over the NYMEX financial — automatically, instead of hunting by hand.

Reverse of build_csi_symbol_map (which matches CSI->PST from exported specs): here we
go PST->CSI across the whole catalog, and:
  - honour manual decisions: KNOWN_OVERRIDES (inverted) win; IGNORE_CSI_SYMBOLS excluded
  - score by name + currency + contract size + exchange, require a real name match,
    then rank the survivors by LastTotalVolume (liquidity)
  - emit a shopping list (PST -> chosen CSI symbol, name, exch, volume, coverage dates,
    + alternatives) and a CSI->PST map, and flag no-match / short-history instruments.

IMPORTANT — AUDIT-FIRST, not authoritative. Validated against our 94 spec-verified
mappings: the auto-pick AGREES only ~37/95. Name matching is too coarse to separate
closely-related instruments (soy meal/oil/beans, EU sector vs main index, gold/copper
micro, bond maturities). So treat the top pick as a HINT and always show/keep the
`alts` and coverage dates; real mapping stays spec-verified in build_csi_symbol_map's
KNOWN_OVERRIDES. Best used as a per-instrument LOOKUP (candidates + volume + StartDate/
EndDate) to speed MANUAL verification and to spot the liquid variant — NOT a blind map.

Usage:
  uv run python -m sysinit.futures.csi_catalog_map                 # full universe
  uv run python -m sysinit.futures.csi_catalog_map --instruments GOLD,NASDAQ,BRENT_W
"""
import argparse
import csv
import re
from difflib import SequenceMatcher

from sysinit.futures.build_csi_symbol_map import (
    load_pst_index, _norm, _first_num, _num, KNOWN_OVERRIDES, IGNORE_CSI_SYMBOLS,
)

CATALOG = "private/commodityfactsheet.csv"
NAME_FLOOR = 0.25         # minimum name similarity to be a candidate at all
GOOD_SCORE = 5.0          # above this = "confident match"; rank these by volume


def _toks(s):
    return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def load_catalog(path=CATALOG) -> list:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sym = (r.get("SymbolUA") or "").strip()
            if not sym:
                continue
            rows.append(dict(
                symbol=sym,
                name=(r.get("Name") or "").strip(),
                exch=(r.get("Exchange") or "").strip(),
                exch_sym=(r.get("ExchangeSymbol") or "").strip(),
                currency=(r.get("Currency") or "").strip().upper(),
                contract_size=_first_num(r.get("ContractSize")),
                full_point=_first_num(r.get("FullPointValue")),
                volume=_num(r.get("LastTotalVolume")) or 0.0,
                start=(r.get("StartDate") or "").strip(),
                end=(r.get("EndDate") or "").strip(),
                active=(r.get("IsActive") or "").strip() == "1",
            ))
    return rows


def _name_score(pst_desc, csi_name):
    ratio = SequenceMatcher(None, _norm(pst_desc), _norm(csi_name)).ratio()
    toks = _toks(pst_desc) & _toks(csi_name)
    return ratio * 4 + min(len(toks) * 0.2, 1.0), ratio, sorted(toks)[:4]


def _nums(s):
    """Significant numbers in a name (maturities, grades, index sizes): Sugar 11 vs
    16, US 2yr vs 5yr, Russell 1000 vs 2000. Excludes huge numbers (point values)."""
    return set(int(n) for n in re.findall(r"\d+", s or "") if int(n) < 3000)


def score_candidate(pst, c):
    ev = {}
    name_sc, ratio, toks = _name_score(pst.get("description", ""), c["name"])
    if ratio < NAME_FLOOR and not toks:
        return None
    score = name_sc
    ev["name"] = f"{ratio:.2f}{toks}"
    ev["ratio"] = ratio
    # number/variant discrimination: same name-family but different number (Sugar
    # #11 vs #16, US 2yr vs 5yr) is a DIFFERENT contract, not a liquidity choice.
    npst, ncsi = _nums(pst.get("description", "")), _nums(c["name"])
    if npst and ncsi and npst != ncsi:
        score -= 3
        ev["num_mismatch"] = f"{sorted(npst)}!={sorted(ncsi)}"
    # distinct-underlying qualifiers (white sugar != raw; mid-cap != main index).
    # NOTE: mini/micro/e-mini deliberately excluded — those are size variants of the
    # SAME underlying, which we WANT volume to choose between.
    dq = {"white", "mid"}
    qpst = {q for q in dq if q in _norm(pst.get("description", ""))}
    qcsi = {q for q in dq if q in _norm(c["name"])}
    if qpst != qcsi:
        score -= 3
        ev["qual_mismatch"] = f"{qpst}^{qcsi}"
    # currency (+2 / big penalty on mismatch)
    pcur = (pst.get("currency", "") or pst.get("ib_currency", "") or "").upper()
    if pcur and c["currency"]:
        if pcur == c["currency"]:
            score += 2
        else:
            score -= 2.5
            ev["ccy_mismatch"] = f"{c['currency']}!={pcur}"
    # contract size / point value (+3)
    ppv = _num(pst.get("pointsize")) or _num(pst.get("ib_multiplier"))
    for csz in (c["contract_size"], c["full_point"]):
        if ppv and csz and ppv > 0 and abs(csz - ppv) / max(csz, ppv) < 0.02:
            score += 3
            ev["size"] = f"{csz:g}"
            break
    # exchange hint (+1) — CSI names vs IB exchange, loose substring
    ex, pex = _norm(c["exch"]), _norm(pst.get("ib_exchange", ""))
    if ex and pex and (ex[:3] == pex[:3] or ex in pex or pex in ex):
        score += 1
        ev["exch"] = c["exch"]
    return score, ev


def choose_for_instrument(pst, catalog, inverted_overrides):
    code = pst["instrument"]
    # 1) manual override wins
    if code in inverted_overrides:
        sym = inverted_overrides[code]
        hit = next((c for c in catalog if c["symbol"] == sym), None)
        return dict(pst=code, csi=sym, name=hit["name"] if hit else "", src="PINNED",
                    volume=hit["volume"] if hit else "", start=hit["start"] if hit else "",
                    end=hit["end"] if hit else "", conf="pinned", alts="")
    # 2) score the catalog; only volume-rank GENUINE same-underlying matches
    scored = []
    for c in catalog:
        if c["symbol"] in IGNORE_CSI_SYMBOLS:
            continue
        r = score_candidate(pst, c)
        if r is None:
            continue
        s, ev = r
        if "ccy_mismatch" in ev:
            continue
        scored.append((s, ev, c))
    if not scored:
        return dict(pst=code, csi="", name="", src="NO-MATCH", volume="", start="", end="", conf="none", alts="")
    scored.sort(key=lambda x: -x[0])
    # confident pool = real name match (ratio>=0.5), no number-variant mismatch, active;
    # ONLY these compete on volume (so we pick the liquid variant, not a wrong-name high-vol one)
    confident = [sc for sc in scored
                 if sc[0] >= GOOD_SCORE and sc[1]["ratio"] >= 0.5
                 and "num_mismatch" not in sc[1] and "qual_mismatch" not in sc[1]
                 and sc[2]["active"]]
    pool = confident if confident else scored[:1]
    best = max(pool, key=lambda sc: (sc[2]["volume"], sc[0]))
    alts = ";".join(f"{c['symbol']}(v{int(c['volume'])})"
                    for _, _, c in scored[:4] if c["symbol"] != best[2]["symbol"])
    conf = "HIGH" if best in confident else "LOW"
    return dict(pst=code, csi=best[2]["symbol"], name=best[2]["name"], src="MATCHED",
                volume=int(best[2]["volume"]), start=best[2]["start"], end=best[2]["end"],
                conf=conf, alts=alts)


def main():
    p = argparse.ArgumentParser(description="Catalog-driven CSI symbol selection")
    p.add_argument("--instruments", help="comma-separated PST codes (default: all)")
    p.add_argument("--out", default="private/csi_catalog_shopping_list.csv")
    args = p.parse_args()

    pst_index = load_pst_index()
    catalog = load_catalog()
    inverted = {pst: csi for csi, pst in KNOWN_OVERRIDES.items()}  # last wins; overrides are 1:1 enough
    print(f"PST instruments: {len(pst_index)} | CSI catalog: {len(catalog)} markets | "
          f"pinned: {len(inverted)}")

    codes = ([c.strip() for c in args.instruments.split(",")] if args.instruments
             else sorted(pst_index))
    results = [choose_for_instrument(pst_index[c], catalog, inverted) for c in codes if c in pst_index]

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pst", "csi", "name", "src", "conf", "volume",
                                          "start", "end", "alts"])
        w.writeheader(); w.writerows(results)

    by = {}
    for r in results:
        by[r["src"] if r["src"] != "MATCHED" else r["conf"]] = by.get(
            r["src"] if r["src"] != "MATCHED" else r["conf"], 0) + 1
    print("breakdown:", by)
    print(f"wrote shopping list -> {args.out}")
    if args.instruments:
        for r in results:
            print(f"  {r['pst']:<14} -> {r['csi']:<8} {r['src']:<8} v{r['volume']} "
                  f"[{r['start']}..{r['end']}] {r['name'][:34]}  alts:{r['alts']}")


if __name__ == "__main__":
    main()
