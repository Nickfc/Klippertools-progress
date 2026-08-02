# Klippertools Suite

Klippertools adds a native Mainsail dashboard suite for Klipper printers. Probe
Progress, Nozzle Guard, StartFlow, Service Manager, Motion Wizard, Thermal Soak,
Calibration Center, Tool Registry, and Printer Health Timeline remain separately
movable cards, with a combined full sidebar workspace.

## Included tools

### Probe Progress

- Shows the generated bed-mesh matrix from above.
- Red means untouched, pulsing yellow means active, and green means complete.
- Tracks each logical point, every configured sample, tolerance retries,
  faulty-region substitutions, and zero-reference positions.
- Calculates a fixed countdown ETA from the first three completed points.

### Nozzle Guard

- Reads nozzle-diameter metadata from the selected G-code automatically.
- Compares it with Klipper's `[extruder] nozzle_diameter`.
- Blocks a confirmed mismatch before virtual SD printing starts by default.
- Allows files with missing or unreadable metadata, but clearly marks their
  status as unknown.
- Offers a deliberate one-file override without weakening later checks.

### StartFlow

- Shows each `PRINT_START` phase: bed heating, homing, mesh, nozzle heating,
  and purge.
- Shows completed, active, and pending stages with an estimated time remaining.
- Refines stage estimates in memory from completed startups.
- The installer instruments a compatible `PRINT_START` conservatively and can
  remove its markers exactly during uninstall.

### Calibration Center

- Orchestrates Klipper's own PID, bed-mesh, Z-offset, input-shaper, pressure-
  advance, rotation-distance, and first-layer calibration workflows.
- Shows prerequisites, current values, runtime hardware availability, and
  attended heat or motion warnings before a workflow can begin.
- Requires explicit confirmation and blocks while printing or paused.
- Never runs `SAVE_CONFIG`, `RESTART`, or `FIRMWARE_RESTART` automatically.
- Leaves permanent results pending for separate user review.

### Nozzle & Tool Registry

- Stores named nozzle/tool profiles with diameter, material, notes, optional
  temperature reference, installed/retired state, usage, and change history.
- Synchronizes the installed profile to Nozzle Guard in memory without silently
  rewriting `[extruder] nozzle_diameter`.
- Falls back to Klipper's configured nozzle if synchronization is unavailable.
- Preserves registry data atomically across normal updates and uninstall.

### Service Manager

- Adds a dedicated **Klippertools** view to Mainsail's left navigation.
- Tracks print time, filament, prints started, calendar age, commanded XY and Z
  travel, hotend and bed heater-on time, and probe touches.
- Gives every task any number of independent countdowns; the first countdown
  to reach zero makes the task due.
- Shows every remaining interval, estimated due dates, green/amber/red state,
  negative overdue values, service instructions, and a compact next-service
  list on the dashboard.
- Includes ten editable conservative starting presets for rails, Z motion,
  belts, extruder, hotend, heater wiring, probe, build plate, fans, and
  electrical connectors.
- Shows idle-only reminder dialogs with Mark serviced, Snooze next print,
  Snooze 24h, and instructions.
- Preserves service history, supports custom tasks and JSON import/export, and
  separates resetting recommended intervals from the strongly confirmed
  lifetime-counter reset.

### Printer Health Timeline

- Records explainable print, calibration, service, registry, updater,
  configuration, and warning events with exact provenance.
- Never stores G-code contents and never turns an observed state transition into
  a claim that configuration was successfully saved.
- Supports category/date filters, bounded retention, strong clear confirmation,
  and local JSON export.

### Smart Maintenance

- Is opt-in and disabled by default.
- Combines existing service countdowns with explicitly mapped warning/failure
  evidence from Printer Health Timeline.
- Shows evidence count, event types, confidence, and the exact reason for every
  earlier-review suggestion.
- Never changes intervals, baselines, counters, or service history silently.

### Motion Wizard

- Guides homing, accelerometer noise testing, and separate X/Y input-shaper
  calibration.
- Uses Klipper's own `MEASURE_AXES_NOISE` and `SHAPER_CALIBRATE` commands.
- Shows the current and newly calibrated shaper type and frequency for each
  axis.
- Keeps `SAVE_CONFIG` behind a separate review-and-confirm step.

### Thermal Soak Assistant

- Watches any Klipper temperature sensor without changing its target.
- Requires the complete configured stability window to remain within the
  temperature, slope, and observed-range limits.
- Shows live heating/stabilizing progress, drift, range, elapsed time, and ETA.
- Learns a session-local completion estimate from earlier soaks without
  writing printer configuration.
- Offers non-blocking monitoring from its own movable card and an optional
  blocking macro command with a hard timeout.

## Validated versions

- Klipper v0.13.0-660-g616242d4
- Klipper v0.13.0-708-g7046bd00
- Mainsail v2.17.0
- Mainsail v2.18.2
- Moonraker v0.10.0-29

The installer accepts only the two listed Mainsail versions because the suite
uses a version-matched native Mainsail build. Use the Klippertools Update button
for suite updates. A standalone Mainsail update replaces the custom UI and must
be followed by a matching Klippertools update from SSH.

## Your supplied printer configuration

The supplied Ender 7 configuration has all required integrations:

- one configured 0.4 mm extruder nozzle;
- virtual SD printing through Mainsail/Moonraker;
- a 7 by 7 bed mesh and three MicroProbe samples per point;
- a LIS2DW accelerometer and `[resonance_tester]`;
- saved input-shaper values of `3hump_ei` at 81.4 Hz on X and `mzv` at
  37.2 Hz on Y;
- a `PRINT_START` shape that the guarded StartFlow instrumenter supports.

A normal full mesh starts with 49 logical cells and 147 planned physical
touches. Tolerance retries add touches only when needed.

## Online install

SSH into the CB1 as the normal Klipper user, then run:

```bash
curl -fsSL https://raw.githubusercontent.com/Nickfc/Klippertools-progress/main/install-online.sh \
  -o /tmp/install-klippertools.sh
bash /tmp/install-klippertools.sh
```

The bootstrap clones the public repository into `~/klippertools`, validates
every packaged file against `SHA256SUMS`, and starts the journaled transactional
installer. It refuses root, an active or paused print, an existing installation,
a legacy Probe Progress install, or an unsupported Mainsail version before
replacing anything.

To install a tag or review branch instead of `main`:

```bash
KLIPPERTOOLS_REF=v0.8.0 bash /tmp/install-klippertools.sh
```

After installation:

1. Restart Moonraker from Mainsail's power menu or over SSH.
2. Send `RESTART` in the Mainsail console.
3. Hard-refresh the browser with Ctrl+Shift+R.
4. Confirm that Probe Progress and Klippertools appear under Console.

The installer retains complete rollback material under
`~/klippertools-backups/`. Before the first mutation it writes and fsyncs a
recovery journal outside the source checkout. It preserves `printer.cfg`,
`moonraker.conf`, previous managed Klipper and Moonraker components,
`klippertools.cfg`, the original Mainsail build, and Mainsail's current
`config.json`. Ordinary failures roll back immediately; a power interruption is
recovered with:

```bash
~/printer_data/klippertools-recovery/recover.sh
```

Recovery also verifies that the printer is idle. Use `--offline` only when
Moonraker is unavailable and you have independently confirmed no print is
active.

## One-click updates

After the first Moonraker restart, the cloud-download icon in the Klippertools
card opens the updater. **Update now** performs one guarded operation:

1. Moonraker proves the printer is neither printing nor paused.
2. A new checkout of the configured repository branch is downloaded to a
   staging directory.
3. Every release file is checked against `SHA256SUMS`.
4. Klipper, Moonraker, and the matching Mainsail build are updated under one
   persistent rollback journal; `klippertools.cfg` and Mainsail `config.json`
   are preserved.
5. The source checkout is swapped last, then Klipper and Moonraker restart.

The POST endpoint is exposed through Moonraker's authenticated API, rejects
concurrent updates, and launches the updater without a shell. If the UI is not
available, the identical path can be run over SSH:

```bash
~/klippertools/scripts/update-online.sh
```

## Manual release ZIP

Download
[`klippertools-suite-0.8.0.zip`](dist/klippertools-suite-0.8.0.zip)
(with its optional
[`SHA-256 sidecar`](dist/klippertools-suite-0.8.0.zip.sha256)), upload the ZIP
under Mainsail's Config Files, then SSH into the CB1 as the normal Klipper
user:

```bash
mkdir -p ~/klippertools
unzip -q ~/printer_data/config/klippertools-suite-0.8.0.zip -d ~/klippertools
cd ~/klippertools
sha256sum -c SHA256SUMS
./scripts/install.sh
```

Then restart Moonraker, send `RESTART`, and hard-refresh the browser as above.

## Safe first checks

### Probe Progress

Clear the bed and keep the printer attended. This central 3 by 3 mesh is inside
the safe bounds in the supplied configuration:

```gcode
G28
BED_MESH_CALIBRATE PROFILE=probe_progress_test PROBE_COUNT=3,3 MESH_MIN=90,75 MESH_MAX=150,135
```

Expected: nine red cells, one pulsing-yellow active cell, green completed cells,
sample counts from 1/3 through 3/3, and an ETA after point three. The test
profile is not written permanently unless `SAVE_CONFIG` is run separately.

### Nozzle Guard

Select a normal OrcaSlicer G-code file without starting it. The Guard tab should
show Klipper's configured nozzle and either the detected file nozzle or
`Unknown`. A proven mismatch is red and will block print start; do not use the
override merely to test the button.

Nozzle Guard looks for numeric `nozzle_diameter`, `nozzle diameter`,
`nozzle_size`, or `nozzle size` comments in the beginning and end of the file.
See [docs/NOZZLE_GUARD.md](docs/NOZZLE_GUARD.md) for modes and behavior.

### StartFlow

No physical test is needed. On the next attended print, its timeline should
advance through bed heat, homing, mesh, nozzle heat, and purge. If the installer
reported that your macro was unsupported, follow [docs/STARTFLOW.md](docs/STARTFLOW.md).

### Motion Wizard

Motion calibration deliberately makes violent movements. Clear the plate, make
sure no print is active, stay beside the printer, then follow the on-screen
steps. Review both axis results before choosing Save and restart. Full safety
details are in [docs/MOTION_WIZARD.md](docs/MOTION_WIZARD.md).

### Thermal Soak

Set the bed target normally, then start monitoring from the Thermal Soak card.
The assistant does not heat or move the printer. For an optional blocking
`PRINT_START` integration, follow [docs/THERMAL_SOAK.md](docs/THERMAL_SOAK.md).

### Calibration Center

Open the Calibration Center card while the printer is idle. Unsupported
workflows must remain visible but disabled with an exact reason. Heat and motion
workflows require explicit confirmation; stay beside the printer. Review any
pending Klipper configuration changes separately.

### Tool Registry

Create a profile without installing it first. Installing or removing a profile
is blocked while printing or paused. The Registry status must show whether
Nozzle Guard is synchronized or safely using its Klipper-configuration fallback.
See [docs/TOOL_REGISTRY.md](docs/TOOL_REGISTRY.md).

### Printer Health Timeline and Smart Maintenance

Timeline events show their exact source and can be exported as JSON. Smart
Maintenance remains disabled until deliberately enabled and must show
insufficient-data instead of a guessed recommendation. See
[docs/HEALTH_TIMELINE.md](docs/HEALTH_TIMELINE.md) and
[docs/SMART_MAINTENANCE.md](docs/SMART_MAINTENANCE.md).

## Configuration

Defaults live in `~/printer_data/config/klippertools.cfg` after installation.

```ini
[nozzle_guard]
mode: block
tolerance: 0.01
```

`mode` may be `block`, `warn`, or `off`. `block` is the recommended default.
Changing Klipper's configured nozzle still requires updating
`[extruder] nozzle_diameter` and restarting Klipper; Nozzle Guard does not hide
or temporarily rewrite that safety-critical setting.

Service Manager settings are edited from the **Klippertools** item in
Mainsail's left menu. Durable counters, task baselines, snoozes, and history are
stored atomically in `~/printer_data/klippertools-service.json`. Tool Registry
uses `~/printer_data/klippertools-tools.json`, and Printer Health Timeline uses
`~/printer_data/klippertools-timeline.json`. These files live outside the source
checkout, survive one-click updates, and are retained by normal uninstall. XY
and Z values are commanded Klipper toolhead distance, not encoder or other
physical feedback.

Thermal Soak defaults are under `[thermal_soak]`. The defaults require five
continuous minutes close to target, low regression slope, and a narrow
observed temperature range. The card can override the target, window,
tolerance, and maximum wait for one run without changing the config file.

## Verify or uninstall

Verify installed files at any time. This checks saved hashes, Python syntax,
configuration wiring, the transaction journal, and every deployed Mainsail
asset rather than merely testing whether filenames exist:

```bash
cd ~/klippertools
./scripts/check-install.sh
```

Uninstall is blocked automatically while printing or paused:

```bash
cd ~/klippertools
./scripts/uninstall.sh
```

Then restart Moonraker and Klipper and hard-refresh the browser. Uninstall
removes only owned marker blocks, restores previous managed files and the
original Mainsail build, preserves the latest Mainsail settings, archives the
source checkout, and retains recovery material. Because `~/klippertools` is no
longer left active, the online installer can be used again cleanly.

## Development

```bash
python3 -m unittest discover -s tests -v
tests/test_transactional_install.sh
```

The `mainsail/` directory contains the suite component source. Corresponding
complete modified source archives are supplied under `source/`, with compiled
UI archives under `dist/`.

## License

GNU GPL version 3 or later. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
