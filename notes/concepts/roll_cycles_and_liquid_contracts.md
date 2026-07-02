# Roll Cycles and Choosing Which (Liquid) Contract to Hold

**Scope.** Why a systematic futures trader (like us: Canada / Interactive Brokers, running a
dynamically-optimised system) does **not** always hold the calendar front month, why for
*seasonal* markets the liquid contract is a specific forward delivery month, and exactly how
`pysystemtrade` encodes and implements this via per-instrument roll parameters. Combines Rob
Carver's blog/books with the code and data in this repo.

Primary sources are preferred and cited inline. Points where the public record is thin (book
chapters not fully quotable online, or paraphrased blog fetches) are flagged as *[uncertain]*.

---

## 0. TL;DR for our situation

- We must trade **liquid** contracts. For many markets that is the front month; for **seasonal**
  markets (grains, energy, softs, some metals) the deep liquidity sits in a *specific delivery
  month*, often well forward of spot.
- `pysystemtrade` separates two ideas per instrument in
  [`data/futures/csvconfig/rollconfig.csv`](../../data/futures/csvconfig/rollconfig.csv):
  - **`HoldRollCycle`** = the months we actually hold/trade (the liquid/seasonal set).
  - **`PricedRollCycle`** = every month we can get a price for (a superset, used only to build a
    continuous price/carry series).
- Plus **`CarryOffset`** (which adjacent priced contract is the carry reference: `+1` = next,
  `-1` = previous), **`RollOffsetDays`** (when to roll vs. expiry), **`ExpiryOffset`** (nominal
  expiry day-of-month for building approximate calendars).
- For us the two highest-risk configuration errors are **(a)** an illiquid held month (bad fills,
  gappy carry) and **(b)** a physically-settled contract we fail to roll before first-notice/
  delivery. Both are controlled through `HoldRollCycle` + `RollOffsetDays`. See §5.

---

## 1. WHY we don't always hold the front month

### 1.1 Rob's four liquidity patterns
In his foundational post *Systems building - futures rolling*, Carver frames contract choice as a
liquidity problem: you cannot buy "the" gold future, only a specific delivery, and different
markets concentrate liquidity differently
([qoppac 2015-05](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html)):

1. **Annual liquidity** (e.g. gold, platinum): decent liquidity for ~a year out; you can pick a
   quarterly delivery and hold a fairly stable maturity.
2. **Extended liquidity** (STIRs like SOFR / the old Eurodollar): liquid *years* forward — you can
   deliberately sit far out on the curve (note `SOFR` has `RollOffsetDays = -1000` in our config,
   i.e. it stays years out).
3. **Seasonal commodities** (agriculture, energy): "a lot of commodity (agricultural, energy)
   contracts are strongly influenced by the season of their delivery month" — only certain
   delivery months stay liquid far out (e.g. only December crude is quoted many years ahead).
4. **Front-only markets** (e.g. US Treasuries): all liquidity is in the front IMM month; you hold
   the front and roll quarterly.

### 1.2 The specific reasons to avoid the very front contract
From the same post and Carver's books:

- **You need an adjacent contract to *measure* carry/rolldown.** "It's better then, if you can,
  not to hold the very nearest contract as it will make it more difficult to measure rolldown"
  ([qoppac 2015-05](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html)).
  If you hold the absolute front, there is no *nearer* contract, so a `-1` carry reference does
  not exist and you are forced to `+1` (see `CarryOffset` in §2/§3).
- **Front-month pathologies.** As expiry approaches, spreads widen, volume thins, and the price
  can go abnormally quiet — Carver warns that artificially low volatility hides fat tails
  ("a horrifically ugly kurtotic distribution") *[uncertain: phrasing from a blog fetch]*.
- **Delivery / first-notice risk.** For physically-settled contracts, holding into the notice
  period risks assignment of the physical. Rolling early and holding a forward month keeps us
  clear of this (critical for us — see §5.3).
- **Constant-maturity comparability.** Holding a fixed seasonal month each year keeps the point
  on the curve roughly constant, so trend/carry signals are comparable across time. Carver: "I
  want to keep roughly that maturity"
  ([qoppac 2015-05](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html)).

### 1.3 Why seasonal markets need a *forward* month specifically
Agricultural markets trade in **crop years**. The harvest-cycle delivery months carry the deepest
open interest because they are the natural hedging points for producers and merchants:

- **Corn / Wheat → December (`Z`).** December is the post-harvest "new-crop" benchmark for corn
  (and the CBOT wheat benchmark), and is the month with liquidity quoted furthest forward. In our
  config: `CORN  Z ... HKNUZ` and `WHEAT  Z ... HKNUZ` — we *hold only December*, but *price*
  across the March/May/July/Sep/Dec cycle.
- **Soybean → November (`X`).** November is the harvest / new-crop delivery for beans, the deepest
  and furthest-quoted month. Config: `SOYBEAN  X ... FHKNQUX`.
- **Crude (WTI winter) → December (`Z`).** Config: `CRUDE_W  Z ... FGHJKMNQUVXZ`; only December
  crude is liquid many years out. (Note the `CRUDE_W_mini`/`_micro` variants hold *all* months
  because the small contracts are only liquid near the front.)
- **Natural gas (`GAS_US`) → all 12 months (`FGHJKMNQUVXZ`).** Gas is seasonal too, but liquidity
  is spread across the strip; Carver notes for AFTS that holding the *second* contract reduces the
  seasonal distortion vs. the spiky front
  ([qoppac AFTS 2023-04](https://qoppac.blogspot.com/2023/04/advanced-futures-trading-strategies.html)).
- **Metals → exchange "active" months.** COMEX concentrates liquidity in specific delivery months:
  gold in Feb/Apr/Jun/Aug/Oct/Dec (`GOLD_micro  GJMQVZ`), silver in Mar/May/Jul/Sep/Dec
  (`SILVER  HKNUZ`), copper in Mar/May/Jul/Sep/Dec (`COPPER-mini HKNUZ`; the full-size `COPPER`
  holds `HNUZ`). We hold those and skip the near-dead intervening months.
- **Equity index / STIRs → quarterly IMM (`HMUZ`).** `SP500_micro`, `US2`, `EUROSTX` all hold and
  price the quarterly cycle only.

**Key seasonal subtlety:** comparing, say, old-crop July corn against new-crop December corn is
comparing across *different crop years* — not a clean carry signal. Choosing a held month plus a
same-regime `CarryOffset` keeps the carry measurement within a comparable part of the curve. See
§3.

### 1.4 The carry / roll-yield rationale for the *choice*
Carry is not only a trading signal (§3); it is also a reason to prefer one contract over another.
For a **long**, you want a delivery month that is *backwardated* vs. its neighbour (the contract
you hold is cheaper than the nearer one, so it should rally as it ages toward spot); for a
**short**, you want *contango* ([qoppac 2015-05](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html)).
The whole point of a stable held month with a measurable neighbour is that this **rolldown** can
be quantified consistently.

---

## 2. HOW `pysystemtrade` encodes it: the roll parameters

### 2.1 The five columns
`data/futures/csvconfig/rollconfig.csv` header:
```
Instrument,HoldRollCycle,RollOffsetDays,CarryOffset,PricedRollCycle,ExpiryOffset
```
Loaded into a `rollParameters` object by
[`sysdata/csv/csv_roll_parameters.py`](../../sysdata/csv/csv_roll_parameters.py)
(`csvRollParametersData.get_roll_parameters_for_instrument`).

The class is [`sysobjects/rolls.py`](../../sysobjects/rolls.py) `rollParameters`
(lines ~184-278). Its own docstrings define the fields precisely:

| Field | Code param | Meaning (from docstring) |
|---|---|---|
| `HoldRollCycle` | `hold_rollcycle` | "The rollcycle which we actually want to hold" |
| `PricedRollCycle` | `priced_rollcycle` | "The entire rollcycle for which prices are available" |
| `RollOffsetDays` | `roll_offset_day` | "The day, relative to the expiry date, when we usually roll" |
| `CarryOffset` | `carry_offset` | "The number of contracts forward or backwards we look for to define carry **in the priced roll cycle**" |
| `ExpiryOffset` | `approx_expiry_offset` | "The offset, relative to the 1st of the contract month, when an expiry date usually occurs" |

Month letters follow the standard code: F G H J K M N Q U V X Z = Jan…Dec
(handled by the `rollCycle` class, `sysobjects/rolls.py` lines ~12-181, which can
`iterate_contract_date(direction, ...)` forward/backward through a cycle string).

### 2.2 How the carry contract is derived from `CarryOffset`
In `sysobjects/rolls.py` (`contractDateWithRollParameters.carry_contract`, lines 409-415):

```python
def carry_contract(self):
    if self.roll_parameters.carry_offset == -1:
        return self.previous_priced_contract()
    elif self.roll_parameters.carry_offset == 1:
        return self.next_priced_contract()
    else:
        raise Exception("carry_offset needs to be +1 or -1")
```

So `CarryOffset` steps **one step in the *priced* cycle** (not the hold cycle):
- `-1` → the previous (nearer) priced contract. Preferred, because a nearer contract usually
  exists and is liquid. Used for the seasonal commodities: `CORN`, `WHEAT`, `SOYBEAN`, `SILVER`,
  `CRUDE_W`, `GAS_US`, `LIVECOW`, `LEANHOG`, `COFFEE`, `COCOA` all use `-1`.
- `+1` → the next (further) priced contract. Necessary when we hold the front month (no nearer
  contract exists), or by exchange convention. Used for `GOLD`/`GOLD_micro`, `COPPER`,
  `SP500_micro`, `US2`, `EUROSTX`, and most financials.

Docs confirm the intent: `-1` is "preferred", `+1` is "necessary when holding the front contract"
([docs/data.md](../../docs/data.md), roll-parameters section).

**Worked example — CORN.** `HoldRollCycle=Z`, `PricedRollCycle=HKNUZ`, `CarryOffset=-1`. We hold
December. The carry reference is the *previous priced* month = September (`U`). Carry is measured
December-vs-September corn — both new-crop, a clean comparison.

**Worked example — GOLD_micro.** `HoldRollCycle=GJMQVZ`, `PricedRollCycle=GJMQVZ`,
`CarryOffset=+1`. Holding (say) December, the carry reference is the *next priced* month =
February next year.

### 2.3 `RollOffsetDays` and `ExpiryOffset` (roll timing / approximate calendar)
- `ExpiryOffset` places the *nominal* expiry inside the month for building an **approximate**
  calendar (real expiries come from the broker in production). Docs example: Bund with
  `ExpiryOffset=6` → notional expiry the 7th ([docs/data.md](../../docs/data.md)).
- `RollOffsetDays` is how many calendar days *before* that expiry we want to roll (negative =
  before). Range is wide: `0` for markets you can hold to the wire, down to `-1000` for SOFR (stay
  years out). Seasonal commodities roll early (e.g. `CORN`/`WHEAT`/`SOYBEAN` `-60`, `SILVER`
  `-45`, `CRUDE_W` `-40`) — early enough to keep clear of first notice **and** because the deep
  liquidity is already in the next held month by then.

`desired_roll_date = contract expiry_date + timedelta(roll_offset_day)`
(`sysobjects/rolls.py`, `desired_roll_date`, ~line 417).

---

## 3. Carry as a signal AND a selection consideration

### 3.1 The carry computation chain (in code)
Carry is computed from the stitched multiple-prices series, using the PRICE and CARRY columns and
their contract labels:

1. **Raw roll** = price of held contract − price of carry contract
   ([`sysobjects/carry_data.py`](../../sysobjects/carry_data.py) `raw_futures_roll`):
   ```python
   raw_roll = self.price - self.carry          # PRICE - CARRY
   ```
2. **Roll differential** = time (in years) between the two contracts, from their `YYYYMM…`
   labels, floored to ≥1 day (`carry_data.py` `roll_differentials`, `raw_differential`):
   ```python
   return carry_contract_as_frac - price_contract_as_frac   # e.g. Sep→Dec = 0.25 yr
   ```
3. **Annualised roll** = raw roll ÷ roll differential
   ([`systems/rawdata.py`](../../systems/rawdata.py) `annualised_roll`, then
   `daily_annualised_roll` resamples to business-daily):
   ```python
   annroll = rawrollvalues / rolldiffs
   ```
4. **Raw carry** = annualised roll ÷ annualised volatility → a Sharpe-like number
   (`rawdata.py` `raw_carry`):
   ```python
   ann_stdev = vol * ROOT_BDAYS_INYEAR
   raw_carry = daily_ann_roll / ann_stdev
   ```
5. **Forecast** = EWMA-smoothed raw carry (default 90 business days), then optionally *relative*
   carry (demeaned vs. the asset-class median)
   ([`systems/provided/rules/carry.py`](../../systems/provided/rules/carry.py)):
   ```python
   smooth_carry = raw_carry.ewm(smooth_days).mean()            # carry()
   relative = smoothed_this_instrument - median_for_asset_class # relative_carry()
   ```

The `raw_carry` docstring calls it "the annualised sharpe ratio of rolldown". The 90-day smooth
matches Carver's own description: "I use a fixed smooth of 90 business days (as many futures roll
quarterly)" ([qoppac 2017-06](https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html)).

### 3.2 Sign / direction
Positive carry (held contract cheaper than the nearer carry contract → backwardation for a `-1`
offset) is a *long* signal; negative is a *short* signal. This is the same reasoning used to
*choose* the contract in §1.4 — carry is simultaneously (a) a forecast and (b) a curve-position
rationale.

### 3.3 In AFTS
*Advanced Futures Trading Strategies* devotes Strategy 10 to "basic carry" and Strategy 11 to
"combined carry and trend" *[uncertain: strategy numbers from secondary summaries, not a primary
quote]*; Part One introduces carry alongside trend, and Part Six covers "when to roll, optimal
execution, risk management"
([qoppac AFTS 2023-04](https://qoppac.blogspot.com/2023/04/advanced-futures-trading-strategies.html)).

---

## 4. Priced vs. forward vs. carry contract — the multiple/adjusted prices

### 4.1 Multiple prices (three contracts side by side)
[`sysobjects/multiple_prices.py`](../../sysobjects/multiple_prices.py), built by
[`sysinit/futures/build_multiple_prices_from_raw_data.py`](../../sysinit/futures/build_multiple_prices_from_raw_data.py).
Columns (see any file under `data/futures/multiple_prices_csv/`):

```
DATETIME, CARRY, CARRY_CONTRACT, PRICE, PRICE_CONTRACT, FORWARD, FORWARD_CONTRACT
```

- **PRICE / PRICE_CONTRACT** — the contract we currently hold (a `HoldRollCycle` month).
- **FORWARD / FORWARD_CONTRACT** — the *next* held contract we will roll into (used to compute the
  roll gap for back-adjustment).
- **CARRY / CARRY_CONTRACT** — the adjacent priced contract chosen by `CarryOffset`, used only for
  the carry rule.

Note that FORWARD steps through the **hold** cycle (next month we will hold) while CARRY steps
through the **priced** cycle by `CarryOffset` — these are different contracts in general. For a
front-holding market with `CarryOffset=+1`, FORWARD and CARRY can coincide.

### 4.2 Adjusted (back-adjusted / "Panama") prices
[`sysobjects/adjusted_prices.py`](../../sysobjects/adjusted_prices.py) `_panama_stitch`. On each
roll it shifts the entire prior history by the roll gap so the series is continuous, then appends
the new contract's prices. This embeds rolldown into the back-adjusted series (a known Panama
bias), which is *why* pysystemtrade computes percentage returns using the adjusted price divided
by the actual current-contract price, not the adjusted price alone
([docs/data.md](../../docs/data.md); [qoppac 2015-05](https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html)).

### 4.3 Data dependency chain
```
rollconfig.csv (roll parameters)
        │
        ▼
individual contract prices ──► ROLL CALENDAR  (build_roll_calendars.py)
        │                              │
        └──────────────┬──────────────┘
                       ▼
             MULTIPLE PRICES (PRICE / FORWARD / CARRY)
                       │
                       ▼
             ADJUSTED PRICES (panama stitch)
                       │
                       ▼
       trend & carry forecasts → dyn-opt positions
```

---

## 5. Building & validating roll calendars — and the sparse-data trap

### 5.1 How the calendar is generated
[`sysinit/futures/build_roll_calendars.py`](../../sysinit/futures/build_roll_calendars.py) +
[`sysobjects/roll_calendars.py`](../../sysobjects/roll_calendars.py), two stages:

1. **Approximate calendar** from roll parameters: for each held contract, ideal roll date =
   expiry (`ExpiryOffset`) + `RollOffsetDays`. The starting point is found by
   `find_earliest_held_contract_with_price_data`
   ([`sysobjects/roll_parameters_with_price_data.py`](../../sysobjects/roll_parameters_with_price_data.py)),
   which requires: contract is in the **hold** cycle, has price data, **and** its carry contract
   has price data.
2. **Adjust to actual prices**: move each ideal roll date to the nearest date where *both* current
   and next contracts have prices (searching forward and backward). If the carry contract is
   missing on that date it retries with the carry requirement dropped and warns.

Output columns: `current_contract, next_contract, carry_contract`. Calendars are validated for
**monotonicity** (dates strictly increasing) and **validity** (both current and next contracts
priced on each roll date), and are stored as human-editable CSV so you can hand-correct them
([docs/data.md](../../docs/data.md)).

### 5.2 The sparse / bad-history trap (important for us)
Because the calendar is *derived from whatever prices exist*, a poor price history can silently
produce a wrong calendar:

- If the correct held month has few/gappy prices but a **further** contract is well populated, the
  earliest-contract search or the forward/backward date search can latch onto a **too-far-forward**
  contract, or roll at the wrong time.
- Missing carry-contract prices cause the row to be rebuilt *without* carry, giving gappy or wrong
  carry later.
- These feed straight into multiple/adjusted prices and then into carry/trend forecasts and
  dyn-opt weights.

**How to correct it:** supply better/denser individual-contract prices for the *held* and *carry*
months; or hand-edit the CSV roll calendar (fix the offending `current/next/carry_contract` and
dates), re-run multiple- and adjusted-price generation, and eyeball the result. Carver's own
validation is deliberately visual: check percentage changes for outliers and plot the stitched
series to confirm it is "vaguely sensible" before committing; for short-history contracts he uses
a longer-lived related contract as a proxy
([qoppac 2021-05, adding new instruments](https://qoppac.blogspot.com/2021/05/adding-new-instruments-or-how-i-learned.html)).

### 5.3 Practical review checklist for our universe (Canada / IB)
For each instrument we intend to trade:

1. **Is the held month actually liquid at IB?** Pull IB volume/open-interest for the
   `HoldRollCycle` months. If our data source's "liquid" month differs from IB's, change
   `HoldRollCycle` (e.g. a mini/micro that is only liquid at the front should hold all months, as
   the `CRUDE_W_micro` / `COPPER-micro` configs already do).
2. **Is `CarryOffset` sane?** If we hold the front month, it must be `+1` (no nearer contract). If
   we hold a forward month, prefer `-1` to a *liquid, same-regime* neighbour. Verify the resulting
   CARRY_CONTRACT exists and is priced (check the multiple-prices CSV for gaps in the CARRY
   column).
3. **First-notice / delivery for physically-settled contracts.** *This is our biggest operational
   risk — we must never take delivery.* Confirm `RollOffsetDays` rolls us out **before** first
   notice day for physically-settled markets (grains, softs, energy, metals). The early
   `-40/-45/-60` offsets on these instruments exist precisely for this; do not shorten them for a
   physically-settled contract without checking the exchange first-notice date. Cash-settled
   markets (equity index, STIRs) are lower risk.
4. **Validate the calendar** after any change: regenerate, confirm monotonic + valid, plot the
   adjusted series, and scan percentage-change outliers.
5. **Watch the too-far-forward symptom:** if a roll calendar rolls into a contract that is several
   months further out than the intended held month, suspect sparse held-month data (§5.2), not a
   parameter you need to "fix" by changing the cycle.

### 5.4 Common pitfalls (summary)
- Illiquid held month → bad fills, wide roll spreads, noisy/gappy carry.
- Wrong `CarryOffset` (or a missing carry contract) → wrong-sign or gappy carry forecast.
- Too-short `RollOffsetDays` on a physically-settled market → first-notice / delivery risk.
- Sparse price history → auto-calendar picks the wrong (often too-far-forward) contract or wrong
  roll date; fix the data or hand-edit the CSV, don't just change the cycle.
- Treating the Panama-adjusted price as a return series → rolldown bias; use per-contract prices
  for % returns (pysystemtrade already does this).

### 5.5 Validation pass + Batch-1 results (2026-07-02)
**Process reconciliation (honest):** Rob's docs are explicit that roll-calendar building is
"careful craftsmanship, **not** suited to a batch process… run for each instrument in turn",
generate → **check (monotonic + valid)** → **manually review**. Our CSI ingest
(`csi_pipeline --instruments all`) ran it **batched with `check_before_writing=False`** — so we
applied Rob's *parameters* correctly but circumvented his *process* (batch, no checks, no review,
and we ignored his shipped calendars). That is the crux of QA task #25 for rolls.

**What we built:** `sysinit/futures/validate_roll_calendars.py` — restores the monotonic+valid
checks AND cross-checks the **held-contract sequence** against Rob's shipped calendars
(`data/futures/roll_calendars_csv/`, which he hand-crafted and, for minis, derives from main-size
contracts) via an identical daily forward-fill on both → % of overlapping days we hold the same
contract Rob does. Run: `uv run python -m sysinit.futures.validate_roll_calendars --instruments all`.

**Batch-1 result (35 instruments): 27 clean (match Rob 91–100%), 8 flagged:**
- **Broken:** `SOYMEAL`, `SOYOIL` → **not monotonic** (rebuild/hand-edit). `GAS_US_mini` → 3% /
  14 rolls (thin-contract break — §5.2; fix = source deep history from **main-size** `GAS_US`,
  which is Rob's own method per docs/data.md "mini prices calculated from main-size contracts").
- **Diverge from Rob (valid+monotonic but different held month):** `RICE` 23%, `KOSPI_mini` 31%,
  `LEANHOG` 34%, `LIVECOW` 49% — seasonal ags where our data-driven roll lands on different
  contracts than Rob. Needs the craftsmanship review (and is where re-reading AFTS Part Six / the
  seasonal delivery-month discussion would confirm intent). `GOLD_micro` 80% borderline.
- The 91–100% matches are strong validation that the generator + `rollconfig` params are correct.

**General rule confirmed:** research/backtest deep history should come from the **most-liquid
(usually main-size) contract**; the live book trades the capital-efficient mini/micro — same
underlying → identical Panama price series, only the multiplier (in config) differs.

**Still open (per §5.3):** first-notice/delivery timing audit for physically-settled names; fix
the 8 flagged; then re-validate. Do NOT batch the fixes — per-instrument.

---

## 6. Source list (Rob Carver blog posts, books, and repo code/docs)

**Blog posts (qoppac.blogspot.com)**
- *Systems building - futures rolling* (the core reference for hold vs. priced cycle, carry
  offset, roll timing, panama, and seasonal contract choice) —
  https://qoppac.blogspot.com/2015/05/systems-building-futures-rolling.html
- *Some more trading rules* (carry rule, 90-day smooth) —
  https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html
- *Adding new instruments…* (practical config + validation + proxy-for-sparse-history) —
  https://qoppac.blogspot.com/2021/05/adding-new-instruments-or-how-i-learned.html
- *Advanced Futures Trading Strategies* (book overview: carry/trend, roll section in Part Six) —
  https://qoppac.blogspot.com/2023/04/advanced-futures-trading-strategies.html
- *Simulating my futures system* / *System building - data capture* (rolldown, back-adjustment
  context) — https://qoppac.blogspot.com/2015/03/simulating-my-futures-system.html ,
  https://qoppac.blogspot.com/2015/04/system-building-data-capture.html
- pysystemtrade landing page — https://qoppac.blogspot.com/p/pysystemtrade.html

**Books (Robert Carver)** — as reflected in the public posts above:
- *Systematic Trading* — carry & EWMAC rule definitions (the carry-vs-vol Sharpe formulation).
- *Leveraged Trading* — introductory carry/trend for retail futures. *[uncertain: not separately
  quotable online]*
- *Advanced Futures Trading Strategies* — Strategy 10 basic carry, Strategy 11 combined
  carry+trend, seasonality of commodity delivery months, and Part Six on rolling/execution.
  *[strategy numbers uncertain — from secondary summaries]*

**pysystemtrade code & docs (this repo, absolute paths)**
- `/home/andrew/pysystemtrade/data/futures/csvconfig/rollconfig.csv` — per-instrument roll params.
- `/home/andrew/pysystemtrade/sysobjects/rolls.py` — `rollParameters`, `rollCycle`,
  `contractDateWithRollParameters.carry_contract` (offset ±1), `desired_roll_date`.
- `/home/andrew/pysystemtrade/sysdata/csv/csv_roll_parameters.py` — CSV loader.
- `/home/andrew/pysystemtrade/sysobjects/roll_parameters_with_price_data.py` —
  `find_earliest_held_contract_with_price_data`.
- `/home/andrew/pysystemtrade/sysinit/futures/build_roll_calendars.py`,
  `/home/andrew/pysystemtrade/sysobjects/roll_calendars.py` — calendar generation/validation.
- `/home/andrew/pysystemtrade/sysobjects/multiple_prices.py`,
  `/home/andrew/pysystemtrade/sysinit/futures/build_multiple_prices_from_raw_data.py` —
  PRICE/FORWARD/CARRY stitching.
- `/home/andrew/pysystemtrade/sysobjects/adjusted_prices.py` — `_panama_stitch`.
- `/home/andrew/pysystemtrade/sysobjects/carry_data.py`,
  `/home/andrew/pysystemtrade/systems/rawdata.py` (`raw_futures_roll`, `annualised_roll`,
  `daily_annualised_roll`, `raw_carry`), `/home/andrew/pysystemtrade/systems/provided/rules/carry.py`
  (`carry`, `relative_carry`) — carry computation and forecast.
- `/home/andrew/pysystemtrade/docs/data.md` — roll parameters, roll calendars, multiple &
  adjusted prices (also on GitHub:
  https://github.com/robcarver17/pysystemtrade/blob/master/docs/data.md ).
