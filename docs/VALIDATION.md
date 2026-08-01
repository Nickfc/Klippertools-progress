# Validation record

Release 0.1.0 was validated on 2026-08-01.

- 14 Python model, configuration, and integration tests passed.
- Klipper's whitespace checker passed the backend and Python tests.
- The backend compiled with Python 3.
- Mainsail v2.17.0 passed ESLint and a production build.
- Mainsail v2.18.2 passed ESLint and a production build.
- Both UI archives contain their exact .version, build marker, and compiled
  Probe Progress card.
- Both corresponding source archives passed ZIP integrity checks.
- The online bootstrap passes shell validation and verifies the complete
  repository checksum manifest before starting the local installer.
- A disposable CB1-style home tree passed the full install, check, and
  uninstall sequence.
- The rollback test verified restoration of an existing probe_progress.py,
  an existing probe_progress.cfg, the original Mainsail build, current
  printer.cfg content, and the latest Mainsail config.json.
- A simulated 7 by 7, three-sample mesh completed 49 logical points and 147
  planned touches.

Hardware probing is intentionally left for the documented central 3 by 3
acceptance test on the target printer.
