# Scaling investigation notes (Stage 5)

This documents what actually happened trying to scale the scheduler
past small demo sizes -- including a wrong turn and how it was caught.
Kept here because the process is arguably more instructive than a clean
success story would be.

## The milestone: IPL scale

**10 teams, 14 games each (real IPL format: two groups of five, own-group
twice, one row rival twice, everyone else once), solved in ~2-3 seconds,
with every constraint independently verified against the output (not
just trusting the solver's "success" status).** See
`src/ipl_scale_demo.py` and `tests/test_ipl_scale.py`.

## What happens past that

Pushing to NBA/NFL scale (30-32 teams) exposed a real performance wall
in the Stage 2 constraint model. A sweep at a fixed 32 teams, varying
games-per-team, found:

| Games/team | Total games | Result |
|---|---|---|
| 6  | 96  | 1.9s |
| 12 | 192 | 7.2s |
| 18 | 288 | 29.6s |
| 24 | 384 | Timeout (45s+) |

The cause: the streak-limit constraint (max consecutive home/away games)
is implemented by giving every game a **rank** within its team's season
(1st game, 2nd game, ...), computed via pairwise "does game A happen
before game B" comparisons. That's `O(k^2)` extra solver variables per
team, where `k` = games that team plays -- and the total cost across the
league is `O(teams * k^2)`. At NBA density (k ~ 76-82) this becomes tens
of thousands of variables just for streak logic, on top of everything
else, and CP-SAT stalls.

## A wrong turn worth documenting

The first fix attempt replaced the rank-based approach with a cheaper
one: instead of computing explicit game order, check a sliding window of
**calendar days** and cap how many away games fall inside it. This is
`O(k)` per team instead of `O(k^2)` -- much cheaper.

It was also **wrong**. Tested against a 32-team NFL-scale case, it
"succeeded" in 51 seconds -- but the resulting schedule had a team with
a **14-game away streak**, against a configured limit of 2. The
constraint had become vacuous.

Root cause: "consecutive away games" is a concept about **game order**
(no home game happened in between), not calendar proximity. A team's
games can legally be spaced arbitrarily far apart on the calendar (there's
nothing forcing them to be close together), so no fixed-width calendar
window can correctly detect an order-based streak in general. A first
patch attempt (sizing the window based on `min_rest_days`) only fixed
the case where games are packed as tightly as the minimum rest allows --
it still failed once games were spread out further than that, which the
solver is completely free to do.

This is why the project reverted to the rank-based approach for
correctness, despite its worse scaling -- and why the IPL-scale result
above is presented as **the actual, defensible milestone**, rather than
overclaiming NBA-scale support that doesn't hold up under verification.

## Why this matches how real systems handle it

This lines up with what's publicly known about real sports-league
scheduling systems (see main README): they don't rely on a single flat
constraint-solve for a full season at NBA/NFL scale either. Real systems
either decompose the problem (schedule at a coarser level first, then
fill in detail) or accept a good-enough feasible schedule quickly rather
than proving optimality, layering local search on top. Hitting this same
wall independently -- and being able to explain precisely why -- is a
reasonable thing to be able to talk through, even without a full fix
implemented yet.

## Ideas for actually fixing NBA-scale performance (not yet implemented)

- **Bounded-neighborhood comparisons**: only build "before" comparisons
  between games that could plausibly land near each other in the
  schedule, instead of every pair -- two games that must be far apart
  anyway can never be part of the same streak.
- **Problem decomposition**: schedule each division's internal games
  first (small, fast, independent sub-problems), then interleave
  cross-division games afterward, rather than solving all 30+ teams
  jointly in one flat CP-SAT model.
- **Two-phase relaxation**: solve a relaxed version without streak
  constraints first (fast), then repair violations with targeted local
  search rather than encoding streaks directly into the CP-SAT model.

## A second correction worth documenting: getting IPL's actual format right

The first version of the "IPL scale" milestone used a flat double
round-robin (10 teams, every pair plays twice = 18 games/team) as a
stand-in for "IPL scale." That's the right team *count*, but the wrong
*format* -- the real IPL splits 10 teams into two groups of five, and
each team plays its own group twice, one designated "row rival" in the
other group twice, and the remaining four cross-group teams once
(8 + 2 + 4 = 14 games/team, 70 total). That's a genuine pairwise
exception (like a specific rival gets extra games), not a uniform
weight based on group membership -- the same kind of team-specific
rotation flagged earlier when correcting an initial claim about NFL
scheduling. `src/ipl_format.py` implements the real rule; `src/round_robin.py`
and `src/unbalanced_schedule.py` (Stage 1/4) don't have a way to express a
single-pair exception like this, since they only support uniform weights
by group relationship. Worth remembering: "the same number of teams" is
not the same claim as "the same schedule shape" -- always check for
these exceptions when modeling a real league's actual rule, not just
its team count.
