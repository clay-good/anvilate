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


def _task_call() -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "run_fea_validation",
                "arguments": {"spec": _spec_document(), "convergence_tol": 1e-4},
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


def _poll_terminal(task_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _task_request("tasks/get", task_id)["result"]
        if result["status"] in {"completed", "cancelled", "failed"}:
            return result
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} did not reach a terminal status")


def test_fea_task_is_durable_before_return_and_retrievable_after_completion(
    monkeypatch, tmp_path
):
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
