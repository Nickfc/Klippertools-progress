import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


class RequestType:
    GET = "GET"
    POST = "POST"


moonraker_package = types.ModuleType("moonraker")
moonraker_package.__path__ = []
components_package = types.ModuleType("moonraker.components")
components_package.__path__ = []
common_module = types.ModuleType("moonraker.common")
common_module.RequestType = RequestType
sys.modules.setdefault("moonraker", moonraker_package)
sys.modules.setdefault("moonraker.components", components_package)
sys.modules["moonraker.common"] = common_module

MODULE_PATH = Path(__file__).parents[1] / "moonraker" / "klippertools.py"
SPEC = importlib.util.spec_from_file_location(
    "moonraker.components.klippertools", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ServerError(Exception):
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code


class FakeKlippyApis:
    def __init__(self, state="standby"):
        self.state = state

    async def query_objects(self, objects):
        return {"print_stats": {"state": self.state}}


class FakeMachine:
    def __init__(self):
        self.actions = []
        self.moonraker_restarts = 0

    async def do_service_action(self, action, service):
        self.actions.append((action, service))

    async def restart_moonraker_service(self):
        self.moonraker_restarts += 1


class FakeEventLoop:
    def __init__(self):
        self.callbacks = []

    def delay_callback(self, delay, callback):
        self.callbacks.append((delay, callback))


class FakeServer:
    error = ServerError

    def __init__(self, state="standby"):
        self.klippy_apis = FakeKlippyApis(state)
        self.machine = FakeMachine()
        self.klippy_connection = types.SimpleNamespace(unit_name="klipper")
        self.eventloop = FakeEventLoop()
        self.endpoints = []

    def get_event_loop(self):
        return self.eventloop

    def lookup_component(self, name):
        return getattr(self, name)

    def register_endpoint(self, path, request_type, callback):
        self.endpoints.append((path, request_type, callback))


class FakeConfig:
    error = ServerError

    def __init__(self, server):
        self.server = server

    def get_server(self):
        return self.server

    def get(self, name, default):
        return default


class MoonrakerComponentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="klippertools-component-")
        self.home = Path(self.temporary.name)
        (self.home / "klippertools" / "scripts").mkdir(parents=True)
        (self.home / "printer_data").mkdir()
        self.home_patch = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop()
        self.temporary.cleanup()

    def component(self, state="standby"):
        server = FakeServer(state)
        return MODULE.Klippertools(FakeConfig(server)), server

    def test_registers_only_get_status_and_post_update(self):
        component, server = self.component()
        endpoints = [(path, method) for path, method, _callback in server.endpoints]
        self.assertEqual(
            endpoints,
            [
                ("/machine/klippertools/status", RequestType.GET),
                ("/machine/klippertools/update", RequestType.POST),
            ],
        )
        self.assertIsNone(component.update_task)

    def test_idle_guard_blocks_printing_and_paused(self):
        for state in ("printing", "paused"):
            component, _server = self.component(state)
            with self.assertRaises(ServerError) as caught:
                asyncio.run(component._assert_idle())
            self.assertEqual(caught.exception.status_code, 409)

    def test_restart_rechecks_idle_after_deployment(self):
        component, server = self.component("printing")
        asyncio.run(component._restart_services())
        self.assertEqual(server.machine.actions, [])
        self.assertIn("after the print", component.update_status["message"])


if __name__ == "__main__":
    unittest.main()
