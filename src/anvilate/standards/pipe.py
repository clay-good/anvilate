"""Steel pipe dimensions by nominal size and schedule (ASME B36.10M).

A pipe's outside diameter does not follow from its nominal size — NPS 4 pipe is
114.3 mm across, not 4 inches — and the wall a schedule carries is a table entry,
not a formula. Both are retrieved here rather than recalled, the same rule the
bearing, dowel-pin, and fastener tables follow.

The schedule system exists so that every schedule of a given NPS shares one outside
diameter and grows its wall inward: a heavier wall fits the same flanges and the
same pipe supports, and buys pressure capacity at the cost of bore. That is why
:class:`PipeDimensions` reports the inside diameter as a derived property — it is
the number a flow calculation needs and the one nobody prints on the pipe.

STD and XS are carried as schedules in their own right, not as aliases for 40 and
80. They agree only up to a point (STD tracks Schedule 40 through NPS 10, XS tracks
Schedule 80 through NPS 8) and then hold flat while the numbered schedules keep
thickening — so treating them as synonyms is right for small bore and wrong for
large.
"""

from __future__ import annotations

import difflib
from functools import cache
from typing import Annotated

import yaml
from pydantic import ConfigDict

from .._models import RevalidatedModel
from ..units import Quantity
from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "PipeDimensions",
    "PipeScheduleTable",
    "UnknownPipeError",
    "default_pipe_schedule_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "pipe dimension")]

# NPS is a designator, not a measurement, and it sorts numerically rather than as
# text: "1-1/4" belongs between "1" and "1-1/2", and "10" after "8".
_FRACTIONS = {"1/2": 0.5, "3/4": 0.75, "1-1/4": 1.25, "1-1/2": 1.5, "2-1/2": 2.5}


def _nps_value(nps: str) -> float:
    """The NPS designator as a number, for ordering only."""
    if nps in _FRACTIONS:
        return _FRACTIONS[nps]
    try:
        return float(nps)
    except ValueError:
        return 0.0


class PipeDimensions(RevalidatedModel):
    """One (nominal size, schedule) pipe's tabled dimensions.

    ``nominal_size`` is the NPS designator as written (``"4"``, ``"1-1/2"``),
    ``schedule`` the wall schedule (``"40"``, ``"80"``, ``"STD"``, ``"XS"``),
    ``outside_diameter`` D the actual outside diameter, and ``wall_thickness`` t the
    nominal wall. :attr:`inside_diameter` and :attr:`flow_area` derive from those two.

    The wall is the *nominal* wall, which is not the wall a pressure calculation may
    rely on: ASME B31.3 takes the mill under-tolerance and the corrosion allowance
    off it first. :meth:`available_wall` does that arithmetic so the two numbers do
    not get confused.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    nominal_size: str
    schedule: str
    outside_diameter: Length
    wall_thickness: Length

    @property
    def designation(self) -> str:
        """The table key, ``"NPS 4 SCH 40"``."""
        return f"NPS {self.nominal_size} SCH {self.schedule}"

    @property
    def inside_diameter(self) -> Quantity:
        """The bore, d = D − 2·t — the number a flow calculation needs."""
        od = self.outside_diameter.quantity.to("mm").magnitude
        t = self.wall_thickness.quantity.to("mm").magnitude
        return Quantity(magnitude=od - 2.0 * t, unit="mm")

    @property
    def flow_area(self) -> Quantity:
        """The internal cross-sectional area π·d²/4 the fluid actually sees."""
        from math import pi

        d = self.inside_diameter.to("mm").magnitude
        return Quantity(magnitude=pi * d**2 / 4.0, unit="mm**2")

    def available_wall(
        self,
        *,
        mill_tolerance_fraction: float = 0.125,
        corrosion_allowance: Quantity | None = None,
    ) -> Quantity:
        """The wall left to hold pressure: nominal, less mill tolerance and corrosion.

        A mill may ship pipe up to ``mill_tolerance_fraction`` thinner than nominal
        (12.5% is the B36.10M under-tolerance), and a ``corrosion_allowance`` is metal
        set aside to be eaten over the line's life. Neither is available to carry
        pressure, so the B31.3 pressure check runs against what is left, not against
        the number stamped on the pipe.

        Returns the available wall, clamped at zero rather than reported negative: a
        wall entirely consumed by its allowances has none available, and a negative
        thickness would flow on into a pressure rating as a plausible number.
        """
        if not 0.0 <= mill_tolerance_fraction < 1.0:
            raise ValueError(
                f"mill_tolerance_fraction must lie in [0, 1); got {mill_tolerance_fraction}"
            )
        left = self.wall_thickness.quantity.to("mm").magnitude * (1.0 - mill_tolerance_fraction)
        if corrosion_allowance is not None:
            if not isinstance(corrosion_allowance, Quantity):
                raise ValueError(
                    f"corrosion_allowance must be a [length] quantity; got {corrosion_allowance!r}"
                )
            if not corrosion_allowance.has_dimension("[length]"):
                raise ValueError(
                    f"corrosion_allowance must be a [length] quantity; got {corrosion_allowance}"
                )
            allowance = corrosion_allowance.to("mm").magnitude
            if allowance < 0:
                raise ValueError(f"corrosion_allowance must not be negative; got {allowance} mm")
            left -= allowance
        return Quantity(magnitude=max(left, 0.0), unit="mm")

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence trail,
        mirroring :meth:`anvilate.standards.DowelPin.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownPipeError(KeyError):
    """A requested (nominal size, schedule) pair has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for pipe {designation!r}{hint}")


class PipeScheduleTable:
    """ASME B36.10M pipe dimensions keyed by nominal size and schedule."""

    def __init__(self, pipes: dict[str, PipeDimensions]) -> None:
        self._pipes = pipes

    def has_pipe(self, nominal_size: str, schedule: str) -> bool:
        return _key(nominal_size, schedule) in self._pipes

    def designations(self) -> list[str]:
        return sorted(
            self._pipes,
            key=lambda k: (_nps_value(self._pipes[k].nominal_size), self._pipes[k].schedule),
        )

    def nominal_sizes(self) -> list[str]:
        """Every tabled NPS, in size order."""
        return sorted({p.nominal_size for p in self._pipes.values()}, key=_nps_value)

    def schedules(self, nominal_size: str | None = None) -> list[str]:
        """Every tabled schedule, or those tabled for one nominal size."""
        return sorted(
            {
                p.schedule
                for p in self._pipes.values()
                if nominal_size is None or p.nominal_size == nominal_size
            }
        )

    def get(self, nominal_size: str, schedule: str) -> PipeDimensions:
        """Return the dimensions for a nominal size and schedule.

        Raises :class:`UnknownPipeError` (with near-misses) rather than interpolating
        a wall for an untabled combination — the schedule-to-wall mapping is a table,
        and a number between two rows of it is not a pipe anybody can buy.
        """
        key = _key(nominal_size, schedule)
        try:
            return self._pipes[key]
        except KeyError:
            raise UnknownPipeError(key, difflib.get_close_matches(key, self._pipes, n=3)) from None

    def __len__(self) -> int:
        return len(self._pipes)


def _key(nominal_size: str, schedule: str) -> str:
    return f"NPS {nominal_size} SCH {schedule}"


def _load_pipes(text: str) -> dict[str, PipeDimensions]:
    doc = yaml.safe_load(text)
    dataset = doc["dataset"]
    diameters = doc["outside_diameter"]

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ASME B36.10M {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    pipes: dict[str, PipeDimensions] = {}
    for schedule, rows in doc["walls"].items():
        for nps, wall in rows.items():
            if nps not in diameters:
                raise ValueError(
                    f"schedule {schedule} tables a wall for NPS {nps}, which has no "
                    f"outside diameter in the table"
                )
            pipes[_key(nps, schedule)] = PipeDimensions.model_validate(
                {
                    "nominal_size": nps,
                    "schedule": schedule,
                    "outside_diameter": _prop(diameters[nps], f"NPS {nps} outside diameter"),
                    "wall_thickness": _prop(wall, f"NPS {nps} schedule {schedule} wall"),
                }
            )
    return pipes


@cache
def default_pipe_schedule_table() -> PipeScheduleTable:
    """The bundled ASME B36.10M pipe dimension table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "pipe_schedules.yaml").read_text(
        encoding="utf-8"
    )
    return PipeScheduleTable(_load_pipes(text))
