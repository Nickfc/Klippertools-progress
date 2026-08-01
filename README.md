# Klipper Probe Progress

Klipper Probe Progress adds a live bed-mesh card to Mainsail. It shows the
generated probe matrix from above, the point and sample currently running,
completed progress, and an estimated time remaining.

The card is placed directly after the Console card in the same dashboard
column.

## Display

- Red: untouched logical mesh point
- Pulsing yellow: point currently being sampled or retried
- Green: every required sample for that logical point is accepted
- Progress bar: completed logical points
- ETA: fixed estimate calculated from the first three completed logical
  points

The backend observes Klipper's actual generated bed-mesh path. It understands
serpentine traversal, command-level mesh bounds and probe counts, sample
tolerance retries, zero-reference points, and faulty-region substitutions.

## Validated versions

- Klipper v0.13.0-660-g616242d4
- Klipper v0.13.0-708-g7046bd00
- Mainsail v2.17.0
- Mainsail v2.18.2
- Moonraker v0.10.0-29

The installer accepts only the two listed Mainsail versions because the card
is a native Mainsail build. It checks the version before changing anything.
Automatic probing with a conventional Z probe is supported. Manual and
rapid-scan bed-mesh methods are outside this release's supported scope.

## Your supplied configuration

Your current bed mesh is 7 by 7 and your MicroProbe takes three samples per
position, with up to five tolerance retries. A normal calibration therefore
starts with:

- 49 logical matrix cells
- 147 planned physical touches
- additional touches only when Klipper retries a sample set

Your PRINT_START macro changes the probed bounds but keeps PROBE_COUNT at 7,7,
so the card remains 49 cells for those adaptive-area prints.

## Online install

Do this only while the printer is idle. SSH into the CB1 as the normal
Klipper user and run:

    curl -fsSL https://raw.githubusercontent.com/Nickfc/Klippertools-progress/main/install-online.sh \
      -o /tmp/install-probe-progress.sh
    bash /tmp/install-probe-progress.sh

The bootstrap downloads this repository into ~/klipper-probe-progress,
validates every packaged file against SHA256SUMS, and then starts the same
transactional installer documented below. It refuses an existing installation
or unsupported Mainsail version before replacing anything.

After installation, send RESTART in the Mainsail console and hard-refresh the
browser with Ctrl+Shift+R.

To install a tagged version instead of the current main branch:

    PROBE_PROGRESS_REF=v0.1.0 bash /tmp/install-probe-progress.sh

## Manual ZIP install

Do this only while the printer is idle.

1. Download klipper-probe-progress-0.1.0.zip.
2. In Mainsail, open Machine, then upload the ZIP under Config Files.
3. SSH into the CB1 and run:

        cd ~
        unzip -q ~/printer_data/config/klipper-probe-progress-0.1.0.zip
        cd ~/klipper-probe-progress
        chmod +x scripts/*.sh scripts/configure.py
        ./scripts/install.sh

4. In the Mainsail console, send:

        RESTART

5. Hard-refresh Mainsail with Ctrl+Shift+R.

The installer preserves printer.cfg, the previous Klipper extra and plugin
configuration if present, your complete original Mainsail installation, and
Mainsail's config.json. Backups remain under
~/probe-progress-backups/. If any install step fails, it restores the original
files automatically.

The default locations are ~/klipper, ~/printer_data, and ~/mainsail. They can
be overridden with KLIPPER_DIR, PRINTER_DATA_DIR, CONFIG_DIR, and MAINSAIL_DIR,
provided every managed path remains inside your home directory.

## Safe first test

Make sure the bed is clear and the printer is not printing. The following
uses a small central 3 by 3 mesh that is inside the safe bounds from your
configuration:

    G28
    BED_MESH_CALIBRATE PROFILE=probe_progress_test PROBE_COUNT=3,3 MESH_MIN=90,75 MESH_MAX=150,135

Expected result:

- nine cells appear red;
- the active cell pulses yellow;
- each point shows sample 1/3 through 3/3;
- completed cells turn green;
- after cell three, the progress bar changes from "calculating" to an ETA.

When the test finishes, clear its active mesh if desired:

    BED_MESH_CLEAR

The profile is not written permanently unless you separately run SAVE_CONFIG.

To verify the files at any time:

    cd ~/klipper-probe-progress
    ./scripts/check-install.sh

## Uninstall

Do this while the printer is idle:

    cd ~/klipper-probe-progress
    ./scripts/uninstall.sh

Then send RESTART in Mainsail and hard-refresh the browser. Uninstall removes
only the include line it added to the current printer.cfg, restores the
pre-install Mainsail build, preserves the latest Mainsail config.json, and
retains recovery files.

## Updates

A normal Mainsail update replaces the custom card. To move from v2.17.0 to
v2.18.2:

1. Uninstall Probe Progress.
2. Update Mainsail normally.
3. Run the Probe Progress installer again.

Do not install this UI archive over a different Mainsail version. New Mainsail
releases need a matching build and patch.

## Development

Backend model tests:

    python3 -m unittest discover -s tests -v

Repository validation also runs automatically through GitHub Actions.

The mainsail directory contains the component source and exact patches for
both supported upstream releases. Corresponding frontend source archives are
included under source/.

## License

GNU GPL version 3 or later. See LICENSE and THIRD_PARTY_NOTICES.md.
