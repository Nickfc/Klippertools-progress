# Changelog

## 0.4.0 - 2026-08-02

- Added Thermal Soak Assistant as a separate movable dashboard card and a
  full-width tool in the Klippertools view.
- Added automatic Klipper temperature-sensor discovery, live heating and
  stabilizing progress, regression slope, observed range, elapsed time, and
  remaining-time estimates.
- Added conservative full-window stability validation: temperature proximity,
  drift, and oscillation must all remain inside their configured limits.
- Added non-blocking monitoring and an optional blocking `THERMAL_SOAK_WAIT`
  macro command with explicit cancellation and a hard timeout.
- Added safe v0.2/v0.3 migration logic that preserves existing user tuning and
  Service Manager history while installing the sixth Klipper extra.
- Built and linted the native UI against Mainsail v2.17.0 and v2.18.2.

## 0.3.0 - 2026-08-02

- Replaced the calendar-style Maintenance Tracker with a durable usage-based
  Service Manager and a dedicated Mainsail sidebar view.
- Added lifetime counters for print time, filament, prints, commanded XY/Z
  travel, hotend/bed heater time, probe touches, and calendar age.
- Added ten editable Ender 7 recommended service presets, custom tasks,
  multi-threshold "first one wins" countdowns, overdue values, estimated due
  dates, service instructions, history, import/export, and reset controls.
- Added idle-only reminders with mark-serviced and two snooze choices.
- Added a boot-local Klipper metric collector reconciled into an atomic
  Moonraker data file with bounded writes and power-safe replacement.
- Added a v0.2.1 migration that preserves user tuning while enabling the new
  collector, preserves newly encountered pre-existing extras for uninstall,
  and retains Service Manager data during normal uninstall.
- Built and linted the native UI against Mainsail v2.17.0 and v2.18.2.

## 0.2.1 - 2026-08-01

- Split Probe Progress, UI Core, Nozzle Guard, StartFlow, Maintenance Tracker,
  and Motion Wizard into independent movable Mainsail dashboard cards.
- Refined the UI with a bed-shaped probing matrix, X/Y orientation, a state
  legend, clearer status hierarchy, and consistent responsive tool cards.
- Added an authenticated Update button to the Klippertools Mainsail panel.
- Added a Moonraker update controller that refuses updates while printing or
  paused and launches commands without a shell.
- Added a verified online updater that stages a fresh checkout before replacing
  any installed files or the active source checkout.
- Replaced transient shell rollback with an fsynced transaction journal and a
  stable recovery helper under `~/printer_data/klippertools-recovery/`.
- Added printer-idle enforcement to install, update, recovery, and uninstall;
  `--offline` is an explicit manual override when Moonraker is unavailable.
- Fixed printer.cfg removal so unrelated blank lines are preserved byte for
  byte, using explicit ownership markers and the original backup when safe.
- Expanded `check-install.sh` to validate content hashes, Python syntax,
  Moonraker wiring, transaction state, and the complete deployed Mainsail file
  manifest instead of checking only for file existence.
- Uninstall now archives the source checkout as well, allowing a clean online
  reinstall while retaining recovery material.
- Added corruption, normal update, print interlock, and simulated power-loss
  recovery tests for install, update, and uninstall.

## 0.2.0 - 2026-08-01

- Add the shared tabbed Klippertools UI Core below Probe Progress.
- Add Nozzle Guard with automatic G-code inspection, confirmed-mismatch
  blocking, warning mode, and one-file override.
- Add StartFlow stage tracking, ETA learning, conservative PRINT_START
  instrumentation, and exact marker removal.
- Add a Maintenance Tracker dashboard backed by Mainsail's existing Moonraker
  maintenance records and print totals.
- Add Motion Wizard for attended noise testing, X/Y shaper calibration,
  result review, and separately confirmed SAVE_CONFIG.
- Expand backend coverage to 33 tests and add two-version transactional
  install/check/uninstall tests.
- Rename release builds, configuration, state, backups, and online-install
  defaults from Probe Progress to the Klippertools Suite.

## 0.1.0 - 2026-08-01

- Add automatic Bed Mesh path discovery.
- Add red, pulsing-yellow, and green top-down matrix states.
- Track multi-sample probing, tolerance retries, faulty-region substitutes,
  and zero-reference positions.
- Add a countdown ETA seeded from the first three completed logical points.
- Add a native Mainsail dashboard card placed directly under Console.
- Add English and Danish interface text.
- Add builds and source patches for Mainsail v2.17.0 and v2.18.2.
- Add a transactional installer, install checker, and reversible uninstaller.
- Add a checksum-verified GitHub bootstrap installer and CI validation.
