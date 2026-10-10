"""Relay the MCP conformance suite's HTTP requests to the real stdio server, unchanged.

The official suite (`npx @modelcontextprotocol/conformance server --url ...`) drives a server
over HTTP only. Stdio support is modelcontextprotocol/conformance#258, still open. Anvilate
speaks stdio only. This bridge starts `python -m anvilate.mcp` as a child process and copies
each POSTed JSON-RPC message to its stdin as one line, answering with the line the server
writes back, or 202 for a notification, which gets no reply. What the suite tests is the
shipped stdio session, revision negotiation included, not a second implementation of it.

Loopback only. It exists to run the suite and stops when the suite does:

    python tools/mcp-conformance/stdio_bridge.py --port 3971 &
    npx -y @modelcontextprotocol/conformance@0.1.16 server \\
        --url http://127.0.0.1:3971/mcp \\
        --expected-failures tools/mcp-conformance/expected-failures.yaml
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

_LOOPBACK = {"127.0.0.1", "localhost", "[::1]"}


class _Server:
    """One stdio server, one message in flight at a time, as a stdio client would have it."""

    def __init__(self) -> None:
        self._child = subprocess.Popen(
            [sys.executable, "-m", "anvilate.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()

    def exchange(self, message: object) -> str | None:
        expects_reply = not (isinstance(message, dict) and "id" not in message)
        with self._lock:
            assert self._child.stdin is not None and self._child.stdout is not None
            self._child.stdin.write(json.dumps(message) + "\n")
            self._child.stdin.flush()
            return self._child.stdout.readline() if expects_reply else None


# How much of a refused request's body is read before the refusal is sent.
_REFUSED_BODY = 8 * 1024 * 1024


def _handler(server: _Server) -> type[BaseHTTPRequestHandler]:
    class Relay(BaseHTTPRequestHandler):
        def _foreign(self) -> bool:
            # A listener on loopback is still reachable from a browser page through DNS
            # rebinding, so a Host or Origin naming anything but this machine is refused.
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            origin = self.headers.get("Origin")
            return host not in _LOOPBACK or (
                origin is not None and (urlsplit(origin).hostname or "") not in _LOOPBACK
            )

        def do_POST(self) -> None:  # noqa: N802 - the stdlib's spelling
            if self._foreign():
                # Read what was sent before refusing it. Closing a socket with the body
                # still unread makes the kernel reset the connection, and the client then
                # gets the reset where the 403 was: 8 of 60 refusals of a 600 kB body were
                # lost that way. Read in pieces and up to a bound, since the sender is the
                # one being refused; past it the reset is theirs to have.
                try:
                    unread = min(int(self.headers.get("Content-Length", 0)), _REFUSED_BODY)
                except ValueError:
                    unread = 0
                while unread > 0:
                    piece = self.rfile.read(min(unread, 65536))
                    if not piece:
                        break
                    unread -= len(piece)
                self.send_response(403)
                self.end_headers()
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                message = json.loads(body)
            except ValueError:
                # The stdio server answers unparseable input itself; send it the raw line.
                message = None
            reply = (
                server.exchange(message)
                if message is not None
                else self._raw(server, body.decode("utf-8", "replace"))
            )
            if reply is None:
                self.send_response(202)
                self.end_headers()
                return
            payload = reply.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            # No server-initiated stream: stdio has none to offer.
            self.send_response(405)
            self.end_headers()

        def do_DELETE(self) -> None:  # noqa: N802
            self.send_response(405)
            self.end_headers()

        @staticmethod
        def _raw(server: _Server, line: str) -> str:
            with server._lock:  # noqa: SLF001 - the same single-flight rule
                assert server._child.stdin is not None and server._child.stdout is not None
                server._child.stdin.write(line.replace("\n", " ") + "\n")
                server._child.stdin.flush()
                return server._child.stdout.readline()

        def log_message(self, *args: object) -> None:
            pass

    return Relay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=3971)
    port = parser.parse_args().port
    ThreadingHTTPServer(("127.0.0.1", port), _handler(_Server())).serve_forever()


if __name__ == "__main__":
    main()
