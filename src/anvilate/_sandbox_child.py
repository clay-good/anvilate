"""The child process that runs one call into a third-party module, confined.

Run by file path as ``python -I _sandbox_child.py``: isolated mode ignores the caller's
``PYTHON*`` environment and user site, and running by path imports nothing of Anvilate, so
the module sees only the standard library, its own directory and the installed packages.
Standard library only, on purpose.

The order is the confinement. The request is read first, the resource limits and an audit
hook are installed second, and only then is the module imported. A hook cannot be removed
once added (PEP 578), so nothing the module does afterwards takes it off. The hook refuses
network access, starting processes, loading native libraries through ctypes, creating links,
writing anywhere but the scratch directory, and reading anything but the module's own
directory, the Python installation and the scratch directory.

**What this is not:** a boundary against hostile native code. An audit hook is enforced by
the interpreter, and a compiled extension the module ships can do what it likes. That is why
every result such a module contributes is marked unverified-origin and is never treated as
an in-tree check. The confinement stops a module's mistakes and ordinary misbehaviour from
reaching the machine. It does not make the module trustworthy.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import sysconfig
import traceback

__all__: list[str] = []


def _limits(cpu_seconds: int, memory_mb: int) -> None:
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows has no rlimits; the wall clock still holds
        return
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    try:
        size = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (size, size))
    except (ValueError, OSError):  # macOS does not enforce an address-space limit
        pass


def _install_hook(module_dir: str, scratch: str) -> list[str]:
    realpath, join, sep = os.path.realpath, os.path.join, os.sep
    readable = tuple(
        {
            realpath(path) + sep
            for path in (
                module_dir,
                scratch,
                sys.prefix,
                sys.base_prefix,
                sys.exec_prefix,
                *(sysconfig.get_paths().values()),
                # What the interpreter already imports from, editable installs included.
                *(entry for entry in sys.path if entry),
            )
            if path
        }
    )
    writable = (realpath(scratch) + sep,)
    refused_events = (
        "socket.",
        "subprocess.",
        "os.system",
        "os.exec",
        "os.posix_spawn",
        "os.spawn",
        "os.fork",
        "os.forkpty",
        "os.kill",
        "os.killpg",
        "os.symlink",
        "os.link",
        "ctypes.",
        "urllib.",
        "webbrowser.",
        "pty.",
    )
    path_events = {
        "os.remove": True,
        "os.rename": True,
        "os.rmdir": True,
        "os.mkdir": True,
        "os.chmod": True,
        "os.chown": True,
        "os.truncate": True,
        "os.utime": True,
        "shutil.rmtree": True,
        "os.listdir": False,
        "os.scandir": False,
        "glob.glob": False,
    }

    def inside(path: object, roots: tuple[str, ...]) -> bool:
        if isinstance(path, int):
            return True  # an already-open descriptor: it was checked when it was opened
        if isinstance(path, bytes):
            path = path.decode("utf-8", "surrogateescape")
        if not isinstance(path, str):
            return False
        resolved = realpath(join(scratch, path))
        return any((resolved + sep).startswith(root) for root in roots)

    # Every refusal is recorded as well as raised: a module that catches the PermissionError
    # and carries on has still tried, and its answer is not used.
    violations: list[str] = []

    def refuse(reason: str) -> None:
        violations.append(reason)
        raise PermissionError(reason)

    def hook(event: str, args: tuple) -> None:
        if event.startswith(refused_events):
            refuse(f"sandbox: {event} is not permitted")
        if event == "open":
            path, mode, flags = args[0], args[1] or "r", args[2] or 0
            writing = any(c in str(mode) for c in "wax+") or flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
            )
            if not inside(path, writable if writing else readable):
                kind = "write" if writing else "read"
                refuse(f"sandbox: may not {kind} {path!r}")
        elif event in path_events:
            for path in args[:2]:
                if isinstance(path, str | bytes) and not inside(
                    path, writable if path_events[event] else readable
                ):
                    refuse(f"sandbox: {event} on {path!r} is not permitted")

    sys.addaudithook(hook)
    return violations


def main() -> None:
    """Answer one request from stdin on stdout: a manifest read, or one screen call."""
    reply = os.fdopen(os.dup(1), "w", encoding="utf-8")
    # A module that prints must not corrupt the one line the parent reads.
    sys.stdout = sys.stderr
    try:
        request = json.loads(sys.stdin.read())
        path = os.path.realpath(request["module"])
        scratch = os.getcwd()
        _limits(int(request["cpu_seconds"]), int(request["memory_mb"]))
        # Importing writes __pycache__ beside the module, which is outside the scratch dir.
        sys.dont_write_bytecode = True
        violations = _install_hook(os.path.dirname(path), scratch)
        spec = importlib.util.spec_from_file_location("anvilate_thirdparty_module", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"{path} is not a Python module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if request["op"] == "manifest":
            result = getattr(module, "MANIFEST", None)
        else:
            screen = getattr(module, f"screen_{request['tag']}", None)
            if screen is None:
                raise AttributeError(f"the module defines no screen_{request['tag']}")
            keywords = {}
            required = request.get("required_safety_factor")
            if (
                required is not None
                and "required_safety_factor" in inspect.signature(screen).parameters
            ):
                keywords["required_safety_factor"] = required
            result = screen(request["params"], **keywords)
        answer = json.dumps({"ok": True, "result": result})
        if violations:
            raise PermissionError(violations[0])
        reply.write(answer)
    except PermissionError as violation:
        reply.write(json.dumps({"ok": False, "violation": str(violation)}))
    except BaseException as failure:  # noqa: BLE001 - every failure is reported, none escapes
        last = traceback.format_exception_only(type(failure), failure)[-1].strip()
        reply.write(json.dumps({"ok": False, "error": last[:2000]}))
    reply.flush()


if __name__ == "__main__":
    main()
