"""Tests for feature control frame drawing geometry.

Two things are pinned here. First, the **symbol constructions**, against their defining
properties rather than against numbers the code itself produced: a circle whose tangent
lines are actually tangent, an angle that is actually 30°, a frame that is actually two
character heights tall. A test whose expected values come from running the thing under
test passes on its own drift.

Second, **propagation**. One :class:`~anvilate.gdt.FeatureControlFrame` feeds three
consumers — the text rendering, the QIF characteristic definition, and the drawing
geometry here — and a declaration changed in the model has to reach all three. A consumer
that quietly ignores a modifier is the failure this catches: on a drawing it is a callout
looser than the one declared, and in QIF it is one tighter.
"""

from __future__ import annotations

import math

import pytest

from anvilate.export.dxf import export_feature_control_frame_dxf
from anvilate.export.fcf import (
    Arc,
    Circle,
    Polyline,
    _circled_letter,
    _diameter_glyph,
    _statistical_glyph,
    characteristic_symbol,
    frame_drawing,
)
from anvilate.export.qif import qif_characteristic_mapping
from anvilate.gdt import (
    Characteristic,
    DatumBoundary,
    DatumReference,
    FeatureControlFrame,
    FeatureType,
    FrameModifier,
    MaterialCondition,
    Y14Edition,
)
from anvilate.units import Quantity

H = Quantity(magnitude=10.0, unit="mm")  # a round character height, so h and mm coincide


def _points(strokes) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for stroke in strokes:
        if isinstance(stroke, Polyline):
            out.extend(stroke.points)
    return out


def _bbox(strokes) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for stroke in strokes:
        if isinstance(stroke, Polyline):
            xs.extend(p[0] for p in stroke.points)
            ys.extend(p[1] for p in stroke.points)
        elif isinstance(stroke, Circle):
            xs.extend((stroke.center[0] - stroke.radius, stroke.center[0] + stroke.radius))
            ys.extend((stroke.center[1] - stroke.radius, stroke.center[1] + stroke.radius))
        else:
            for angle in (stroke.start_angle, stroke.end_angle, 0.0, 90.0, 180.0, 270.0):
                sweep = (stroke.end_angle - stroke.start_angle) % 360.0
                if (angle - stroke.start_angle) % 360.0 > sweep:
                    continue
                xs.append(stroke.center[0] + stroke.radius * math.cos(math.radians(angle)))
                ys.append(stroke.center[1] + stroke.radius * math.sin(math.radians(angle)))
    return min(xs), min(ys), max(xs), max(ys)


def _segments(strokes) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    out = []
    for stroke in strokes:
        if not isinstance(stroke, Polyline):
            continue
        pts = list(stroke.points) + ([stroke.points[0]] if stroke.closed else [])
        out.extend(zip(pts, pts[1:], strict=False))
    return out


def _angle_deg(seg) -> float:
    (x0, y0), (x1, y1) = seg
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0


# --- Every characteristic can be drawn ------------------------------------------------


def test_every_characteristic_has_a_symbol():
    """A characteristic the model accepts and the drawing layer cannot draw is a frame
    that renders as text and silently vanishes from the drawing."""
    drawn = {c for c in Characteristic if characteristic_symbol(c, height=H)}
    assert drawn == set(Characteristic)
    assert len(drawn) == 14, "the geometric characteristics of Y14.5 number fourteen"


@pytest.mark.parametrize("characteristic", list(Characteristic))
def test_symbol_geometry_is_finite_and_centred(characteristic):
    strokes = characteristic_symbol(characteristic, height=H, center=(7.0, -3.0))
    x0, y0, x1, y1 = _bbox(strokes)
    assert all(math.isfinite(v) for v in (x0, y0, x1, y1))
    assert (x0 + x1) / 2 == pytest.approx(7.0, abs=1e-9)
    assert (y0 + y1) / 2 == pytest.approx(-3.0, abs=1e-9)
    assert x1 - x0 > 0


@pytest.mark.parametrize("characteristic", list(Characteristic))
def test_symbols_scale_with_the_character_height(characteristic):
    """Every proportion is a multiple of h, so doubling h doubles every extent."""
    small = _bbox(characteristic_symbol(characteristic, height=H))
    big = _bbox(characteristic_symbol(characteristic, height=Quantity(magnitude=20.0, unit="mm")))
    assert big[2] - big[0] == pytest.approx(2 * (small[2] - small[0]), rel=1e-12)
    assert big[3] - big[1] == pytest.approx(2 * (small[3] - small[1]), rel=1e-12)


# --- The constructions, pinned by their defining property -----------------------------
#
# Proportions are from the Genium Drafting Manual Section 6.1 symbol chart (based on
# ASME Y14.5M-1994), read out of the figures rather than recalled — which is how the
# symmetry symbol turned out to be three lines of 2h, 1.2h and 2h rather than an equals
# sign, and how the cylindricity tangents turned out to stand at 60°.


def test_straightness_is_a_line_two_character_heights_long():
    x0, y0, x1, y1 = _bbox(characteristic_symbol(Characteristic.STRAIGHTNESS, height=H))
    assert x1 - x0 == pytest.approx(20.0)
    assert y1 - y0 == pytest.approx(0.0)


def test_circularity_is_a_circle_of_one_and_a_half_character_heights():
    (circle,) = characteristic_symbol(Characteristic.CIRCULARITY, height=H)
    assert isinstance(circle, Circle)
    assert 2 * circle.radius == pytest.approx(15.0)


def test_cylindricity_lines_are_tangent_to_its_circle_at_sixty_degrees():
    strokes = characteristic_symbol(Characteristic.CYLINDRICITY, height=H)
    circles = [s for s in strokes if isinstance(s, Circle)]
    assert len(circles) == 1
    circle = circles[0]
    assert 2 * circle.radius == pytest.approx(10.0), "the circle is h in diameter"
    segments = _segments(strokes)
    assert len(segments) == 2
    for seg in segments:
        assert _angle_deg(seg) == pytest.approx(60.0)
        (x0, y0), (x1, y1) = seg
        # Distance from the circle centre to the line through the segment.
        dx, dy = x1 - x0, y1 - y0
        distance = abs(dy * (circle.center[0] - x0) - dx * (circle.center[1] - y0)) / math.hypot(
            dx, dy
        )
        assert distance == pytest.approx(circle.radius), "the lines are drawn tangent"
    _, y0, _, y1 = _bbox(strokes)
    assert y1 - y0 == pytest.approx(15.0), "the pair stands 1.5h tall"


def test_angularity_is_a_thirty_degree_angle():
    strokes = characteristic_symbol(Characteristic.ANGULARITY, height=H)
    angles = sorted(_angle_deg(s) for s in _segments(strokes))
    assert angles[0] == pytest.approx(0.0), "a horizontal leg"
    assert angles[1] == pytest.approx(30.0), "and one at 30° to it"
    _, y0, _, y1 = _bbox(strokes)
    assert y1 - y0 == pytest.approx(15.0)


def test_perpendicularity_is_a_right_angle_on_a_two_h_base():
    strokes = characteristic_symbol(Characteristic.PERPENDICULARITY, height=H)
    angles = sorted(_angle_deg(s) for s in _segments(strokes))
    assert angles == pytest.approx([0.0, 90.0])
    x0, y0, x1, y1 = _bbox(strokes)
    assert x1 - x0 == pytest.approx(20.0)
    assert y1 - y0 == pytest.approx(15.0)


def test_parallelism_is_two_parallel_lines_at_sixty_degrees():
    strokes = characteristic_symbol(Characteristic.PARALLELISM, height=H)
    segments = _segments(strokes)
    assert len(segments) == 2
    assert [_angle_deg(s) for s in segments] == pytest.approx([60.0, 60.0])
    # 0.6h apart measured horizontally, which is what the chart dimensions.
    lows = sorted(min(p[1] for p in s) for s in segments)
    bottoms = sorted(s[0][0] if s[0][1] < s[1][1] else s[1][0] for s in segments)
    assert lows[0] == pytest.approx(lows[1])
    assert bottoms[1] - bottoms[0] == pytest.approx(6.0)


def test_position_is_a_crosshair_through_a_circle():
    strokes = characteristic_symbol(Characteristic.POSITION, height=H)
    circles = [s for s in strokes if isinstance(s, Circle)]
    assert len(circles) == 1 and 2 * circles[0].radius == pytest.approx(10.0)
    angles = sorted(_angle_deg(s) for s in _segments(strokes))
    assert angles == pytest.approx([0.0, 90.0])
    x0, y0, x1, y1 = _bbox(strokes)
    assert (x1 - x0, y1 - y0) == pytest.approx((15.0, 15.0))


def test_concentricity_is_two_concentric_circles():
    circles = list(characteristic_symbol(Characteristic.CONCENTRICITY, height=H))
    assert all(isinstance(c, Circle) for c in circles)
    assert circles[0].center == circles[1].center
    assert sorted(2 * c.radius for c in circles) == pytest.approx([10.0, 15.0])


def test_symmetry_is_three_lines_and_the_middle_one_is_the_short_one():
    """Not an equals sign, and not three lines of the same length."""
    segments = _segments(characteristic_symbol(Characteristic.SYMMETRY, height=H))
    assert len(segments) == 3
    by_height = sorted(segments, key=lambda s: s[0][1])
    lengths = [abs(s[1][0] - s[0][0]) for s in by_height]
    assert lengths == pytest.approx([20.0, 12.0, 20.0])
    spacings = [by_height[1][0][1] - by_height[0][0][1], by_height[2][0][1] - by_height[1][0][1]]
    assert spacings == pytest.approx([5.0, 5.0])


def test_line_profile_is_an_open_arc_and_surface_profile_closes_it():
    line = characteristic_symbol(Characteristic.PROFILE_OF_A_LINE, height=H)
    surface = characteristic_symbol(Characteristic.PROFILE_OF_A_SURFACE, height=H)
    assert [type(s) for s in line] == [Arc]
    assert sum(isinstance(s, Arc) for s in surface) == 1
    assert len(_segments(surface)) == 1, "the surface symbol is the arc plus a base line"
    for strokes in (line, surface):
        x0, y0, x1, y1 = _bbox(strokes)
        assert (x1 - x0, y1 - y0) == pytest.approx((20.0, 10.0))


def test_total_runout_is_two_of_the_circular_runout_arrow():
    single = _segments(characteristic_symbol(Characteristic.CIRCULAR_RUNOUT, height=H))
    total = _segments(characteristic_symbol(Characteristic.TOTAL_RUNOUT, height=H))
    assert len(total) == 2 * len(single) + 1, "two arrows joined by one line at their tails"
    shafts = [s for s in total if _angle_deg(s) == pytest.approx(45.0)]
    assert len(shafts) == 2
    tails = sorted(min(s, key=lambda p: p[1])[0] for s in shafts)
    assert tails[1] - tails[0] == pytest.approx(11.0), "1.1h apart, per the chart"


def test_the_modifier_glyphs_stand_one_and_a_half_character_heights_tall():
    """Ø, the circled letters and ⟨ST⟩ are all dimensioned 1.5h tall on the chart.

    For Ø that 1.5h is the symbol's height and not the slash's length: read as the length
    it draws a Ø only 1.3h tall, barely taller than the circle it crosses.
    """
    for glyph in (_diameter_glyph(), _circled_letter("M"), _statistical_glyph()):
        assert glyph.height == pytest.approx(1.5)
    assert _diameter_glyph().width == pytest.approx(1.0), "the circle is h across"
    assert _circled_letter("M").width == pytest.approx(1.5)
    assert _statistical_glyph().width == pytest.approx(2.5)


# --- Frame layout ---------------------------------------------------------------------


def _frame(**kwargs) -> FeatureControlFrame:
    defaults = {
        "characteristic": Characteristic.POSITION,
        "tolerance": Quantity(magnitude=0.2, unit="mm"),
        "feature_type": FeatureType.FEATURE_OF_SIZE,
        "datums": (DatumReference(letter="A"),),
    }
    return FeatureControlFrame(**{**defaults, **kwargs})


def test_the_frame_is_two_character_heights_tall_with_one_compartment_per_part():
    frame = _frame(
        datums=(DatumReference(letter="A"), DatumReference(letter="B"), DatumReference(letter="C"))
    )
    drawing = frame_drawing(frame, text_height=H)
    assert drawing.height == pytest.approx(20.0)
    assert len(drawing.compartment_edges) == 2 + 1 + 3, "symbol, value, and one per datum"
    assert drawing.compartment_edges == tuple(sorted(drawing.compartment_edges))
    assert drawing.compartment_edges[-1] - drawing.compartment_edges[0] == pytest.approx(
        drawing.width
    )


def test_nothing_in_a_compartment_crosses_a_divider():
    """The layout allowance is an allowance, so the containment is what gets asserted.

    Every symbol and every text run has to sit inside one compartment. A glyph that
    straddles a divider is a callout a reader assigns to the wrong compartment — a datum
    modifier read as belonging to the tolerance, say.
    """
    frame = _frame(
        material_condition=MaterialCondition.MMC,
        modifiers=(FrameModifier.DIAMETER, FrameModifier.PROJECTED, FrameModifier.STATISTICAL),
        datums=(
            DatumReference(letter="A"),
            DatumReference(letter="BB", boundary=DatumBoundary.MMB, is_feature_of_size=True),
        ),
    )
    drawing = frame_drawing(frame, text_height=H)
    edges = drawing.compartment_edges
    intervals = list(zip(edges, edges[1:], strict=False))
    # The frame box and the dividers are the last strokes; everything before them is
    # symbol geometry that must live inside a compartment.
    content = drawing.strokes[: -(1 + len(intervals) - 1)]
    assert content, "the frame drew no symbol geometry at all"
    for stroke in content:
        x0, _, x1, _ = _bbox([stroke])
        assert any(lo - 1e-9 <= x0 and x1 <= hi + 1e-9 for lo, hi in intervals), (
            f"symbol geometry spanning {x0:.3f}..{x1:.3f} crosses a compartment divider"
        )
    for label in drawing.labels:
        half = len(label.text) * 0.75 * label.height / 2
        assert any(
            lo - 1e-9 <= label.center[0] - half and label.center[0] + half <= hi + 1e-9
            for lo, hi in intervals
        ), f"the text {label.text!r} crosses a compartment divider"


def test_everything_drawn_lies_inside_the_frame_box():
    drawing = frame_drawing(_frame(), text_height=H, origin=(12.0, -4.0))
    x0, y0, x1, y1 = _bbox(drawing.strokes)
    assert (x0, y0) == pytest.approx((12.0, -4.0))
    assert (x1, y1) == pytest.approx((12.0 + drawing.width, -4.0 + drawing.height))


def test_the_tolerance_is_drawn_in_millimetres():
    """A frame declared in inches whose number crossed unchanged would read 25.4 times
    tighter than the one declared."""
    drawing = frame_drawing(_frame(tolerance=Quantity(magnitude=0.005, unit="in")), text_height=H)
    assert [label.text for label in drawing.labels] == ["0.127", "A"]


def test_a_tolerance_a_drawing_cannot_carry_is_refused():
    with pytest.raises(ValueError, match="cannot carry as a number"):
        frame_drawing(_frame(tolerance=Quantity(magnitude=1e-7, unit="mm")), text_height=H)


def test_the_character_height_must_be_a_positive_length():
    with pytest.raises(ValueError, match=r"\[length\]"):
        frame_drawing(_frame(), text_height=Quantity(magnitude=3.5, unit="kg"))
    with pytest.raises(ValueError, match="must be positive"):
        frame_drawing(_frame(), text_height=Quantity(magnitude=0.0, unit="mm"))


def test_a_datum_letter_the_layout_allowance_was_never_checked_for_is_refused():
    """The model's datum-letter rule is ``isalpha() and isupper()``, which ``Ä`` satisfies.

    That is right for the model — a drawing in another language carries the letters it
    carries — and it means the drawing layer's closed character set is a guard that can
    actually fire, not decoration. The width allowance was measured for ASCII digits and
    letters; laying out a character it was never checked for is how text ends up across a
    compartment divider.
    """
    exotic = DatumReference(letter="Ä")
    assert exotic.letter == "Ä", "the model accepts it, which is what makes the guard live"
    with pytest.raises(ValueError, match="width allowance was never checked"):
        frame_drawing(_frame(datums=(exotic,)), text_height=H)


def test_an_arc_survives_the_stroke_union():
    """``Stroke`` is a pydantic union, and an Arc has every field a Circle has plus two.

    A union that coerced the profile arc to a Circle would draw a full circle where the
    symbol is an open one, and every extent assertion would still pass.
    """
    frame = _frame(
        characteristic=Characteristic.PROFILE_OF_A_LINE,
        feature_type=FeatureType.SURFACE,
        datums=(),
    )
    kinds = {type(stroke).__name__ for stroke in frame_drawing(frame, text_height=H).strokes}
    assert "Arc" in kinds


# --- Propagation: one declaration, three consumers ------------------------------------


def _consumers(frame: FeatureControlFrame):
    drawing = frame_drawing(frame, text_height=H)
    return frame.render(), qif_characteristic_mapping(frame), drawing


def test_a_diametral_zone_reaches_all_three_consumers():
    plain = _frame()
    diametral = _frame(modifiers=(FrameModifier.DIAMETER,))
    text, qif, drawing = _consumers(plain)
    d_text, d_qif, d_drawing = _consumers(diametral)

    assert "Ø" not in text and "Ø" in d_text
    assert qif.zone_shape != d_qif.zone_shape
    assert d_qif.zone_shape == "DiametricalZone"
    assert d_drawing.width > drawing.width, "the drawn frame grew by a Ø glyph"
    assert len(d_drawing.strokes) > len(drawing.strokes)


def test_a_material_condition_reaches_all_three_consumers():
    rfs = _frame()
    mmc = _frame(material_condition=MaterialCondition.MMC)
    text, qif, drawing = _consumers(rfs)
    m_text, m_qif, m_drawing = _consumers(mmc)

    assert "Ⓜ" not in text and "Ⓜ" in m_text
    assert qif.material_modifier == "REGARDLESS"
    assert m_qif.material_modifier == "MAXIMUM"
    assert "M" not in [label.text for label in drawing.labels]
    assert "M" in [label.text for label in m_drawing.labels], (
        "a modifier that vanishes on the drawing is a looser callout than the one declared"
    )


def test_a_datum_reference_reaches_all_three_consumers():
    one = _frame()
    two = _frame(datums=(DatumReference(letter="A"), DatumReference(letter="B")))
    text, qif, drawing = _consumers(one)
    t_text, t_qif, t_drawing = _consumers(two)

    assert text.count("|") + 1 == 3 and t_text.count("|") + 1 == 4
    assert len(qif.datums) == 1 and len(t_qif.datums) == 2
    assert len(drawing.compartment_edges) == 4 and len(t_drawing.compartment_edges) == 5


def test_the_characteristic_itself_reaches_all_three_consumers():
    position = _frame()
    runout = _frame(characteristic=Characteristic.TOTAL_RUNOUT)
    text, qif, drawing = _consumers(position)
    r_text, r_qif, r_drawing = _consumers(runout)

    assert text.split(" | ")[0] != r_text.split(" | ")[0]
    assert qif.definition_type != r_qif.definition_type
    assert drawing.compartment_edges[1] != r_drawing.compartment_edges[1], (
        "a different symbol sizes its compartment differently"
    )


def test_a_legacy_characteristic_still_draws_on_the_edition_that_has_it():
    frame = _frame(
        characteristic=Characteristic.CONCENTRICITY,
        edition=Y14Edition.Y14_5_2009,
        modifiers=(FrameModifier.DIAMETER,),
    )
    drawing = frame_drawing(frame, text_height=H)
    assert drawing.width > 0
    assert "◎" in frame.render()


# --- DXF ------------------------------------------------------------------------------


def test_the_dxf_carries_the_frame_on_its_own_layer(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    frame = _frame(material_condition=MaterialCondition.MMC, modifiers=(FrameModifier.DIAMETER,))
    path = export_feature_control_frame_dxf(frame=frame, path=tmp_path / "fcf.dxf", text_height=H)
    doc = ezdxf.readfile(path)
    entities = list(doc.modelspace())
    assert entities, "the DXF came back empty"
    assert {e.dxf.layer for e in entities} == {"GDT"}, (
        "annotation on a cut layer is geometry a fabricator's tool path picks up"
    )
    drawing = frame_drawing(frame, text_height=H)
    assert len(entities) == len(drawing.strokes) + len(drawing.labels)
    assert [e.dxf.text for e in entities if e.dxftype() == "TEXT"] == ["0.2", "M", "A"]


def test_the_dxf_writes_an_arc_as_an_arc(tmp_path):
    """The profile symbols are the only arcs in the set, so nothing else exercises the
    branch that writes one."""
    ezdxf = pytest.importorskip("ezdxf")
    frame = _frame(
        characteristic=Characteristic.PROFILE_OF_A_SURFACE,
        feature_type=FeatureType.SURFACE,
    )
    path = export_feature_control_frame_dxf(
        frame=frame, path=tmp_path / "profile.dxf", text_height=H
    )
    arcs = [e for e in ezdxf.readfile(path).modelspace() if e.dxftype() == "ARC"]
    assert len(arcs) == 1
    assert arcs[0].dxf.radius == pytest.approx(10.0), "a semicircle 2h across is h in radius"


def test_the_dxf_places_the_frame_where_it_was_asked_to(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    origin = (Quantity(magnitude=50.0, unit="mm"), Quantity(magnitude=25.0, unit="mm"))
    path = export_feature_control_frame_dxf(
        frame=_frame(), path=tmp_path / "placed.dxf", text_height=H, origin=origin
    )
    doc = ezdxf.readfile(path)
    boxes = [e for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE" and e.closed]
    corners = [p for box in boxes for p in box.get_points("xy")]
    assert min(p[0] for p in corners) == pytest.approx(50.0)
    assert min(p[1] for p in corners) == pytest.approx(25.0)
