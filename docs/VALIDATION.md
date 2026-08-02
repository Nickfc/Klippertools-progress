# Validation record

Release 0.4.0 was validated on 2026-08-02.

- 49 Python model, parser, instrumentation, configuration, and integration
  tests passed.
- Every Klipper extra, Moonraker component, and Python helper compiled with
  Python 3.
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
- The print-state interlock rejected an active `printing` state before creating
  install state or modifying Mainsail.
- The integrity verifier rejected a deliberately corrupted, syntactically
  invalid installed backend, then passed after the exact packaged file was
  restored.
- A normal transactional update preserved a user edit to `klippertools.cfg`,
  replaced the verified source checkout last, and passed the full post-update
  manifest check.
- A real 0.2.0 install and key/value state were migrated to 0.2.1, verified,
  and uninstalled; the pre-suite `printer.cfg`, `moonraker.conf`, and Mainsail
  build were restored byte-for-byte.
- Simulated SIGKILL/power loss after backend installation, after the update UI
  backup rename, and during uninstall each left a persistent journal. The
  stable recovery helper restored the prior coherent installation in all three
  cases, after which full verification passed where applicable.
- A local Git remote exercised the public online workflow end to end: online
  install, checksum verification, online update, configuration preservation,
  uninstall with source archival, and immediate clean online reinstall.
- Both compiled UI builds include the authenticated update dialog and passed
  their respective production Vite builds.
- Service Manager tests cover all ten recommended tasks, multi-threshold
  first-one-wins due logic, baseline resets, exact confirmation for lifetime
  resets, live print/filament reconciliation, boot-local motion/probe counter
  reconciliation, and commanded XY/Z collection.
- Thermal Soak tests cover full-window stability, target proximity, excessive
  drift, oscillation range, timeout, cancellation, reset, ETA, and completion
  learning.
- A deployed 0.2.1 fixture was transactionally upgraded to 0.4.0. The test
  preserved a user edit in `klippertools.cfg`, added `[service_metrics]` and
  `[thermal_soak]`, installed both new Klipper extras, preserved the service
  data file byte-for-byte, and passed full installed-file verification.
- The real CB1 target passed the v0.2.1 pre-upgrade verifier: install state and
  journal, four backend hashes and syntax, Moonraker checksum/include,
  Klipper include, and the complete Mainsail v2.17.0 manifest were all clean.
- Moonraker controller tests confirm authenticated update and Service Manager
  endpoints, printing/paused update rejection, exact destructive-reset
  confirmation, and a second idle check before automatic service restart.

Hardware probing and resonance motion remain intentionally reserved for the
documented attended acceptance checks on the target printer.
