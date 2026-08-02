# Smart Maintenance

Smart Maintenance augments Service Manager with explainable suggestions based
on recorded warning and failure trends. It is disabled by default and never
changes a task interval, baseline, lifetime counter, or service history entry
silently.

## Evidence model

Each recommended task has an explicit list of relevant timeline event types.
Only warning and error events after the latest of these boundaries are used:

- the configured lookback window;
- the task's last service timestamp;
- the latest Smart Maintenance evidence reset.

Warnings carry weight 1 and errors carry weight 2. A suggestion is not produced
until the configured minimum number of matching events is reached. The status
then shows the exact event counts and types, confidence level, evidence list,
and maximum earlier-review percentage.

## Due-state behavior

The original usage/countdown state remains available as `base_state`,
`base_due`, and `base_progress`. Smart Maintenance computes a separate effective
progress for presentation. A task may be highlighted for earlier review, but
its configured countdowns and baseline values remain unchanged.

## Controls

Users may configure:

- enabled or disabled;
- lookback period, 1–3,650 days;
- evidence threshold, 1–20 matching events;
- maximum earlier-review adjustment, 0–50 percent.

Resetting evidence requires typing `RESET SMART ESTIMATES`. It only advances the
evidence-window timestamp; counters, tasks, intervals, baselines, and timeline
events are preserved.

## Mechanism guidance

When Klipper reports a known CoreXY, Cartesian, or Delta mechanism, the UI may
show a matching inspection-focus preset. It is guidance only and is never
automatically applied. Unknown mechanisms produce an explicit unknown state
rather than a guessed preset.
