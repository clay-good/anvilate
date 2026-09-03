"""Anvilate units layer: SI and US customary as first-class citizens.

Physical values enter the system as :class:`Quantity` objects that keep the
unit as entered, expose the canonical Pint quantity for computation, and are
dimensionally checked wherever a field pins an expected dimension.
"""

from __future__ import annotations

from .format import decimals_distinguishing, decimals_for, render, render_dual
from .quantity import (
    DimensionError,
    MissingUnitError,
    Quantity,
    UnitError,
    require_dimension,
    require_finite,
)
from .registry import UREG, build_registry
from .rotation import (
    AmbiguousCountRateError,
    AmbiguousRotationalSpeedError,
    angular_speed_rad_per_s,
    count_rate_per_second,
    revolutions_per_minute,
    revolutions_per_second,
)
from .system import UnitSystem
from .temperature import OffsetTemperatureError, temperature_difference_kelvin

__all__ = [
    "Quantity",
    "UnitError",
    "MissingUnitError",
    "DimensionError",
    "require_dimension",
    "require_finite",
    "UnitSystem",
    "UREG",
    "build_registry",
    # The rotational-speed and offset-temperature traps, and the converters that close
    # them. Every one of these is raised at a caller, and a caller who wants to tell an
    # ambiguous rpm from any other unit error has to be able to import the class from the
    # package the rest of the units layer lives in.
    "AmbiguousRotationalSpeedError",
    "AmbiguousCountRateError",
    "OffsetTemperatureError",
    "angular_speed_rad_per_s",
    "revolutions_per_minute",
    "revolutions_per_second",
    "count_rate_per_second",
    "temperature_difference_kelvin",
    "render",
    "render_dual",
    "decimals_for",
    "decimals_distinguishing",
]
