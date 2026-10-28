# Tourney Scheduler

A constraint-based sports league scheduling engine — a scaled-down version
of the systems real leagues (NBA, MLB, IPL) use to generate season schedules.

Give it a number of teams, a season length, and a set of constraints
(max consecutive away games, road trip length, minimum rest days, etc.),
and it produces a valid, optimized schedule.


## Why this problem is hard

Scheduling N teams isn't just "pair everyone up" — it's a constraint
satisfaction problem with competing objectives: minimize travel, respect
rest requirements, keep road trips and homestands within bounds, and
balance fairness across teams. Real leagues describe searching billions
of possible schedules to find one that's both feasible and good. See
`docs/` for design notes as they're added.
