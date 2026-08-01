# Klippertools Suite

Klippertools adds a native Mainsail dashboard suite for Klipper printers. The
Probe Progress matrix remains directly under Console, followed by one compact
Klippertools card with Nozzle Guard, StartFlow, Maintenance, and Motion tabs.

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

### Maintenance Tracker

- Shows repeating maintenance tasks and the most urgent task first.
- Tracks print hours, filament metres, calendar days, or any combination.
- Reuses Mainsail's existing Moonraker maintenance database and dialogs, so
  tasks remain compatible with Mainsail's History page.
- Supports editable intervals, notes, completion history, and repeating tasks.

### Motion Wizard

- Guides homing, accelerometer noise testing, and separate X/Y input-shaper
  calibration.
- Uses Klipper's own `MEASURE_AXES_NOISE` and `SHAPER_CALIBRATE` commands.
- Shows the current and newly calibrated shaper type and frequency for each
  axis.
- Keeps `SAVE_CONFIG` behind a separate review-and-confirm step.

## Validated versions

- Klipper v0.13.0-660-g616242d4
- Klipper v0.13.0-708-g7046bd00
- Mainsail v2.17.0
- Mainsail v2.18.2
- Moonraker v0.10.0-29

The installer accepts only the two listed Mainsail versions because the suite
uses a version-matched native Mainsail build. A normal Mainsail update replaces
the custom UI and requires a matching Klippertools build.

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

Only install while the printer is idle. SSH into the CB1 as the normal Klipper
user, then run:

```bash
curl -fsSL https://raw.githubusercontent.com/Nickfc/Klippertools-progress/main/install-online.sh \
  -o /tmp/install-klippertools.sh
bash /tmp/install-klippertools.sh
```

The bootstrap clones the public repository into `~/klippertools`, validates
every packaged file against `SHA256SUMS`, and starts the transactional
installer. It refuses root, an existing installation, a legacy Probe Progress
install, or an unsupported Mainsail version before replacing anything.

To install a tag or review branch instead of `main`:

```bash
KLIPPERTOOLS_REF=v0.2.0 bash /tmp/install-klippertools.sh
```

After installation:

1. Send `RESTART` in the Mainsail console.
2. Hard-refresh the browser with Ctrl+Shift+R.
3. Confirm that Probe Progress and Klippertools appear under Console.

The installer retains complete rollback material under
`~/klippertools-backups/`. It preserves `printer.cfg`, previous versions of all
managed Klipper extras and `klippertools.cfg`, the original Mainsail build, and
Mainsail's current `config.json`. Any failed install restores the originals.

## Manual release ZIP

Download
[`klippertools-suite-0.2.0.zip`](dist/klippertools-suite-0.2.0.zip)
(with its optional
[`SHA-256 sidecar`](dist/klippertools-suite-0.2.0.zip.sha256)), upload the ZIP
under Mainsail's Config Files, then SSH into the CB1 as the normal Klipper
user:

```bash
mkdir -p ~/klippertools
unzip -q ~/printer_data/config/klippertools-suite-0.2.0.zip -d ~/klippertools
cd ~/klippertools
sha256sum -c SHA256SUMS
./scripts/install.sh
```

Then send `RESTART` and hard-refresh the browser as above.

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

## Verify or uninstall

Verify installed files at any time:

```bash
cd ~/klippertools
./scripts/check-install.sh
```

Uninstall only while idle:

```bash
cd ~/klippertools
./scripts/uninstall.sh
```

Then send `RESTART` and hard-refresh the browser. Uninstall removes only the
include and StartFlow markers it added, restores previous managed files and the
original Mainsail build, preserves the latest Mainsail settings, and retains
recovery files.

## Development

```bash
python3 -m unittest discover -s tests -v
tests/test_transactional_install.sh
```

The `mainsail/` directory contains component source and exact patches for both
supported Mainsail releases. Corresponding complete modified source archives
are supplied under `source/`, with compiled UI archives under `dist/`.

## License

GNU GPL version 3 or later. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
