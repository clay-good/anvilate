"""T1 analytical protective-coating film-thickness and coverage checks (closed-form).

A paint or protective coating is specified by its *dry* film thickness — the cured layer that
actually does the protecting — but it is *applied* wet, and only the fraction of the wet film that
is non-volatile solids stays behind. Three closed-form relations tie the wet application, the dry
result, and the paint a job consumes together, all built on the coating's volume-solids fraction.

The dry film thickness is the wet film scaled by the volume solids, DFT = WFT·VS, and inverting it
gives the wet film an applicator must lay down to hit a target dry thickness, WFT = DFT/VS. The
theoretical coverage — the area one unit of paint would cover at that dry thickness with no losses —
is the volume-solids over the dry film thickness, and it sets the paint quantity a job needs (before
the practical loss factor for overspray, thinning, and surface roughness). These are the numbers a
coating spec and a paint take-off are built from; the film thicknesses are dimension-checked
:class:`~anvilate.units.Quantity` lengths and the volume solids a fraction in (0, 1].

Sources: ASTM D4414 (wet-film thickness by notch gage) with the volume-solids relation it is
read against — the dry film a wet film leaves at a stated solids content, the wet film a target
dry film needs, and the theoretical coverage a volume of coating gives.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "coating_dry_film_thickness",
    "coating_theoretical_coverage",
    "coating_wet_film_thickness",
]


def coating_dry_film_thickness(
    *, wet_film_thickness: Quantity, volume_solids_fraction: float
) -> Quantity:
    """The dry film thickness of a coating, DFT = WFT·VS.

    Only the non-volatile solids of an applied wet film remain once the solvent flashes off, so the
    cured layer is the ``wet_film_thickness`` WFT scaled by the ``volume_solids_fraction`` VS (the
    fraction of the wet paint that is solids, from the data sheet): DFT = WFT·VS. It is the
    thickness that actually protects the substrate and the number an inspector gauges. The volume
    solids is a fraction in (0, 1]. Returns the dry film thickness in the wet film's length units.
    """
    _check(wet_film_thickness, "[length]", "wet_film_thickness")
    _fraction(volume_solids_fraction, "volume_solids_fraction")
    wft = wet_film_thickness.to("um").magnitude
    if wft < 0:
        raise ValueError("wet_film_thickness must be non-negative")
    return Quantity(magnitude=wft * volume_solids_fraction, unit="um")


def coating_wet_film_thickness(
    *, dry_film_thickness: Quantity, volume_solids_fraction: float
) -> Quantity:
    """The wet film thickness to apply for a target dry film, WFT = DFT/VS.

    The design inverse of :func:`coating_dry_film_thickness`: to end up with a target
    ``dry_film_thickness`` DFT after the solvent leaves, the applicator must lay down a wetter film,
    WFT = DFT/``volume_solids_fraction`` VS. It is the reading a wet-film comb must show during
    application to hit the spec dry thickness — always thicker than the target, more so for a
    low-solids paint. ``volume_solids_fraction`` is a fraction in (0, 1]. Returns the wet film
    thickness in the dry film's length units.
    """
    _check(dry_film_thickness, "[length]", "dry_film_thickness")
    _fraction(volume_solids_fraction, "volume_solids_fraction")
    dft = dry_film_thickness.to("um").magnitude
    if dft < 0:
        raise ValueError("dry_film_thickness must be non-negative")
    return Quantity(magnitude=dft / volume_solids_fraction, unit="um")


def coating_theoretical_coverage(
    *, volume_solids_fraction: float, dry_film_thickness: Quantity
) -> Quantity:
    """The theoretical coverage rate of a coating, coverage = VS/DFT.

    The area one unit volume of paint would cover at the target ``dry_film_thickness`` DFT with no
    losses: coverage = ``volume_solids_fraction`` VS / DFT — all the solids spread to the dry
    thickness. It is the spreading rate a data sheet quotes (e.g. m²/L) and the basis of a paint
    take-off; the real coverage is lower by a loss factor for overspray, thinning, and surface
    profile. A higher-solids paint or a thinner film covers more area per litre. The volume solids
    is a fraction in (0, 1]. Returns the coverage rate as an area-per-volume quantity (convert with
    e.g. ``.to("m**2/L")``).
    """
    _fraction(volume_solids_fraction, "volume_solids_fraction")
    _check(dry_film_thickness, "[length]", "dry_film_thickness")
    dft = dry_film_thickness.to("m").magnitude
    if dft <= 0:
        raise ValueError("dry_film_thickness must be positive")
    return Quantity(magnitude=volume_solids_fraction / dft * 1e-3, unit="m**2/L")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
