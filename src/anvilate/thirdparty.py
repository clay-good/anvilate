"""Discipline modules from outside this repository: enabled by name, run confined, marked.

A third-party module is one Python file. It declares a ``MANIFEST`` (the same fields as an
in-tree :class:`~anvilate.modules.ModuleManifest`) and, for each element type it ``covers``,
a function ``screen_<element_type>(params)``. The function takes the document's
``element_params`` as plain JSON and returns plain JSON, a list of entries with ``name``,
``status``, ``detail`` and optionally ``reference``, ``safety_factor`` and
``required_safety_factor``. It never receives this library's objects, and what it returns is
validated here like any input from outside.

Three rules, from the discipline-packs spec:

- **Nothing loads unless named.** :func:`enable_module` takes a path; there is no discovery,
  no entry-point scan and no search path. A module that is installed but not named
  contributes nothing.
- **Every call runs confined**, in a separate process (``_sandbox_child.py``) with a scratch
  directory as its working directory, CPU, memory, file-size and descriptor limits, a
  wall-clock timeout, and an audit hook that refuses network access, new processes,
  ctypes, and file access outside the module's directory, the Python installation and the
  scratch directory. A violation, a crash or a timeout ends the call, and the check is
  reported not evaluated with the reason. That confinement stops mistakes and ordinary
  misbehaviour. It is not a boundary against hostile native code, which is why the next rule
  exists.
- **Every result is marked.** Each entry carries an :class:`~anvilate.scorecard.UnverifiedOrigin`
  naming the module, its version, its path and the SHA-256 of the source that ran. The
  evidence bundle embeds the card, so it records them too, and
  :func:`~anvilate.export.gate.authorize_export` never counts such an entry as validated.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ._models import parse_json
from .modules import MODULE_MANIFESTS, ModuleManifest
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, ScorecardEntry, UnverifiedOrigin

__all__ = ["ThirdPartyModule", "ThirdPartyModuleError", "enable_module"]

_CHILD = Path(__file__).with_name("_sandbox_child.py")
_TIMEOUT_SECONDS = 30
_CPU_SECONDS = 20
_MEMORY_MB = 1024
_STATUSES = {status.value for status in CheckStatus}


class ThirdPartyModuleError(RefusalError, ValueError):
    """A third-party module that cannot be enabled as named."""

    def __init__(self, message: str, *, subject: str) -> None:
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="correct",
                    subject=subject,
                    source=(
                        "the third-party module contract, https://github.com/clay-good/anvilate/"
                        "blob/main/docs/discipline-modules.md#third-party-modules"
                    ),
                ),
            ),
        )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(path: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    """One confined call; the child's reply, or a failure stated in the same shape."""
    message = {
        **request,
        "module": str(path),
        "cpu_seconds": _CPU_SECONDS,
        "memory_mb": _MEMORY_MB,
    }
    with tempfile.TemporaryDirectory(prefix="anvilate-module-") as scratch:
        try:
            done = subprocess.run(
                [sys.executable, "-I", str(_CHILD)],
                input=json.dumps(message),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                cwd=scratch,
                env={"HOME": scratch, "TMPDIR": scratch},
                start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"no answer within {_TIMEOUT_SECONDS} s; stopped"}
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 or not lines:
        reason = done.stderr.strip().splitlines()[-1:] or [f"exit status {done.returncode}"]
        return {"ok": False, "error": f"the module process ended abnormally: {reason[0]}"}
    try:
        reply = parse_json(lines[-1])
    except ValueError:
        return {"ok": False, "error": "the module process answered with something not JSON"}
    return reply if isinstance(reply, dict) else {"ok": False, "error": "a malformed answer"}


@dataclass(frozen=True)
class ThirdPartyModule:
    """One enabled out-of-tree module: where it is, what it declares, and its origin mark."""

    path: Path
    manifest: ModuleManifest
    origin: UnverifiedOrigin

    def covers(self, element_type: str) -> bool:
        return element_type in self.manifest.covers

    def screen(
        self, element_type: str, params: Mapping[str, Any], required: float | None = None
    ) -> list[ScorecardEntry]:
        """The module's entries for one element, each marked; or one saying why there are none."""
        name = f"{self.manifest.id} {element_type}"
        if _digest(self.path) != self.origin.sha256:
            return [self._unrun(name, "its source changed after it was enabled; enable it again")]
        reply = _run(
            self.path,
            {
                "op": "screen",
                "tag": element_type,
                "params": dict(params),
                "required_safety_factor": required,
            },
        )
        if not reply.get("ok"):
            reason = reply.get("violation") or reply.get("error") or "no reason given"
            return [self._unrun(name, f"the module did not complete: {reason}")]
        result = reply.get("result")
        if not isinstance(result, list) or not result:
            return [self._unrun(name, "the module returned no entries")]
        entries = []
        allowed = {"name", "status", "detail", "reference"}
        allowed |= {"safety_factor", "required_safety_factor"}
        for index, raw in enumerate(result):
            problem = None
            if not isinstance(raw, dict) or raw.get("status") not in _STATUSES:
                problem = f"status must be one of {sorted(_STATUSES)}"
            elif set(raw) - allowed:
                problem = f"fields this library does not read: {sorted(set(raw) - allowed)}"
            else:
                try:
                    entries.append(ScorecardEntry(**raw, origin=self.origin))
                except (ValidationError, ValueError, TypeError) as refused:
                    problem = str(refused)
            if problem is not None:
                detail = f"entry {index} is not one this library can read: {problem}"
                entries.append(self._unrun(name, detail[:1000]))
        return entries

    def _unrun(self, name: str, reason: str) -> ScorecardEntry:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=f"third-party module {self.manifest.id}: {reason}",
            origin=self.origin,
        )


def enable_module(path: str | Path) -> ThirdPartyModule:
    """Enable one third-party module by its path, after reading its manifest confined.

    Refused: a path that is not a Python file; a manifest the in-tree contract refuses; an id
    or check namespace that is, contains or sits inside one this library ships; and an
    element type this library already screens, because a third-party module may add a
    screen but never replace one.
    """
    from .screening import element_registry

    file = Path(path).expanduser().resolve()
    if not file.is_file() or file.suffix != ".py":
        raise ThirdPartyModuleError(
            f"a third-party module is one .py file; {file} is not one",
            subject=f"the module path {file}",
        )
    reply = _run(file, {"op": "manifest"})
    if not reply.get("ok"):
        reason = reply.get("violation") or reply.get("error") or "no reason given"
        raise ThirdPartyModuleError(
            f"{file.name} could not be loaded to read its manifest: {reason}",
            subject=f"the module {file.name}",
        )
    try:
        manifest = ModuleManifest.model_validate(reply.get("result"))
    except ValidationError as refused:
        raise ThirdPartyModuleError(
            f"{file.name} declares no valid MANIFEST: {refused}",
            subject=f"the MANIFEST in {file.name}",
        ) from refused
    for shipped in MODULE_MANIFESTS.manifests:
        overlapping = {manifest.namespace, shipped.namespace}
        nested = manifest.namespace.startswith(f"{shipped.namespace}.") or (
            shipped.namespace.startswith(f"{manifest.namespace}.")
        )
        if manifest.id == shipped.id or len(overlapping) == 1 or nested:
            raise ThirdPartyModuleError(
                f"{file.name} claims the id or check namespace of the shipped module "
                f"{shipped.id!r}; a third-party module takes names of its own",
                subject=f"the MANIFEST id and namespace in {file.name}",
            )
    taken = sorted(set(manifest.covers) & set(element_registry()))
    if taken:
        raise ThirdPartyModuleError(
            f"{file.name} covers {taken}, which this library already screens; a third-party "
            "module may add an element type, never replace one",
            subject=f"the MANIFEST covers in {file.name}",
        )
    origin = UnverifiedOrigin(
        module=manifest.id, version=manifest.version, source=str(file), sha256=_digest(file)
    )
    return ThirdPartyModule(path=file, manifest=manifest, origin=origin)
