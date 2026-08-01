# Validation record

Release 0.2.0 was validated on 2026-08-01.

- 33 Python model, parser, instrumentation, configuration, and integration
  tests passed.
- Every Klipper extra and Python helper compiled with Python 3.
- Every shell entry point passed `bash -n`.
- Mainsail v2.17.0 passed ESLint and a production Vite build.
- Mainsail v2.18.2 passed ESLint and a production Vite build.
- Both UI archives contain the exact Mainsail `.version`, compiled Probe
  Progress and Klippertools components, and `klippertools-build.txt`.
- Both corresponding full source archives passed ZIP integrity checks.
- A simulated 7 by 7, three-sample mesh completed 49 logical points and 147
  planned touches.
- Nozzle metadata tests cover Orca-style comments, multi-extruder values,
  missing metadata, confirmed mismatch, warn mode, tail scanning, and
  one-selected-file override scope.
- StartFlow tests cover stage order, ETA, learning, command errors, custom
  stages, idempotent instrumentation, unsupported macros, and exact removal.
- The supplied `PRINT_START` completed an in-memory add/remove round trip with
  byte-for-byte equality.
- Motion Wizard tests expose the supplied X `3hump_ei` 81.4 Hz and Y `mzv`
  37.2 Hz results and reject calibration without XYZ homing.
- Disposable CB1-style home trees for both supported Mainsail versions passed
  install, install verification, and uninstall.
- Transaction tests restored original `printer.cfg` byte-for-byte, restored a
  previous backend and suite config, removed newly introduced backends,
  restored the original Mainsail build, and preserved Mainsail settings changed
  after installation.
- The online bootstrap and GitHub Actions workflow validate the full checksum
  manifest before installation.

Hardware probing and resonance motion remain intentionally reserved for the
documented attended acceptance checks on the target printer.
