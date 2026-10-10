"""Run the README's three steps against an installed Anvilate, from outside its checkout.

    python -m build --wheel
    python -m venv /tmp/clean && /tmp/clean/bin/pip install "dist/<the wheel>[geometry,export,pdf]"
    cd "$(mktemp -d)" && /tmp/clean/bin/python <checkout>/tools/wheel-check/readme_steps.py

The suite runs against `src/` through an editable install, so it cannot see a data file the
wheel leaves out, a console script that does not start, or a path that only resolves inside
the repository. This does what a newcomer does after `pip install`: it starts the
`anvilate-mcp` the install put on the path, connects the way an agent does, and asks the
README's questions. It reads nothing from the checkout; the specs it sends are the examples
the installed server hands out.

Exits 0 when every step answers, and 1 naming the first that did not.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]


class _Server:
    """`anvilate-mcp` on stdio: one JSON-RPC message per line, as a client speaks to it."""

    def __init__(self, command: Path, out: Path) -> None:
        self._process = subprocess.Popen(  # noqa: S603 - the console script under test
            [str(command), "--out", str(out)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._sent = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._sent += 1
        message = {"jsonrpc": "2.0", "id": self._sent, "method": method, "params": params or {}}
        assert self._process.stdin is not None and self._process.stdout is not None
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise SystemExit(f"anvilate-mcp stopped answering at {method}")
        response = json.loads(line)
        if "error" in response:
            raise SystemExit(f"{method} {params}: {response['error']['message']}")
        return response["result"]

    def tool(self, name: str, **arguments: object) -> dict:
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise SystemExit(f"{name}: {result['content'][0]['text']}")
        return result

    def close(self) -> None:
        assert self._process.stdin is not None
        self._process.stdin.close()
        self._process.wait(timeout=30)


def _example(server: _Server, element_type: str) -> dict:
    described = server.tool("describe_part", element_type=element_type)
    (part,) = described["structuredContent"]["catalog"]["parts"]
    return part["example"]


def main() -> int:
    import anvilate

    # An editable install imports from a source tree, this one or another, and a run from
    # inside the checkout can read its files: either would pass on what the wheel lacks.
    installed, here = Path(anvilate.__file__).resolve(), Path.cwd().resolve()
    if "site-packages" not in installed.parts or CHECKOUT in (here, *here.parents):
        print(
            "failed: this must run on an installed wheel, from outside the checkout; "
            f"anvilate is {installed} and the working directory is {here}"
        )
        return 1
    commands = Path(sys.executable).parent
    steps: list[str] = []

    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "anvilate-out"
        # Step 2 of the README: the agent's client starts the server and lists its tools.
        server = _Server(commands / "anvilate-mcp", out)
        hello = server.call(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wheel-check", "version": "0"},
            },
        )
        assert hello["serverInfo"]["name"] == "anvilate" and hello["instructions"], hello
        tools = {tool["name"] for tool in server.call("tools/list")["tools"]}
        needed = {"describe_part", "build_part", "render_viewport", "run_validation"}
        assert needed | {"export_artifact"} <= tools, sorted(tools)
        steps.append(f"the server starts and lists {len(tools)} tools")

        # "What parts can you draw?"
        catalog = server.tool("describe_part")["structuredContent"]["catalog"]["parts"]
        drawable = [part["element_type"] for part in catalog if part["drawable"]]
        assert {"mounting_plate", "lifting_lug", "base_plate"} <= set(drawable), drawable
        steps.append(f"{len(drawable)} of {len(catalog)} elements are drawn")

        # "Draw a mounting plate ... and give me the STEP file."
        built = server.tool("build_part", spec=_example(server, "mounting_plate"))
        geometry = built["structuredContent"]["geometry"]
        assert geometry["valid"] and geometry["volumeMm3"] > 0, geometry
        subject = built["structuredContent"]["subject"]
        picture = server.tool("render_viewport", subject=subject, view="iso")
        assert any(item["type"] == "image" for item in picture["content"]), picture["content"]
        exported = server.tool("export_artifact", subject=subject, format="step")
        step = Path(exported["structuredContent"]["file"]["path"])
        assert step.parent == out.resolve() and step.read_text("utf-8").startswith("ISO-10303-21")
        steps.append(f"a mounting plate is built, drawn and written to {step.name}")

        # "Check a lifting lug ... for a 50 kN load and a safety factor of 2."
        lug = _example(server, "lifting_lug")
        lug["constraints"] = {"min_safety_factor": {"value": 2.0, "origin": "user_stated"}}
        card = server.tool("run_validation", spec=lug)["structuredContent"]["scorecard"]
        judged = [entry for entry in card["entries"] if entry.get("safety_factor") is not None]
        assert card["status"] in {"pass", "fail"} and len(judged) >= 2, card["status"]
        steps.append(f"a lifting lug is screened: {card['status']}, {len(judged)} checks judged")
        server.close()

        # The same verdict from the command line the install put on the path.
        spec = Path(folder) / "lug.yaml"
        spec.write_text(json.dumps(lug), encoding="utf-8")
        checked = subprocess.run(  # noqa: S603 - the console script under test
            [str(commands / "anvilate"), "check", str(spec)], capture_output=True, text=True
        )
        assert checked.returncode in (0, 1) and "padeye" in checked.stdout, checked.stderr
        assert (checked.returncode == 0) == (card["status"] == "pass"), checked.stdout
        steps.append(f"`anvilate check` agrees, exit {checked.returncode}")

    for step in steps:
        print(f"ok: {step}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as failed:
        print(f"failed: {failed}")
        sys.exit(1)
