"""Worked example: an O-ring that seals on the bench and loses its squeeze in the cold.

A 3.53 mm O-ring in an aluminium gland is drawn for 18% squeeze at 23 °C. The elastomer
shrinks about ten times as fast as the gland, so at -40 °C the squeeze falls to 17.1%.
Against a 15% minimum that passes; against a stricter 17.5% minimum, it fails.

Over its life the elastomer takes a compression set. With 25% set from the elastomer
record, the squeeze left at -40 °C is 12.8%: the seal that passed on day one does not
pass at end of life, cold. At 120 °C the gland fill rises to 72.9%, still inside an 85%
limit, so heat is not the problem here.

The limits are the caller's, each with its source; the screen applies them across the
temperature range rather than at the drawing's single temperature.

Run it directly (``python examples/o_ring_cold_squeeze.py``);
:func:`o_ring_cold_squeeze` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import o_ring_seal_screen
from anvilate.units import Quantity


def _screen(minimum_squeeze: float, compression_set: float | None = None):
    return o_ring_seal_screen(
        cross_section_diameter=Quantity(magnitude=3.53, unit="mm"),
        gland_depth=Quantity(magnitude=2.8946, unit="mm"),
        groove_width=Quantity(magnitude=4.8, unit="mm"),
        reference_temperature=Quantity(magnitude=23.0, unit="degC"),
        minimum_temperature=Quantity(magnitude=-40.0, unit="degC"),
        maximum_temperature=Quantity(magnitude=120.0, unit="degC"),
        seal_expansion=2.0e-4,
        gland_expansion=2.3e-5,
        minimum_squeeze=minimum_squeeze,
        maximum_fill=0.85,
        limits_source="the program's gland standard (illustrative)",
        compression_set=compression_set,
        compression_set_source="elastomer record, 1,000 h at 100 °C (illustrative)",
    )


def _value(screen, prefix: str) -> float:
    return next(c.value for c in screen.conditions if c.condition.startswith(prefix))


def o_ring_cold_squeeze() -> dict[str, float | str]:
    """Return the cold squeeze, the hot fill, the squeeze left after set, and the verdicts."""
    loose, strict = _screen(0.15), _screen(0.175)
    aged = _screen(0.15, compression_set=0.25)

    def state(screen, prefix: str) -> str:
        return next(c.state for c in screen.conditions if c.condition.startswith(prefix))

    return {
        "cold_squeeze": _value(loose, "squeeze at the cold"),
        "hot_fill": _value(loose, "gland fill"),
        "squeeze_left": _value(aged, "squeeze left"),
        "at_15": state(loose, "squeeze at the cold"),
        "at_17_5": state(strict, "squeeze at the cold"),
        "aged": state(aged, "squeeze left"),
    }


def main() -> None:
    d = o_ring_cold_squeeze()
    print(f"squeeze at -40 °C: {d['cold_squeeze']:.1%}")
    print(f"against 15%: {d['at_15']}; against 17.5%: {d['at_17_5']}")
    print(f"after 25% compression set: {d['squeeze_left']:.1%} ({d['aged']})")
    print(f"fill at 120 °C: {d['hot_fill']:.1%}")


if __name__ == "__main__":
    main()
