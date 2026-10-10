"""Measure interactive responsiveness against `budget.json`, and say whether a release may ship.

Each operation is timed `repeats` times in a fresh process, as a user first meets it, and
its median is compared with its budget. Every timing first checks that the operation
succeeded: a refusal returns fast, and timing one would pass a budget for work that never
ran. A breach counts only if a second full pass reproduces it ("sustained"), so one noisy
sample on a shared runner does not block a release.

    python tools/responsiveness/measure.py --out responsiveness.json
    python tools/responsiveness/measure.py --first-part --out first-part.json

Exit 0 within budget, 1 on a sustained breach. The JSON is the record a release keeps.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_BUDGET = json.loads((Path(__file__).with_name("budget.json")).read_text(encoding="utf-8"))
_PASSING = _ROOT / "examples" / "transmission_shaft.spec.yaml"  # a card that passes, and draws


def _cli(*argv: str, produces: Path | None = None) -> float:
    if produces is not None and produces.exists():
        produces.unlink()
    start = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-m", "anvilate.cli", *argv], capture_output=True, text=True
    )
    elapsed = time.perf_counter() - start
    if done.returncode != 0 or (produces is not None and not produces.exists()):
        raise SystemExit(f"`anvilate {' '.join(argv)}` did not succeed: {done.stderr[-400:]}")
    return elapsed


class _Session:
    """One fresh stdio server, as an agent's first connection meets it."""

    def __init__(self) -> None:
        self._child = subprocess.Popen(
            [sys.executable, "-m", "anvilate.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0

    def call(self, method: str, params: dict) -> tuple[float, dict]:
        assert self._child.stdin is not None and self._child.stdout is not None
        self._id += 1
        start = time.perf_counter()
        message = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        self._child.stdin.write(json.dumps(message) + "\n")
        self._child.stdin.flush()
        reply = json.loads(self._child.stdout.readline())
        elapsed = time.perf_counter() - start
        result = reply.get("result")
        if result is None or result.get("isError"):
            raise SystemExit(f"{method} {params.get('name', '')} did not succeed: {reply}")
        return elapsed, result

    def tool(self, name: str, arguments: dict) -> tuple[float, dict]:
        return self.call("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        self._child.terminate()
        self._child.wait(timeout=10)


def _mcp_pass() -> dict[str, float]:
    import yaml

    spec = yaml.safe_load(_PASSING.read_text(encoding="utf-8"))
    session = _Session()
    try:
        timings: dict[str, float] = {}
        start = time.perf_counter()
        session.call(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "responsiveness", "version": "1"},
            },
        )
        timings["mcp initialize"] = time.perf_counter() - start
        timings["mcp tools/list"], _ = session.call("tools/list", {})
        timings["mcp compile_spec"], _ = session.tool("compile_spec", {"document": spec})
        timings["mcp run_validation"], card = session.tool("run_validation", {"spec": spec})
        handle = card["structuredContent"]["subject"]
        timings["mcp read_scorecard"], _ = session.tool("read_scorecard", {"subject": handle})
        timings["mcp build_part"], built = session.tool("build_part", {"spec": spec})
        part = built["structuredContent"]["subject"]
        timings["mcp render_viewport"], _ = session.tool(
            "render_viewport", {"subject": part, "view": "iso"}
        )
        timings["mcp measure_geometry"], _ = session.tool(
            "measure_geometry", {"subject": part, "query": "volume"}
        )
        timings["mcp export_artifact"], _ = session.tool(
            "export_artifact", {"subject": handle, "format": "evidence_bundle"}
        )
        timings["mcp describe_part"], _ = session.tool(
            "describe_part", {"element_type": "mounting_plate"}
        )
        return timings
    finally:
        session.close()


def _one_pass(repeats: int) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {name: [] for name in _BUDGET["operations"]}
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        # Each repeat gets its own content-addressed store, so nothing is served from a
        # previous repeat's cache: every call is the first of its kind.
        for repeat in range(repeats):
            os.environ["ANVILATE_DATA_HOME"] = str(work / f"data-{repeat}")
            samples["cli check"].append(_cli("check", str(_PASSING)))
            step = work / "part.step"
            samples["cli build"].append(
                _cli("build", str(_PASSING), "--output", str(step), produces=step)
            )
            sheet = work / "part.html"
            samples["cli view"].append(
                _cli("view", str(_PASSING), "--output", str(sheet), "--no-open", produces=sheet)
            )
            for name, seconds in _mcp_pass().items():
                samples[name].append(seconds)
    return samples


def _judge(samples: dict[str, list[float]]) -> dict[str, dict]:
    verdicts = {}
    for name, budget in _BUDGET["operations"].items():
        median = statistics.median(samples[name])
        verdicts[name] = {
            "budget_seconds": budget["seconds"],
            "median_seconds": round(median, 4),
            "samples_seconds": [round(value, 4) for value in samples[name]],
            "within": median <= budget["seconds"],
        }
    return verdicts


def _first_part() -> dict:
    """A fresh virtual environment, the install, and one validated STEP export."""
    with tempfile.TemporaryDirectory() as scratch:
        venv = Path(scratch) / "venv"
        start = time.perf_counter()
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts" if os.name == "nt" else "bin") / "python"
        subprocess.run(
            [str(python), "-m", "pip", "install", "-q", f"{_ROOT}[geometry,export]"], check=True
        )
        step = Path(scratch) / "first.step"
        subprocess.run(
            [str(python), "-m", "anvilate.cli", "build", str(_PASSING), "--output", str(step)],
            check=True,
        )
        if not step.exists():
            raise SystemExit("the first part was not written")
        elapsed = time.perf_counter() - start
    budget = _BUDGET["time_to_first_part"]["seconds"]
    return {"budget_seconds": budget, "seconds": round(elapsed, 1), "within": elapsed <= budget}


def _profile() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "runner": os.environ.get("RUNNER_NAME"),
        "image": os.environ.get("ImageOS"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=_BUDGET["repeats"])
    parser.add_argument("--first-part", action="store_true")
    args = parser.parse_args()

    if args.first_part:
        record = {"profile": _profile(), "time_to_first_part": _first_part()}
        breached = not record["time_to_first_part"]["within"]
    else:
        first = _judge(_one_pass(args.repeats))
        breaches = sorted(name for name, verdict in first.items() if not verdict["within"])
        record = {"profile": _profile(), "operations": first}
        if breaches:
            # Sustained or noise: measure again, and count only what breaches twice.
            second = _judge(_one_pass(args.repeats))
            record["second_pass"] = {name: second[name] for name in breaches}
            breaches = [name for name in breaches if not second[name]["within"]]
        record["sustained_breaches"] = breaches
        breached = bool(breaches)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for name, verdict in record.get("operations", {}).items():
        mark = "ok  " if verdict["within"] else "OVER"
        median, budget = verdict["median_seconds"], verdict["budget_seconds"]
        print(f"{mark} {name:22} {median:8.3f} s / {budget} s")
    if "time_to_first_part" in record:
        ttfp = record["time_to_first_part"]
        print(f"time to first part {ttfp['seconds']} s / {ttfp['budget_seconds']} s")
    if breached:
        print("sustained breach: " + ", ".join(record.get("sustained_breaches", ["first part"])))
    return 1 if breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
