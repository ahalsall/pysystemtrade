# Canada Tax & Brokerage Situation for a Systematic Futures Trader

> **DISCLAIMER — THIS IS GENERAL RESEARCH, NOT PROFESSIONAL TAX ADVICE.**
> Nothing in this document is tax, legal, accounting, or investment advice. Tax rules
> change, depend on individual facts, and are interpreted case-by-case by the CRA and the
> courts. **You must engage a qualified Canadian accountant / tax professional (CPA),
> ideally one familiar with derivatives trading, to confirm anything here before acting on
> it.** Several CRA primary-source pages could not be fetched directly during research
> (they returned HTTP 403 to automated tools); quotations from CRA bulletins were taken
> from search-engine excerpts and corroborated against reputable tax-firm sources, but
> exact paragraph numbers should be confirmed against the live CRA pages.

*Audience: an individual resident in Canada, ~CAD 150k capital, wanting to run a
Rob-Carver-style systematic futures strategy via Interactive Brokers. Researched June 2026.*

---

## 0. Executive summary

- A Canadian individual's futures gains/losses are taxed either as **capital gains
  (50% inclusion)** or as **business/income (100% inclusion)** depending on the facts; an
  active systematic trader is at real risk of being treated as **carrying on a business
  (100% taxable)**.
- CRA bulletin **IT-346R** gives a "speculator" an administrative concession to report on
  **either capital OR income account, provided it is done consistently year to year** — but
  this is *not* the s.39(4) "Canadian securities" election, which **excludes** commodity
  futures.
- **Futures cannot be held in RRSP/TFSA** (not "qualified investments"; risk of loss can
  exceed cost), and Canadian brokers (including IB Canada) **do not allow futures in
  registered accounts**. The only registered-account route to futures *exposure* is a
  listed futures-based **ETF**.
- **There is no Canadian equivalent of UK tax-free spread betting.** The central UK retail
  edge that Rob Carver exploits for smaller accounts simply does not exist in Canada. A
  Canadian must trade real futures in a **taxable non-registered account**.
- Interactive Brokers serves Canadians through **Interactive Brokers Canada Inc.**,
  regulated by **CIRO**, with **CIPF** coverage (CAD 1M/category, and CIPF *does* cover
  futures — unlike US SIPC). It issues Canadian slips (**T5008**, T5, Quebec RL-18).
- You must report to the CRA **in CAD** regardless of IB base currency. The IB base
  currency setting is a **statement/margin convenience only — it changes nothing for tax.**
- Recommendation leaning: **CAD base currency for readability, but hold USD cash balances**
  to fund USD-settled futures and convert deliberately via cheap IDEALPRO spot FX.

---

## 1. How are futures gains/losses taxed for an individual?

### 1.1 Capital vs. business/income, and the inclusion rate

The CRA treats futures gains/losses as **either** capital (50% included in income) **or**
business/income (100% included, taxed at marginal rates). Casual/infrequent traders
typically land on capital account; frequent, active, business-like traders are often
treated as earning **business income**
([Wealthsimple](https://www.wealthsimple.com/en-ca/learn/futures-trading-tax-canada);
[TaxTips.ca](https://www.taxtips.ca/personaltax/investing/taxtreatment/futures-contracts-and-commodities-futures.htm)).

**Inclusion rate — current status (important):** The longstanding **50% capital gains
inclusion rate remains in effect.** The proposed increase to **66.67% (two-thirds) on
gains above $250k for individuals** was first **deferred** from June 25, 2024 to January 1,
2026
([Dept. of Finance, Jan 2025](https://www.canada.ca/en/department-finance/news/2025/01/government-of-canada-announces-deferral-in-implementation-of-change-to-capital-gains-inclusion-rate.html)),
and then **cancelled outright on March 21, 2025**; it was never enacted into law, so 50%
still applies in 2026 ([Prospyr summary](https://www.prospyr.ca/blog/capital-gains-inclusion-rate-canada-2026)).

The asymmetry matters for a systematic strategy that *will* have losing years:
- **Capital account:** only 50% of gains taxed, but capital **losses** are deductible
  **only against capital gains** (carry back 3 years / forward indefinitely).
- **Income/business account:** 100% of gains taxed at marginal rate, but the **full loss**
  is deductible against **other income** in the year (Wealthsimple, above).

### 1.2 Trading frequency / intent ("badges of trade")

No single factor is decisive; the CRA weighs the whole picture. Factors pushing toward
**business/income** treatment: high **frequency** of transactions; short-term **intent**
to profit; substantial **time and expertise** devoted (research, monitoring, execution);
**organized, business-like** methods; and heavy use of **borrowed funds / leverage**
([Wealthsimple](https://www.wealthsimple.com/en-ca/learn/futures-trading-tax-canada);
[TaxTool.ca](https://taxtool.ca/tax-implications-of-derivatives-and-futures-trading/)). A
leveraged, frequently-rebalanced systematic futures program ticks several of these boxes,
so income/business classification is a genuine risk.

### 1.3 CRA Interpretation Bulletin IT-346R "Commodity Futures and Certain Commodities"

IT-346R is the key bulletin
([canada.ca, archived](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it346r/archived-commodity-futures-certain-commodities.html)).
Its substance (per retrieved verbatim excerpts):

- A **"speculator"** is a taxpayer who trades futures/commodities **other than** in the
  business/insider/hedging circumstances of paragraphs 3–5 of the bulletin.
- **General concession (key point):** "it is acceptable for speculators to report **all**
  their gains and losses from transactions in commodity futures or in commodities as
  **capital gains and losses ... provided such reporting is followed consistently from year
  to year**."
- **Income alternative:** a speculator who "**prefers to use the income treatment** ... may
  [do so] **provided this reporting practice is followed consistently from year to year**."
- **Limitation:** it is ultimately a **question of fact**; a taxpayer who **carries on a
  business** of trading futures is **not** a "speculator," and must report on **income
  account** regardless of whether trading is a primary or secondary occupation.

So an individual *speculator* may indeed elect (informally) to report on **either** capital
or income account — but the concession evaporates if the activity rises to "carrying on a
business."

### 1.4 The s.39(4) election — and why it does NOT cover futures

Subsection **39(4)** of the *Income Tax Act* lets a taxpayer elect (form **T123**) that
every **"Canadian security"** they own is deemed capital property, locking in capital
treatment ([ITA s.39](https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-39.html);
[T123](https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t123.html)).

**Critical: the 39(4) election does NOT extend to commodity futures or commodities.** A
"Canadian security" is defined as shares of resident corporations, mutual-fund-trust units,
and bonds/debentures/notes — commodities and futures fall outside that definition
([CRA IT-479R "Transactions in Securities"](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html);
[CRA technical interpretation 2009-0321871E5](https://taxinterpretations.com/cra/severed-letters/2009-0321871E5)).

**Consequence:** for futures there is **no T123-style statutory election**. The only
mechanism is the **IT-346R administrative practice** — pick capital OR income and apply it
**consistently**. (You can hold *securities* on capital account via 39(4) while reporting
*futures* under IT-346R; the two regimes are separate.)

### 1.5 Superficial loss rule; realized vs. mark-to-market

- **Superficial loss ("30-day rule"):** a loss is denied if you (re)acquire identical or
  substantially identical property within 30 days before/after the disposition and still
  hold it at day 30; the denied loss is added to the ACB of the reacquired property
  (deferred, not lost)
  ([TaxPage](https://taxpage.com/articles-and-tips/superficial-loss-rules/);
  [Sun Life](https://www.sunlifeglobalinvestments.com/en/insights/investor-education/tax-and-estate-planning/the-superficial-loss-rules-have-you-tripped-the-wire/)).
  This is a **capital-account** rule, so it is only relevant when futures are reported on
  capital account; under income/business treatment losses are ordinary business losses
  (Wealthsimple, above).
- **Realized vs. mark-to-market:** for **individuals**, taxation is generally on a
  **realized basis** (gain/loss when the position closes/settles), **not** statutory
  mark-to-market (which is a financial-institution / trader-election regime, not the default
  for individual speculators). Broker daily margin/variation cash flows are a
  settlement mechanism and do not by themselves create taxable events for a realized-basis
  individual (Wealthsimple, above). *Confidence note:* this is well-supported by secondary
  sources but I could not pin it to a single fetchable CRA page — confirm with your CPA, as
  active futures traders sometimes account on a position-by-position realized basis that in
  practice resembles annual mark-to-market because most positions are rolled/closed yearly.

---

## 2. Futures / derivatives in REGISTERED accounts (RRSP, TFSA)

### 2.1 Qualified-investment rules — outright futures are NOT qualified

The governing law is CRA **Income Tax Folio S3-F10-C1, "Qualified Investments"**,
interpreting ITA s.204
([canada.ca](https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-3-property-investments-savings-plans/series-3-property-investments-savings-plan-folio-10-registered-plans-individuals/income-tax-folio-s3-f10-c1-qualified-investments-rrsps-resps-rrifs-rdsps-tfsas.html)).

- **Outright futures contracts are NOT qualified investments.** The s.204 definition covers
  securities listed on a designated stock exchange **"other than a futures contract or
  other derivative instrument in respect of which the holder's risk of loss may exceed the
  holder's cost"** — and a futures position can lose more than amounts paid, so it is
  excluded ([TaxTips.ca summary](https://www.taxtips.ca/rrsp/qualified-investments-rrsp-rrif-resp-rdsp-tfsa.htm)).
- **Long listed options DO qualify** if the underlying is itself a qualified investment
  (e.g., a protective/long put or long index option), because the holder's loss is capped
  at the premium paid. **Naked/written options and futures fail** the
  "risk-of-loss-may-exceed-cost" test (TaxTips.ca, above).

### 2.2 Practical broker restrictions (incl. IB Canada)

Even setting aside the law, major Canadian brokers do not permit outright futures in
registered accounts. Per **Interactive Brokers Canada's RSP/TFSA documentation**
([IB Canada](https://www.interactivebrokers.ca/en/accounts/rsp_tfsa_information.php);
[IB Traders' Insight](https://www.interactivebrokers.com/campus/traders-insight/securities/options/options-as-part-of-an-rrsp-tfsa-strategy/)):

- **No futures trading** in IB Canada RRSP/TFSA accounts.
- Options limited to **long/covered** strategies (e.g., protective puts, long index
  puts/calls); no naked writing.
- **Cash only — no margin/borrowing** (you cannot borrow inside a registered plan;
  leverage would breach plan rules / create an "advantage"). Same picture at other Canadian
  brokers (e.g., [Questrade](https://www.questrade.com/learning/tfsa-options-trading)).

### 2.3 The work-around: futures-based ETFs

You can get futures *exposure* in a registered account by holding a **listed futures-based
ETF**. At the unitholder level you own a listed security (limited-loss equity), not the
futures themselves, so the "risk-of-loss" exclusion doesn't bite, and an ETF on a
**designated stock exchange** is a qualified investment (TaxTips.ca, above).
**Caveats:** eligibility depends on the ETF being listed on a *designated* exchange; some
US-listed commodity/futures ETFs are structured as partnerships/grantor trusts with their
own tax and withholding wrinkles — verify the specific product
([futures-based ETF universe](https://etfdb.com/etfs/commodity-exposure/futures-based/)).

### 2.4 Implications, and the "carrying on a business in a TFSA" trap

- **Pros:** tax-sheltered growth (TFSA fully tax-free; RRSP tax-deferred).
- **Cons:** **losses inside a registered plan are NOT deductible** outside it (a real
  drawback for volatile derivative strategies); **no leverage**; size capped by
  contribution limits ([TFSA guide RC4466](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4466/tax-free-savings-account-tfsa-guide-individuals.html)).
- **TFSA day-trading risk:** under ITA s.146.2(6) a TFSA that **"carries on a business"**
  is **taxable** on that business income. In **_Ahamed v. The King_, 2023 TCC 17**, an
  adviser who grew a TFSA from ~$15k to ~$550k by frequent speculative trading was found to
  be carrying on a business and taxed; the decision was upheld on appeal
  ([Canadian Tax Foundation](https://www.ctf.ca/EN/EN/Newsletters/Canadian_Tax_Focus/2023/2/230203.aspx);
  [Globe and Mail](https://www.theglobeandmail.com/business/article-day-trading-tfsa-income-taxable/);
  [Jamie Golombek](https://www.jamiegolombek.com/articledetail.php?article_id=2126)).
  *(Exact Federal Court of Appeal citation reported but not independently fetched.)*
- **Key asymmetry:** an **RRSP is sheltered even from business income**, but a **TFSA is
  not** — so active/speculative trading is *more dangerous in a TFSA than an RRSP*. (See
  also Folio [S3-F10-C3 "Advantages"](https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-3-property-investments-savings-plans/series-3-property-investments-savings-plan-folio-10-registered-plans-individuals/income-tax-folio-s3-f10-c3-advantages-rrsps-rrifs-tfsas.html).)

---

## 3. Interactive Brokers Canada specifics

- **Legal entity:** **Interactive Brokers Canada Inc.** (registered office: 1800 McGill
  College Ave, Suite 2106, Montreal, QC), an **order-execution-only** dealer (no advice)
  ([IB Canada — About](https://www.interactivebrokers.ca/en/general/about/aboutCA.php);
  [CIRO dealer registry](https://www.ciro.ca/investors/choosing-investment-advisor/dealers-we-regulate/interactive-brokers-canada-inc)).
- **Regulator: CIRO** (Canadian Investment Regulatory Organization, formed 2023 by merging
  IIROC + MFDA; older IB docs still say "IIROC"). IB Canada is a CIRO-regulated dealer
  ([CIRO](https://www.ciro.ca/investors/choosing-investment-advisor/dealers-we-regulate/interactive-brokers-canada-inc)).
- **CIPF coverage:** IB Canada clients are covered by the **Canadian Investor Protection
  Fund**, **CAD 1 million per account category** (separate $1M each for: general accounts
  incl. cash/margin/TFSA/FHSA; registered retirement accounts; and RESPs). CIPF replaces
  *missing* property (cash, securities, **and futures contracts**) on member insolvency —
  **not** market losses
  ([CIPF coverage](https://www.cipf.ca/cipf-coverage/about-cipf-coverage);
  [CIPF member directory](https://www.cipf.ca/member-directory/current-cipf-members);
  [IB Canada protection](https://www.interactivebrokers.ca/en/general/security-investor-protection.php)).
  - **Differs from US SIPC:** SIPC is USD 500k/customer (USD 250k cash sub-limit) and
    **does not cover futures** (US futures rely on CFTC segregation). So a Canadian futures
    client at IB Canada has insolvency protection for futures that a US SIPC-only client
    would not. *(SIPC figures are well-known US program facts, supplied as context.)*
- **Account types for Canadians:** Individual & Joint (cash/margin), **RRSP, Spousal RRSP,
  RRIF, TFSA, FHSA** — i.e., both registered and non-registered
  ([IB Canada accounts](https://www.interactivebrokers.ca/en/accounts/individual.php)).
- **Futures permissions:** **Yes in cash/margin accounts** (CME and global futures
  exchanges); **No in registered accounts** (driven by CRA qualified-investment rules — see
  §2) ([IB Canada RSP/TFSA](https://www.interactivebrokers.ca/en/accounts/rsp_tfsa_information.php)).
- **Tax reporting:** IB Canada issues Canadian slips to residents — **T5008 (Statement of
  Securities Transactions)**, **T5** (investment income, for information), and Quebec
  **RL-18 / RL-3** ([IB Canada tax forms](https://www.interactivebrokers.ca/en/support/tax-ca-forms.php)).
  - **Futures nuance:** on the T5008, futures carry security type **"FUT"** (box 15), and
    for futures/options **box 21 (proceeds) may be negative** — the slip shows a *net
    realized result*, not a conventional proceeds figure
    ([CRA T5008 guide T4091](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4091/t5008-guide-return-securities-transactions.html)).
    Practically, the T5008 alone often won't give a ready-to-file gain/loss; you typically
    need IB's **Activity Statements** and must **compute the gain/loss yourself** and decide
    income-vs-capital treatment. *(The "compute it yourself" operational point is
    well-supported by CRA's FUT/negative-box-21 rules plus user reports rather than an
    explicit IB statement.)*

---

## 4. How this differs from Rob Carver's UK setup

### 4.1 UK spread betting is tax-free (the central difference)

For UK individuals, financial spread-bet gains are **exempt from both CGT and income tax**,
because spread betting is treated as **gambling, not investing**:
- HMRC Capital Gains Manual **CG56105**: "no assets are acquired or disposed of and no
  chargeable gains or allowable losses arise from spread betting"
  ([gov.uk CG56105](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg56105)).
- HMRC Business Income Manual **BIM22015**: the spread bettor "is not normally carrying on a
  trade ... not taxable on the profits, nor do they receive relief for their losses"
  ([gov.uk BIM22015](https://www.gov.uk/hmrc-internal-manuals/business-income-manual/bim22015)).

The flip side: **losses are not deductible**. *(Broker commentary that a full-time
professional could be taxed is widely repeated but is not firmly established HMRC practice —
HMRC has historically kept spread betting outside the tax net entirely.)*

### 4.2 ISA vs TFSA

UK **ISAs** shelter interest/dividends/gains but **cannot hold futures or spread bets** —
permitted holdings are cash, listed shares, funds, investment trusts and bonds
([gov.uk ISAs](https://www.gov.uk/individual-savings-accounts)). The Canadian **TFSA** is
analogous and **similarly cannot hold futures** (not qualified investments; §2). So
**neither** wrapper lets a retail trader run a leveraged futures system tax-sheltered — the
decisive UK advantage is the *spread-betting route*, not the ISA.

### 4.3 UK CGT (for futures held outside a wrapper)

Exchange-traded financial futures held by a UK individual are within CGT. The **annual
exempt amount was cut to £3,000** from 6 April 2024
([gov.uk AEA](https://www.gov.uk/government/publications/reducing-the-annual-exempt-amount-for-capital-gains-tax/capital-gains-tax-annual-exempt-amount));
current main CGT rates (post-30 Oct 2024 Budget) are **18% (basic band) / 24% (higher)**
([gov.uk CGT rates](https://www.gov.uk/capital-gains-tax/rates)).

### 4.4 Carver's actual approach, and what it means for a Canadian

Rob Carver is "an independent systematic futures trader"
([qoppac bio](https://qoppac.blogspot.com/p/about-me.html)) whose practical guidance is
**cost-driven with account size as the deciding variable**
([qoppac: small accounts](https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html)):
- **Smaller accounts (roughly < ~$50k) → ETFs or spread bets**; **larger accounts → real
  futures via Interactive Brokers.**
- His primary rationale is **cost** (he has noted spread betting is on the order of ~10x
  more expensive per trade than futures, but capital-efficient and low-minimum at small
  size); the tax-free status is a *secondary sweetener*, not his main reason.
  *(Exact $50k threshold and "10x" figure are approximate, drawn from blog prose/comments.)*

**KEY CONTRAST for a Canadian:** **Canada has no tax-free spread-betting equivalent.**
Financial spread betting is not legally offered to Canadian residents, and any speculative
derivative gains are **taxable**
([Wealthsimple](https://www.wealthsimple.com/en-ca/learn/futures-trading-tax-canada);
[TaxTips.ca](https://www.taxtips.ca/personaltax/investing/taxtreatment/futures-contracts-and-commodities-futures.htm)).
A Canadian replicating Carver's approach gets only the **"large account" half** of his
playbook — **real futures in a taxable non-registered account**, paying tax as capital
gains (50% inclusion) or business income (100% inclusion). The UK retail edge — *tax-free,
leveraged exposure via spread bets for smaller accounts* — **does not exist in Canada.**
(Even newer Canadian "prediction/forecast-market" products are regulated as derivatives
under CIRO and are **taxable** — no gambling-style exemption for financial speculation:
[taxlawcanada](https://taxlawcanada.com/the-complete-arbitrage-betting-canada-tax-guide-canadian-tax-implications-for-prediction-market-and-arbitrage-profits-updated-june-2026/).)

---

## 5. Currency / foreign-withholding considerations

### 5.1 You report in CAD (functional/reporting currency)

A Canadian individual must compute and report all tax results in **Canadian dollars**. CRA
**Income Tax Folio S5-F4-C1 "Income Tax Reporting Currency"** states Canadian taxpayers
determine their tax results in CAD, converting foreign amounts at the **relevant spot rate**
on the day the amount arises
([canada.ca S5-F4-C1](https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-5-international-residency/series-5-international-residency-folio-4-foreign-currency/income-tax-folio-s5-f4-c1-income-tax-reporting-currency.html)).
- **Capital transactions (ACB / proceeds):** use the **Bank of Canada rate on the
  transaction date**.
- **Income items (interest/dividends):** transaction-date rate **or** the Bank of Canada
  **annual average rate**, applied consistently
  ([TaxTips.ca](https://www.taxtips.ca/filing/reporting-foreign-transactions.htm);
  [CRA line 12100](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12100-interest-other-investment-income.html)).

**Implication:** every futures trade's realized P&L must be translated to CAD; IB's USD
statements are only a starting point.

### 5.2 FX gain/loss on USD cash — the $200 de minimis

An individual's net foreign-currency capital gain/loss is recognized only to the extent it
**exceeds CAD $200 per year**. *(Technical note: historically cited as **s.39(2)**, the
individual $200 threshold now sits in **s.39(1.1)** after 2013 amendments — substance
unchanged; [ITA s.39](https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-39.html).)*
- The gain/loss is triggered only on an **actual disposition** of the currency — converting
  USD to CAD, or using USD to buy another asset/instrument; merely holding fluctuating USD
  is not a realization
  ([CRA IT-95R](https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it95r/archived-foreign-exchange-gains-losses.html);
  [CRA 2020-0868031I7](https://taxinterpretations.com/cra/severed-letters/2020-0868031i7)).
- **Implication:** a USD futures account receiving frequent USD variation margin can
  generate many small FX dispositions; the $200 floor only shields the first $200 net/year.
  Tracking the ACB of a fluctuating USD cash pool is genuinely complex — get professional
  advice.

### 5.3 Withholding tax — generally N/A for outright futures

- **Outright futures pay no dividends or interest**, so US dividend withholding (and the
  treaty 15% rate) is **generally not applicable** to futures positions themselves.
- **US dividends (only if you also hold US equities/ETFs):** default 30%, reduced to **15%
  under the Canada–US treaty** by filing **W-8BEN**
  ([IB W-8BEN](https://www.interactivebrokers.com/campus/trading-lessons/form-w-8ben/);
  [IB tax treaties](https://www.interactivebrokers.com/campus/trading-lessons/tax-treaties/)).
- **Idle USD cash interest at IB:** US-source **portfolio interest and bank-deposit
  interest to non-resident aliens is generally exempt** from US withholding
  ([IRS Pub 515](https://www.irs.gov/publications/p515);
  [Scotia Wealth](https://enrichedthinking.scotiawealthmanagement.com/2025/06/05/new-u-s-income-tax-proposal-on-non-resident-withholding-taxes-what-canadian-investors-with-u-s-securities-need-to-know/)).
  But any interest IB pays you is still **taxable in Canada** (line 12100, in CAD).
- **W-8BEN is still required** for Canadians at IB even if trading only futures (certifies
  foreign status; valid for signing year + 3 years)
  ([IB non-US application](https://www.interactivebrokers.ca/en/support/tax-nonus-initial.php)).

---

## 6. Base currency (CAD vs USD) and cost/opportunity for a ~CAD 150k trader

### 6.1 IB base currency does NOT affect tax

IB defines base currency as the currency for **statement translation, margin determination,
and fee billing** — an accounting/reporting convenience
([IB base-currency glossary](https://www.interactivebrokers.com/campus/glossary-terms/base-currency/);
[IB FX P&L](https://www.interactivebrokers.com/en/support/tax-fxpl.php)). For non-US clients
IB reports FX P&L in your chosen base currency, but **a Canadian still reports to CRA in
CAD** under CRA rates (§5.1). **So choose base currency for readability/operations, never
for tax.**

### 6.2 FX cost mechanics

- **Manual spot FX via IDEALPRO** is very cheap: ~**0.20 basis points (0.00002), ~USD $2
  minimum** ([IB spot-currency commissions](https://www.interactivebrokers.com/en/pricing/commissions-spot-currencies.php)).
- IB's **automatic conversion** carries a larger markup (third-party guides cite on the
  order of ~0.03%), so for any non-trivial amount a deliberate IDEALPRO conversion (or
  simply holding the native currency) is cheaper
  ([guide](https://quantroutine.com/brokers/interactive-brokers-currency-conversion-guide/)).
  *(Auto-convert markup figure is approximate.)*

### 6.3 Practical recommendation

Most CME/CBOT/NYMEX/COMEX (and many foreign) futures **settle in USD** (or the contract's
native currency), so margin and daily variation flow in USD. A sensible setup for a CAD
resident with ~CAD 150k:

- **Set IB base currency to CAD for readability** (net liquidation, margin and statements
  read in CAD so you can gauge value against your CAD 150k), **but hold a USD cash balance**
  to fund USD-settled futures so variation margin accrues in USD without per-cycle
  conversions. (Base = CAD does *not* force auto-conversion of every USD flow; IB only
  auto-converts if you leave a debit/credit in a non-held currency or enable settlement in
  base.)
- **Convert deliberately in larger blocks via cheap IDEALPRO** when repatriating to CAD,
  rather than relying on auto-convert.
- **Track USD-cash ACB** for the s.39(1.1) FX gain/loss, and **file everything to the CRA in
  CAD** regardless of base setting.

**Cost/opportunity bottom line vs. the UK:** A Canadian cannot escape tax via a spread-bet
wrapper and cannot shelter futures in TFSA/RRSP. The realistic structure is a **taxable
non-registered margin account at IB Canada**, trading real futures, with the main *managed*
costs being (a) the **capital vs. income classification** (worth deciding deliberately and
applying consistently per IT-346R, with CPA input — income treatment's full-loss
deductibility can actually help in drawdown years), (b) **FX conversion** (minimize via
native-currency balances + IDEALPRO), and (c) **record-keeping** for CAD translation and
USD-cash ACB. At ~CAD 150k with a frequently-traded systematic program, **engaging a
Canadian CPA familiar with derivatives is well worth the cost.**

---

## Open / unresolved questions

1. **Capital vs. income for *this* trader:** whether a specific systematic futures program
   is "speculation" (IT-346R, electable) or "carrying on a business" (mandatory income
   account) is fact-dependent and unresolved without professional review. Frequent, leveraged
   trading leans toward business/income.
2. **Realized vs. mark-to-market detail** for an active individual futures trader is
   supported mainly by secondary sources; confirm the precise mechanics with a CPA.
3. **Specific futures-based ETFs** for registered-account exposure need product-level
   verification (designated-exchange listing; partnership/grantor-trust structures; US
   withholding).
4. **CRA primary pages (IT-346R, IT-479R, S3-F10-C1, S5-F4-C1)** were not directly fetchable
   during research (HTTP 403); quotations were corroborated via excerpts and tax-firm
   sources — confirm exact wording/paragraphs on the live CRA pages.
5. **_Ahamed_ Federal Court of Appeal citation** is reported as upheld but was not
   independently fetched.

---

## Sources

**CRA / Government of Canada**
- Dept. of Finance — capital gains inclusion rate deferral (Jan 2025): https://www.canada.ca/en/department-finance/news/2025/01/government-of-canada-announces-deferral-in-implementation-of-change-to-capital-gains-inclusion-rate.html
- IT-346R, Commodity Futures and Certain Commodities (archived): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it346r/archived-commodity-futures-certain-commodities.html
- IT-479R, Transactions in Securities (archived): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html
- Income Tax Act s.39 (Justice Canada): https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-39.html
- Form T123 (election re Canadian securities): https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t123.html
- Folio S3-F10-C1, Qualified Investments: https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-3-property-investments-savings-plans/series-3-property-investments-savings-plan-folio-10-registered-plans-individuals/income-tax-folio-s3-f10-c1-qualified-investments-rrsps-resps-rrifs-rdsps-tfsas.html
- Folio S3-F10-C3, Advantages: https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-3-property-investments-savings-plans/series-3-property-investments-savings-plan-folio-10-registered-plans-individuals/income-tax-folio-s3-f10-c3-advantages-rrsps-rrifs-tfsas.html
- TFSA Guide RC4466: https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4466/tax-free-savings-account-tfsa-guide-individuals.html
- Folio S5-F4-C1, Income Tax Reporting Currency: https://www.canada.ca/en/revenue-agency/services/tax/technical-information/income-tax/income-tax-folios-index/series-5-international-residency/series-5-international-residency-folio-4-foreign-currency/income-tax-folio-s5-f4-c1-income-tax-reporting-currency.html
- IT-95R, Foreign Exchange Gains and Losses (archived): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it95r/archived-foreign-exchange-gains-losses.html
- T5008 Guide (T4091): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4091/t5008-guide-return-securities-transactions.html
- Line 12100 (interest/investment income): https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12100-interest-other-investment-income.html

**Interactive Brokers Canada / IB**
- IB Canada — About: https://www.interactivebrokers.ca/en/general/about/aboutCA.php
- IB Canada — Security & Investor Protection: https://www.interactivebrokers.ca/en/general/security-investor-protection.php
- IB Canada — Individual accounts: https://www.interactivebrokers.ca/en/accounts/individual.php
- IB Canada — RSP/TFSA information: https://www.interactivebrokers.ca/en/accounts/rsp_tfsa_information.php
- IB Canada — Tax forms: https://www.interactivebrokers.ca/en/support/tax-ca-forms.php
- IB Canada — Non-US initial application / W-8: https://www.interactivebrokers.ca/en/support/tax-nonus-initial.php
- IB — FX P&L for tax: https://www.interactivebrokers.com/en/support/tax-fxpl.php
- IB — base-currency glossary: https://www.interactivebrokers.com/campus/glossary-terms/base-currency/
- IB — spot-currency commissions: https://www.interactivebrokers.com/en/pricing/commissions-spot-currencies.php
- IB — W-8BEN lesson: https://www.interactivebrokers.com/campus/trading-lessons/form-w-8ben/
- IB — Options in RRSP/TFSA (Traders' Insight): https://www.interactivebrokers.com/campus/traders-insight/securities/options/options-as-part-of-an-rrsp-tfsa-strategy/

**Regulators / protection funds**
- CIRO — IB Canada dealer page: https://www.ciro.ca/investors/choosing-investment-advisor/dealers-we-regulate/interactive-brokers-canada-inc
- CIPF — about coverage: https://www.cipf.ca/cipf-coverage/about-cipf-coverage
- CIPF — current members: https://www.cipf.ca/member-directory/current-cipf-members
- IRS Publication 515 (withholding on non-resident aliens): https://www.irs.gov/publications/p515

**UK (HMRC / gov.uk)**
- HMRC CG56105 (spread betting, CGT): https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg56105
- HMRC BIM22015 (betting/gambling not a trade): https://www.gov.uk/hmrc-internal-manuals/business-income-manual/bim22015
- gov.uk — ISAs: https://www.gov.uk/individual-savings-accounts
- gov.uk — CGT annual exempt amount reduction: https://www.gov.uk/government/publications/reducing-the-annual-exempt-amount-for-capital-gains-tax/capital-gains-tax-annual-exempt-amount
- gov.uk — CGT rates: https://www.gov.uk/capital-gains-tax/rates

**Rob Carver**
- About / bio: https://qoppac.blogspot.com/p/about-me.html
- Diversification and small account size: https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html

**Reputable tax/financial media & firms**
- Wealthsimple — futures trading tax in Canada: https://www.wealthsimple.com/en-ca/learn/futures-trading-tax-canada
- TaxTips.ca — futures/commodities tax treatment: https://www.taxtips.ca/personaltax/investing/taxtreatment/futures-contracts-and-commodities-futures.htm
- TaxTips.ca — qualified investments: https://www.taxtips.ca/rrsp/qualified-investments-rrsp-rrif-resp-rdsp-tfsa.htm
- TaxTips.ca — reporting foreign transactions: https://www.taxtips.ca/filing/reporting-foreign-transactions.htm
- TaxTool.ca — derivatives & futures: https://taxtool.ca/tax-implications-of-derivatives-and-futures-trading/
- Canadian Tax Foundation — TFSA carrying on business (_Ahamed_): https://www.ctf.ca/EN/EN/Newsletters/Canadian_Tax_Focus/2023/2/230203.aspx
- Globe and Mail — day-trading TFSA taxable: https://www.theglobeandmail.com/business/article-day-trading-tfsa-income-taxable/
- Jamie Golombek — TFSA business income: https://www.jamiegolombek.com/articledetail.php?article_id=2126
- TaxPage — superficial loss rules: https://taxpage.com/articles-and-tips/superficial-loss-rules/
- Sun Life — superficial loss rules: https://www.sunlifeglobalinvestments.com/en/insights/investor-education/tax-and-estate-planning/the-superficial-loss-rules-have-you-tripped-the-wire/
- Scotia Wealth — US withholding for Canadian investors: https://enrichedthinking.scotiawealthmanagement.com/2025/06/05/new-u-s-income-tax-proposal-on-non-resident-withholding-taxes-what-canadian-investors-with-u-s-securities-need-to-know/
- CRA technical interpretation 2009-0321871E5 (39(4) scope): https://taxinterpretations.com/cra/severed-letters/2009-0321871E5
- CRA technical interpretation 2020-0868031I7 (FX $200 / disposition): https://taxinterpretations.com/cra/severed-letters/2020-0868031i7
