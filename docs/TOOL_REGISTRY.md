# Nozzle & Tool Registry

The Nozzle & Tool Registry extends Nozzle Guard with persistent named tool
profiles. It does not replace Klipper's `[extruder] nozzle_diameter` setting and
never rewrites printer configuration.

## Profile data

Each profile stores:

- a stable profile ID and user-facing name;
- nozzle diameter and tool material;
- optional notes and maximum-temperature reference;
- available, installed, or retired state;
- creation, update, installation, and retirement timestamps;
- accumulated print time, filament, print count, and hotend-heater time.

Registry data is written atomically to
`~/printer_data/klippertools-tools.json`. Normal update and uninstall operations
retain it unless the user deliberately removes the data file.

## Installed-tool behavior

Installing a profile is blocked while the printer is printing or paused. The
Moonraker component sends the profile diameter to Nozzle Guard's in-memory
runtime reference. Nozzle Guard then compares selected G-code metadata against
that profile. Clearing the installed profile immediately restores the normal
Klipper-configured nozzle reference.

If synchronization is unavailable, the registry reports a visible fallback
state and Nozzle Guard continues using Klipper's configured nozzle diameter. A
failed synchronization therefore never disables or weakens the existing guard.

## Configuration review

The registry does not silently edit `[extruder] nozzle_diameter`, restart
Klipper, or claim that the runtime profile is a permanent printer configuration
change. Any permanent configuration change remains a separate user-reviewed
operation.

## Import, export, and deletion

JSON export includes profiles, accumulated usage, and history. Import creates
new profiles and resolves duplicate IDs without overwriting existing profiles.
Deleting a profile requires typing `DELETE TOOL PROFILE`; an installed profile
must first be removed. Retirement is reversible and preserves usage history.
