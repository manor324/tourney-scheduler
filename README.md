# Tourney Scheduler

A constraint-based sports league scheduling engine — a scaled-down version
of the systems real leagues (NBA, MLB) use to generate season schedules.

Give it a number of teams, a season length, and a set of constraints
(max consecutive away games, road trip length, minimum rest days, etc.),
and it produces a valid, optimized schedule.

This mirrors the real-world approach used by companies like Fastbreak AI
(built by ex-NBA schedule engineers) and KPMG's league scheduling systems:
generate a feasible schedule with constraint programming, then refine it
with local search optimization.

## Project stages

- [x] **Stage 1 — Round-robin generator.** Circle-method algorithm that
      generates a valid "everyone plays everyone" schedule skeleton
      (home-and-away, no team plays itself, balanced pairings).
- [ ] **Stage 2 — Constraint model.** Use Google OR-Tools (CP-SAT) to
      layer in real scheduling rules: max consecutive home/away games,
      road trip length bounds, minimum rest between games.
- [ ] **Stage 3 — Optimization pass.** Local search (simulated annealing)
      to improve a feasible schedule — minimize total travel distance,
      balance rest days across teams.
- [ ] **Stage 4 — Interface.** CLI powered by a JSON/YAML config file,
      with schedule output as JSON/CSV. Possibly a simple visualization
      later.

## Tech stack

- **Python** — core language
- **Google OR-Tools (CP-SAT)** — constraint satisfaction / optimization solver
- **JSON/YAML** — input config format
- **pytest**-style tests (currently plain assertions, no framework dependency yet)

## Current status

Stage 1 is complete: `src/round_robin.py` generates a double round-robin
schedule for any list of teams using the circle method.

```bash
python3 src/round_robin.py
```

```
Round 1:
  Heat @ Warriors
  Nets @ Lakers
  Bulls @ Celtics
...
Total games: 30
```

Run tests:

```bash
python3 tests/test_round_robin.py
```

## Project structure

```
tourney-scheduler/
├── src/            # core scheduling logic
├── tests/          # unit tests
├── configs/        # example input configs (Stage 4)
├── docs/           # design notes
└── README.md
```

## Why this problem is hard

Scheduling N teams isn't just "pair everyone up" — it's a constraint
satisfaction problem with competing objectives: minimize travel, respect
rest requirements, keep road trips and homestands within bounds, and
balance fairness across teams. Real leagues describe searching billions
of possible schedules to find one that's both feasible and good. See
`docs/` for design notes as they're added.
