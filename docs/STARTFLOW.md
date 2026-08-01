# StartFlow integration

The installer automatically instruments a `PRINT_START` only when it can find
one unambiguous command for every supported boundary. Unsupported macros remain
untouched and the installer reports the reason.

For manual integration, place these commands around the equivalent phases in
your macro:

```gcode
START_FLOW_BEGIN STAGES=bed_heat,homing,mesh,nozzle_heat,purge
START_FLOW_STAGE NAME=bed_heat
M140 S{BED}
M190 S{BED}

START_FLOW_STAGE NAME=homing
G28

START_FLOW_STAGE NAME=mesh
BED_MESH_CALIBRATE

START_FLOW_STAGE NAME=nozzle_heat
M109 S{EXTRUDER}

START_FLOW_STAGE NAME=purge
; purge moves

START_FLOW_COMPLETE
```

The commands must execute in that order, but other macro logic may remain
between them. Custom stages are allowed; use a lowercase underscore name, for
example `START_FLOW_STAGE NAME=gantry_level`.

Automatic markers use the form `# KLIPPERTOOLS_STARTFLOW:<stage>`. Do not edit a
marker's immediately following StartFlow command. The uninstaller intentionally
refuses to remove a modified pair so that it cannot mistake user content for an
installer-owned line.
