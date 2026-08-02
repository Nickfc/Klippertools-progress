# Service Manager

Klippertools 0.3.0 and later track maintenance from actual printer usage rather than
only a calendar reminder. Open **Klippertools** in Mainsail's left navigation
to see lifetime counters, the service schedule, history, presets, and data
controls.

## Counters

- Print time and filament are accumulated from Klipper `print_stats` while a
  job runs and reconciled again when it finishes.
- Prints counts newly started jobs.
- XY and Z are commanded toolhead travel measured inside Klipper. They are not
  encoder feedback and cannot prove that a mechanism physically moved.
- Hotend and bed time count while the corresponding heater has a non-zero
  target.
- Probe touches count accepted `probe:update_results` events, including samples
  and retries.
- Calendar age is calculated from the task's last-serviced timestamp.

The Moonraker component polls at five-second intervals and writes dirty data at
most every 30 seconds, plus job transitions and shutdown. Data is atomically
replaced at `~/printer_data/klippertools-service.json` with owner-only mode.

## Due logic and reminders

A task can enable several countdowns. Each is evaluated independently, and the
first to reach zero makes the task due. Progress is green below 80%, amber from
80%, and red at or beyond 100%. A due task continues into a negative overdue
value; maintenance reminders never block a print.

The dashboard opens a reminder only while the printer is idle. Actions are:

- **Mark serviced**: records history and moves every baseline for that task to
  the current lifetime counters.
- **Snooze next print**: suppresses the reminder until another print starts.
- **Snooze 24h**: suppresses the reminder for one day without changing its
  actual due state.
- **Close**: hides it for the current browser session or until the print count
  changes.

## Resets and portability

**Reset to recommended** restores the ten supplied Ender 7 starting tasks and
intervals, removes custom tasks, and preserves matching task baselines and all
history. **Reset lifetime counters** is advanced, requires the exact phrase
`RESET LIFETIME COUNTERS`, is blocked during a print, resets all task baselines,
and records the old counters in history.

Export includes tasks and service history. Import adds tasks and resolves ID
collisions; it never imports or overwrites lifetime counters. Normal uninstall
retains the service data file. Delete it manually only if the history and all
counters are intentionally no longer wanted.

The supplied intervals are conservative editable starting points, not printer
or component manufacturer requirements. Inspect sooner after a crash, unusual
noise, contamination, looseness, overheating, wiring damage, or changed print
quality.

## Smart Maintenance

Smart Maintenance is disabled by default. When enabled, each recommended task
may compare its normal countdown progress with explicitly mapped warning and
failure events from Printer Health Timeline. The status always includes the
normal `base_progress`, `base_state`, and `base_due` values separately from the
advisory result.

A suggestion states its event count, types, confidence, evidence window, and
maximum earlier-review percentage. It never rewrites the task's thresholds,
baseline, service timestamp, or lifetime counters. See
[SMART_MAINTENANCE.md](SMART_MAINTENANCE.md).
