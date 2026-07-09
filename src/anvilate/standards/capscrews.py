"""Socket-head cap screw head geometry (ISO 4762 / DIN 912).

A design counterbores to clear a cap-screw head, so the standardized facts it
retrieves are the head diameter, head height, and hex-key socket width. They are
looked up here, not recalled. The thread pitch and tap/clearance holes come from
the ISO 261/724 and ISO 273 tables (:mod:`anvilate.standards.threads`); the
screw length and shank are order-specific and omitted — the same "mount, not
body" rule the bearing and dowel tables follow.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "SocketHeadCapScrew",
    "CapScrewTable",
    "UnknownCapScrewError",
    "default_cap_screw_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "cap-screw dimension")]


def _screw_key(designation: str) -> tuple[float, str]:
    """Sort key: the nominal thread diameter after the ``ISO4762-M`` prefix, then
    the full designation, so ``ISO4762-M4`` sorts before ``ISO4762-M10``."""
    tail = designation.rsplit("-M", 1)[-1]
    try:
        return (float(tail), designation)
    except ValueError:
        return (0.0, designation)


class SocketHeadCapScrew(BaseModel):
    """An ISO 4762 socket-head cap screw's standardized head geometry.

    ``head_diameter`` is the head outer diameter dk (the counterbore must clear
    it), ``head_height`` the head height k (the counterbore depth to bury it), and
    ``socket`` the hex-key width across flats s.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    head_diameter: Length
    head_height: Length
    socket: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.Bearing.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownCapScrewError(KeyError):
    """A requested cap-screw designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for cap screw {designation!r}{hint}")


class CapScrewTable:
    """ISO 4762 socket-head cap screw head geometry keyed by designation
    (``ISO4762-M5``)."""

    def __init__(self, screws: dict[str, SocketHeadCapScrew]) -> None:
        self._screws = screws

    def has_screw(self, designation: str) -> bool:
        return designation in self._screws

    def designations(self) -> list[str]:
        return sorted(self._screws, key=_screw_key)

    def get(self, designation: str) -> SocketHeadCapScrew:
        """Return the head-geometry record for ``designation``.

        Raises :class:`UnknownCapScrewError` (with near-misses) rather than
        estimating dimensions for an unrecorded screw.
        """
        try:
            return self._screws[designation]
        except KeyError:
            raise UnknownCapScrewError(
                designation, difflib.get_close_matches(designation, self._screws, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._screws)


def _load_screws(text: str) -> dict[str, SocketHeadCapScrew]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 4762 {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    screws: dict[str, SocketHeadCapScrew] = {}
    for designation, row in doc["screws"].items():
        screws[designation] = SocketHeadCapScrew.model_validate(
            {
                "designation": designation,
                "head_diameter": _prop(row["head_diameter"], "head diameter"),
                "head_height": _prop(row["head_height"], "head height"),
                "socket": _prop(row["socket"], "hex socket across flats"),
            }
        )
    return screws


def default_cap_screw_table() -> CapScrewTable:
    """The bundled ISO 4762 socket-head cap screw head-geometry table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "cap_screws.yaml").read_text(encoding="utf-8")
    return CapScrewTable(_load_screws(text))
