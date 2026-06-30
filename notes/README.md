# notes/

Reference roadmaps for building backtests and going to production on pysystemtrade,
compiled from the project docs + codebase. Background for implementing AFTS Strategy 17
with Strategy 25 dynamic optimization against our Barchart price database.

- **[SESSION_HANDOFF.md](SESSION_HANDOFF.md) — START HERE: full project state, what's done, what's pending, how to resume from a fresh session.**
- [backtest_roadmap.md](backtest_roadmap.md) — build/run a backtest: System, stages, config, trading rules, estimated vs fixed, AFTS replication.
- [strategy17_dynopt_repo_map.md](strategy17_dynopt_repo_map.md) — what's already in the repo for trend+carry and dynamic optimization; `rob_system` is the AFTS template; implementation plan for S17.
- [production_ib_roadmap.md](production_ib_roadmap.md) — taking a strategy live via Interactive Brokers
- concepts/ — conceptual knowledge base:
  - [concepts/portfolio_and_dynopt.md](concepts/portfolio_and_dynopt.md) — portfolio construction, vol targeting, IDM/FDM, dynamic optimization (Mr Greedy), mapped to rob_system config.
  - [concepts/canada_tax_brokerage.md](concepts/canada_tax_brokerage.md) — Canada futures tax & IB brokerage vs UK (capital vs income, registered accounts, CIPF covers futures, CAD-base recommendation). NOT tax advice — confirm with a CPA.
  - [concepts/rob_system_allocation.md](concepts/rob_system_allocation.md) — rob_system's actual strategy allocation (by family/rule) + realized Sharpe per rule from his Trading_rule_p&l report; allocation-vs-performance cross-check.
  - [concepts/ib_canada_instruments_and_data.md](concepts/ib_canada_instruments_and_data.md) — which exchanges IB Canada can trade (LME blocked), and market-data subscriptions (develop free off Barchart; stream only at go-live; US bundle + Eurex, mostly commission-waived).
  - [concepts/ib_historical_depth.md](concepts/ib_historical_depth.md) — measured IB futures history (~3-4yr continuous, no expired contracts, current front month); IB bootstraps usable full coverage now, barchart for depth.
  - [concepts/rob_reports.md](concepts/rob_reports.md) — Rob's public repos + his `reports` production diagnostics; static instrument selection by capital; the micros-not-in-bc-utils tension.
  - [concepts/costs_and_capital.md](concepts/costs_and_capital.md) — minimum capital per contract (why micros matter), the SR-cost screen (24 of our 224 too expensive), and how dynamic opt helps.: IB Gateway/ib_async, production processes, order stacks, dynamic-opt in production, go-live checklist.
