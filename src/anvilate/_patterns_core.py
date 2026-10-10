"""Registrations for the first four patterns, whose builders live in :mod:`anvilate.geometry`."""

from __future__ import annotations

from . import geometry
from .packs.industrial import CoverPlate
from .packs.machinery import TransmissionShaft
from .packs.structural import BasePlate
from .packs.timber import TimberBeam
from .patterns import Pattern, register

__all__: list[str] = []

register(
    Pattern(
        name=geometry.BASE_PLATE_PATTERN,
        element_type="base_plate",
        model=BasePlate,
        build=lambda element, name: geometry.build_base_plate(element),
        summary="A rectangular column base plate: width, depth and thickness.",
        outputs=("views", "step", "3mf", "dxf"),
    )
)
register(
    Pattern(
        name=geometry.COVER_PLATE_PATTERN,
        element_type="cover_plate",
        model=CoverPlate,
        build=lambda element, name: geometry.build_cover_plate(element),
        summary="A flat cover: rectangular, round, or round with a central bore.",
        outputs=("views", "step", "3mf", "dxf"),
    )
)
register(
    Pattern(
        name=geometry.TRANSMISSION_SHAFT_PATTERN,
        element_type="transmission_shaft",
        model=TransmissionShaft,
        build=lambda element, name: geometry.build_transmission_shaft(element, name=name),
        summary="A plain solid round shaft of one diameter and length.",
    )
)
register(
    Pattern(
        name=geometry.TIMBER_BEAM_PATTERN,
        element_type="timber_beam",
        model=TimberBeam,
        build=lambda element, name: geometry.build_timber_beam(element),
        summary="A sawn timber beam between its supports: dressed width and depth over a span.",
    )
)
