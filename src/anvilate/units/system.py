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
    def moment_unit(self) -> str:
        """The conventional unit for a moment or torque in a calculation report.

        N·mm and kip·in, not N·m and kip·ft — deliberately the *self-consistent* pair
        rather than the more familiar one. A report's whole job is a substituted line a
        reviewer can follow, and σ = M/Z only reads right when the moment's length unit
        matches the section modulus's: 1500000.00 N·mm / 42000.00 mm³ = 35.7 MPa checks
        by hand, while 1500.00 N·m / 42000.00 mm³ does not. The magnitudes are larger and
        that is the price of arithmetic a reader can verify. An author who wants N·m for
        a particular symbol still pins it.
        """
        return "N*mm" if self is UnitSystem.SI else "kip*in"

    @property
    def area_unit(self) -> str:
        """The conventional unit for an area, mm² or in² — the square of :attr:`length_unit`.

        Unmapped until an audit found a US-system derivation printing "1.5 · 6.0 kN /
        5000.00 mm²" above a result in ksi: SI force over SI area against a US stress, a
        substituted line mixing two systems inside one equals sign.
        """
        return "mm**2" if self is UnitSystem.SI else "in**2"

    @property
    def second_moment_unit(self) -> str:
        """The conventional unit for a second moment of area, mm⁴ or in⁴.

        The fourth power of :attr:`length_unit`, which keeps M·c/I dimensionally legible
        alongside :attr:`moment_unit` and :attr:`length_unit` in the same line.
        """
        return "mm**4" if self is UnitSystem.SI else "in**4"

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
