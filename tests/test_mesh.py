"""Tagged faces across the mesher boundary: the shape carries the name, and is verified.

The FEA tier applies a load to a face the spec NAMED. The name is the one thing a STEP
write and a mesher's read may not preserve, so what is carried across is the face's own
shape — its area, its area centroid, and where it faces when it is flat — recorded at
build and matched against what comes back.

What these hold is mostly the refusals. A load applied to the wrong face is not a wrong
number somebody can argue with; it is a different problem solved correctly, and nothing
downstream would say so.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("build123d")

from anvilate.geometry import build_base_plate, build_spec  # noqa: E402
from anvilate.mesh import (  # noqa: E402
    ROUND_TRIP_DISTANCE_TOLERANCE_MM,
    FaceSignature,
    face_signatures,
    match_face_signatures,
)
from test_geometry import _plate  # noqa: E402


def _signed() -> tuple[FaceSignature, ...]:
    return face_signatures(build_base_plate(_plate()).faces)


def test_every_tagged_face_is_recorded_by_its_shape_and_not_its_name():
    """The 300 x 240 x 25 base plate: six faces, each with the area its sides give it."""
    signed = {s.tag: s for s in _signed()}
    assert set(signed) == {"west", "east", "south", "north", "bottom", "top"}
    assert signed["top"].area_mm2 == pytest.approx(300 * 240)
    assert signed["west"].area_mm2 == pytest.approx(240 * 25)
    assert signed["south"].area_mm2 == pytest.approx(300 * 25)
    assert signed["top"].centroid_mm == pytest.approx((0.0, 0.0, 25.0))
    assert signed["bottom"].centroid_mm == pytest.approx((0.0, 0.0, 0.0))
    # Flat faces face somewhere, and the two that differ ONLY in that are the test.
    assert signed["west"].normal == pytest.approx((-1.0, 0.0, 0.0))
    assert signed["east"].normal == pytest.approx((1.0, 0.0, 0.0))
    assert signed["west"].area_mm2 == signed["east"].area_mm2


def test_a_curved_face_records_its_area_centroid_and_no_normal():
    """A cylinder has no one normal, and its PARAMETRIC centre is not its centroid.

    The shaft's outside surface is parameterised from a point on the surface, a radius off
    the axis. Recording that point would record how the face happens to be parameterised,
    which is exactly what a round trip is free to change; the area centroid is on the axis.
    """
    from pathlib import Path

    from anvilate._models import parse_yaml
    from anvilate.spec import parse_spec

    document = Path(__file__).parents[1] / "examples" / "transmission_shaft.spec.yaml"
    built = build_spec(parse_spec(parse_yaml(document.read_text(encoding="utf-8"))))
    signed = {s.tag: s for s in face_signatures(built.faces)}
    outside = signed["outside_surface"]
    assert outside.normal is None
    assert outside.centroid_mm[0] == pytest.approx(0.0, abs=1e-9)
    assert outside.centroid_mm[1] == pytest.approx(0.0, abs=1e-9)
    # Its two flat ends do have one, and they point opposite ways.
    assert signed["drive_end"].normal == pytest.approx((0.0, 0.0, -1.0))
    assert signed["driven_end"].normal == pytest.approx((0.0, 0.0, 1.0))


def test_the_tags_are_found_again_whatever_order_the_faces_come_back_in():
    """The mesher's face order is its own; the match does not depend on it."""
    signed = _signed()
    shuffled = list(reversed(signed))
    matched = match_face_signatures(signed, shuffled).faces
    assert set(matched) == {s.tag for s in signed}
    for tag, index in matched.items():
        assert shuffled[index].tag == tag


def test_the_match_reads_as_which_face_carries_which_tag():
    """Both renderings, against the values they are built from rather than each other."""
    signed = _signed()
    top = next(s for s in signed if s.tag == "top")
    assert str(top) == "top: 72000 mm² centred at (0, 0, 25) mm facing 0, 0, 1"
    shuffled = list(reversed(signed))
    match = match_face_signatures(signed, shuffled)
    rendered = str(match)
    for tag, index in match.faces.items():
        assert f"{tag} -> face {index}" in rendered
    # In tag order, so two matches of the same pairs read the same whatever order they
    # were found in.
    assert rendered.index("bottom") < rendered.index("east") < rendered.index("west")


def test_a_tag_that_matches_nothing_is_refused_rather_than_dropped():
    signed = _signed()
    without_top = [s for s in signed if s.tag != "top"]
    with pytest.raises(ValueError, match="no imported face matches top"):
        match_face_signatures(signed, without_top)


def test_a_tag_that_matches_two_faces_is_refused_rather_than_chosen_between():
    """Two faces of one shape in one place: nothing can say which the load belongs on."""
    signed = _signed()
    top = next(s for s in signed if s.tag == "top")
    twice = [*signed, top.model_copy(update={"tag": "an imported face with no name"})]
    with pytest.raises(ValueError, match="2 imported faces match top"):
        match_face_signatures(signed, twice)


def test_one_imported_face_cannot_carry_two_tags():
    """Two recorded tags on one shape: the solid changed under the tags, and it says so."""
    signed = list(_signed())
    top = next(s for s in signed if s.tag == "top")
    signed.append(top.model_copy(update={"tag": "also_top"}))
    with pytest.raises(ValueError, match="claimed by 'top' and by 'also_top'"):
        match_face_signatures(signed, _signed())


def test_a_face_that_moved_further_than_the_round_trip_allows_is_not_that_face():
    """The tolerance is float noise through a STEP write, not a physical allowance.

    Just inside it the face is still itself; a hundred times outside it is a different
    face, and refusing is the right answer rather than applying the load anyway.
    """
    signed = _signed()
    top = next(s for s in signed if s.tag == "top")
    nudge = ROUND_TRIP_DISTANCE_TOLERANCE_MM / 2
    near = [s.model_copy(update={"centroid_mm": (s.centroid_mm[0] + nudge, *s.centroid_mm[1:])})
            for s in signed]  # fmt: skip
    assert match_face_signatures(signed, near).faces["top"] == signed.index(top)
    far = [s.model_copy(update={"centroid_mm": (s.centroid_mm[0] + nudge * 200,
                                                *s.centroid_mm[1:])}) for s in signed]  # fmt: skip
    with pytest.raises(ValueError, match="no imported face matches"):
        match_face_signatures(signed, far)


def test_a_signature_states_a_real_area_a_finite_centroid_and_a_unit_normal():
    fields = {"tag": "top", "area_mm2": 10.0, "centroid_mm": (0.0, 0.0, 1.0)}
    with pytest.raises(ValueError, match="a centroid is three finite millimetres"):
        FaceSignature(**{**fields, "centroid_mm": (0.0, math.inf, 0.0)})
    with pytest.raises(ValueError, match="a normal is a unit direction"):
        FaceSignature(**fields, normal=(0.0, 0.0, 2.0))
    with pytest.raises(ValueError):
        FaceSignature(**{**fields, "area_mm2": 0.0})
    assert "10 mm" in str(FaceSignature(**fields))


def test_the_match_refuses_what_it_cannot_be_asked():
    signed = _signed()
    with pytest.raises(ValueError, match="recorded is the signatures taken when"):
        match_face_signatures([], signed)
    with pytest.raises(ValueError, match="a mesher that returned no face"):
        match_face_signatures(signed, [])
    with pytest.raises(ValueError, match="the tolerances are positive"):
        match_face_signatures(signed, signed, area_tolerance=0.0)
    with pytest.raises(ValueError, match="and it has none"):
        face_signatures({})
