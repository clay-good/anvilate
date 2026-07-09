"""Cross-section properties as one value object.

The beam, column, and axial checks each need a section's area, second moment, and
extreme-fibre distance. :class:`CrossSection` bundles them (plus the derived
section modulus and radius of gyration) and builds them for the common shapes —
rectangular, solid round, and hollow round — so a caller constructs the section
once and hands its properties to any check.
"""

from __future__ import annotations

from math import pi

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = ["CrossSection"]


def _mm(magnitude: float) -> Quantity:
    return Quantity(magnitude=magnitude, unit="mm")


def _require_length(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
    return value.to("mm").magnitude


class CrossSection(BaseModel):
    """A prismatic cross-section's properties, all about the bending neutral axis.

    ``area`` A, ``second_moment`` I, and ``extreme_fibre`` c (neutral axis to the
    outermost fibre) are the trio the stress checks consume;
    :attr:`section_modulus` (I/c) and :attr:`radius_of_gyration` (√(I/A)) derive
    from them. Build one with :meth:`rectangular`, :meth:`solid_circular`, or
    :meth:`hollow_circular`.
    """

    model_config = ConfigDict(frozen=True)

    area: Quantity
    second_moment: Quantity
    extreme_fibre: Quantity

    @property
    def section_modulus(self) -> Quantity:
        """The elastic section modulus Z = I/c — a bending stress is M/Z."""
        z = self.second_moment.to("mm**4").magnitude / self.extreme_fibre.to("mm").magnitude
        return Quantity(magnitude=z, unit="mm**3")

    @property
    def radius_of_gyration(self) -> Quantity:
        """The radius of gyration r = √(I/A), for slenderness."""
        r = (self.second_moment.to("mm**4").magnitude / self.area.to("mm**2").magnitude) ** 0.5
        return _mm(r)

    @classmethod
    def rectangular(cls, *, width: Quantity, height: Quantity) -> CrossSection:
        """A solid rectangle, bending about the axis normal to ``height`` (the load
        direction): A = b·h, I = b·h³/12, c = h/2."""
        b = _require_length(width, "width")
        h = _require_length(height, "height")
        return cls(
            area=Quantity(magnitude=b * h, unit="mm**2"),
            second_moment=Quantity(magnitude=b * h**3 / 12, unit="mm**4"),
            extreme_fibre=_mm(h / 2),
        )

    @classmethod
    def solid_circular(cls, *, diameter: Quantity) -> CrossSection:
        """A solid round bar: A = π·d²/4, I = π·d⁴/64, c = d/2."""
        d = _require_length(diameter, "diameter")
        return cls(
            area=Quantity(magnitude=pi * d**2 / 4, unit="mm**2"),
            second_moment=Quantity(magnitude=pi * d**4 / 64, unit="mm**4"),
            extreme_fibre=_mm(d / 2),
        )

    @classmethod
    def hollow_circular(cls, *, outer_diameter: Quantity, inner_diameter: Quantity) -> CrossSection:
        """A round tube: A = π·(D²−d²)/4, I = π·(D⁴−d⁴)/64, c = D/2."""
        do = _require_length(outer_diameter, "outer_diameter")
        di = _require_length(inner_diameter, "inner_diameter")
        if not 0 <= di < do:
            raise ValueError(
                f"inner_diameter ({inner_diameter}) must be non-negative and below "
                f"outer_diameter ({outer_diameter})"
            )
        return cls(
            area=Quantity(magnitude=pi * (do**2 - di**2) / 4, unit="mm**2"),
            second_moment=Quantity(magnitude=pi * (do**4 - di**4) / 64, unit="mm**4"),
            extreme_fibre=_mm(do / 2),
        )
