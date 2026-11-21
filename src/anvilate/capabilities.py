"""Optional capabilities: what each extra adds, and the one command that installs it here.

Anvilate's core screens with nothing beyond its required dependencies. Building solids,
writing DXF or IFC, and reading PDFs each need an optional extra. A missing extra is not a
broken install: `anvilate doctor` reports it as *optional, not installed*, exits 0 for it,
and prints the command that installs it on this platform and through the channel this copy
was installed with. Every tool that needs the capability refuses with the same sentence,
because two different install instructions for one missing package is one too many.
"""

from __future__ import annotations

import importlib.util
import sys

from pydantic import ConfigDict

from ._models import Named, StatableModel
from .refusal import RefusalError, Remedy

__all__ = [
    "Capability",
    "CAPABILITIES",
    "capability",
    "install_command",
    "install_remedy",
    "installed",
]


class Capability(StatableModel):
    """One optional capability: the extra that adds it, the module it needs, what it is for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    extra: Named
    module: Named
    purpose: Named


#: Every optional capability, by the extra in ``pyproject.toml`` that installs it.
CAPABILITIES: tuple[Capability, ...] = (
    Capability(name="geometry kernel", extra="geometry", module="build123d",
               purpose="building solids, viewport images, STEP, 3MF and reading STEP"),
    Capability(name="DXF writer", extra="export", module="ezdxf",
               purpose="writing and reading DXF drawings"),
    Capability(name="IFC writer", extra="ifc", module="ifcopenshell",
               purpose="exporting structural parts as IFC"),
    Capability(name="PDF reader", extra="pdf", module="pdfminer",
               purpose="reading requirements out of PDF documents"),
)  # fmt: skip


class _CapabilityInputError(RefusalError, ValueError):
    """A capability lookup that names no capability."""


def capability(extra: str) -> Capability:
    """The capability the extra ``extra`` installs."""
    for found in CAPABILITIES:
        if found.extra == extra:
            return found
    raise _CapabilityInputError(
        f"no optional capability is installed by the extra {extra!r}; the extras are "
        f"{[c.extra for c in CAPABILITIES]}",
        remedies=(Remedy(action="replace", subject="extra", source="pyproject.toml extras"),),
    )


def installed(extra: str) -> bool:
    """Whether the module the extra installs can be found, without importing it."""
    try:
        return importlib.util.find_spec(capability(extra).module) is not None
    except (ImportError, ValueError):
        return False


def install_command(extra: str, *, platform: str | None = None, prefix: str | None = None) -> str:
    """The one command that adds ``extra`` to this copy of Anvilate.

    The channel is read from where this interpreter lives: a ``uv tool`` install is
    reinstalled with ``uv tool install``, a ``pipx`` one with ``pipx install``, anything
    else with ``pip``. Windows' shell does not strip single quotes, so the requirement is
    double-quoted there. ``platform`` and ``prefix`` default to this process's own.
    """
    capability(extra)
    where = (prefix if prefix is not None else sys.prefix).replace("\\", "/")
    quote = '"' if (platform or sys.platform).startswith("win") else "'"
    requirement = f"{quote}anvilate[{extra}]{quote}"
    if "/uv/tools/" in where:
        return f"uv tool install --force {requirement}"
    if "/pipx/venvs/" in where:
        return f"pipx install --force {requirement}"
    return f"pip install {requirement}"


def install_remedy(extra: str) -> str:
    """The sentence every surface gives when ``extra`` is missing: what, and the command."""
    found = capability(extra)
    return (f"{found.name} is an optional capability, not installed; install it with "
            f"`{install_command(extra)}`")  # fmt: skip
