"""Durable subprocess tasks for the stateless MCP surface.

The MCP Tasks extension makes a long-running call durable before it returns: another
server process must be able to poll or cancel it using only the task ID.  A JSON record in
the local cache is that durable hand-off; the worker is a separate process group so
cancellation reaches solver children as well as the Python coordinator.

Task IDs are bearer handles.  They are generated from 256 bits of entropy and are never
listed, which is the extension's isolation model for a server with no caller identity.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .fetch import cache_root

# Private implementation module. MCP is the supported surface; none of the storage and
# process-management helpers below is a compatibility promise.
__all__: list[str] = []

TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
_TASK_ID_PREFIX = "task_"
_TERMINAL = frozenset({"completed", "cancelled", "failed"})


def _progress(
    activity: str, *, completed: int, total: int | None, indeterminate: bool
) -> dict[str, Any]:
    """Namespaced task progress that survives polling through another server process."""
    return {
        "dev.anvilate/progress": {
            "activity": activity,
            "completedUnits": completed,
            "totalUnits": total,
            "indeterminate": indeterminate,
        }
    }


class UnknownTask(KeyError):
    """A task handle this store does not hold or cannot read."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def task_store_root(explicit: str | Path | None = None) -> Path:
    """Where task handles resolve: explicit path, environment, then local cache."""
    if explicit is not None:
        if str(explicit) == "":
            raise ValueError("an empty task-store path is not the current directory")
        return Path(explicit)
    named = os.environ.get("ANVILATE_TASK_STORE")
    return Path(named) if named else cache_root() / "tasks"


class TaskStore:
    """Small durable state machine behind ``tasks/get`` and ``tasks/cancel``."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = task_store_root(root)

    def create(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Persist a working task before any handle is returned to the client."""
        task_id = _TASK_ID_PREFIX + secrets.token_hex(32)
        timestamp = _now()
        record = {
            "taskId": task_id,
            "status": "working",
            "statusMessage": f"Queued {operation}.",
            "createdAt": timestamp,
            "lastUpdatedAt": timestamp,
            "ttlMs": None,
            "pollIntervalMs": 250,
            "_meta": _progress(
                f"Queued {operation}.", completed=0, total=None, indeterminate=True
            ),
            "_operation": operation,
            "_arguments": arguments,
            "_pid": None,
            "_nonce": secrets.token_hex(32),
        }
        self._write(task_id, record)
        return record

    def attach_worker(self, task_id: str, pid: int) -> dict[str, Any]:
        with self._record_lock(task_id):
            record = self.read(task_id)
            if record["status"] not in _TERMINAL:
                record["_pid"] = pid
                record["lastUpdatedAt"] = _now()
                self._write(task_id, record)
            return record

    def update_message(self, task_id: str, message: str) -> None:
        with self._record_lock(task_id):
            record = self.read(task_id)
            if record["status"] in _TERMINAL:
                return
            record["statusMessage"] = message
            record["lastUpdatedAt"] = _now()
            record["_meta"] = _progress(
                message, completed=0, total=None, indeterminate=True
            )
            self._write(task_id, record)

    def complete(self, task_id: str, result: dict[str, Any], message: str) -> None:
        with self._record_lock(task_id):
            record = self.read(task_id)
            if record["status"] in _TERMINAL:
                return
            record.update(
                status="completed",
                statusMessage=message,
                lastUpdatedAt=_now(),
                result=result,
                _meta=_progress(message, completed=1, total=1, indeterminate=False),
            )
            self._write(task_id, record)

    def fail(self, task_id: str, error: dict[str, Any], message: str) -> None:
        with self._record_lock(task_id):
            record = self.read(task_id)
            if record["status"] in _TERMINAL:
                return
            record.update(
                status="failed",
                statusMessage=message,
                lastUpdatedAt=_now(),
                error=error,
                _meta=_progress(message, completed=0, total=1, indeterminate=False),
            )
            self._write(task_id, record)

    def cancel(self, task_id: str, result: dict[str, Any], message: str) -> None:
        """Record the cancellation result, then terminate the owned process group.

        The task completes because the original tool call has a valid result: a scorecard
        saying the affected checks were not evaluated.  MCP's bare ``cancelled`` variant
        cannot carry a result, while a completed task may carry a tool result whose domain
        status is ``not_evaluated``.
        """
        with self._record_lock(task_id):
            record = self.read(task_id)
            if record["status"] in _TERMINAL:
                return
            record.update(
                status="completed",
                statusMessage=message,
                lastUpdatedAt=_now(),
                result=result,
                _meta=_progress(message, completed=0, total=1, indeterminate=False),
            )
            self._write(task_id, record)
            pid = record.get("_pid")
        if not isinstance(pid, int) or pid <= 0:
            return
        if not self._owns_worker(pid, task_id):
            return
        try:
            if hasattr(os, "killpg"):
                os.killpg(pid, signal.SIGTERM)
            else:  # pragma: no cover - Windows fallback; CI exercises process groups.
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def read(self, task_id: str) -> dict[str, Any]:
        path = self._path(task_id)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as unreadable:
            raise UnknownTask(f"{task_id!r} is not a readable task in {self.root}") from unreadable
        if not isinstance(record, dict) or record.get("taskId") != task_id:
            raise UnknownTask(f"{task_id!r} does not name a task record in {self.root}")
        return record

    def public(self, task_id: str) -> dict[str, Any]:
        record = self.read(task_id)
        return {
            key: value
            for key, value in record.items()
            if key == "_meta" or not key.startswith("_")
        }

    def worker_input(self, task_id: str, nonce: str) -> tuple[str, dict[str, Any]]:
        record = self.read(task_id)
        if not secrets.compare_digest(str(record.get("_nonce", "")), nonce):
            raise UnknownTask(f"{task_id!r} worker token does not match its task")
        if record["status"] in _TERMINAL:
            raise UnknownTask(f"{task_id!r} already reached {record['status']}")
        return str(record["_operation"]), dict(record["_arguments"])

    @contextmanager
    def worker_lease(self, task_id: str):
        """Hold an OS lock for the worker lifetime so cancellation never trusts a stale PID."""
        import fcntl

        path = self._path(task_id).with_suffix(".worker")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX)
            yield

    @contextmanager
    def _record_lock(self, task_id: str):
        """Serialize read-modify-write transitions across server and worker processes."""
        import fcntl

        path = self._path(task_id).with_suffix(".lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _path(self, task_id: str) -> Path:
        if not task_id.startswith(_TASK_ID_PREFIX) or len(task_id) != len(_TASK_ID_PREFIX) + 64:
            raise UnknownTask(f"{task_id!r} is not an Anvilate task handle")
        digest = task_id.removeprefix(_TASK_ID_PREFIX)
        if any(character not in "0123456789abcdef" for character in digest):
            raise UnknownTask(f"{task_id!r} is not an Anvilate task handle")
        return self.root / digest[:2] / f"{task_id}.json"

    def _write(self, task_id: str, record: dict[str, Any]) -> None:
        path = self._path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, encoding="utf-8"
        ) as scratch:
            json.dump(record, scratch, sort_keys=True, separators=(",", ":"))
            scratch.flush()
            os.fsync(scratch.fileno())
            temporary = Path(scratch.name)
        os.replace(temporary, path)

    def _owns_worker(self, pid: int, task_id: str) -> bool:
        """A held worker lease proves the PID still belongs to this task."""
        if os.name != "posix":  # pragma: no cover - see cancellation fallback above.
            return True
        try:
            import fcntl

            with self._path(task_id).with_suffix(".worker").open("a+") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return False
        except BlockingIOError:
            return True
        except OSError:
            return False


def task_store(root: str | Path | None = None) -> TaskStore:
    return TaskStore(root)


def launch_task(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create and launch one worker, returning the already-durable public task."""
    store = task_store()
    record = store.create(operation, arguments)
    task_id = record["taskId"]
    nonce = record["_nonce"]
    environment = os.environ.copy()
    environment["ANVILATE_TASK_STORE"] = str(store.root)
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module, no shell
        [sys.executable, "-m", "anvilate._mcp_tasks", "--worker", task_id, nonce],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        start_new_session=True,
    )
    store.attach_worker(task_id, process.pid)
    # Reaping is process hygiene, not task state. The durable JSON record remains the only
    # source of truth; this thread merely prevents a completed detached child becoming a
    # zombie (or producing ResourceWarning when its Popen wrapper is collected).
    threading.Thread(target=process.wait, daemon=True).start()
    return store.public(task_id)


def _run_worker(task_id: str, nonce: str) -> int:
    store = task_store()
    try:
        with store.worker_lease(task_id):
            operation, arguments = store.worker_input(task_id, nonce)
            store.update_message(task_id, f"Running {operation}.")
            from .mcp import _execute_task

            result = _execute_task(operation, arguments)
            store.complete(task_id, result, f"Completed {operation}.")
    except UnknownTask:
        return 2
    except Exception as failure:  # noqa: BLE001 - failure becomes the task's typed error.
        store.fail(
            task_id,
            {"code": -32603, "message": f"{type(failure).__name__}: {failure}"},
            f"{operation if 'operation' in locals() else 'task'} failed.",
        )
        return 1
    return 0


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit(
            "usage: python -m anvilate._mcp_tasks --worker TASK_ID NONCE"
        )
    raise SystemExit(_run_worker(sys.argv[2], sys.argv[3]))


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess.
    main()
