# Printer Health Timeline

Printer Health Timeline is an explainable local event history. It records facts
from Klippertools, Klipper status objects, Moonraker job-state transitions, and
explicit user actions. It does not compute a vague health score.

## Recorded event categories

- print starts, completions, cancellations, and failures;
- calibration completion, timeout, cancellation, and error states;
- service and tool-registry actions;
- Nozzle Guard mismatches and inspection errors;
- configuration warnings and pending-change state;
- explicit `SAVE_CONFIG`, `RESTART`, and `FIRMWARE_RESTART` requests received
  through Moonraker;
- Klipper connection state and Klippertools updater outcomes.

Each event contains a timestamp, category, event type, summary, severity,
source, and bounded structured details. G-code contents are never stored. A
filename may be recorded for print provenance, but file contents and unrelated
printer data are not collected.

## Configuration-save accuracy

A `SAVE_CONFIG` request is recorded as a request, not as proof of successful
persistence. Likewise, if Klipper's pending-change state disappears, the
timeline records only that it is no longer pending and explicitly states that
this alone cannot distinguish save, restart, or abort.

## Persistence and retention

Timeline data is written atomically to
`~/printer_data/klippertools-timeline.json`. Default retention is 365 days and
2,000 events; the user may configure 1–3,650 days and 100–20,000 events. The
first limit reached wins. Corrupt data is preserved under a timestamped
`.corrupt-*` name before a clean state is created.

The UI supports category, exact event-type, date-window, and count filters.
Export produces a local JSON file. Clearing all events requires typing
`CLEAR HEALTH TIMELINE`.
