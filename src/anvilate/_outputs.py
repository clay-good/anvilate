"""The one folder the MCP server writes to, chosen by the user when the server starts.

An agent that builds a part needs to leave the engineer something to open: a picture, a STEP
file, a sheet. Passing a CAD file through the model costs tokens and corrupts nothing only
by luck, and a tool that took a destination path would let a client write anywhere the
server can. So there is one output folder, named at launch (``anvilate-mcp --out DIR``, or
``ANVILATE_OUT``), and every file a tool produces is written there under a name derived from
the part. No tool accepts a path, and nothing here can write outside the folder.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from .refusal import RefusalError, Remedy

__all__: list[str] = []

_ROOT: Path | None = None
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class _OutputRefused(RefusalError, ValueError):
    """A file that cannot be written to the output folder as asked."""


def _refusal(message: str, *, subject: str) -> _OutputRefused:
    return _OutputRefused(
        message,
        remedies=(
            Remedy(
                action="set" if subject == "--out" else "replace",
                subject=subject,
                source="`anvilate-mcp --out DIR`, the one folder results are written to by name",
            ),
        ),
    )


def set_output_folder(path: str | Path | None) -> None:
    """Name the folder results are written to; ``None`` turns writing off."""
    global _ROOT
    _ROOT = None if path is None else Path(path).expanduser().resolve()


def output_folder() -> Path | None:
    """The folder results are written to, from ``set_output_folder`` or ``ANVILATE_OUT``."""
    if _ROOT is not None:
        return _ROOT
    configured = os.environ.get("ANVILATE_OUT")
    return Path(configured).expanduser().resolve() if configured else None


def safe_stem(name: str) -> str:
    """A part name as a file stem: letters, digits, dot, dash and underscore only."""
    stem = _SAFE.sub("-", name).strip("-.")
    return stem[:80] or "part"


def write_output(name: str, data: bytes) -> dict[str, object]:
    """Write ``data`` as ``name`` in the output folder and say where, how big and what digest.

    The name is a file name, never a path: one that carries a separator, or resolves outside
    the folder, is refused. The write replaces a file of the same name, so a rebuild updates
    its outputs rather than accumulating them, and is atomic, so a reader never sees half.
    """
    root = output_folder()
    if root is None:
        raise _refusal(
            f"this server was started without an output folder, so it has nowhere to write {name}",
            subject="--out",
        )
    if name != Path(name).name or name in {"", ".", ".."} or _SAFE.search(name):
        raise _refusal(
            f"{name!r} is not a plain file name; results are written by name into {root}",
            subject="name",
        )
    root.mkdir(parents=True, exist_ok=True)
    target = (root / name).resolve()
    if target.parent != root:
        raise _refusal(
            f"{name!r} resolves outside the output folder {root}",
            subject="name",
        )
    handle, staging = tempfile.mkstemp(dir=root, prefix=".anvilate-", suffix=".partial")
    try:
        with os.fdopen(handle, "wb") as staged:
            staged.write(data)
        os.replace(staging, target)
    except BaseException:
        Path(staging).unlink(missing_ok=True)
        raise
    return {"path": str(target), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
