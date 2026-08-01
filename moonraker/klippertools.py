# Klippertools Suite update controller
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..common import RequestType


class Klippertools:
    def __init__(self, config) -> None:
        self.server = config.get_server()
        self.eventloop = self.server.get_event_loop()
        self.klippy_apis = self.server.lookup_component("klippy_apis")
        self.machine = self.server.lookup_component("machine")
        self.klippy_connection = self.server.lookup_component("klippy_connection")

        home = Path.home().resolve()
        self.repo_path = Path(config.get("repo_path", "~/klippertools")).expanduser().resolve()
        self.state_path = Path(
            config.get("state_path", "~/printer_data/klippertools-install-state")
        ).expanduser().resolve()
        for path in (self.repo_path, self.state_path):
            try:
                path.relative_to(home)
            except ValueError as exc:
                raise config.error(f"Klippertools path must remain inside {home}: {path}") from exc

        self.update_task: Optional[asyncio.Task] = None
        self.update_status: Dict[str, Any] = {
            "state": "idle",
            "message": "Ready",
            "started_at": None,
            "finished_at": None,
            "restart_required": False,
        }
        self.server.register_endpoint(
            "/machine/klippertools/status", RequestType.GET, self._handle_status
        )
        self.server.register_endpoint(
            "/machine/klippertools/update", RequestType.POST, self._handle_update
        )

    def _installed_version(self) -> str:
        try:
            text = self.state_path.read_text(encoding="utf-8").lstrip()
            if text.startswith("{"):
                state = json.loads(text)
                return str(state.get("plugin_version", "unknown"))
            for line in text.splitlines():
                if line.startswith("PLUGIN_VERSION="):
                    return line.split("=", 1)[1]
        except (OSError, ValueError, TypeError):
            logging.exception("Unable to read Klippertools install state")
        return "unknown"

    async def _handle_status(self, web_request) -> Dict[str, Any]:
        result = dict(self.update_status)
        result["installed_version"] = self._installed_version()
        result["updating"] = self.update_task is not None and not self.update_task.done()
        return result

    async def _assert_idle(self) -> str:
        status = await self.klippy_apis.query_objects({"print_stats": ["state"]})
        state = str(status.get("print_stats", {}).get("state", "unknown")).lower()
        if state in {"printing", "paused"}:
            raise self.server.error(
                f"Klippertools updates are blocked while printer state is {state}", 409
            )
        if state not in {"standby", "complete", "cancelled", "error"}:
            raise self.server.error(
                f"Klippertools could not prove the printer is idle (state: {state})", 409
            )
        return state

    async def _handle_update(self, web_request) -> Dict[str, Any]:
        if self.update_task is not None and not self.update_task.done():
            raise self.server.error("A Klippertools update is already running", 409)
        await self._assert_idle()
        updater = (self.repo_path / "scripts" / "update-online.sh").resolve()
        try:
            updater.relative_to(self.repo_path)
        except ValueError as exc:
            raise self.server.error("Unsafe Klippertools updater path", 500) from exc
        if not updater.is_file():
            raise self.server.error(f"Klippertools updater is missing: {updater}", 500)

        now = datetime.now(timezone.utc).isoformat()
        self.update_status = {
            "state": "downloading",
            "message": "Downloading and verifying update",
            "started_at": now,
            "finished_at": None,
            "restart_required": False,
        }
        self.update_task = asyncio.create_task(self._run_update(updater))
        return {"started": True, "started_at": now}

    async def _run_update(self, updater: Path) -> None:
        environment = os.environ.copy()
        environment["HOME"] = str(Path.home())
        try:
            process = await asyncio.create_subprocess_exec(
                str(updater),
                cwd=str(self.repo_path),
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _unused = await process.communicate()
            message = output.decode("utf-8", errors="replace").strip()
            if process.returncode:
                self.update_status.update(
                    {
                        "state": "error",
                        "message": message[-4000:] or f"Updater exited {process.returncode}",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "restart_required": False,
                    }
                )
                logging.error("Klippertools update failed: %s", message)
                return

            self.update_status.update(
                {
                    "state": "complete",
                    "message": "Update installed; restarting Klipper and Moonraker",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "restart_required": True,
                }
            )
            logging.info("Klippertools update completed: %s", message)
            await self._restart_services()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.exception("Klippertools update controller failed")
            self.update_status.update(
                {
                    "state": "error",
                    "message": str(exc),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "restart_required": False,
                }
            )

    async def _restart_services(self) -> None:
        try:
            await self._assert_idle()
        except Exception:
            logging.warning(
                "Klippertools update completed, but a print started before restart"
            )
            self.update_status["message"] = (
                "Update installed; restart Klipper and Moonraker manually after the print"
            )
            return
        try:
            service_name = getattr(self.klippy_connection, "unit_name", "klipper")
            await self.machine.do_service_action("restart", service_name)
            self.eventloop.delay_callback(2.0, self.machine.restart_moonraker_service)
        except Exception:
            # Deployment is complete and recoverable even when the service
            # manager is not permitted to restart a unit.  Keep the flag set so
            # Mainsail tells the user a manual restart remains necessary.
            logging.exception("Klippertools installed but automatic service restart failed")
            self.update_status["message"] = (
                "Update installed; restart Klipper and Moonraker manually"
            )


def load_component(config):
    return Klippertools(config)
