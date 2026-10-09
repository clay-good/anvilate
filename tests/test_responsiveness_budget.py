"""The responsiveness budget is declared once, measured as declared, and blocks only when sustained.

`tools/responsiveness/measure.py` is what a release runs on the reference profile
(add-interaction-quality 6.1). These tests hold its logic offline: the budget names every
operation the harness times and every interactive MCP tool, the no-progress command fits the
CLI's own responsiveness threshold, and a breach blocks only when a second pass repeats it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "responsiveness"


@pytest.fixture(scope="module")
def measure():
    spec = importlib.util.spec_from_file_location("measure", _TOOL / "measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _budget() -> dict:
    return json.loads((_TOOL / "budget.json").read_text(encoding="utf-8"))


def test_every_interactive_mcp_tool_is_budgeted():
    """A tool added to the catalogue without a budget is a wait nobody measures. The FEA
    task is excluded: it is dispatched as a task and reports its own progress."""
    from anvilate.mcp import tool_catalog

    budgeted = {name.removeprefix("mcp ") for name in _budget()["operations"]}
    tools = {tool.name for tool in tool_catalog()} - {"run_fea_validation"}
    assert tools <= budgeted, sorted(tools - budgeted)


def test_a_command_without_progress_fits_the_threshold_it_promises():
    from anvilate.cli import RESPONSIVENESS_THRESHOLD_SECONDS

    assert _budget()["operations"]["cli check"]["seconds"] <= RESPONSIVENESS_THRESHOLD_SECONDS


def _samples(seconds: float) -> dict[str, list[float]]:
    return {name: [seconds] * 3 for name in _budget()["operations"]}


def test_the_harness_times_exactly_what_the_budget_names(measure, monkeypatch, tmp_path):
    # The harness points each repeat at its own store through the environment; saved here so
    # the change is undone when the test ends.
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path))
    seen: list[str] = []
    monkeypatch.setattr(measure, "_cli", lambda *argv, produces=None: seen.append(argv[0]) or 0.1)
    monkeypatch.setattr(
        measure,
        "_mcp_pass",
        lambda: {name: 0.1 for name in _budget()["operations"] if name.startswith("mcp ")},
    )
    samples = measure._one_pass(2)
    assert set(samples) == set(_budget()["operations"])
    assert all(len(values) == 2 for values in samples.values()), samples
    assert set(seen) == {"check", "build", "view"}


def _run(measure, monkeypatch, tmp_path, passes):
    results = iter(passes)
    monkeypatch.setattr(measure, "_one_pass", lambda repeats: next(results))
    out = tmp_path / "record.json"
    monkeypatch.setattr("sys.argv", ["measure.py", "--out", str(out)])
    return measure.main(), json.loads(out.read_text(encoding="utf-8"))


def test_a_breach_one_pass_only_is_noise_and_does_not_block(measure, monkeypatch, tmp_path):
    slow = _samples(0.1)
    slow["cli check"] = [9.0, 9.0, 9.0]
    code, record = _run(measure, monkeypatch, tmp_path, [slow, _samples(0.1)])
    assert code == 0
    assert record["sustained_breaches"] == []
    assert record["second_pass"]["cli check"]["within"] is True


def test_a_breach_both_passes_repeat_blocks_the_release(measure, monkeypatch, tmp_path):
    slow = _samples(0.1)
    slow["mcp build_part"] = [60.0, 60.0, 60.0]
    code, record = _run(measure, monkeypatch, tmp_path, [slow, slow])
    assert code == 1
    assert record["sustained_breaches"] == ["mcp build_part"]


def test_a_refused_operation_is_not_timed(measure, monkeypatch):
    """A refusal returns fast; timing one passes a budget for work that never ran."""

    class Done:
        returncode = 3
        stderr = "anvilate build: output already exists"

    monkeypatch.setattr(measure.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(SystemExit, match="did not succeed"):
        measure._cli("build", "x.yaml")
