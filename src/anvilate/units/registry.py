"""The process-wide Pint unit registry.

A single shared registry guarantees that every :class:`~anvilate.units.quantity.Quantity`
resolves against the same unit definitions, so dimensional analysis is
consistent everywhere. Pint already ships the units engineering codes are
written in (``kip``, ``ksi``, ``psi``, ``lbf``, ``kN``, ``MPa`` and the
derived moment/inertia units); we only add the distributed line loads it
omits.
"""

from __future__ import annotations

import pint

__all__ = ["UREG", "build_registry"]


def build_registry() -> pint.UnitRegistry:
    """Build the Anvilate unit registry."""
    ureg = pint.UnitRegistry()
    # Distributed line loads used throughout US structural practice; Pint does
    # not define these, so we express them in terms of units it does.
    ureg.define("pound_per_foot = pound_force / foot = plf")
    ureg.define("kip_per_foot = kip / foot = klf")
    return ureg


#: The shared registry. Import this, do not construct your own — Pint quantities
#: from different registries cannot be compared or combined.
UREG = build_registry()
