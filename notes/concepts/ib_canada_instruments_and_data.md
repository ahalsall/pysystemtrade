# Interactive Brokers Canada — Futures Instrument Availability & Market-Data Subscriptions

**Purpose:** Research note for running a dynamically-optimized futures portfolio (pysystemtrade) through an
**Interactive Brokers Canada Inc.** account, with ~CAD 150k capital holding ~28–32 instruments selected from a
~200-instrument cost-screened candidate set.

> **Caveat / accuracy warning.** IBKR's market-data offerings, bundle names, prices and per-product residency
> restrictions change frequently, and IBKR's live pricing tables are JavaScript-rendered and were not directly
> fetchable for this note (the public pricing pages returned HTTP 403 to automated retrieval). Concept-level facts
> below are taken from IBKR's official API documentation, IBKR product pages and IBKR knowledge-base content; **exact
> dollar figures should be confirmed against the IBKR Canada Market Data Pricing page and Client Portal before you
> rely on them.** Where a number is approximate or uncertain it is flagged explicitly.

---

## 0. Regulatory framing

The account would be with **Interactive Brokers Canada Inc.**, a member of the **Canadian Investment Regulatory
Organization (CIRO)** (the 2023 merger of IIROC + MFDA). IB Canada is registered as an investment dealer in all
provinces, a **futures commission merchant in Ontario and Manitoba**, and a derivatives dealer in Quebec; it is
headquartered in Montreal.
([CIRO/IIROC dealer page](https://www.iiroc.ca/investors/choosing-investment-advisor/dealers-we-regulate/interactive-brokers-canada-inc),
[OSC decision](https://www.osc.ca/en/securities-law/orders-rulings-decisions/interactive-brokers-canada-inc-2))

For an **individual Canadian resident**, IBKR grants product/exchange permissions based on financial profile (net
worth, objectives, knowledge, experience) **and, for some products, residency**. The decisive constraints for our
candidate set are residency-based product blocks (see LME below), not the FCM relationship itself.
([Trading Overseas with IBKR](https://www.interactivebrokers.com/campus/trading-lessons/trading-overseas-with-ibkr/))

---

## 1. Instrument / exchange availability for a Canadian-resident individual

IB Canada offers global futures across 30+ market centres; the candidate-set exchanges are almost all accessible to a
Canadian retail client who holds the relevant Futures (and, per region, "international") trading permission. The one
hard block in our set is LME.

| Candidate-set exchange (count) | IB code | Available to CA resident? | Notes |
|---|---|---|---|
| CME (55), CBOT (27), NYMEX (12), COMEX (6) | CME group | **Yes** | Core US futures; needs Futures permission only. ([CME futures – IB Canada](https://www.interactivebrokers.ca/en/trading/cme-futures.php)) |
| ICE US / NYBOT (7) | NYBOT/ICEUS | **Yes** | US soft/ag & FX futures. Data is a separate (and costly) ICE feed — see §2. |
| CFE — Cboe Futures (3) | CFE | **Yes** | VIX complex etc. ([CFE fee page](https://www.interactivebrokers.com/en/accounts/fees/CBOE.php)) |
| EUREX (36) | EUREX | **Yes** | Major European index/rate futures. |
| ICE Futures Europe (8), IPE (5), ICE EU soft (2) | ICEEU/IPE | **Yes** | Brent, gas-oil, Euribor, soft commodities. Data costly — see §2. |
| ENDEX (2) | ENDEX | **Yes** (likely) | ICE Endex gas/power; confirm permission. |
| **LME (6)** | **LMEOTC** | **NO — blocked for Canada** | IBKR's only LME access is *synthetic "IBKR OTC Futures on LME Metals"* with IBKR(UK) as counterparty; explicitly offered to clients **excluding residents of the US, Canada, Hong Kong and Israel.** These 6 instruments are **not tradeable** by a Canadian resident. ([IBKR OTC Futures on LME Metals](https://www.interactivebrokers.com/en/trading/ibkr-otc-futures-lme-metals.php)) |
| SGX (11) | SGX | **Yes** (likely) | Singapore index/rate futures; permission + eligibility checks. |
| OSE.JPN (6) | OSE.JPN | **Yes** (likely) | Osaka index futures. |
| HKFE (4) | HKFE | **Yes** (likely) | Hong Kong index futures. ([HKFE fees – IB Canada](https://www.interactivebrokers.ca/en/accounts/fees/HKFE.php)) |
| CDE — Bourse de Montréal (3) | CDE | **Yes** | Domestic exchange; Canadian rate/index futures. |
| MATIF (2), MONEP (1), BELFOX (1), FTA (1, Euronext Amsterdam), NYSELIFFE (1) | Euronext / NYSE Liffe US | **Yes** (likely) | European/Euronext futures + NYSE Liffe US. |
| SNFE (1) | SNFE (ASX 24/Sydney) | **Yes** (likely) | Australian futures. |

**Net effect on the candidate set:** of the 200 instruments, the **6 LME (LMEOTC) instruments must be removed** as
unavailable to a Canadian resident. Everything else is, in principle, permissionable. "(likely)" entries are
non-US/non-EU venues where individual products can carry residency or knowledge footnotes — verify each on the
[Products/Exchanges search](https://www.interactivebrokers.ca/en/trading/products-exchanges.php) and the product
listing footnotes before relying on them.

> For a CAD 150k / 28–32-instrument optimized portfolio this is not a real constraint: the dynamically-selected
> portfolio will be dominated by the deep, cheap CME-group / Eurex / ICE contracts, all of which are available.

---

## 2. Market data — the key question

### 2a. Historical data via the IB API — does it need a paid subscription?

**Yes, in the general case.** IBKR's official API documentation is explicit:

- *"Receiving historical data from the API has the same market data subscription requirement as receiving streaming
  top-of-book live data."* — and, unlike the TWS desktop charts, *"the API always requires Level 1 streaming
  real-time data to return historical data."*
  ([TWS API – Historical Market Data](https://interactivebrokers.github.io/tws-api/historical_data.html))
- **Delayed data does NOT cover historical.** You can switch streaming quotes to delayed via
  `reqMarketDataType(3)`/`(4)` and many instruments then return 10–15-min delayed *streaming* quotes **without a
  subscription** — but *"historical data still requires market data subscriptions."* Delayed mode only affects
  `reqMktData`, not `reqHistoricalData`.
  ([TWS API – Delayed Streaming Data](https://interactivebrokers.github.io/tws-api/delayed_data.html),
  [Market Data Types](https://interactivebrokers.github.io/tws-api/market_data_type.html))

**Precise summary of what works without a subscription vs. what needs one:**

| Action | Subscription needed? |
|---|---|
| `reqMktData` real-time streaming quotes | **Yes** (per exchange) |
| `reqMktData` 10–15-min **delayed** streaming (`reqMarketDataType 3/4`) | **No** for most instruments (limited tick types) |
| **`reqHistoricalData` daily/intraday bars** (what pysystemtrade pulls for forecasts & covariance) | **Yes** — same requirement as live top-of-book; **delayed mode does not help here** |

> **On the "2023 change" premise:** IBKR did broaden *free delayed streaming* and free snapshots around that period,
> but this note found **no authoritative documentation that the API will return *historical bars* for futures without
> a subscription.** Real-world behaviour can vary by product (some users report bars returning, others get
> "market data not subscribed" errors 162/354), so **test per-exchange**, but **plan on needing the subscription**
> for reliable per-contract historical pulls via the API. (Uncertain — confirm with IBKR.)

**Important practical consequence for pysystemtrade:** you do **not** have to source historical price history from IB
at all. pysystemtrade is normally seeded from a separate vendor — this repo already ships a Barchart loader
(`sysinit/futures/barchart_futures_contract_prices.py`) — and IB is then used for ongoing daily/intraday updates and
execution. **Backtests, forecast generation and the covariance/dynamic-optimization step can be run entirely off
non-IB historical data, with zero IB market-data subscriptions.** See §3.

### 2b. Live streaming for execution algos — bundles & approximate monthly cost

pysystemtrade's default execution algos need **live streaming quotes** for the exchanges you actually trade. These do
require subscriptions. Bundles relevant to the candidate set (non-professional; **confirm exact CAD/USD figures on the
IBKR Canada pricing page**):

| Exchange(s) | Bundle (IBKR name) | Approx. monthly (non-pro) | Confidence |
|---|---|---|---|
| CME + CBOT + NYMEX + COMEX (top-of-book, real-time) | **"US Securities Snapshot and Futures Value Bundle"** | **USD 10** (waivable, see §2c) | High — bundle name & price confirmed ([US bundle](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php)) |
| CME + CBOT + NYMEX + COMEX (alternative, futures-only) | **"US Futures Value Bundle PLUS"** | **USD 5** (not waivable) | Medium-high |
| ICE Futures U.S. / NYBOT (cotton, coffee, sugar, FX) | ICE US data (per product group) | **Costly, varies by product group** — confirm | Low (ICE feeds are notoriously expensive and split by group) |
| CFE — Cboe Futures (VIX etc.) | Cboe/CFE data | Small monthly fee — confirm | Low |
| EUREX | **"Eurex Core"** (L1, non-pro) | **~EUR 1 / month** (pro fee much higher) | Medium ([Deutsche Börse Eurex Retail/Core](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/derivatives-markets/Eurex-Retail-Europe-1339980)) |
| ICE Futures Europe / IPE / ICE EU soft / ENDEX (Brent, gas-oil, Euribor, softs, gas/power) | ICE Europe data (per product group) | **Costly, varies** — confirm | Low |
| LME | n/a | **N/A — product unavailable to Canadians (§1)** | High |
| SGX | SGX data | confirm | Low |
| OSE Japan | OSE data | confirm | Low |
| HKFE | HKFE data | confirm | Low |
| Bourse de Montréal (CDE) | Montreal/CDE data | modest CAD fee (possibly low/included) — confirm | Low |
| Euronext (MATIF / MONEP / FTA / BELFOX) | Euronext data bundle | confirm | Low |

The US futures bundle is the well-anchored figure (~USD 5–10/mo) and Eurex Core is cheap (~EUR 1/mo non-pro). The ICE
feeds (ICE US, ICE Europe/IPE) are the expensive outliers and are **billed per product group** — budget conservatively
and confirm. ([IBKR Market Data Pricing](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php))

### 2c. Fee waiver + professional vs non-professional

- **Commission waiver:** monthly market-data fees are **waived if you generate enough commissions** that month. The
  threshold depends on the service (commonly **USD 5 or USD 15**); the US futures data bundle requires roughly
  **≥ USD 30 in monthly commissions per subscribed user** to waive. Waivers are **not cumulative** and are applied
  first to the highest-priced service.
  ([Market-data exchange/access fees FAQ](https://www.ibkrguides.com/kb/en-us/market-data-exchange-access-fees.htm),
  [Market Data Pricing](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php))
- **Non-professional vs professional:** a **non-professional** is an individual not registered with a financial
  regulator, not acting as an adviser, and not using the data for business purposes; a **professional** (firms,
  registered advisers, business use) pays **substantially higher** exchange fees. A self-directed individual running a
  personal systematic account normally qualifies **non-professional** — but note IBKR/exchanges define this; if the
  account is held by a corporation or used for a business, professional rates may apply. ([same FAQ](https://www.ibkrguides.com/kb/en-us/market-data-exchange-access-fees.htm))

---

## 3. Recommendation — minimal, cost-effective data plan

**Headline:** A 28–32-instrument optimized portfolio that concentrates in liquid US-group + Eurex (+ a little ICE)
needs only a **handful of cheap streaming subscriptions, and those are largely waived once you are actually trading.**
Historical/backtest work needs **no** IB subscription at all.

**Step 1 — Generate forecasts & backtests with NO live subscriptions (deferred subs).**
Seed and maintain historical price history from a non-IB vendor (this repo already has the Barchart loader,
`sysinit/futures/barchart_futures_contract_prices.py`). Forecast generation, the covariance matrix, and the dynamic
optimization all run off this stored history. **You can build and validate the entire system, and choose the 28–32
instruments, before paying IBKR a cent for data.** Subscribe to IB streaming only when you go live and only for the
exchanges you will actually execute on.

**Step 2 — Subscribe to streaming only for execution exchanges.** For a portfolio concentrated in the majors:
- **US futures bundle** ("US Securities Snapshot and Futures Value Bundle" ~USD 10/mo, or "US Futures Value Bundle
  PLUS" ~USD 5/mo) — covers CME + CBOT + NYMEX + COMEX, i.e. the bulk of the optimized set.
- **Eurex Core** (~EUR 1/mo non-pro) — covers the Eurex instruments.
- Add **ICE / CFE / Montreal / others only if** the optimizer actually parks positions there; ICE feeds are the
  expensive ones, so prefer keeping ICE exposure minimal or, if optimization-selected, accept the per-group fee
  consciously.
- **Drop LME entirely** (the 6 LMEOTC instruments are not available to Canadian residents anyway).

**Step 3 — Lean on the commission waiver.** A live 28–32-instrument trend/optimized system rebalancing regularly will
comfortably exceed the USD 5–30/month commission thresholds, so most/all of these data fees should be **waived in
practice**. Net steady-state data cost for a US-group + Eurex book is plausibly **near zero**; the ICE/CFE/Asian feeds
are the only items likely to carry a residual non-waivable cost.

**Step 4 — Keep non-pro status.** Hold the account as an individual (not a corporation / not "business use") to retain
non-professional pricing; professional rates would multiply these figures.

**Bottom line:** You can do **all** research, forecasting and dynamic-optimization off stored (Barchart-seeded)
historical data with **no IBKR subscriptions**, then turn on a **very small** streaming footprint (US futures bundle
+ Eurex Core, ~USD 10–15/mo gross, largely waived by commissions) for live execution. Avoid LME; treat ICE/Asian data
as opt-in only when the optimizer demands those instruments.

---

## Unresolved / to confirm directly with IBKR

1. **Historical-via-API without a subscription** — official docs say it needs one; real-world behaviour reportedly
   varies by product. Confirm empirically per exchange (this drives whether you can update prices from IB or must
   keep using Barchart). *(Mitigated: just keep sourcing history from Barchart.)*
2. **Exact streaming prices** for ICE US/NYBOT, ICE Europe/IPE, CFE, SGX, OSE, HKFE, Montreal/CDE, Euronext —
   IBKR's live pricing tables were not machine-readable for this note. Pull current figures from the
   [IBKR Canada Market Data Pricing](https://www.interactivebrokers.ca/en/pricing/market-data-pricing.php) page in CAD.
3. **Per-product residency footnotes** for SGX / OSE / HKFE / SNFE / Euronext venues — verify each candidate
   instrument's footnotes; some non-US/EU products carry residency or knowledge restrictions.
4. **Exact commission-waiver thresholds per data service** (USD 5 vs 15 vs 30) — confirm which applies to each
   subscription you actually take.

---

## Sources

- IBKR TWS API — Historical Market Data: https://interactivebrokers.github.io/tws-api/historical_data.html
- IBKR TWS API — Historical Data Limitations: https://interactivebrokers.github.io/tws-api/historical_limitations.html
- IBKR TWS API — Delayed Streaming Data: https://interactivebrokers.github.io/tws-api/delayed_data.html
- IBKR TWS API — Market Data Types: https://interactivebrokers.github.io/tws-api/market_data_type.html
- IBKR Campus — Market Data Subscriptions (API): https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/
- IBKR — Market Data Pricing (LLC): https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
- IBKR Canada — Market Data Pricing: https://www.interactivebrokers.ca/en/pricing/market-data-pricing.php
- IBKR KB — Market Data Exchange/Access Fees (waiver, pro vs non-pro): https://www.ibkrguides.com/kb/en-us/market-data-exchange-access-fees.htm
- IBKR — OTC Futures on LME Metals (Canada exclusion): https://www.interactivebrokers.com/en/trading/ibkr-otc-futures-lme-metals.php
- IBKR Canada — CME Futures: https://www.interactivebrokers.ca/en/trading/cme-futures.php
- IBKR — CME Group Futures Trading (permissions): https://www.interactivebrokers.com/en/trading/cme-futures-trading.php
- IBKR Campus — Trading Overseas with IBKR (residency-based permissions): https://www.interactivebrokers.com/campus/trading-lessons/trading-overseas-with-ibkr/
- IBKR Canada — Products/Exchanges search: https://www.interactivebrokers.ca/en/trading/products-exchanges.php
- IBKR Canada — HKFE fees: https://www.interactivebrokers.ca/en/accounts/fees/HKFE.php
- IBKR — CFE (Cboe Futures) fees: https://www.interactivebrokers.com/en/accounts/fees/CBOE.php
- Deutsche Börse — Eurex Retail/Core market data (~EUR 1/mo non-pro): https://www.mds.deutsche-boerse.com/mds-en/real-time-data/derivatives-markets/Eurex-Retail-Europe-1339980
- CIRO/IIROC — Interactive Brokers Canada Inc. dealer page: https://www.iiroc.ca/investors/choosing-investment-advisor/dealers-we-regulate/interactive-brokers-canada-inc
- OSC — Interactive Brokers Canada Inc. decision: https://www.osc.ca/en/securities-law/orders-rulings-decisions/interactive-brokers-canada-inc-2

*Research note compiled 2026-06-30. Market-data offerings change — confirm all prices and per-product availability
directly with Interactive Brokers Canada before relying on them.*
