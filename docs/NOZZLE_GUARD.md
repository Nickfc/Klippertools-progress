# Nozzle Guard

Nozzle Guard compares numeric slicer metadata with Klipper's configured
`[extruder] nozzle_diameter` whenever virtual SD selects a G-code file.

## States

- `match`: every detected nozzle value is within `tolerance`.
- `mismatch`: at least one detected value differs beyond `tolerance`.
- `unknown`: no supported numeric metadata was found; printing is allowed.
- `overridden`: the current selected mismatch was explicitly acknowledged.
- `error`: the file could not be inspected; printing is allowed because a
  mismatch was not proven.

The default `block` mode intercepts virtual SD resume before printing starts.
`warn` reports the mismatch without blocking. `off` disables comparison.

```ini
[nozzle_guard]
mode: block
tolerance: 0.01
scan_bytes: 524288
```

The scanner reads only the configured amount from each end of the file. It
recognizes numeric comment forms using `nozzle_diameter`, `nozzle diameter`,
`nozzle_size`, and `nozzle size`. Template variables are not treated as proof.

An override applies only until another file is selected or the current file is
rechecked. Correcting an actual nozzle change requires updating Klipper's
extruder configuration and restarting; the guard never alters that value.

## Tool Registry integration

When a Tool Registry profile is installed, Moonraker synchronizes its diameter,
profile ID, and display name to Nozzle Guard's in-memory comparison reference.
Nozzle Guard status identifies whether the comparison source is the installed
registry profile or Klipper configuration.

This does not edit `[extruder] nozzle_diameter`. Clearing the installed profile,
restarting before synchronization, or a failed synchronization returns to the
Klipper-configured fallback without disabling mismatch blocking. See
[TOOL_REGISTRY.md](TOOL_REGISTRY.md).
