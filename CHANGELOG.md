# Changelog

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
