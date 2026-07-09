"""Process capability screening: can the manufacturing process hold a tolerance?

T2 DFM (see openspec/specs/tolerance-management/) compares every explicit
tolerance against the declared process's achievable-tolerance profile and flags
any that are tighter than the process can deliver. This module supplies the
achievable-tolerance floor per process (a bundled, clearly-labeled screening
estimate) and the comparison. The floor is deliberately the *finest* a process
can reasonably hold, so the check fails only clearly-unachievable tolerances.
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .general import ToleranceRangeError

__all__ = [
    "ProcessCapability",
    "AchievabilityCheck",
    "process_capability",
    "tolerance_is_achievable",
]


class ProcessCapability(BaseModel):
    """The finest total tolerance band a process can reasonably hold (a screening
    estimate), with its source and a caveat note."""

    model_config = ConfigDict(frozen=True)

    process: str
    finest_tolerance: Quantity  # finest achievable total tolerance band, a length
    source: str
    note: str


class AchievabilityCheck(BaseModel):
    """The result of screening a demanded tolerance against a process's floor.

    ``achievable`` is True when the demanded total tolerance band is at least the
    process's finest achievable band. ``demanded`` and ``finest`` are both total
    bands (a length); ``source`` cites the capability estimate.
    """

    model_config = ConfigDict(frozen=True)

    process: str
    demanded: Quantity
    finest: Quantity
    achievable: bool
    source: str

    def __str__(self) -> str:
        verdict = "achievable" if self.achievable else "UNACHIEVABLE"
        d = self.demanded.to("mm").magnitude
        f = self.finest.to("mm").magnitude
        return f"{self.process}: {d:.3f} mm demanded vs {f:.3f} mm floor — {verdict}"


_TABLE: dict | None = None


def _table() -> dict:
    global _TABLE
    if _TABLE is None:
        from importlib.resources import files

        text = (files("anvilate.tolerance") / "data" / "process_capability.yaml").read_text(
            encoding="utf-8"
        )
        _TABLE = yaml.safe_load(text)
    return _TABLE


def process_capability(process: str) -> ProcessCapability:
    """The finest-achievable tolerance floor for ``process`` (a screening estimate).

    ``process`` is the manufacturing-process name (e.g. ``"cnc_milling"``, the
    value of :class:`~anvilate.spec.ManufacturingProcess`). Raises
    :class:`ToleranceRangeError` if the process has no capability record.
    """
    doc = _table()
    row = doc["processes"].get(process)
    if row is None:
        known = ", ".join(sorted(doc["processes"]))
        raise ToleranceRangeError(
            f"no tolerance-capability record for process {process!r}; have {known}"
        )
    return ProcessCapability(
        process=process,
        finest_tolerance=Quantity(magnitude=float(row["finest_tolerance"]), unit="mm"),
        source=doc["dataset"]["source"],
        note=row["note"],
    )


def tolerance_is_achievable(process: str, demanded_width: Quantity) -> AchievabilityCheck:
    """Screen a demanded total tolerance band against ``process``'s floor.

    ``demanded_width`` is the total tolerance band (e.g. a symmetric +/-0.05 mm is
    a 0.1 mm band — :attr:`ResolvedTolerance.width`). Must be a length, else
    :class:`ToleranceRangeError`. The tolerance is achievable when its band is at
    least the process's finest achievable band.
    """
    if not demanded_width.has_dimension("[length]"):
        raise ToleranceRangeError(
            f"a tolerance band must be a length; got {demanded_width.dimensionality} "
            f"({demanded_width})"
        )
    cap = process_capability(process)
    demanded_mm = demanded_width.to("mm").magnitude
    finest_mm = cap.finest_tolerance.to("mm").magnitude
    return AchievabilityCheck(
        process=process,
        demanded=demanded_width,
        finest=cap.finest_tolerance,
        achievable=demanded_mm >= finest_mm,
        source=cap.source,
    )
