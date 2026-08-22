"""T1 analytical ASCE 7 load combinations (LRFD strength and ASD, closed-form).

Once the individual loads are known — dead, live, roof/snow/rain, wind, seismic (see
:mod:`~anvilate.analysis.building_loads`) — a structure is designed not for any one of them but for
the worst *factored combination* of them all acting together. ASCE 7 fixes the combinations and
their load factors; this module evaluates them and returns the governing (largest) one.

The two design philosophies weight the loads differently. **LRFD** (§2.3, strength design) inflates
each load to a strength level and checks against the member's factored resistance — e.g.
1.2D + 1.6L + 0.5S. **ASD** (§2.4, allowable stress) keeps the loads near their service level and
checks against an allowable — e.g. D + 0.75L + 0.75(0.6W) + 0.75S. Because LRFD works at strength
level, its governing combination is the larger number; the two are not directly comparable without
the matching resistance side.

The inputs are the load *effects* on a single element — the axial force, moment, or stress that each
load source produces in it — all in the same units and the same sense. The functions combine those
effects with the code factors and return the governing effect in the dead load's units, so they work
for forces, moments, or stresses alike.
"""

from __future__ import annotations

from ..units import Quantity, require_finite

__all__ = [
    "asce7_lrfd_factored_load",
    "asce7_asd_factored_load",
]


def _effects(
    dead: Quantity,
    live: Quantity | None,
    roof_snow_rain: Quantity | None,
    wind: Quantity | None,
    seismic: Quantity | None,
) -> tuple[float, float, float, float, float]:
    """Resolve the five load effects to magnitudes in the dead load's units."""
    if not isinstance(dead, Quantity):
        raise TypeError("dead must be a Quantity load effect")
    unit = dead.unit
    d = require_finite(dead, name="dead")
    if d < 0:
        raise ValueError("dead must be non-negative (pass load effects in a consistent sense)")

    def resolve(value: Quantity | None, name: str) -> float:
        if value is None:
            return 0.0
        if not value.has_dimension(dead.dimensionality):
            raise ValueError(
                f"{name} must share the dead load's dimensionality "
                f"({dead.dimensionality}); got {value.dimensionality}"
            )
        # A non-finite effect is refused here rather than carried. `max(combinations)`
        # DROPS a NaN candidate instead of propagating it, so a single NaN wind load
        # deletes every wind combination from the envelope and the governing effect is
        # reported from the survivors -- 57% low, with a comfortable PASS. The sibling
        # `anvilate.loads.LoadCombination.evaluate` has refused this from the start; this
        # is the same rule where the analysis-layer version needed it.
        require_finite(value, name=name)
        m = value.to(unit).magnitude
        if m < 0:
            raise ValueError(f"{name} must be non-negative (use a consistent sense)")
        return m

    return (
        d,
        resolve(live, "live"),
        resolve(roof_snow_rain, "roof_snow_rain"),
        resolve(wind, "wind"),
        resolve(seismic, "seismic"),
    )


def asce7_lrfd_factored_load(
    *,
    dead: Quantity,
    live: Quantity | None = None,
    roof_snow_rain: Quantity | None = None,
    wind: Quantity | None = None,
    seismic: Quantity | None = None,
) -> Quantity:
    """The governing ASCE 7 LRFD (strength) load combination (§2.3.1).

    The largest of the seven basic strength combinations, evaluated on the load *effects* passed in:
    ``dead`` D, ``live`` L, ``roof_snow_rain`` S (the largest of roof-live, snow, and rain),
    ``wind`` W, and ``seismic`` E — each the force, moment, or stress that load source produces in
    the element, in a consistent sense. The combinations are 1.4D; 1.2D+1.6L+0.5S;
    1.2D+1.6S+max(L,0.5W); 1.2D+1.0W+L+0.5S; 1.2D+1.0E+L+0.2S; 0.9D+1.0W; and 0.9D+1.0E. Omitted
    loads are taken as zero. Returns the governing factored effect in the dead load's units.
    """
    d, live_e, s, w, e = _effects(dead, live, roof_snow_rain, wind, seismic)
    combinations = (
        1.4 * d,
        1.2 * d + 1.6 * live_e + 0.5 * s,
        1.2 * d + 1.6 * s + max(live_e, 0.5 * w),
        1.2 * d + 1.0 * w + live_e + 0.5 * s,
        1.2 * d + 1.0 * e + live_e + 0.2 * s,
        0.9 * d + 1.0 * w,
        0.9 * d + 1.0 * e,
    )
    return Quantity(magnitude=max(combinations), unit=dead.unit)


def asce7_asd_factored_load(
    *,
    dead: Quantity,
    live: Quantity | None = None,
    roof_snow_rain: Quantity | None = None,
    wind: Quantity | None = None,
    seismic: Quantity | None = None,
) -> Quantity:
    """The governing ASCE 7 ASD (allowable stress) load combination (§2.4.1).

    The largest of the ASD basic combinations, evaluated on the same load *effects* as
    :func:`asce7_lrfd_factored_load`: ``dead`` D, ``live`` L, ``roof_snow_rain`` S, ``wind`` W, and
    ``seismic`` E. The combinations are D; D+L; D+S; D+0.75L+0.75S; D+max(0.6W,0.7E);
    D+0.75L+0.75(0.6W)+0.75S; D+0.75L+0.75(0.7E)+0.75S; 0.6D+0.6W; and 0.6D+0.7E. These keep the
    loads near service level, so the result is smaller than the LRFD one and is checked against an
    allowable, not a factored, resistance. Omitted loads are taken as zero. Returns the governing
    effect in the dead load's units.
    """
    d, live_e, s, w, e = _effects(dead, live, roof_snow_rain, wind, seismic)
    combinations = (
        d,
        d + live_e,
        d + s,
        d + 0.75 * live_e + 0.75 * s,
        d + max(0.6 * w, 0.7 * e),
        d + 0.75 * live_e + 0.75 * (0.6 * w) + 0.75 * s,
        d + 0.75 * live_e + 0.75 * (0.7 * e) + 0.75 * s,
        0.6 * d + 0.6 * w,
        0.6 * d + 0.7 * e,
    )
    return Quantity(magnitude=max(combinations), unit=dead.unit)
