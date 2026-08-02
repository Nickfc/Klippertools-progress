# Thermal Soak Assistant

Thermal Soak decides that a sensor is stable only after the complete configured
window satisfies all three checks:

- the current temperature is within `temperature_tolerance` of the target;
- the linear-regression slope is no greater than `slope_limit` in °C/min;
- the highest minus lowest sample is no greater than `range_limit`.

This rejects a temperature that merely crosses the target, is still drifting,
or oscillates too widely. Samples and learned estimates are held in memory;
the assistant does not rewrite Klipper configuration.

## Dashboard use

Set the heater target through Mainsail as usual, select a sensor, and press
**Start monitoring**. The command never changes a heater target and never moves
the printer. **Cancel** stops monitoring. **Reset** clears the terminal state.

The default configuration is conservative:

```ini
[thermal_soak]
default_sensor: heater_bed
stability_window: 300
max_wait: 1800
temperature_tolerance: 0.30
slope_limit: 0.05
range_limit: 0.50
sample_interval: 2.0
```

Sensor names are discovered from Klipper and may include chamber or enclosure
temperature sensors. A passive sensor needs an explicit target in the card or
G-code command.

## Optional PRINT_START wait

The UI monitor is non-blocking. To make a macro wait, add this only after the
bed target has already been set:

```gcode
THERMAL_SOAK_WAIT SENSOR=heater_bed TARGET={BED_TEMP} WINDOW=300 MAX_WAIT=1800
```

`THERMAL_SOAK_WAIT` does not set a temperature. It returns when stable and
raises a Klipper command error on timeout, cancellation, or shutdown. Test any
macro edit while the printer is attended. Do not remove the normal heater
safety commands or use Thermal Soak as a replacement for `M190`.

Available parameters for `THERMAL_SOAK_START` and `THERMAL_SOAK_WAIT` are:

- `SENSOR`: Klipper sensor object name;
- `TARGET`: required if the selected sensor has no active target;
- `WINDOW`: full stability window in seconds;
- `MAX_WAIT`: hard timeout in seconds;
- `TOLERANCE`: allowed target difference in °C;
- `SLOPE`: maximum absolute regression slope in °C/min;
- `RANGE`: maximum observed high-to-low range in °C.

Use `THERMAL_SOAK_CANCEL` to cancel and `THERMAL_SOAK_RESET` to return the card
to idle. The built-in hard timeout prevents an unattended indefinite wait.
