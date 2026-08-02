#!/usr/bin/env python3
"""Transactional install, update, verification, recovery, and uninstall.

The deployment modifies files owned by three independently updated projects
(Klipper, Moonraker, and Mainsail).  Every mutation is therefore preceded by
an on-disk journal and a complete snapshot of the path being changed.  The
journal deliberately lives outside the source checkout so recovery still
works if an update is interrupted while that checkout is being replaced.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile


VERSION = "0.3.0"
SCHEMA = 2
EXTRA_NAMES = (
    "probe_progress",
    "nozzle_guard",
    "start_flow",
    "motion_wizard",
    "service_metrics",
)
ACTIVE_PRINT_STATES = {"printing", "paused"}
SAFE_PRINT_STATES = {"standby", "complete", "cancelled", "error"}
MOONRAKER_INCLUDE = "[include klippertools-moonraker.conf]"
MOONRAKER_BEGIN = "# >>> KLIPPERTOOLS SUITE: moonraker.conf >>>"
MOONRAKER_END = "# <<< KLIPPERTOOLS SUITE: moonraker.conf <<<"
RECOVERY_MARKER = ".klippertools-recovery-v1"


class LifecycleError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise LifecycleError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        fsync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: object) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    atomic_write_bytes(path, data)


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        shutil.copy2(source, temporary_path, follow_symlinks=False)
        with temporary_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        fsync_directory(target.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def move_path(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        fail(f"recovery target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    fsync_directory(source.parent)
    if target.parent != source.parent:
        fsync_directory(target.parent)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected a JSON object in {path}")
    return value


def parse_legacy_state(path: Path) -> dict:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value
    required = {
        "BACKUP_DIR",
        "KLIPPER_DIR",
        "PRINTER_DATA_DIR",
        "CONFIG_DIR",
        "MAINSAIL_DIR",
    }
    if not required.issubset(values):
        fail("legacy install state is incomplete")
    extras = {}
    for name in EXTRA_NAMES:
        key = f"EXTRA_EXISTED_{name.upper()}"
        if key in values:
            extras[name] = values[key] == "1"
    backup_dir = Path(values["BACKUP_DIR"])
    ui_backup = backup_dir / "mainsail"
    return {
        "schema": 1,
        "plugin_version": values.get("PLUGIN_VERSION", "0.2.0"),
        "mainsail_version": values.get("MAINSAIL_VERSION", ""),
        "backup_dir": str(backup_dir),
        "original_ui_backup": str(ui_backup),
        "paths": {
            "klipper_dir": values["KLIPPER_DIR"],
            "printer_data_dir": values["PRINTER_DATA_DIR"],
            "config_dir": values["CONFIG_DIR"],
            "mainsail_dir": values["MAINSAIL_DIR"],
            "source_dir": str(Path.home() / "klippertools"),
            "moonraker_dir": str(Path.home() / "moonraker"),
        },
        "originals": {
            "extras": extras,
            "suite_config": values.get("CONFIG_EXISTED", "0") == "1",
            "moonraker_component": False,
        },
        "owned_changes": {
            "printer_include": values.get("CONFIG_INCLUDE_ADDED", "0") == "1",
            "startflow": values.get("PRINT_START_INSTRUMENTED", "0") == "1",
            "moonraker_include": False,
        },
        "source": {
            "url": "https://github.com/Nickfc/Klippertools-progress.git",
            "ref": "main",
        },
    }


def load_state(path: Path, allow_legacy: bool = False) -> dict:
    try:
        first = path.read_text(encoding="utf-8", errors="strict").lstrip()[:1]
    except OSError as exc:
        fail(f"cannot read install state: {exc}")
    if first == "{":
        return load_json(path)
    if allow_legacy:
        return parse_legacy_state(path)
    fail("legacy 0.2.0 state found; run the 0.2.1 updater before verification")


@dataclass(frozen=True)
class Paths:
    home: Path
    suite_root: Path
    klipper_dir: Path
    printer_data_dir: Path
    config_dir: Path
    mainsail_dir: Path
    moonraker_dir: Path
    source_dir: Path

    @property
    def printer_cfg(self) -> Path:
        return self.config_dir / "printer.cfg"

    @property
    def suite_cfg(self) -> Path:
        return self.config_dir / "klippertools.cfg"

    @property
    def moonraker_cfg(self) -> Path:
        configured = os.environ.get("MOONRAKER_CONFIG")
        return Path(configured).expanduser().resolve() if configured else self.config_dir / "moonraker.conf"

    @property
    def moonraker_suite_cfg(self) -> Path:
        return self.config_dir / "klippertools-moonraker.conf"

    @property
    def moonraker_component(self) -> Path:
        return self.moonraker_dir / "moonraker" / "components" / "klippertools.py"

    @property
    def state_file(self) -> Path:
        return self.printer_data_dir / "klippertools-install-state"

    @property
    def legacy_state_file(self) -> Path:
        return self.printer_data_dir / "probe-progress-install-state"

    @property
    def journal_file(self) -> Path:
        return self.printer_data_dir / "klippertools-transaction.json"

    @property
    def lock_dir(self) -> Path:
        return self.printer_data_dir / ".klippertools-transaction.lock"

    @property
    def recovery_dir(self) -> Path:
        return self.printer_data_dir / "klippertools-recovery"


def paths_from_environment(suite_root: Path | None = None, state: dict | None = None) -> Paths:
    home = Path(os.environ["HOME"]).expanduser().resolve()
    root = (suite_root or Path(__file__).resolve().parent.parent).resolve()
    stored = state.get("paths", {}) if state else {}

    def selected(env_name: str, stored_name: str, default: Path) -> Path:
        raw = os.environ.get(env_name) or stored.get(stored_name) or str(default)
        return Path(raw).expanduser().resolve()

    result = Paths(
        home=home,
        suite_root=root,
        klipper_dir=selected("KLIPPER_DIR", "klipper_dir", home / "klipper"),
        printer_data_dir=selected("PRINTER_DATA_DIR", "printer_data_dir", home / "printer_data"),
        config_dir=selected("CONFIG_DIR", "config_dir", home / "printer_data" / "config"),
        mainsail_dir=selected("MAINSAIL_DIR", "mainsail_dir", home / "mainsail"),
        moonraker_dir=selected("MOONRAKER_DIR", "moonraker_dir", home / "moonraker"),
        source_dir=selected("KLIPPERTOOLS_DIR", "source_dir", home / "klippertools"),
    )
    for managed in (
        result.klipper_dir,
        result.printer_data_dir,
        result.config_dir,
        result.mainsail_dir,
        result.moonraker_dir,
        result.source_dir,
        result.moonraker_cfg,
    ):
        try:
            managed.relative_to(home)
        except ValueError:
            fail(f"managed path must stay inside {home}: {managed}")
    return result


def check_user(paths: Paths) -> None:
    if os.geteuid() == 0:
        allowed = os.environ.get("_KLIPPERTOOLS_TEST_ALLOW_ROOT") == "1"
        if not allowed or not str(paths.home).startswith("/tmp/klippertools-"):
            fail("run this as the normal Klipper user, not root")


def assert_idle(offline: bool) -> str:
    test_state = os.environ.get("_KLIPPERTOOLS_TEST_PRINT_STATE")
    if test_state is not None:
        state = test_state.strip().lower()
    elif offline:
        print("Warning: Moonraker idle check explicitly bypassed with --offline.", file=sys.stderr)
        return "offline"
    else:
        base = os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125").rstrip("/")
        url = base + "/printer/objects/query?print_stats"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.load(response)
            state = str(payload["result"]["status"]["print_stats"]["state"]).lower()
        except (OSError, KeyError, TypeError, ValueError, urllib.error.URLError) as exc:
            fail(
                "could not prove the printer is idle through Moonraker "
                f"({exc}); stop all printing, then rerun with --offline only if Moonraker is unavailable"
            )
    if state in ACTIVE_PRINT_STATES:
        fail(f"refusing filesystem changes while printer state is {state}")
    if state not in SAFE_PRINT_STATES and state != "offline":
        fail(f"Moonraker returned an unrecognized print state: {state}")
    return state


@contextmanager
def operation_lock(paths: Paths, recovery: bool = False):
    paths.lock_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = paths.lock_dir.open("a+")
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("another Klippertools lifecycle operation is already running")
        if recovery:
            if not paths.journal_file.exists():
                fail("no interrupted transaction was found")
        elif paths.journal_file.exists():
            fail(
                "an interrupted transaction needs recovery first: "
                f"{paths.recovery_dir / 'recover.sh'}"
            )
        yield
    finally:
        lock_handle.close()


def checkpoint(name: str) -> None:
    if os.environ.get("_KLIPPERTOOLS_CRASH_AT") == name:
        os._exit(97)
    if os.environ.get("_KLIPPERTOOLS_FAIL_AT") == name:
        fail(f"injected failure at {name}")


def validate_source(paths: Paths) -> None:
    for name in EXTRA_NAMES:
        if not (paths.suite_root / "klipper" / f"{name}.py").is_file():
            fail(f"Klipper backend is missing: {name}.py")
    for relative in (
        "config/klippertools.cfg",
        "config/klippertools-moonraker.conf",
        "moonraker/klippertools.py",
        "scripts/configure.py",
        "scripts/instrument_print_start.py",
        "scripts/recover.sh",
    ):
        if not (paths.suite_root / relative).is_file():
            fail(f"suite payload is missing: {relative}")


def validate_host(paths: Paths) -> None:
    if not (paths.klipper_dir / "klippy" / "extras").is_dir():
        fail(f"Klipper was not found at {paths.klipper_dir}")
    if not paths.printer_cfg.is_file():
        fail(f"printer.cfg was not found at {paths.printer_cfg}")
    if not (paths.mainsail_dir / ".version").is_file():
        fail(f"Mainsail was not found at {paths.mainsail_dir}")
    if not paths.moonraker_component.parent.is_dir():
        fail(f"Moonraker components were not found at {paths.moonraker_component.parent}")
    if not paths.moonraker_cfg.is_file():
        fail(f"moonraker.conf was not found at {paths.moonraker_cfg}")


def mainsail_payload(paths: Paths, version: str) -> Path:
    if version not in {"v2.17.0", "v2.18.2"}:
        fail(f"Mainsail {version} is unsupported; expected v2.17.0 or v2.18.2")
    archive = paths.suite_root / "dist" / f"mainsail-{version}-klippertools.zip"
    if not archive.is_file():
        fail(f"UI build is missing: {archive}")
    return archive


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            pure = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if pure.is_absolute() or ".." in pure.parts or (mode & 0o170000) == 0o120000:
                fail(f"unsafe path in UI archive: {item.filename}")
        bundle.extractall(destination)
    if not (destination / "klippertools-build.txt").is_file():
        fail("the UI archive did not contain its Klippertools marker")


def run_helper(paths: Paths, script: str, *arguments: str) -> str:
    command = [sys.executable, str(paths.suite_root / "scripts" / script), *arguments]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def add_moonraker_include(text: str) -> tuple[str, bool]:
    if MOONRAKER_INCLUDE in {line.strip() for line in text.splitlines()}:
        return text, False
    suffix = "" if not text or text.endswith("\n") else "\n"
    block = (
        f"{MOONRAKER_BEGIN}\n"
        "# Added by Klippertools Suite\n"
        f"{MOONRAKER_INCLUDE}\n"
        f"{MOONRAKER_END}\n"
    )
    return text + suffix + block, True


def remove_moonraker_include(text: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if line.strip() == MOONRAKER_BEGIN), None)
    if start is not None:
        end = next(
            (index for index in range(start + 1, len(lines)) if lines[index].strip() == MOONRAKER_END),
            None,
        )
        if end is None:
            fail("moonraker.conf contains an incomplete Klippertools marker block")
        del lines[start : end + 1]
        return "".join(lines), True
    return text, False


def transform_file(path: Path, transform) -> bool:
    original = path.read_text(encoding="utf-8")
    updated, changed = transform(original)
    if changed:
        mode = path.stat().st_mode & 0o777
        atomic_write_bytes(path, updated.encode(), mode)
    return changed


def snapshot_file(target: Path, backup: Path) -> dict:
    existed = target.exists() or target.is_symlink()
    if existed:
        if target.is_symlink():
            fail(f"refusing managed symlink: {target}")
        if target.is_dir():
            fail(f"expected a file but found a directory: {target}")
        atomic_copy(target, backup)
    return {"target": str(target), "backup": str(backup), "existed": existed}


def deploy_recovery(paths: Paths) -> None:
    recovery = paths.recovery_dir
    if recovery.exists() and not (recovery / RECOVERY_MARKER).is_file():
        fail(f"refusing unrelated recovery directory: {recovery}")
    recovery.mkdir(parents=True, exist_ok=True)
    atomic_copy(paths.suite_root / "scripts" / "lifecycle.py", recovery / "lifecycle.py")
    atomic_copy(paths.suite_root / "scripts" / "recover.sh", recovery / "recover.sh")
    atomic_write_bytes(recovery / RECOVERY_MARKER, (VERSION + "\n").encode())
    os.chmod(recovery / "recover.sh", 0o755)


def write_journal(paths: Paths, journal: dict) -> None:
    atomic_write_json(paths.journal_file, journal)


def restore_snapshot(entry: dict) -> None:
    target = Path(entry["target"])
    backup = Path(entry["backup"])
    if entry["existed"]:
        if not backup.exists() and not backup.is_symlink():
            fail(f"recovery snapshot is missing: {backup}")
        atomic_copy(backup, target)
    else:
        remove_path(target)


def recover_transaction(paths: Paths) -> None:
    journal = load_json(paths.journal_file)
    backup_dir = Path(journal.get("backup_dir", "")).resolve()
    expected_root = (paths.home / "klippertools-backups").resolve()
    try:
        backup_dir.relative_to(expected_root)
    except ValueError:
        fail(f"refusing unexpected transaction backup path: {backup_dir}")

    action = journal.get("action")
    if action not in {"install", "update", "uninstall"}:
        fail(f"unknown recovery action: {action}")

    def validate_home_path(raw: str, label: str) -> Path:
        candidate = Path(raw).expanduser().resolve()
        try:
            candidate.relative_to(paths.home)
        except ValueError:
            fail(f"refusing {label} outside {paths.home}: {candidate}")
        return candidate

    for entry in journal.get("files", []):
        validate_home_path(entry["target"], "recovery target")
        backup = validate_home_path(entry["backup"], "recovery snapshot")
        try:
            backup.relative_to(expected_root)
        except ValueError:
            fail(f"refusing recovery snapshot outside {expected_root}: {backup}")
    for key in (
        "ui_target",
        "ui_backup",
        "ui_replacement_origin",
        "source_target",
        "source_backup",
        "state_file",
        "state_backup",
    ):
        if journal.get(key):
            validate_home_path(journal[key], key)

    source_target = Path(journal["source_target"]) if journal.get("source_target") else None
    source_backup = Path(journal["source_backup"]) if journal.get("source_backup") else None
    if source_backup and source_backup.exists():
        if source_target is None:
            fail("recovery journal omitted the source target")
        if source_target.exists():
            failed = backup_dir / "source-failed-recovery"
            remove_path(failed)
            move_path(source_target, failed)
        move_path(source_backup, source_target)

    ui_target = Path(journal["ui_target"])
    ui_backup = Path(journal["ui_backup"])
    ui_replacement_origin = (
        Path(journal["ui_replacement_origin"]) if journal.get("ui_replacement_origin") else None
    )
    if action == "uninstall" and ui_replacement_origin and not ui_replacement_origin.exists():
        if ui_target.exists():
            move_path(ui_target, ui_replacement_origin)
    if ui_backup.exists():
        if ui_target.exists():
            failed_ui = backup_dir / "mainsail-failed-recovery"
            remove_path(failed_ui)
            move_path(ui_target, failed_ui)
        move_path(ui_backup, ui_target)

    for entry in journal.get("files", []):
        restore_snapshot(entry)

    state_file = Path(journal["state_file"])
    state_backup = Path(journal["state_backup"])
    if journal.get("state_existed"):
        atomic_copy(state_backup, state_file)
    else:
        state_file.unlink(missing_ok=True)

    paths.journal_file.unlink()
    fsync_directory(paths.journal_file.parent)


def recover_after_error(paths: Paths, error: BaseException) -> None:
    if not paths.journal_file.exists():
        raise error
    try:
        recover_transaction(paths)
    except BaseException as recovery_error:
        print(f"Operation failed: {error}", file=sys.stderr)
        print(f"Automatic recovery also failed: {recovery_error}", file=sys.stderr)
        print(f"Journal retained at: {paths.journal_file}", file=sys.stderr)
        raise LifecycleError("manual recovery is required") from recovery_error
    print(f"Operation failed and all managed files were restored: {error}", file=sys.stderr)
    raise LifecycleError(str(error)) from error


def new_backup_dir(paths: Paths, action: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = paths.home / "klippertools-backups" / f"{stamp}-{action}-{os.getpid()}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def source_metadata() -> dict:
    return {
        "url": os.environ.get(
            "KLIPPERTOOLS_SOURCE_URL", "https://github.com/Nickfc/Klippertools-progress.git"
        ),
        "ref": os.environ.get("KLIPPERTOOLS_SOURCE_REF", "main"),
    }


def build_state(
    paths: Paths,
    backup_dir: Path,
    original_ui_backup: Path,
    mainsail_version: str,
    originals: dict,
    owned_changes: dict,
    printer_hash: str,
    moonraker_hash: str,
    source: dict,
) -> dict:
    installed_extras = {
        name: sha256(paths.klipper_dir / "klippy" / "extras" / f"{name}.py") for name in EXTRA_NAMES
    }
    archive = mainsail_payload(paths, mainsail_version)
    manifest_file = paths.suite_root / "SHA256SUMS"
    return {
        "schema": SCHEMA,
        "plugin_version": VERSION,
        "installed_at": datetime.now().astimezone().isoformat(),
        "mainsail_version": mainsail_version,
        "backup_dir": str(backup_dir),
        "original_ui_backup": str(original_ui_backup),
        "paths": {
            "klipper_dir": str(paths.klipper_dir),
            "printer_data_dir": str(paths.printer_data_dir),
            "config_dir": str(paths.config_dir),
            "mainsail_dir": str(paths.mainsail_dir),
            "moonraker_dir": str(paths.moonraker_dir),
            "source_dir": str(paths.source_dir),
        },
        "originals": originals,
        "owned_changes": owned_changes,
        "managed_config_hashes": {
            "printer_cfg": printer_hash,
            "moonraker_cfg": moonraker_hash,
        },
        "installed_hashes": {
            "extras": installed_extras,
            "moonraker_component": sha256(paths.moonraker_component),
            "ui_archive": sha256(archive),
            "release_manifest": sha256(manifest_file) if manifest_file.is_file() else None,
        },
        "source": source,
    }


def prepare_file_snapshots(paths: Paths, backup_dir: Path) -> tuple[list[dict], dict]:
    entries: list[dict] = []
    originals = {"extras": {}}
    for name in EXTRA_NAMES:
        target = paths.klipper_dir / "klippy" / "extras" / f"{name}.py"
        entry = snapshot_file(target, backup_dir / "originals" / "extras" / f"{name}.py")
        entries.append(entry)
        originals["extras"][name] = entry["existed"]
    suite_entry = snapshot_file(paths.suite_cfg, backup_dir / "originals" / "klippertools.cfg")
    component_entry = snapshot_file(
        paths.moonraker_component, backup_dir / "originals" / "moonraker-klippertools.py"
    )
    entries.extend(
        [
            suite_entry,
            component_entry,
            snapshot_file(paths.printer_cfg, backup_dir / "originals" / "printer.cfg"),
            snapshot_file(paths.moonraker_cfg, backup_dir / "originals" / "moonraker.conf"),
            snapshot_file(
                paths.moonraker_suite_cfg,
                backup_dir / "originals" / "klippertools-moonraker.conf",
            ),
        ]
    )
    originals["suite_config"] = suite_entry["existed"]
    originals["moonraker_component"] = component_entry["existed"]
    originals["moonraker_suite_config"] = entries[-1]["existed"]
    return entries, originals


def install(paths: Paths, offline: bool) -> None:
    check_user(paths)
    validate_source(paths)
    validate_host(paths)
    if paths.state_file.exists():
        fail("Klippertools is already installed; use Update instead of reinstalling")
    if paths.legacy_state_file.exists():
        fail("Probe Progress 0.1 is installed; uninstall it before installing Klippertools")
    if "[include probe_progress.cfg]" in paths.printer_cfg.read_text(encoding="utf-8"):
        fail("printer.cfg still includes probe_progress.cfg; remove the legacy install first")

    mainsail_version = paths.mainsail_dir.joinpath(".version").read_text().strip()
    archive = mainsail_payload(paths, mainsail_version)
    assert_idle(offline)
    backup_dir = new_backup_dir(paths, "install")
    staged_ui = backup_dir / "mainsail-staged"
    safe_extract(archive, staged_ui)
    if (paths.mainsail_dir / "config.json").is_file():
        shutil.copy2(paths.mainsail_dir / "config.json", staged_ui / "config.json")

    entries, originals = prepare_file_snapshots(paths, backup_dir)
    original_ui = backup_dir / "mainsail-original"
    state_backup = backup_dir / "state-before"
    journal = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "action": "install",
        "phase": "prepared",
        "backup_dir": str(backup_dir),
        "files": entries,
        "ui_target": str(paths.mainsail_dir),
        "ui_backup": str(original_ui),
        "state_file": str(paths.state_file),
        "state_backup": str(state_backup),
        "state_existed": False,
    }
    deploy_recovery(paths)
    write_journal(paths, journal)

    try:
        for name in EXTRA_NAMES:
            atomic_copy(
                paths.suite_root / "klipper" / f"{name}.py",
                paths.klipper_dir / "klippy" / "extras" / f"{name}.py",
            )
        checkpoint("after_backends")
        atomic_copy(paths.suite_root / "config" / "klippertools.cfg", paths.suite_cfg)
        atomic_copy(paths.suite_root / "moonraker" / "klippertools.py", paths.moonraker_component)
        atomic_copy(
            paths.suite_root / "config" / "klippertools-moonraker.conf",
            paths.moonraker_suite_cfg,
        )
        checkpoint("after_components")

        include_result = run_helper(paths, "configure.py", "add", str(paths.printer_cfg))
        startflow_result = run_helper(
            paths, "instrument_print_start.py", "add", str(paths.printer_cfg), "--optional"
        )
        moonraker_added = transform_file(paths.moonraker_cfg, add_moonraker_include)
        checkpoint("after_config")

        move_path(paths.mainsail_dir, original_ui)
        checkpoint("after_ui_backup")
        move_path(staged_ui, paths.mainsail_dir)
        checkpoint("after_ui")

        state = build_state(
            paths,
            backup_dir,
            original_ui,
            mainsail_version,
            originals,
            {
                "printer_include": include_result == "updated",
                "startflow": startflow_result == "updated",
                "moonraker_include": moonraker_added,
            },
            sha256(paths.printer_cfg),
            sha256(paths.moonraker_cfg),
            source_metadata(),
        )
        atomic_write_json(paths.state_file, state)
        checkpoint("after_state")
        paths.journal_file.unlink()
        fsync_directory(paths.journal_file.parent)
    except BaseException as exc:
        recover_after_error(paths, exc)

    print(f"\nKlippertools Suite {VERSION} installed successfully.")
    print(f"Backup retained at: {backup_dir}")
    if startflow_result == "updated":
        print("StartFlow markers were added safely to PRINT_START.")
    else:
        print(f"StartFlow was not auto-instrumented: {startflow_result}")
    print("\nNext:")
    print("  1. Restart Moonraker, then send RESTART to Klipper.")
    print("  2. Hard-refresh Mainsail (Ctrl+Shift+R).")
    print("  3. Run ./scripts/check-install.sh.")


def ensure_original_backup_for_update(paths: Paths, state: dict) -> tuple[dict, dict]:
    originals = dict(state.get("originals", {}))
    originals["extras"] = dict(originals.get("extras", {}))
    owned = dict(state.get("owned_changes", {}))
    initial_backup = Path(state["backup_dir"])

    # New suite releases may add a Klipper extra. Preserve any unrelated file
    # already using that name in the original install backup before replacing
    # it, so a future uninstall still restores the true pre-suite host.
    for name in EXTRA_NAMES:
        if name in originals["extras"]:
            continue
        target = paths.klipper_dir / "klippy" / "extras" / f"{name}.py"
        backup = initial_backup / "originals" / "extras" / f"{name}.py"
        existed = target.exists() or target.is_symlink()
        if existed and not backup.exists():
            atomic_copy(target, backup)
        originals["extras"][name] = existed

    # 0.2.0 did not manage Moonraker.  Capture its untouched configuration in
    # the original install backup before 0.2.1 adds the component/include, so a
    # later uninstall still returns to the true pre-suite state.
    original_moonraker = initial_backup / "originals" / "moonraker.conf"
    if not original_moonraker.exists():
        atomic_copy(paths.moonraker_cfg, original_moonraker)

    if "moonraker_component" not in originals or state.get("schema") == 1:
        component_backup = initial_backup / "originals" / "moonraker-klippertools.py"
        existed = paths.moonraker_component.exists()
        if existed and not component_backup.exists():
            component_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.moonraker_component, component_backup)
        originals["moonraker_component"] = existed

    if "moonraker_suite_config" not in originals:
        config_backup = initial_backup / "originals" / "klippertools-moonraker.conf"
        existed = paths.moonraker_suite_cfg.exists()
        if existed and not config_backup.exists():
            config_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.moonraker_suite_cfg, config_backup)
        originals["moonraker_suite_config"] = existed
    owned.setdefault("moonraker_include", False)
    return originals, owned


def ensure_service_metrics_config(paths: Paths) -> bool:
    """Add the v0.3 collector section without replacing user tuning."""
    text = paths.suite_cfg.read_text(encoding="utf-8")
    if any(line.strip() == "[service_metrics]" for line in text.splitlines()):
        return False
    addition = (
        "\n[service_metrics]\n"
        "# Motion distance is commanded travel reported by Klipper, not encoder or\n"
        "# other closed-loop physical feedback. Persistent counters and service\n"
        "# intervals are configured in Mainsail's Klippertools view.\n"
    )
    mode = paths.suite_cfg.stat().st_mode & 0o777
    atomic_write_bytes(paths.suite_cfg, (text.rstrip() + "\n" + addition).encode(), mode=mode)
    return True


def update(paths: Paths, offline: bool, source_target: Path) -> None:
    check_user(paths)
    validate_source(paths)
    state_path = paths.state_file
    if not state_path.is_file():
        fail("Klippertools install state was not found")
    state = load_state(state_path, allow_legacy=True)
    paths = paths_from_environment(paths.suite_root, state)
    check_user(paths)
    validate_host(paths)
    if source_target.resolve() != paths.source_dir:
        fail(f"source target does not match install state: {source_target} != {paths.source_dir}")
    if paths.suite_root == paths.source_dir:
        fail("the updater must run from a verified staging checkout; use update-online.sh")

    mainsail_version = paths.mainsail_dir.joinpath(".version").read_text().strip()
    archive = mainsail_payload(paths, mainsail_version)
    assert_idle(offline)
    backup_dir = new_backup_dir(paths, "update")
    staged_ui = backup_dir / "mainsail-staged"
    safe_extract(archive, staged_ui)
    if (paths.mainsail_dir / "config.json").is_file():
        shutil.copy2(paths.mainsail_dir / "config.json", staged_ui / "config.json")

    entries, _unused = prepare_file_snapshots(paths, backup_dir)
    state_backup = backup_dir / "state-before"
    shutil.copy2(paths.state_file, state_backup)
    ui_backup = backup_dir / "mainsail-before-update"
    source_backup = backup_dir / "source-before-update"
    journal = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "action": "update",
        "phase": "prepared",
        "backup_dir": str(backup_dir),
        "files": entries,
        "ui_target": str(paths.mainsail_dir),
        "ui_backup": str(ui_backup),
        "source_target": str(paths.source_dir),
        "source_backup": str(source_backup),
        "state_file": str(paths.state_file),
        "state_backup": str(state_backup),
        "state_existed": True,
    }
    deploy_recovery(paths)
    write_journal(paths, journal)

    try:
        originals, owned = ensure_original_backup_for_update(paths, state)
        for name in EXTRA_NAMES:
            atomic_copy(
                paths.suite_root / "klipper" / f"{name}.py",
                paths.klipper_dir / "klippy" / "extras" / f"{name}.py",
            )
        checkpoint("after_backends")
        if not paths.suite_cfg.exists():
            atomic_copy(paths.suite_root / "config" / "klippertools.cfg", paths.suite_cfg)
        ensure_service_metrics_config(paths)
        atomic_copy(paths.suite_root / "moonraker" / "klippertools.py", paths.moonraker_component)
        atomic_copy(
            paths.suite_root / "config" / "klippertools-moonraker.conf",
            paths.moonraker_suite_cfg,
        )
        checkpoint("after_components")

        include_result = run_helper(paths, "configure.py", "add", str(paths.printer_cfg))
        if include_result == "updated":
            owned["printer_include"] = True
        moonraker_added = transform_file(paths.moonraker_cfg, add_moonraker_include)
        if moonraker_added:
            owned["moonraker_include"] = True
        checkpoint("after_config")

        move_path(paths.mainsail_dir, ui_backup)
        checkpoint("after_ui_backup")
        move_path(staged_ui, paths.mainsail_dir)
        checkpoint("after_ui")

        original_ui = Path(state.get("original_ui_backup") or Path(state["backup_dir"]) / "mainsail")
        new_state = build_state(
            paths,
            Path(state["backup_dir"]),
            original_ui,
            mainsail_version,
            originals,
            owned,
            sha256(paths.printer_cfg),
            sha256(paths.moonraker_cfg),
            source_metadata() if os.environ.get("KLIPPERTOOLS_SOURCE_URL") else state.get("source", source_metadata()),
        )
        new_state["updated_at"] = datetime.now().astimezone().isoformat()
        new_state["previous_version"] = state.get("plugin_version")
        atomic_write_json(paths.state_file, new_state)
        checkpoint("after_state")

        if not paths.source_dir.exists():
            fail(f"installed source checkout is missing: {paths.source_dir}")
        move_path(paths.source_dir, source_backup)
        checkpoint("after_source_backup")
        move_path(paths.suite_root, paths.source_dir)
        checkpoint("after_source")

        paths.journal_file.unlink()
        fsync_directory(paths.journal_file.parent)
    except BaseException as exc:
        recover_after_error(paths, exc)

    print(f"\nKlippertools Suite updated transactionally to {VERSION}.")
    print("Klipper and Moonraker will be restarted by the update controller.")


def restore_original_file(current: Path, backup: Path, existed: bool, retained: Path) -> None:
    if current.exists() or current.is_symlink():
        retained.parent.mkdir(parents=True, exist_ok=True)
        if retained.exists() or retained.is_symlink():
            remove_path(retained)
        move_path(current, retained)
    if existed:
        if not backup.exists() and not backup.is_symlink():
            fail(f"original backup is missing: {backup}")
        atomic_copy(backup, current)


def uninstall(paths: Paths, offline: bool) -> None:
    check_user(paths)
    if not paths.state_file.is_file():
        fail(f"install state was not found at {paths.state_file}")
    state = load_state(paths.state_file, allow_legacy=True)
    paths = paths_from_environment(paths.suite_root, state)
    check_user(paths)
    assert_idle(offline)

    initial_backup = Path(state["backup_dir"])
    try:
        initial_backup.resolve().relative_to((paths.home / "klippertools-backups").resolve())
    except ValueError:
        fail(f"refusing unexpected original backup path: {initial_backup}")
    original_ui = Path(state.get("original_ui_backup") or initial_backup / "mainsail")
    if not original_ui.is_dir():
        fail(f"original Mainsail backup is missing: {original_ui}")

    backup_dir = new_backup_dir(paths, "uninstall")
    entries, _unused = prepare_file_snapshots(paths, backup_dir)
    state_backup = backup_dir / "state-before"
    shutil.copy2(paths.state_file, state_backup)
    ui_backup = backup_dir / "mainsail-with-klippertools"
    source_backup = initial_backup / "source-uninstalled"
    if source_backup.exists():
        fail(f"uninstall source backup already exists: {source_backup}")
    journal = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "action": "uninstall",
        "phase": "prepared",
        "backup_dir": str(backup_dir),
        "files": entries,
        "ui_target": str(paths.mainsail_dir),
        "ui_backup": str(ui_backup),
        "ui_replacement_origin": str(original_ui),
        "source_target": str(paths.source_dir),
        "source_backup": str(source_backup),
        "state_file": str(paths.state_file),
        "state_backup": str(state_backup),
        "state_existed": True,
    }
    write_journal(paths, journal)

    try:
        original_printer = initial_backup / "originals" / "printer.cfg"
        if not original_printer.exists():
            original_printer = initial_backup / "printer.cfg"
        current_printer_hash = sha256(paths.printer_cfg)
        managed_hash = state.get("managed_config_hashes", {}).get("printer_cfg")
        if managed_hash and current_printer_hash == managed_hash and original_printer.is_file():
            atomic_copy(original_printer, paths.printer_cfg)
        else:
            if state.get("owned_changes", {}).get("startflow"):
                run_helper(paths, "instrument_print_start.py", "remove", str(paths.printer_cfg))
            if state.get("owned_changes", {}).get("printer_include"):
                run_helper(paths, "configure.py", "remove", str(paths.printer_cfg))
            if original_printer.is_file() and sha256(paths.printer_cfg) == sha256(original_printer):
                atomic_copy(original_printer, paths.printer_cfg)

        original_moonraker = initial_backup / "originals" / "moonraker.conf"
        current_moon_hash = sha256(paths.moonraker_cfg)
        managed_moon_hash = state.get("managed_config_hashes", {}).get("moonraker_cfg")
        if managed_moon_hash and current_moon_hash == managed_moon_hash and original_moonraker.is_file():
            atomic_copy(original_moonraker, paths.moonraker_cfg)
        elif state.get("owned_changes", {}).get("moonraker_include"):
            transform_file(paths.moonraker_cfg, remove_moonraker_include)
        checkpoint("after_config")

        originals = state.get("originals", {})
        for name in EXTRA_NAMES:
            previous = initial_backup / "originals" / "extras" / f"{name}.py"
            if not previous.exists():
                previous = initial_backup / f"{name}.py.previous"
            restore_original_file(
                paths.klipper_dir / "klippy" / "extras" / f"{name}.py",
                previous,
                bool(originals.get("extras", {}).get(name)),
                initial_backup / "installed-removed" / f"{name}.py",
            )
        suite_previous = initial_backup / "originals" / "klippertools.cfg"
        if not suite_previous.exists():
            suite_previous = initial_backup / "klippertools.cfg.previous"
        restore_original_file(
            paths.suite_cfg,
            suite_previous,
            bool(originals.get("suite_config")),
            initial_backup / "installed-removed" / "klippertools.cfg",
        )
        restore_original_file(
            paths.moonraker_component,
            initial_backup / "originals" / "moonraker-klippertools.py",
            bool(originals.get("moonraker_component")),
            initial_backup / "installed-removed" / "moonraker-klippertools.py",
        )
        restore_original_file(
            paths.moonraker_suite_cfg,
            initial_backup / "originals" / "klippertools-moonraker.conf",
            bool(originals.get("moonraker_suite_config")),
            initial_backup / "installed-removed" / "klippertools-moonraker.conf",
        )
        checkpoint("after_backends")

        latest_config = backup_dir / "config.json.latest"
        if (paths.mainsail_dir / "config.json").is_file():
            shutil.copy2(paths.mainsail_dir / "config.json", latest_config)
        move_path(paths.mainsail_dir, ui_backup)
        checkpoint("after_ui_backup")
        move_path(original_ui, paths.mainsail_dir)
        if latest_config.is_file():
            atomic_copy(latest_config, paths.mainsail_dir / "config.json")
        checkpoint("after_ui")

        state_retained = initial_backup / "install-state.uninstalled"
        atomic_copy(paths.state_file, state_retained)
        paths.state_file.unlink()
        if paths.source_dir.exists():
            move_path(paths.source_dir, source_backup)
        checkpoint("after_source")

        paths.journal_file.unlink()
        fsync_directory(paths.journal_file.parent)
        remove_path(paths.recovery_dir)
    except BaseException as exc:
        recover_after_error(paths, exc)

    print("\nKlippertools Suite uninstalled successfully.")
    print(f"Recovery files were retained at: {initial_backup}")
    print("Restart Moonraker and Klipper, then hard-refresh Mainsail.")


def compare_ui(paths: Paths, archive: Path) -> list[str]:
    problems: list[str] = []
    expected: dict[str, str] = {}
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            if item.is_dir() or item.filename == "config.json":
                continue
            expected[item.filename] = hashlib.sha256(bundle.read(item)).hexdigest()
    actual_files = {
        item.relative_to(paths.mainsail_dir).as_posix()
        for item in paths.mainsail_dir.rglob("*")
        if (item.is_file() or item.is_symlink()) and item.name != "config.json"
    }
    for relative, digest in expected.items():
        target = paths.mainsail_dir / relative
        if not target.is_file() or target.is_symlink():
            problems.append(f"Mainsail file missing or unsafe: {relative}")
        elif sha256(target) != digest:
            problems.append(f"Mainsail file modified: {relative}")
    for relative in sorted(actual_files - set(expected)):
        problems.append(f"unexpected Mainsail file: {relative}")
    return problems


def verify_release_manifest(paths: Paths, expected_digest: str | None) -> list[str]:
    problems: list[str] = []
    manifest = paths.suite_root / "SHA256SUMS"
    if not manifest.is_file() or manifest.is_symlink():
        return ["release checksum manifest is missing or unsafe"]
    if expected_digest and sha256(manifest) != expected_digest:
        problems.append("release checksum manifest was modified")
        return problems
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"release checksum manifest is unreadable: {exc}"]
    for number, line in enumerate(lines, 1):
        try:
            digest, raw_path = line.split("  ", 1)
        except ValueError:
            problems.append(f"malformed release checksum line {number}")
            continue
        relative = PurePosixPath(raw_path.removeprefix("./"))
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            problems.append(f"unsafe release checksum line {number}")
            continue
        target = paths.suite_root.joinpath(*relative.parts)
        if not target.is_file() or target.is_symlink():
            problems.append(f"release file missing or unsafe: {relative.as_posix()}")
        elif sha256(target) != digest:
            problems.append(f"release file failed checksum: {relative.as_posix()}")
    return problems


def verify(paths: Paths) -> None:
    check_user(paths)
    if not paths.state_file.is_file():
        fail(f"install state was not found at {paths.state_file}")
    state = load_state(paths.state_file)
    paths = paths_from_environment(paths.suite_root, state)
    check_user(paths)
    problems: list[str] = []

    if paths.journal_file.exists():
        problems.append(f"interrupted transaction present: {paths.journal_file}")
    if state.get("schema") != SCHEMA or state.get("plugin_version") != VERSION:
        problems.append("install state version does not match this verifier")

    installed_hashes = state.get("installed_hashes", {})
    problems.extend(
        verify_release_manifest(paths, installed_hashes.get("release_manifest"))
    )
    expected_extras = installed_hashes.get("extras", {})
    for name in EXTRA_NAMES:
        target = paths.klipper_dir / "klippy" / "extras" / f"{name}.py"
        source = paths.suite_root / "klipper" / f"{name}.py"
        if not target.is_file() or target.is_symlink():
            problems.append(f"Klipper backend missing or unsafe: {name}.py")
            continue
        digest = sha256(target)
        if digest != expected_extras.get(name) or not source.is_file() or digest != sha256(source):
            problems.append(f"Klipper backend failed checksum: {name}.py")
        try:
            compile(target.read_text(encoding="utf-8"), str(target), "exec")
        except (OSError, UnicodeError, SyntaxError) as exc:
            problems.append(f"Klipper backend has invalid Python: {name}.py ({exc})")

    component = paths.moonraker_component
    if not component.is_file() or component.is_symlink():
        problems.append("Moonraker updater component is missing or unsafe")
    else:
        digest = sha256(component)
        source = paths.suite_root / "moonraker" / "klippertools.py"
        if digest != installed_hashes.get("moonraker_component") or digest != sha256(source):
            problems.append("Moonraker updater component failed checksum")
        try:
            compile(component.read_text(encoding="utf-8"), str(component), "exec")
        except (OSError, UnicodeError, SyntaxError) as exc:
            problems.append(f"Moonraker updater component has invalid Python: {exc}")

    if not paths.suite_cfg.is_file():
        problems.append("suite configuration is missing")
    elif "[service_metrics]" not in {
        line.strip() for line in paths.suite_cfg.read_text(encoding="utf-8").splitlines()
    }:
        problems.append("suite configuration does not enable service_metrics")
    printer_text = paths.printer_cfg.read_text(encoding="utf-8") if paths.printer_cfg.is_file() else ""
    if "[include klippertools.cfg]" not in {line.strip() for line in printer_text.splitlines()}:
        problems.append("printer.cfg does not include klippertools.cfg")
    moon_text = paths.moonraker_cfg.read_text(encoding="utf-8") if paths.moonraker_cfg.is_file() else ""
    if MOONRAKER_INCLUDE not in {line.strip() for line in moon_text.splitlines()}:
        problems.append("moonraker.conf does not include klippertools-moonraker.conf")
    if not paths.moonraker_suite_cfg.is_file():
        problems.append("Klippertools Moonraker configuration is missing")

    version = state.get("mainsail_version", "")
    archive = mainsail_payload(paths, version)
    if sha256(archive) != installed_hashes.get("ui_archive"):
        problems.append("packaged Mainsail archive failed its installed checksum")
    else:
        problems.extend(compare_ui(paths, archive))

    if problems:
        for problem in problems:
            print(f"[fail] {problem}")
        fail(f"installation verification failed with {len(problems)} problem(s)")
    print(f"[ok] Klippertools Suite {VERSION} state and transaction journal")
    print("[ok] five Klipper backends: checksums and Python syntax")
    print("[ok] Moonraker updater: checksum, Python syntax, and include")
    print("[ok] Klipper configuration include")
    print(f"[ok] complete Mainsail {version} file manifest")


def recover(paths: Paths, offline: bool) -> None:
    check_user(paths)
    assert_idle(offline)
    with operation_lock(paths, recovery=True):
        recover_transaction(paths)
    print("Interrupted Klippertools transaction recovered successfully.")


def show_source_info(paths: Paths) -> None:
    state = load_state(paths.state_file, allow_legacy=True)
    source = state.get("source", source_metadata())
    print(source.get("url", source_metadata()["url"]))
    print(source.get("ref", "main"))
    print(state.get("plugin_version", "unknown"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("install", "uninstall", "recover"):
        command = subparsers.add_parser(name)
        command.add_argument(
            "--offline",
            action="store_true",
            help="bypass Moonraker only after independently confirming no print is active",
        )
    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--offline", action="store_true")
    update_parser.add_argument("--source-target", type=Path, required=True)
    subparsers.add_parser("verify")
    subparsers.add_parser("source-info")
    return result


def main() -> int:
    args = parser().parse_args()
    paths = paths_from_environment()
    try:
        if args.command == "install":
            with operation_lock(paths):
                install(paths, args.offline)
        elif args.command == "update":
            with operation_lock(paths):
                update(paths, args.offline, args.source_target.expanduser().resolve())
        elif args.command == "uninstall":
            with operation_lock(paths):
                uninstall(paths, args.offline)
        elif args.command == "recover":
            recover(paths, args.offline)
        elif args.command == "verify":
            verify(paths)
        elif args.command == "source-info":
            show_source_info(paths)
        return 0
    except LifecycleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
