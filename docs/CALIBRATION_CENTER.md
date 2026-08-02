# Calibration Center v0.5.0 — behavior and safety contract

Calibration Center is an attended orchestration layer around Klipper's own
calibration commands and status objects. It does not replace Klipper's
algorithms, choose printer-specific calibration values, or persist results
without a separate user decision.

## Global safety rules

- Every workflow requires `CONFIRM=YES` after its warning and prerequisites are
  shown.
- No workflow starts while `print_stats.state` is `printing` or `paused`, or
  while `pause_resume.is_paused` is true.
- Motion workflows require X, Y, and Z to be homed.
- Hardware and commands are discovered at runtime. Missing workflows remain
  visible but disabled with an exact reason.
- The component never invokes `SAVE_CONFIG`, `RESTART`, or `FIRMWARE_RESTART`.
- Calibration Center never invents a heater target, pressure-advance factor,
  probe speed, mesh bounds, extrusion amount, or other printer-specific value.
- Rotation-distance support is calculation-only. It does not heat, extrude, or
  edit `[extruder]`.
- The first-layer workflow launches no heater, motion, or file. It guides the
  user to start a separately reviewed sliced test.
- Errors and Klipper shutdowns terminate the active workflow visibly.

## Workflow mapping

| Workflow | Availability and status inputs | Klipper command | Safety/application behavior |
|---|---|---|---|
| PID | `gcode.commands`, `heaters.available_heaters`, `configfile.settings.<heater>.min_temp/max_temp`, heater status | `PID_CALIBRATE HEATER=... TARGET=...` | Requires a user-selected heater and target inside that heater's configured limits. Heat warning. Result is review-only; no `SAVE_CONFIG`. |
| Bed mesh | `gcode.commands`, `toolhead.homed_axes`, `bed_mesh.profile_name`, matrix/profile status | `BED_MESH_CALIBRATE` with an optional validated profile name | Attended motion. Uses configured probe and mesh parameters; does not synthesize bounds or speeds. The generated mesh may become active immediately. |
| Z offset | `gcode.commands`, `toolhead.homed_axes`, `probe`, `manual_probe`, `configfile.save_config_pending_items` | Prefer `PROBE_CALIBRATE`; otherwise `Z_ENDSTOP_CALIBRATE` | Attended manual-probe helper. The user performs `TESTZ`, `ACCEPT`, or `ABORT`. Calibration Center only starts and observes the helper. |
| Input shaper | `gcode.commands`, `resonance_tester`, `input_shaper`, `toolhead.homed_axes`, current input-shaper config | `SHAPER_CALIBRATE [AXIS=X|Y]` | Attended high-vibration motion with X/Y/BOTH choice. No automatic saving. |
| Pressure advance | `gcode.commands`, extruder `pressure_advance` | Preview of `TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=... FACTOR=...` | Requires explicit START and FACTOR. The backend does not arm the tuning tower because that changes runtime print behavior and has no universal cancel action. The UI must present a separate send action immediately before the user-supplied test print. |
| Extruder rotation distance | `configfile.settings.extruder.rotation_distance` | No Klipper motion command | Implements the documented calculation `previous * actual / requested`, rounded for review. No extrusion and no config write. |
| First layer | `toolhead`, `extruder`, print state | No command | Guidance-only. The user reviews and starts their own sliced test file. |

## State model

`idle -> running -> review` is used for synchronous Klipper calibrations.
Manual Z calibration remains `running` while `manual_probe.is_active` is true.
Pressure advance and first-layer checks enter `guided`, because the next action
is deliberately performed by the user outside the component. `error` records a
failed command or shutdown. Reset does not discard or alter Klipper's pending
configuration; it clears only Calibration Center session state.

## Permanent changes

Klipper may report proposed changes through `configfile.save_config_pending` and
`configfile.save_config_pending_items`. The UI must show those items verbatim
before offering a separate, strongly confirmed save action. v0.5's backend does
not provide that save action; the existing Motion Wizard's separately confirmed
save behavior must not be weakened or bypassed.
