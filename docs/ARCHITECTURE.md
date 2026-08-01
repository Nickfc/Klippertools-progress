# Architecture

## Suite boundary

Klippertools uses four small Klipper extras, Mainsail's existing maintenance
store, and one shared native Mainsail panel. No Moonraker component or custom
network endpoint is required.

| Tool | Runtime source | Status object |
| --- | --- | --- |
| Probe Progress | `probe_progress.py` | `probe_progress` |
| Nozzle Guard | `nozzle_guard.py` | `nozzle_guard` |
| StartFlow | `start_flow.py` | `start_flow` |
| Maintenance | Mainsail/Moonraker database | `gui/maintenance` |
| Motion Wizard | `motion_wizard.py` | `motion_wizard` |

Mainsail already subscribes to every available Klipper status object. The
Klippertools UI therefore receives real-time state through the normal
`printer.objects.subscribe` connection.

## UI Core

Probe Progress remains a dedicated matrix card. The other tools share
`KlippertoolsPanel.vue`, which supplies responsive tabs, a common location under
Console, and an attention count. A confirmed blocking nozzle mismatch and each
overdue maintenance entry contribute to that count.

Dashboard injection is version matched. Existing saved dashboard layouts gain
Probe Progress and Klippertools immediately after Console without moving other
saved panels. Both cards remain available in Mainsail's dashboard editor.

## Probe Progress

After Klipper is ready, the extra observes Bed Mesh's `ProbeManager.start_probe`
call. Bed Mesh has already produced the command's real logical points, physical
probe path, counts, bounds, faulty-region substitutes, and optional zero
reference. `probe:update_results` advances sample and retry state.

A logical cell becomes complete only when every physical substitute completes
its accepted sample set. The first three logical point durations seed a fixed
deadline:

```text
seconds_per_point = duration(first three points) / 3
deadline = seed_completion_time + seconds_per_point * remaining_points
```

## Nozzle Guard

At `klippy:ready`, Nozzle Guard wraps the configured virtual SD object's private
file-load and resume methods. Load inspects at most the configured number of
bytes at both the beginning and end of the G-code. Resume is the enforcement
boundary: a confirmed mismatch in `block` mode raises a command error before
virtual SD work starts.

Missing metadata is not proof of a mismatch and therefore remains non-blocking.
An override changes state only for the currently selected file; loading another
file performs a new check.

## StartFlow

StartFlow is an explicit stage state machine. `START_FLOW_BEGIN` creates the
planned stages, each `START_FLOW_STAGE` closes the previous stage and starts the
next, and `START_FLOW_COMPLETE` closes the run. Command errors, cancellation,
and Klipper shutdown mark an active stage as failed.

The installer edits `PRINT_START` only when it finds one unambiguous M140/M190
start, G28, BED_MESH_CALIBRATE, M109, and final completion response. Every
inserted command has a paired marker. Removal refuses a marker whose paired
command was modified, preventing accidental deletion of user macro content.

Stage estimates use configurable seeds and an in-memory exponential update:

```text
new_estimate = old_estimate * (1 - learning_rate)
             + measured_duration * learning_rate
```

## Maintenance Tracker

Mainsail already stores maintenance entries in Moonraker's `maintenance`
namespace and relates them to Moonraker history totals. Klippertools reads the
same entries and opens Mainsail's existing add, edit, detail, and perform
dialogs. No data migration or parallel persistence exists.

For a task with multiple enabled thresholds, the dashboard shows the threshold
with the highest completion ratio. Any reached threshold makes the task due.

## Motion Wizard

Motion Wizard validates that the printer is idle and that XYZ are homed before
calibration. It invokes Klipper's own synchronous `MEASURE_AXES_NOISE` and
`SHAPER_CALIBRATE AXIS=...` handlers. After calibration it reads the applied
`InputShaperParams` directly and exposes the review data.

Klipper's calibration command stages configfile changes internally. The wizard
does not call `SAVE_CONFIG`; Mainsail exposes that separately behind a
confirmation dialog after both X and Y have new results.

## Installation model

The installer copies the four extras, one configuration include, a
version-matched Mainsail build, and optional StartFlow markers. Before mutation
it saves `printer.cfg`, every pre-existing managed file, and the complete
Mainsail tree. A trap restores originals after any failed operation.

Uninstall uses the recorded paths and existence flags, validates every path
under the normal user's home, reverses only recorded changes, preserves the
latest Mainsail `config.json`, and retains recovery material.

The Probe Progress and Nozzle Guard hooks use Klipper private methods because
Klipper currently exposes neither a public bed-mesh progress event nor a public
pre-resume validation hook. Both boundaries are validated against the two
listed Klipper revisions.
