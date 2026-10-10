"""The durable MCP Tasks lifecycle: create, poll, cancel, and reconnect."""

from __future__ import annotations

import os
import threading
import time

from anvilate._mcp_tasks import TaskStore
from anvilate.mcp import handle_request
from anvilate.spec import (
    AcceptanceCriteria,
    DesignSpec,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    ValidationTier,
)
from anvilate.units import UnitSystem


def _spec_document() -> dict:
    return DesignSpec(
        name="task_plate",
        description="A plate whose T3 request crosses the durable task boundary.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T3_FEA]),
    ).model_dump(mode="json")


def _task_call(spec: dict | None = None) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "run_fea_validation",
                "arguments": {
                    "spec": _spec_document() if spec is None else spec,
                    "convergence_tol": 1e-4,
                },
                "_meta": {
                    "io.modelcontextprotocol/clientCapabilities": {
                        "extensions": {"io.modelcontextprotocol/tasks": {}}
                    }
                },
            },
        }
    )


def _task_request(method: str, task_id: str, **params) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": method,
            "params": {"taskId": task_id, **params},
        }
    )


def _poll_terminal(task_id: str, timeout: float = 90.0) -> dict:
    """The task's result once it is terminal.

    The wait is patience, not a requirement: these tests hold that a task finishes, and a
    worker is a fresh interpreter that has to import the library first. Five seconds was
    enough on a quiet machine and failed three tests on one at load 15, twice. It returns
    as soon as the task is terminal, so the generous bound costs a passing run nothing.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _task_request("tasks/get", task_id)["result"]
        if result["status"] in {"completed", "cancelled", "failed"}:
            return result
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} did not reach a terminal status")


def test_fea_task_is_durable_before_return_and_retrievable_after_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    created = _task_call()["result"]

    assert created["resultType"] == "task"
    assert created["status"] == "working"
    assert created["taskId"].startswith("task_") and len(created["taskId"]) == 69
    assert created["ttlMs"] is None
    assert created["_meta"]["dev.anvilate/progress"] == {
        "activity": "Queued run_fea_validation.",
        "completedUnits": 0,
        "totalUnits": None,
        "indeterminate": True,
    }

    # A separate store object can resolve it immediately. The handle is durable state, not
    # memory held by the handler that answered the tool call.
    assert TaskStore(tmp_path).public(created["taskId"])["taskId"] == created["taskId"]

    completed = _poll_terminal(created["taskId"])
    assert completed["resultType"] == "complete"
    assert completed["status"] == "completed"
    assert completed["_meta"]["dev.anvilate/progress"] == {
        "activity": "Completed run_fea_validation.",
        "completedUnits": 1,
        "totalUnits": 1,
        "indeterminate": False,
    }
    tool_result = completed["result"]
    assert tool_result["isError"] is False
    card = tool_result["structuredContent"]["scorecard"]
    assert card["status"] == "not_evaluated"
    t3 = next(entry for entry in card["entries"] if entry["name"] == "T3 FEA")
    assert "ships no finite-element solver backend" in t3["detail"]


def test_cancellation_terminates_the_worker_and_returns_not_evaluated(monkeypatch, tmp_path):
    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    created = _task_call()["result"]
    task_id = created["taskId"]
    pid = TaskStore(tmp_path).read(task_id)["_pid"]

    acknowledged = _task_request("tasks/cancel", task_id)["result"]
    assert acknowledged == {"resultType": "complete"}

    completed = _poll_terminal(task_id)
    assert completed["status"] == "completed"
    assert "Cancellation honored" in completed["statusMessage"]
    cancelled_progress = completed["_meta"]["dev.anvilate/progress"]
    assert cancelled_progress["completedUnits"] == 0
    assert cancelled_progress["totalUnits"] == 1
    assert cancelled_progress["indeterminate"] is False
    card = completed["result"]["structuredContent"]["scorecard"]
    assert card["status"] == "not_evaluated"
    assert "cancelled" in card["entries"][0]["detail"]

    deadline = time.monotonic() + 3.0
    running = True
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            running = False
        if not running:
            break
        time.sleep(0.02)
    assert not running, "the task record completed but its worker process survived cancellation"


def test_a_transient_permission_error_while_reaping_does_not_break_cancellation(
    monkeypatch, tmp_path
):
    """macOS may briefly return EPERM for a group that accepted SIGTERM and is exiting."""
    import signal

    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    store.attach_worker(task_id, 12345)
    monkeypatch.setattr(store, "_owns_worker", lambda pid, owned_task: True)
    calls = []

    def killpg(pid, requested_signal):
        calls.append((pid, requested_signal))
        if requested_signal == signal.SIGTERM:
            return
        if len([call for call in calls if call[1] == 0]) == 1:
            raise PermissionError("group is being reaped")
        raise ProcessLookupError

    monkeypatch.setattr(os, "killpg", killpg)
    store.cancel(task_id, {"cancelled": True}, "Cancellation honored.")

    assert calls == [(12345, signal.SIGTERM), (12345, 0), (12345, 0)]
    assert store.read(task_id)["status"] == "completed"


def test_task_update_is_an_ack_and_unknown_handles_are_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    task_id = _task_call()["result"]["taskId"]
    assert _task_request("tasks/update", task_id, inputResponses={})["result"] == {
        "resultType": "complete"
    }

    unknown = "task_" + "0" * 64
    for method in ("tasks/get", "tasks/update", "tasks/cancel"):
        extra = {"inputResponses": {}} if method == "tasks/update" else {}
        error = _task_request(method, unknown, **extra)["error"]
        assert error["code"] == -32602
        assert "not a readable task" in error["message"]


def test_task_handles_are_unguessable_and_not_content_addresses(tmp_path):
    store = TaskStore(tmp_path)
    first = store.create("run_fea_validation", {"spec": {}})
    second = store.create("run_fea_validation", {"spec": {}})
    assert first["taskId"] != second["taskId"]
    assert first["_nonce"] != second["_nonce"]


def test_a_failed_task_finishes_progress_without_claiming_a_completed_unit(tmp_path):
    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    store.fail(task_id, {"code": -32603, "message": "solver failed"}, "Failed.")

    task = store.public(task_id)
    assert task["status"] == "failed"
    assert task["_meta"]["dev.anvilate/progress"] == {
        "activity": "Failed.",
        "completedUnits": 0,
        "totalUnits": 1,
        "indeterminate": False,
    }


def test_invalid_spec_is_a_task_refusal_not_an_internal_server_defect(monkeypatch, tmp_path):
    """The worker preserves the handler's error category across the process boundary."""
    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    created = _task_call({})["result"]

    failed = _poll_terminal(created["taskId"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == -32602
    assert "spec." in failed["error"]["message"]
    assert "internal" not in failed["error"]["message"].lower()
    assert failed["error"]["data"]["issues"]
    assert failed["error"]["data"]["remedies"]
    assert any("name" in remedy for remedy in failed["error"]["data"]["remedies"])
    progress = failed["_meta"]["dev.anvilate/progress"]
    assert progress["completedUnits"] == 0
    assert progress["indeterminate"] is False

    # The other expected refusal keeps its distinct category too. Drive the worker in this
    # process so the test can replace the future task handler with the unavailable branch.
    import anvilate.mcp as mcp
    from anvilate._mcp_tasks import _run_worker

    def unavailable(_arguments):
        raise mcp._Unavailable("the configured solver backend is unavailable")

    monkeypatch.setitem(mcp._TASK_DISPATCH, "run_fea_validation", unavailable)
    store = TaskStore(tmp_path)
    record = store.create("run_fea_validation", {"spec": _spec_document()})
    assert _run_worker(record["taskId"], record["_nonce"]) == 1
    unavailable_task = store.public(record["taskId"])
    assert unavailable_task["status"] == "failed"
    assert unavailable_task["error"] == {
        "code": -32000,
        "message": "the configured solver backend is unavailable",
    }


def test_a_late_worker_attachment_cannot_overwrite_a_terminal_result(monkeypatch, tmp_path):
    """Every task transition is one serialized read-modify-write operation.

    The launcher attaches the PID just after spawning. A fast worker can finish during that
    write; without the record lock, the launcher then restores its stale ``working`` copy
    over the completed result and the handle polls forever.
    """
    store = TaskStore(tmp_path)
    record = store.create("run_fea_validation", {"spec": {}})
    task_id = record["taskId"]
    attachment_is_ready_to_write = threading.Event()
    allow_attachment_to_write = threading.Event()
    original_write = store._write

    def delayed_write(named_task: str, candidate: dict) -> None:
        if candidate.get("_pid") == 12345 and candidate["status"] == "working":
            attachment_is_ready_to_write.set()
            assert allow_attachment_to_write.wait(2.0)
        original_write(named_task, candidate)

    monkeypatch.setattr(store, "_write", delayed_write)
    attachment = threading.Thread(target=store.attach_worker, args=(task_id, 12345))
    attachment.start()
    assert attachment_is_ready_to_write.wait(2.0)

    completion = threading.Thread(
        target=store.complete,
        args=(task_id, {"structuredContent": {"scorecard": {}}}, "Completed."),
    )
    completion.start()
    time.sleep(0.05)
    allow_attachment_to_write.set()
    attachment.join(2.0)
    completion.join(2.0)

    assert not attachment.is_alive() and not completion.is_alive()
    final = store.read(task_id)
    assert final["status"] == "completed"
    assert final["result"]["structuredContent"] == {"scorecard": {}}


# A stand-in worker: holds its task's lease, as the real one does, and starts a solver child in
# its own process group. `stubborn` makes the child ignore SIGTERM, the way a solver that traps
# the signal to write a restart file does.
_WORKER = """
import fcntl, signal, subprocess, sys, time
lease_path, ready, stubborn = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
lease = open(lease_path, "a+")
fcntl.flock(lease, fcntl.LOCK_EX)
solver = (
    "import signal, sys, time\\n"
    + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n" if stubborn else "")
    + "open(sys.argv[1], 'w').close()\\n"
    + "time.sleep(60)\\n"
)
child = subprocess.Popen([sys.executable, "-c", solver, ready + ".solver"])
while True:
    try:
        open(ready + ".solver").close()
        break
    except OSError:
        time.sleep(0.01)
with open(ready, "w") as marker:
    marker.write(str(child.pid))
time.sleep(60)
"""


def _cancel_a_worker_with_a_solver_child(tmp_path, *, stubborn: bool) -> tuple[int, int]:
    import subprocess
    import sys

    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    lease = store._path(task_id).with_suffix(".worker")
    ready = tmp_path / "ready"
    worker = subprocess.Popen(
        [sys.executable, "-c", _WORKER, str(lease), str(ready), "1" if stubborn else "0"],
        start_new_session=True,
    )
    threading.Thread(target=worker.wait, daemon=True).start()
    store.attach_worker(task_id, worker.pid)
    deadline = time.monotonic() + 10.0
    while not (ready.exists() and ready.read_text()):
        assert time.monotonic() < deadline, "the stand-in worker never started its solver"
        time.sleep(0.02)
    solver = int(ready.read_text())
    store.cancel(task_id, {"cancelled": True}, "Cancellation honored.")
    return worker.pid, solver


def _gone(pid: int, within: float) -> bool:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.02)
    return False


def test_cancellation_terminates_the_solver_the_worker_started(tmp_path):
    """Interaction-quality 1.5: the whole process group goes, not only the coordinator."""
    worker, solver = _cancel_a_worker_with_a_solver_child(tmp_path, stubborn=False)
    assert _gone(solver, 5.0), "the solver child survived its task's cancellation"
    assert _gone(worker, 5.0)


def test_a_solver_that_ignores_sigterm_is_killed_after_the_grace_period(tmp_path):
    """A trapped SIGTERM does not keep a cancelled solver running."""
    worker, solver = _cancel_a_worker_with_a_solver_child(tmp_path, stubborn=True)
    assert _gone(solver, 5.0), "a solver ignoring SIGTERM outlived its task's cancellation"
    assert _gone(worker, 5.0)


def test_the_docs_quote_the_grace_the_code_gives():
    from pathlib import Path

    from anvilate._mcp_tasks import CANCEL_GRACE_SECONDS

    docs = Path(__file__).parents[1] / "docs"
    for page in ("agent-mcp-integration.md", "mcp-tool-contracts.md"):
        assert f"{CANCEL_GRACE_SECONDS:g}-second grace" in (docs / page).read_text(), page


def test_worker_launch_failure_is_a_durable_failed_task(monkeypatch, tmp_path):
    import subprocess

    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))

    def cannot_start(*args, **kwargs):
        raise OSError("worker process limit reached")

    monkeypatch.setattr(subprocess, "Popen", cannot_start)
    created = _task_call()["result"]
    assert created["resultType"] == "task"
    assert created["status"] == "failed"
    failed = _poll_terminal(created["taskId"])
    assert failed["error"]["code"] == -32603
    assert "worker process limit reached" in failed["error"]["message"]
    assert failed["_meta"]["dev.anvilate/progress"]["completedUnits"] == 0
    assert "result" not in failed
    assert handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]


def test_workers_that_exit_without_results_do_not_leave_tasks_working(monkeypatch, tmp_path):
    import subprocess
    import sys

    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    popen = subprocess.Popen
    for code in (0, 7, -15):
        script = (
            f"import os, signal; os._exit({code})"
            if code >= 0
            else ("import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        )

        def exit_before_result(command, *, script=script, **kwargs):
            return popen([sys.executable, "-c", script], **kwargs)

        monkeypatch.setattr(subprocess, "Popen", exit_before_result)
        created = _task_call()["result"]
        failed = _poll_terminal(created["taskId"])
        assert failed["status"] == "failed"
        assert failed["error"]["code"] == -32603
        assert str(code) in failed["error"]["message"]
        assert "without recording" in failed["error"]["message"]
        assert "result" not in failed
        assert failed["_meta"]["dev.anvilate/progress"]["indeterminate"] is False


def test_reaping_cannot_replace_a_workers_terminal_result(tmp_path):
    from anvilate._mcp_tasks import _reap_worker

    store = TaskStore(tmp_path)
    for outcome in ("complete", "fail", "cancel"):
        record = store.create("run_fea_validation", {"spec": {}})
        task_id = record["taskId"]

        class Worker:
            def wait(self, outcome=outcome, task_id=task_id):
                getattr(store, outcome)(task_id, {"original": outcome}, "Original outcome.")
                return 7

        _reap_worker(store, task_id, Worker())
        finished = store.public(task_id)
        assert finished["statusMessage"] == "Original outcome."
        assert finished["error" if outcome == "fail" else "result"] == {"original": outcome}


def test_recovery_uses_an_execution_lease_not_a_reusable_pid(tmp_path):
    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    with store.execution_lease(task_id):
        store.enable_recovery(task_id)
        # This PID is alive, but it is not proof that the task has an owner.
        store.attach_worker(task_id, os.getpid())
        assert TaskStore(tmp_path).public(task_id)["status"] == "working"
    recovered = TaskStore(tmp_path).public(task_id)
    assert recovered["status"] == "failed"
    assert recovered["error"]["code"] == -32603
    assert "owner" in recovered["error"]["message"]
    assert recovered["_meta"]["dev.anvilate/progress"]["completedUnits"] == 0
    assert TaskStore(tmp_path).public(task_id) == recovered


def test_recovery_does_not_guess_about_legacy_records(tmp_path):
    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    assert store.public(task_id)["status"] == "working"


def test_recovery_preserves_terminal_records(tmp_path):
    store = TaskStore(tmp_path)
    for outcome in ("complete", "fail", "cancel"):
        task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
        with store.execution_lease(task_id):
            store.enable_recovery(task_id)
            getattr(store, outcome)(task_id, {"original": outcome}, "Original outcome.")
        record = store.public(task_id)
        assert record["statusMessage"] == "Original outcome."
        assert record["error" if outcome == "fail" else "result"] == {"original": outcome}


def test_recovery_does_not_treat_a_lock_access_error_as_abandonment(monkeypatch, tmp_path):
    import fcntl

    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    with store.execution_lease(task_id):
        store.enable_recovery(task_id)

    def inaccessible(*args):
        raise PermissionError("lease inaccessible")

    monkeypatch.setattr(fcntl, "flock", inaccessible)
    assert store.public(task_id)["status"] == "working"


# The launcher exits before the worker imports Anvilate. Only the inherited OS lock
# protects that startup interval; no Python worker code has acquired a lease yet.
_ORPHAN_LAUNCHER = '''
import json, os, subprocess, sys
from anvilate._mcp_tasks import launch_task
popen = subprocess.Popen
worker = """
import os, sys, time
from pathlib import Path
gate = Path(sys.argv[1])
deadline = time.monotonic() + 10
while not gate.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
if sys.argv[2] == "crash":
    os._exit(7)
if sys.argv[2] == "killed":
    import signal
    os.kill(os.getpid(), signal.SIGKILL)
from anvilate._mcp_tasks import _run_worker
raise SystemExit(_run_worker(sys.argv[3], sys.argv[4], int(sys.argv[5])))
"""
def delayed_worker(command, **kwargs):
    return popen([sys.executable, "-c", worker, sys.argv[1], sys.argv[2], *command[4:]], **kwargs)
subprocess.Popen = delayed_worker
print(json.dumps(launch_task("run_fea_validation", {"spec": json.loads(sys.argv[3])})), flush=True)
os._exit(0)
'''


def test_reconnecting_after_launcher_exit_recovers_only_an_abandoned_worker(monkeypatch, tmp_path):
    import json
    import subprocess
    import sys

    monkeypatch.setenv("ANVILATE_TASK_STORE", str(tmp_path))
    for outcome in ("crash", "killed", "finish"):
        gate = tmp_path / outcome
        try:
            launcher = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _ORPHAN_LAUNCHER,
                    str(gate),
                    outcome,
                    json.dumps(_spec_document()),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            created = json.loads(launcher.stdout)
            task_id = created["taskId"]
            assert _task_request("tasks/get", task_id)["result"]["status"] == "working"
            gate.touch()
            terminal = _poll_terminal(task_id)
            if outcome == "finish":
                assert terminal["status"] == "completed"
                assert (
                    terminal["result"]["structuredContent"]["scorecard"]["status"]
                    == "not_evaluated"
                )
            else:
                assert terminal["status"] == "failed"
                assert terminal["error"]["code"] == -32603
        finally:
            gate.touch()


def test_monitor_keeps_ownership_until_the_exit_code_is_persisted(tmp_path):
    import pytest

    from anvilate._mcp_tasks import _reap_worker

    store = TaskStore(tmp_path)
    task_id = store.create("run_fea_validation", {"spec": {}})["taskId"]
    with store.execution_lease(task_id) as lease:
        store.enable_recovery(task_id)
        monitor_fd = os.dup(lease.fileno())
    try:
        assert store.public(task_id)["status"] == "working"

        class Worker:
            def wait(self):
                return 7

        _reap_worker(store, task_id, Worker(), monitor_fd)
        assert "code 7" in store.public(task_id)["error"]["message"]
        with pytest.raises(OSError):
            os.fstat(monitor_fd)
    finally:
        try:
            os.close(monitor_fd)
        except OSError:
            pass
