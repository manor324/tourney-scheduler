# Scaling investigation note

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

