"""An O-ring across temperature, pressure and life, held to hand calculations.

The cross-section and the gland each scale by (1 + α·ΔT) from the drawing's temperature.
For CS 3.53 mm and a gland depth giving 18% squeeze at 23 °C, an elastomer at 2.0e-4 /K
and an aluminium gland at 2.3e-5 /K, at −40 °C (ΔT = −63 K):
CS = 3.53 × 0.9874 = 3.48552, E = 2.8946 × 0.998551 = 2.89041, squeeze = 0.17074.
"""

from __future__ import annotations

from math import pi

import pytest

from anvilate.analysis.o_ring import o_ring_seal_screen
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _mm(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="mm")


def _c(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="degC")


def _screen(**overrides: object):
    fields: dict[str, object] = {
        "cross_section_diameter": _mm(3.53), "gland_depth": _mm(2.8946),
        "groove_width": _mm(4.8), "reference_temperature": _c(23),
        "minimum_temperature": _c(-40), "maximum_temperature": _c(120),
        "seal_expansion": 2.0e-4, "gland_expansion": 2.3e-5, "minimum_squeeze": 0.15,
        "maximum_fill": 0.85, "limits_source": "the user's gland standard, rev C",
    } | overrides  # fmt: skip
    return o_ring_seal_screen(**fields)  # type: ignore[arg-type]


def _condition(screen, prefix: str):
    (c,) = [c for c in screen.conditions if c.condition.startswith(prefix)]
    return c


def test_squeeze_is_lowest_at_the_cold_extreme():
    """The spec's scenario: 18% at 23 °C, reported at −40 °C."""
    assert (3.53 - 2.8946) / 3.53 == pytest.approx(0.18, abs=1e-4)
    cold = _condition(_screen(), "squeeze at the cold extreme")
    cs, e = 3.53 * (1 - 2.0e-4 * 63), 2.8946 * (1 - 2.3e-5 * 63)
    assert cold.value == pytest.approx((cs - e) / cs, rel=1e-12)
    assert cold.value == pytest.approx(0.17074, abs=1e-5)
    assert cold.state == "pass" and "-40 °C" in cold.condition


def test_squeeze_lost_in_the_cold_fails_against_the_cited_minimum():
    cold = _condition(_screen(minimum_squeeze=0.175), "squeeze at the cold extreme")
    assert cold.state == "fail" and cold.limit == 0.175
    assert cold.source == "the user's gland standard, rev C"


def test_fill_is_highest_at_the_hot_extreme():
    hot = _condition(_screen(), "gland fill at the hot extreme")
    k_s, k_g = 1 + 2.0e-4 * 97, 1 + 2.3e-5 * 97
    expected = pi * (3.53 * k_s) ** 2 / 4 / (2.8946 * k_g * 4.8 * k_g)
    assert hot.value == pytest.approx(expected, rel=1e-12)
    # and it is above the 23 °C fill, π × 3.53²/4/(2.8946 × 4.8) = 0.70443
    assert hot.value > pi * 3.53**2 / 4 / (2.8946 * 4.8)


def test_extrusion_at_pressure_names_gap_limit_and_source():
    """The spec's scenario: a gap above the user's cited limit for 10 MPa and 70 Shore A."""
    screen = _screen(
        diametral_gap=_mm(0.20),
        extrusion_gap_limit=_mm(0.15),
        limits_source="limit read for 10 MPa, 70 Shore A, ORD 5700 Fig. 3-2",
    )
    gap = _condition(screen, "extrusion gap")
    assert gap.state == "fail" and not screen.passes
    assert "0.2 mm against a limit of 0.15 mm (limit read for 10 MPa" in gap.detail


def test_compression_set_leaves_less_squeeze():
    screen = _screen(compression_set=0.25, compression_set_source="elastomer record E-70-1000h")
    left = _condition(screen, "squeeze left")
    assert left.value == pytest.approx(0.17074 * 0.75, abs=1e-5)  # 0.12806 < 0.15
    assert left.state == "fail"


def test_an_undeclared_condition_keeps_the_screen_from_passing():
    screen = _screen(diametral_gap=_mm(0.1), extrusion_gap_limit=_mm(0.15), compression_set=0.1,
                     compression_set_source="record")  # fmt: skip
    assert _condition(screen, "fluid").state == "not evaluated"
    assert not screen.passes
    fully = _screen(diametral_gap=_mm(0.1), extrusion_gap_limit=_mm(0.15), compression_set=0.1,
                    compression_set_source="record", fluid_compatible=True)  # fmt: skip
    assert fully.passes and "seal passes" in str(fully)


def test_refusals():
    with pytest.raises(RefusalError, match="reference_temperature"):
        _screen(reference_temperature=_c(150))
    with pytest.raises(RefusalError, match="seal_expansion"):
        _screen(seal_expansion=0.2)
    with pytest.raises(RefusalError, match="compression_set_source"):
        _screen(compression_set=0.2)
    with pytest.raises(ValueError, match="minimum_temperature"):
        _screen(minimum_temperature=_mm(1))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_an_expansion_coefficient_that_is_no_number_is_refused(value):
    with pytest.raises(ValueError, match="gland_expansion"):
        _screen(gland_expansion=value)
