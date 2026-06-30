# notes/

Reference roadmaps for building backtests and going to production on pysystemtrade,
compiled from the project docs + codebase. Background for implementing AFTS Strategy 17
with Strategy 25 dynamic optimization against our Barchart price database.

- **[SESSION_HANDOFF.md](SESSION_HANDOFF.md) — START HERE: full project state, what's done, what's pending, how to resume from a fresh session.**
- [backtest_roadmap.md](backtest_roadmap.md) — build/run a backtest: System, stages, config, trading rules, estimated vs fixed, AFTS replication.
- [strategy17_dynopt_repo_map.md](strategy17_dynopt_repo_map.md) — what's already in the repo for trend+carry and dynamic optimization; `rob_system` is the AFTS template; implementation plan for S17.
- [production_ib_roadmap.md](production_ib_roadmap.md) — taking a strategy live via Interactive Brokers: IB Gateway/ib_async, production processes, order stacks, dynamic-opt in production, go-live checklist.
