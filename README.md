# Tourney Scheduler

A constraint-based sports league scheduling engine — a scaled-down version
of the systems real leagues (NBA, MLB, IPL) use to generate season schedules.

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
- [x] **Stage 2 — Constraint model.** Uses Google OR-Tools (CP-SAT) to
      assign each matchup a day, respecting max consecutive home/away
      games and minimum rest between games. Verified correct via tests
      that walk the resulting schedule and check every constraint holds.
- [x] **Stage 3 — Optimization pass.** Local search (simulated annealing)
      minimizes total travel distance across a season, using real NBA
      team city coordinates and great-circle (haversine) distance. Never
      breaks a Stage 2 constraint, and never leaves a schedule worse off
      than where it started.
- [x] **Stage 4 — Unbalanced schedules.** Generalizes matchup generation
      beyond flat round-robin: teams are grouped into conferences and
      divisions, and matchup count depends on relationship (division
      rivals play most, cross-conference teams play least) — the
      structural pattern real leagues actually use. Plugs directly into
      Stage 2/3 with no changes to either.
- [x] **Stage 5 — Scale to IPL size.** Verified working at real IPL
      scale and format — 10 teams in two groups of five, 14 games each
      via the actual group/row-rival rule (not a flat round-robin
      approximation) — solving in ~2-3s with every constraint
      independently checked against the actual output. Pushing further
      (NBA/NFL/MLB scale, 30+ teams at higher game density) hit a real
      performance wall — see `docs/scaling_notes.md` for the
      investigation, including a wrong turn that looked fast but
      silently broke correctness, and why IPL scale (not NBA scale) is
      the honest milestone here.

- [x] **CLI + config files.** The whole pipeline runs from one command
      and a JSON config file — no need to open source files or call
      functions directly. Supports all three matchup-generation modes
      (flat round-robin, weighted conference/division, real IPL format),
      optional travel optimization, and JSON/CSV output.

- [x] **Realistic IPL calendar.** Goes beyond Stage 5's plain "14 games
      solved somewhere in a season" and adds the real IPL broadcast
      structure: opening day is always a single evening match (ideally
      the defending champion at home), Saturdays are double-headers
      early in the season and taper to single evening games later,
      Sundays are always double-headers, weekdays never are, a team
      can't play both slots of a double-header day, and rest is
      enforced in real hours (48-72h) rather than abstract "days apart"
      — because slots aren't evenly spaced in time. Wired into the CLI
      as `ipl_calendar` mode, including a dedicated calendar-aware
      travel optimizer that never breaks these rules while minimizing
      travel distance. Solving Stage 2 is noticeably slower than the
      plain IPL milestone (60-90s+ vs 2-3s) due to the added realism —
      tried a few solver-parameter tweaks and none helped meaningfully,
      so this is left as a known, documented tradeoff rather than
      force-fixed — but every rule is independently verified against
      the actual output. See `src/ipl_calendar.py`,
      `src/ipl_calendar_scheduler.py`, `src/ipl_calendar_optimizer.py`,
      and their tests.

## Quick start (CLI)

```bash
cd src
python3 cli.py --config ../configs/example_ipl.json --output schedule.json
```

That's the whole thing — no need to touch source code. Four example
configs are provided in `configs/`, one per matchup-generation mode:

- `example_round_robin.json` — flat "everyone plays everyone" (Stage 1)
- `example_weighted.json` — conference/division weighting + travel
  optimization (Stage 4)
- `example_ipl.json` — the real IPL group/row-rival format (Stage 5)
- `example_ipl_calendar.json` — real IPL format + realistic broadcast
  calendar (opening day, double-headers, hour-based rest) — slower to
  solve (60-90s+), so raise `--time-limit` when using it

Config file fields:

```jsonc
{
  "mode": "round_robin" | "weighted" | "ipl" | "ipl_calendar",
  // mode-specific fields (see example configs above)
  "constraints": {
    "season_days": 60,
    "max_consecutive_away": 2,
    "max_consecutive_home": 3,
    "min_rest_days": 1
  },
  "optimize": true,              // run Stage 3 travel optimization
  "optimizer_iterations": 6000,
  "cities": { "Team Name": [lat, lon], ... }  // required if optimize=true
}
```

CLI flags:

```bash
python3 cli.py --config <path> --output <path> [--format json|csv] [--time-limit 60]
```

`--format` is inferred from the output file extension if omitted. If
`optimize` is true but no `cities` are given (or a team is missing from
`cities`), the CLI skips optimization with a warning instead of
crashing — Stage 2's feasible schedule is still written out. The CLI
auto-defaults `--time-limit` to 150s for `ipl_calendar` mode (60s for
everything else) if you don't pass one explicitly.

## Tech stack

- **Python** — core language
- **Google OR-Tools (CP-SAT)** — constraint satisfaction / optimization solver
- **JSON** — input config format
- **Anthropic API / Ollama** — optional natural-language-to-config translation
- **pytest**-style tests (currently plain assertions, no framework dependency yet)

## Current status

**Stage 1** — `src/round_robin.py` generates a double round-robin
schedule for any list of teams using the circle method (who plays who).

**Stage 2** — `src/constrained_scheduler.py` takes that matchup list and
assigns each game an actual day, using OR-Tools CP-SAT to enforce:
- No team plays two games on the same day
- Minimum rest days between a team's games
- Max consecutive away games (caps road trip length)
- Max consecutive home games (caps homestand length)

```bash
cd src
python3 round_robin.py            # Stage 1: who plays who
python3 constrained_scheduler.py  # Stage 2: who plays who, and when
```

Run tests:

```bash
python3 tests/test_round_robin.py
python3 tests/test_constrained_scheduler.py
```

The Stage 2 tests don't just check the solver returns *something* —
they walk the actual output schedule and verify every constraint
(rest days, streak limits, no double-booking) genuinely holds, plus
confirm the solver correctly reports infeasibility when constraints
can't possibly be satisfied.

**Stage 3** — `src/optimizer.py` takes a Stage 2 feasible schedule and
improves it using simulated annealing: repeatedly swap two games' days,
keep the swap if it reduces total travel distance (occasionally accept
a worse swap early on to avoid getting stuck), and always fall back to
the best schedule seen. `src/travel_cost.py` computes real travel
distance using great-circle (haversine) distance between team home
cities, pulled from `src/team_locations.py` (real NBA team coordinates).

Run the full pipeline end to end (Stage 1 → 2 → 3) with a before/after
travel comparison:

```bash
cd src
python3 run_full_pipeline.py
```

Run all tests:

```bash
python3 tests/test_round_robin.py
python3 tests/test_constrained_scheduler.py
python3 tests/test_optimizer.py
```

Stage 3 tests confirm: the optimizer never breaks a Stage 2 constraint,
never returns a worse schedule than it started with, never adds,
removes, or changes which teams play each other, and returns output
sorted by day (a real bug that got caught: early versions could return
schedules with days out of order after optimization, even though the
schedule itself was valid — see `test_optimizer_returns_day_sorted_output`).

**Stage 4** — `src/unbalanced_schedule.py` replaces the flat round-robin
with a weighted generator: teams have a conference and division, and
the number of games between any two teams depends on their relationship
(same division = most games, same conference/different division =
medium, cross-conference = fewest). This is the structural pattern real
leagues use — the NBA doesn't play every team the same number of times.
The output is still a plain matchup list, so Stage 2 and Stage 3 work on
it completely unchanged.

```bash
cd src
python3 unbalanced_schedule.py
```

Run all tests:

```bash
python3 tests/test_round_robin.py
python3 tests/test_constrained_scheduler.py
python3 tests/test_optimizer.py
python3 tests/test_unbalanced_schedule.py
```

The Stage 4 tests confirm matchup counts match the configured rules
exactly, and — the real point of this stage — that its output plugs
into the existing Stage 2 solver and Stage 3 optimizer with zero
changes to either, and travel distance still improves after
optimization.

**Stage 5** — `src/ipl_format.py` generates matchups using the ACTUAL
IPL format: 10 teams split into two groups of five, each team plays
its own group twice, one designated "row rival" in the other group
twice, and the remaining four cross-group teams once — 14 games per
team, 70 total, matching the real league exactly. (An earlier version
of this stage used a flat double round-robin approximation — 18
games/team — before this was caught and corrected; see
`docs/scaling_notes.md`.) `src/ipl_scale_demo.py` runs the full
pipeline on this real format and explicitly verifies every Stage 2
constraint against the actual output, not just the solver's success
flag.

```bash
cd src
python3 ipl_scale_demo.py
```

```
Teams: 10
Games per team: 14  (real IPL: 14)
Total games: 70  (real IPL: 70 in league stage)

Stage 2: feasible schedule found in 2.2s.

Verification against Stage 2 constraints:
  Max away streak observed: 2 (limit 2)
  Max home streak observed: 3 (limit 3)
  Min rest gap observed:    2 days (required >= 2)
  All constraints verified OK.

Travel distance before optimization: 176,095 km
Travel distance after optimization:  149,342 km
Improvement: 15.2%
```

Run all tests:

```bash
python3 tests/test_round_robin.py
python3 tests/test_constrained_scheduler.py
python3 tests/test_optimizer.py
python3 tests/test_unbalanced_schedule.py
python3 tests/test_ipl_scale.py
```

**CLI** — `src/cli.py` ties every stage together behind one command,
driven by a JSON config file. See "Quick start (CLI)" above for usage
and `configs/` for example configs covering all four modes, including
`ipl_calendar`.

**Realistic IPL calendar** — `src/ipl_calendar.py` builds an actual
day-of-week-aware calendar (weekday singles, weekend/early-season
double-headers, single-slot opening day), and `src/ipl_calendar_scheduler.py`
assigns real matches to it, enforcing double-header conflict rules,
hour-based rest, and the opening-day/defending-champion rule on top of
Stage 2's constraints. Wired into the CLI as `"mode": "ipl_calendar"`
(see `configs/example_ipl_calendar.json`) — no need to pass
`--time-limit` manually, the CLI defaults to 150s automatically for
this mode since it's noticeably slower than the others:

```bash
cd src
python3 cli.py --config ../configs/example_ipl_calendar.json --output schedule.json
```

```
Generated 70 matchups for 10 teams.
(no --time-limit given, defaulting to 150s for ipl_calendar mode)
Calendar: 70 days starting Saturday, 84 total slots.
Opening day will feature: Chennai Super Kings (home)
Solving with realistic calendar constraints (this typically takes 60-90+ seconds -- see module docstring) ...
Feasible schedule found in 61.7s.
Running calendar-aware travel optimization (4000 iterations) ...
Travel distance: 124,379 km -> 112,634 km (9.4% improvement)
(opening-day game was left untouched during optimization)
Wrote 70 games to schedule.json
```

`src/ipl_calendar_optimizer.py` runs Stage 3-style simulated annealing
on top of the calendar-aware schedule — but it's a dedicated
implementation, not a reuse of `optimizer.py`, because a naive reuse
would silently break calendar rules: swapping raw day values could put
a team in both slots of a double-header, ignore real-hour rest
requirements, or (worst case) bump the defending champion off the
opening slot. This version validates every swap against the full set of
calendar-aware constraints and never touches the opening-day game at all.

A tried-and-reported finding on solve time (Stage 2, not the
optimizer): a few solver parameter tweaks (more workers, portfolio
search branching, different linearization levels) were tested and none
meaningfully beat the defaults — the slowdown comes from the number of
interacting global constraints, not search strategy, so a real speedup
would need structural changes similar to what's discussed in
`docs/scaling_notes.md` for NBA-scale performance. The optimizer itself
is fast (a few seconds) regardless, since it's pure Python validity
checks rather than another CP-SAT solve.

## Natural-language to config (`nl_to_config.py`)

`src/nl_to_config.py` turns a plain-English request into a valid config
file for the CLI — e.g. `"10-team IPL season, CSK is defending champion,
keep road trips under 3 games"` becomes the same kind of JSON that
`configs/example_ipl_calendar.json` contains.

**This is a usability layer, not a scheduling algorithm.** It doesn't
touch the constraint-solving logic at all — some LLM translates English
into JSON, then that JSON gets validated against the exact same schema
`cli.py` already enforces (`config_loader.parse_config`) before writing
anything to disk. A malformed or invalid model response fails loudly
with a clear error instead of silently producing a broken or unintended
config — and this validation step doesn't care which backend produced
the JSON, which is what makes supporting two backends easy.

**Two backends:**

- **`--backend claude`** (default) — uses the Anthropic API. Requires
  `ANTHROPIC_API_KEY` (get one at console.anthropic.com).
- **`--backend ollama`** — runs entirely locally via a running
  [Ollama](https://ollama.com) server, on your own GPU. No API key, no
  cost, no external network call at all. Needs a model pulled first
  (`ollama pull qwen2.5:7b-instruct` is the default this project
  assumes — an 8GB-class GPU handles a 7B model at Q4 comfortably).
  This is a good fit for a local model: structured JSON generation
  against a schema with worked examples already in the prompt, not
  open-ended reasoning — exactly what smaller local models tend to do
  reliably.

```bash
# Claude API
export ANTHROPIC_API_KEY=sk-ant-...
cd src
python3 nl_to_config.py "10-team IPL season, CSK is defending champion" --output config.json

# Local Ollama -- no API key needed
ollama pull qwen2.5:7b-instruct
python3 nl_to_config.py "10-team IPL season, CSK is defending champion" --output config.json --backend ollama

python3 cli.py --config config.json --output schedule.json
```

**What to actually type as the description:** plain English is enough —
you don't need to know the JSON schema at all. Mention team count or
mode signals ("IPL", "conferences", "opening day"), and any constraints
you care about (rest days, road trip length, season length). A few
examples:
```
"10-team IPL season, CSK is defending champion, no more than 2 away games in a row"
"8 NBA-style teams in two conferences, minimize travel"
"Simple 6-team round robin, 3 week season"
```

**Handling missing details:** anything you don't specify gets filled in
with a documented default rather than causing an error — season length,
rest days, streak limits all fall back to sensible values (see the
"DEFAULTS" section inside `nl_to_config.py`'s `SYSTEM_PROMPT`). For
`ipl_calendar` mode specifically, if you don't name a defending
champion, the model is instructed to leave that field out entirely
rather than guess — and a separate, deterministic Python step
(`_apply_missing_field_defaults`) then picks the first team in group_a
as the default, printing a note so it's visible rather than silent:
```
Note: No defending champion specified -- defaulted to 'T1' (first team in group_a).
```
This split is intentional: prompt instructions can get dropped,
especially by smaller local models, but Python-side logic can't forget.
Anything safety-relevant to get right consistently should live in code,
not just in the prompt.

**Honest note on testing:** neither a real Anthropic API key nor a
running Ollama server was available in the environment this was built
in, so neither backend's actual network call was ever run live — no
end-to-end result from either one has actually been seen. What's tested
(`tests/test_nl_to_config.py`, 21 tests) is everything around the call:
markdown-fence cleanup, backend dispatch (confirming `--backend ollama`
really calls the Ollama path and not Claude's), the deterministic
defending-champion default (both applied directly and end-to-end
through `translate()` for both backends), and validation logic against
realistic simulated responses for all four modes — both well-formed
and deliberately broken (invalid mode name, wrong IPL group size,
non-JSON output, missing API key, Ollama unreachable, Ollama model not
pulled). The Ollama connection-error path specifically was verified
against a real (but not running) local port, not just a mock, so that
piece of error handling is confirmed to actually fire. If the real API
or Ollama response format ever drifts from what's assumed here, that's
the first thing to check — try it yourself and see how it holds up on
an actual request.

## Project structure

```
tourney-scheduler/
├── src/            # core scheduling logic + CLI (cli.py)
├── tests/          # unit tests
├── configs/        # example CLI config files (one per mode)
├── docs/           # design notes, including the scaling investigation
└── README.md
```

## Why this problem is hard

Scheduling N teams isn't just "pair everyone up" — it's a constraint
satisfaction problem with competing objectives: minimize travel, respect
rest requirements, keep road trips and homestands within bounds, and
balance fairness across teams. Real leagues describe searching billions
of possible schedules to find one that's both feasible and good. See
`docs/` for design notes as they're added.
