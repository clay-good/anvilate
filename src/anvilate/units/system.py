"""Unit systems and their conventions.

Every Design Spec declares a unit system. The system drives which units values
render in, the default drawing-sheet standard, and the plausible units offered
when a bare number needs disambiguation.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["UnitSystem"]


class UnitSystem(StrEnum):
    """The unit system a spec is authored and reported in."""

    SI = "SI"
    US = "US"

    @property
    def length_unit(self) -> str:
        return "mm" if self is UnitSystem.SI else "in"

    @property
    def force_unit(self) -> str:
        return "kN" if self is UnitSystem.SI else "kip"

    @property
    def stress_unit(self) -> str:
        return "MPa" if self is UnitSystem.SI else "ksi"

    @property
    def mass_unit(self) -> str:
        return "kg" if self is UnitSystem.SI else "lb"

    @property
    def sheet_standard(self) -> str:
        """Default drawing-sheet series for this system."""
        return "ISO" if self is UnitSystem.SI else "ANSI"

    def plausible_units(self, dimension: str) -> list[str]:
        """Candidate units to offer when a physical quantity arrives without one.

        ``dimension`` is a coarse hint (``"force"``, ``"mass"``, ``"stress"``,
        ``"length"``). Candidates from both systems are offered so a user can
        answer in whichever they think in, but the project system's units lead.
        """
        table = {
            "force": {"SI": ["N", "kN"], "US": ["lbf", "kip"]},
            "mass": {"SI": ["g", "kg"], "US": ["lb"]},
            "stress": {"SI": ["MPa"], "US": ["psi", "ksi"]},
            "length": {"SI": ["mm", "m"], "US": ["in", "ft"]},
        }
        by_system = table.get(dimension)
        if by_system is None:
            return []
        mine = by_system[self.value]
        other = by_system["US" if self is UnitSystem.SI else "SI"]
        return mine + other
