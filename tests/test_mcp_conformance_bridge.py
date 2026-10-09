"""The bridge the weekly conformance run goes through relays, and refuses what it should.

`tools/mcp-conformance/stdio_bridge.py` puts the real stdio server behind loopback HTTP for
the official suite. What the suite reports is only about the server if the bridge passes
messages through unchanged, answers a notification with no body, and turns away a request
that names another host, which is how DNS rebinding reaches a loopback listener.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

_BRIDGE = Path(__file__).resolve().parents[1] / "tools" / "mcp-conformance" / "stdio_bridge.py"


@pytest.fixture(scope="module")
def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    src = str(Path(__file__).resolve().parents[1] / "src")
    env = {**os.environ, "PYTHONPATH": src + os.pathsep + os.environ.get("PYTHONPATH", "")}
    bridge = subprocess.Popen([sys.executable, str(_BRIDGE), "--port", str(free)], env=env)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", free), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield free
    bridge.terminate()
    bridge.wait(timeout=10)


def _post(port: int, message: object, headers: dict | None = None) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    connection.request("POST", "/mcp", json.dumps(message), headers or {})
    response = connection.getresponse()
    return response.status, response.read()


def test_a_request_is_answered_by_the_stdio_server(port):
    status, body = _post(port, {"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
    assert status == 200
    reply = json.loads(body)
    assert reply["id"] == 7
    assert {tool["name"] for tool in reply["result"]["tools"]} >= {"build_part", "compile_spec"}


def test_a_notification_gets_no_body(port):
    status, body = _post(port, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert (status, body) == (202, b"")
    # And the stream is still in step: the next request gets its own answer.
    status, body = _post(port, {"jsonrpc": "2.0", "id": 8, "method": "ping"})
    assert json.loads(body)["id"] == 8


@pytest.mark.parametrize(
    "headers", [{"Host": "evil.example:80"}, {"Origin": "http://evil.example"}]
)
def test_a_request_naming_another_host_is_refused(port, headers):
    status, _body = _post(port, {"jsonrpc": "2.0", "id": 9, "method": "ping"}, headers)
    assert status == 403
