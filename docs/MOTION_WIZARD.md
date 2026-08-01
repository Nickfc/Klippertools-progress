# Motion Wizard safety

Input-shaper calibration deliberately commands rapid oscillating motion.

Before starting:

1. Ensure no print is active or paused.
2. Remove prints, tools, clips, and loose objects from the plate and frame.
3. Inspect the accelerometer and toolhead wiring.
4. Stay beside the printer with emergency stop available.
5. Home XYZ from the wizard.

Run the noise check first. Then calibrate X and Y separately. Klipper applies
each calculated result at runtime and stages it for `SAVE_CONFIG`; the wizard
shows shaper type and frequency for review.

Only the final **Save and restart** confirmation sends `SAVE_CONFIG`. If a
result looks implausible, do not save it: inspect mechanics and accelerometer
mounting, reset the wizard, and diagnose the printer first.

Calibration CSV files are written by Klipper using names beginning with
`calibration_data_<axis>_klippertools_`.
