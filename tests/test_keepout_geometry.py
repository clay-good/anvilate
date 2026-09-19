"""Keepout bodies built on the part and the part's intrusion into each, at nominal geometry."""

from __future__ import annotations

import pytest

pytest.importorskip("build123d")

from anvilate.geometry import build_spec  # noqa: E402
from anvilate.keepouts import screen_keepouts  # noqa: E402
from anvilate.packs.structural import BasePlate  # noqa: E402
from anvilate.scorecard import CheckStatus, Direction  # noqa: E402
from anvilate.spec import (  # noqa: E402
    AcceptanceCriteria,
    CylinderKeepout,
    DesignSpec,
    FrustumKeepout,
    ImportedBodyKeepout,
    Keepout,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Origin,
    PrismKeepout,
    Provenanced,
    ValidationTier,
)
from anvilate.units import Quantity, UnitSystem  # noqa: E402

q = Quantity.parse


def _plate(thickness: str) -> dict:
    return BasePlate(
        name="bp1",
        width=q("300 mm"),
        depth=q("240 mm"),
        plate_thickness=q(thickness),
        plate_material="ASTM-A36",
        cantilever=q("50 mm"),
        axial_load=q("200 kN"),
        concrete_strength=q("25 MPa"),
    ).model_dump()


def _beam_path(**changes) -> Keepout:  # type: ignore[no-untyped-def]
    fields = {
        "tag": "beam_path",
        "anchor": "bottom",
        "rule": PrismKeepout(width=q("100 mm"), depth=q("50 mm"), height=q("30 mm")),
        "clearance_margin": q("0.5 mm"),
        "reason": "the sensor's beam passes 27 mm above the mounting face",
        "offset": q("27 mm"),
    }
    fields.update(changes)
    return Keepout(**fields)


def _plate_spec(thickness: str = "25 mm", keepouts: tuple = ()) -> DesignSpec:  # type: ignore[type-arg]
    return DesignSpec(
        name="bp1",
        description="A base plate under a sensor's beam.",
        units=Provenanced(value=UnitSystem.SI, origin=Origin.USER_STATED),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        element_type="base_plate",
        element_params=_plate(thickness),
        keepouts=keepouts,
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )


def _check(thickness: str, *keepouts: Keepout):  # type: ignore[no-untyped-def]
    spec = DesignSpec(
        name="bp1",
        description="A base plate under a sensor's beam.",
        units=Provenanced(value=UnitSystem.SI, origin=Origin.USER_STATED),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        element_type="base_plate",
        element_params=_plate(thickness),
        keepouts=keepouts or (_beam_path(),),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )
    built = build_spec(spec)
    entries, bodies = screen_keepouts(spec, built)
    return {entry.name: entry for entry in entries}, bodies, built


def test_a_clear_keepout_states_the_clearance_it_was_measured_at() -> None:
    entries, bodies, built = _check("25 mm")
    entry = entries["keepout beam_path"]
    assert entry.status is CheckStatus.PASS
    assert "clears keepout 'beam_path'" in entry.detail and "by 2 mm" in entry.detail
    assert "at nominal geometry" in entry.detail
    summary = entries["keepout intrusion"]
    assert summary.status is CheckStatus.PASS
    assert "1 of 1 keepouts screened against 1 body" in summary.detail
    assert "smallest clearance 2 mm, at keepout 'beam_path'" in summary.detail
    # The body is beside the part, never unioned into it.
    assert len(bodies) == 1
    assert built.volume_mm3 == pytest.approx(300 * 240 * 25)


def test_a_thickened_plate_intrudes_and_the_card_fails_with_a_repair() -> None:
    """The plate thickened to fix deflection reaches into the beam path."""
    entries, _, _ = _check("27.3 mm")
    entry = entries["keepout beam_path"]
    assert entry.status is CheckStatus.FAIL
    assert "1.5e+03 mm³ in the protected core, 0.3 mm deep" in entry.detail
    assert "the sensor's beam passes 27 mm above the mounting face" in entry.detail
    assert entry.repair_hint is not None
    assert entry.repair_hint.parameter == "plate_thickness"
    assert entry.repair_hint.direction is Direction.DECREASE
    assert entry.repair_hint.corrective_value is not None
    assert entry.repair_hint.corrective_value < 27.3 - 0.3 - 0.5 + 1e-6
    assert entries["keepout intrusion"].status is CheckStatus.FAIL


def test_material_in_the_margin_band_is_a_warning_not_a_pass() -> None:
    entries, _, _ = _check("26.7 mm")
    entry = entries["keepout beam_path"]
    assert entry.status is CheckStatus.WARNING
    assert entries["keepout intrusion"].status is CheckStatus.WARNING
    assert "stops 0.3 mm from keepout 'beam_path'" in entry.detail
    assert "inside its 0.5 mm clearance margin" in entry.detail
    assert "the core is clear" in entry.detail


def test_a_keepout_moves_with_its_anchor() -> None:
    """Anchored to the top face, the keepout rides up as the plate thickens.

    The body runs from its near end into the part, so one sitting 5 mm to 35 mm above the
    face starts 35 mm out: an offset of -35 mm.
    """
    above = _beam_path(anchor="top", offset=q("-35 mm"))
    for thickness in ("25 mm", "40 mm"):
        entries, _, _ = _check(thickness, above)
        assert entries["keepout beam_path"].status is CheckStatus.PASS
        assert "by 5 mm" in entries["keepout beam_path"].detail


def test_an_ungenerated_keepout_is_not_evaluated_and_nothing_screened_is_said() -> None:
    lost = _beam_path(anchor="rib_face")
    imported = _beam_path(
        tag="optics_envelope",
        rule=ImportedBodyKeepout(source="optical design", sha256="a" * 64, volume=q("1 cm**3")),
    )
    entries, bodies, _ = _check("25 mm", lost, imported)
    assert bodies == ()
    assert entries["keepout beam_path"].status is CheckStatus.NOT_EVALUATED
    assert "'rib_face' is not a face this build tags" in entries["keepout beam_path"].detail
    assert "imported body" in entries["keepout optics_envelope"].detail
    summary = entries["keepout intrusion"]
    assert summary.status is CheckStatus.NOT_EVALUATED
    assert "0 of 2 declared keepouts were generated" in summary.detail


def test_every_rule_generates_a_body_of_its_own_volume() -> None:
    from math import pi

    cylinder = _beam_path(tag="bore", rule=CylinderKeepout(diameter=q("20 mm"), height=q("10 mm")))
    cone = _beam_path(
        tag="cone",
        rule=FrustumKeepout(base_diameter=q("20 mm"), top_diameter=q("0 mm"), height=q("30 mm")),
    )
    _, bodies, _ = _check("25 mm", cylinder, cone)
    volumes = {body.keepout.tag: float(body.core.volume) for body in bodies}
    assert volumes["bore"] == pytest.approx(pi * 10**2 * 10, rel=1e-6)
    assert volumes["cone"] == pytest.approx(pi * 10**2 * 30 / 3, rel=1e-6)


def test_keepouts_export_labelled_and_apart_from_the_machinable_solid(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """5.3: the keepout body is present and labelled, and absent from the part's STEP."""
    import re

    from build123d import import_step

    from anvilate.export.gate import authorize_export
    from anvilate.geometry import write_step
    from anvilate.keepouts import write_keepout_step

    authorization = authorize_export(None, override=True)
    _, bodies, built = _check("25 mm")
    first = write_keepout_step(bodies, tmp_path / "keepouts.step", authorization=authorization)
    # ISO 10303-21 ignores line breaks, and the writer wraps a long name across them.
    text = "".join(first.read_text().splitlines())
    assert re.findall(r"PRODUCT\(\s*'((?:[^']|'')*)'", text)[1:] == [
        "KEEPOUT beam_path (non-manufacturing): the sensor''s beam passes 27 mm above the "
        "mounting face"
    ]
    again = write_keepout_step(bodies, tmp_path / "again.step", authorization=authorization)
    assert again.read_bytes() == first.read_bytes()
    part = write_step(built, tmp_path / "part.step", authorization=authorization)
    machinable = import_step(str(part))
    assert len(machinable.solids()) == 1
    assert float(machinable.volume) == pytest.approx(300 * 240 * 25)
    assert "KEEPOUT" not in part.read_text()


def test_the_drawing_carries_each_keepout_on_its_own_non_manufacturing_layer() -> None:
    ezdxf = pytest.importorskip("ezdxf")
    import io

    from anvilate.export.dxf import render_geometry_dxf
    from anvilate.export.gate import authorize_export

    _, bodies, built = _check("25 mm")
    data = render_geometry_dxf(
        geometry=built, authorization=authorize_export(None, override=True), keepouts=bodies
    )
    drawing = ezdxf.read(io.StringIO(data.decode()))
    on_layer = drawing.modelspace().query('*[layer=="KEEPOUT_NON_MANUFACTURING"]')
    assert len(on_layer) == 2  # the footprint and its label
    (label,) = [entity for entity in on_layer if entity.dxftype() == "TEXT"]
    assert label.dxf.text.startswith("KEEPOUT beam_path (non-manufacturing)")
    outline = drawing.modelspace().query('*[layer=="OUTLINE"]')
    assert len(outline) == 1


# Golden cases per archetype: the rule's extents in mm, and the volume a closed form gives.
# The expected volume is the formula's, never the kernel's, so a kernel change that moved
# a body would fail here rather than rewrite its own golden value.
def _golden():  # type: ignore[no-untyped-def]
    from math import pi

    def frustum(r1: float, r2: float, h: float) -> float:
        return pi * h * (r1 * r1 + r1 * r2 + r2 * r2) / 3

    return {
        "prism": [
            ({"width": w, "depth": d, "height": h}, w * d * h)
            for w, d, h in ((10, 10, 10), (100, 50, 30), (1, 2, 3), (250, 0.5, 40), (7.5, 7.5, 7.5))
        ],
        "cylinder": [
            ({"diameter": dia, "height": h}, pi * (dia / 2) ** 2 * h)
            for dia, h in ((20, 10), (24, 38), (1, 1), (200, 5), (3.2, 60))
        ],
        "frustum": [
            ({"base_diameter": b, "top_diameter": t, "height": h}, frustum(b / 2, t / 2, h))
            for b, t, h in ((20, 0, 30), (40, 20, 10), (10, 10, 5), (100, 1, 50), (6, 3, 12))
        ],
        "swept_profile": [
            ({"profile_width": w, "profile_height": ph, "path_length": run}, w * ph * run)
            for w, ph, run in ((80, 60, 40), (10, 10, 100), (1, 1, 1), (300, 20, 5), (45, 90, 12))
        ],
    }


def _rule(name: str, extents: dict):  # type: ignore[no-untyped-def]
    from anvilate.spec import SweptProfileKeepout

    kind = {
        "prism": PrismKeepout,
        "cylinder": CylinderKeepout,
        "frustum": FrustumKeepout,
        "swept_profile": SweptProfileKeepout,
    }[name]
    return kind(**{key: q(f"{value} mm") for key, value in extents.items()})


def test_every_generated_rule_is_an_archetype_meeting_the_contribution_contract() -> None:
    import typing

    from anvilate.keepouts import KEEPOUT_ARCHETYPES
    from anvilate.spec import KeepoutRule

    members = typing.get_args(typing.get_args(KeepoutRule)[0])
    generated = {m.model_fields["rule"].default for m in members} - {"imported_body"}
    assert generated == set(KEEPOUT_ARCHETYPES)
    golden = _golden()
    for rule, archetype in KEEPOUT_ARCHETYPES.items():
        assert archetype.pattern == f"keepout_{rule}/1"
        assert archetype.bounds and archetype.checked_by and "never manufactured" in archetype.dfm
        assert len(golden[rule]) >= 5, f"{rule} has {len(golden[rule])} golden cases"


@pytest.mark.parametrize(
    ("rule", "extents", "volume"),
    [(rule, extents, volume) for rule, cases in _golden().items() for extents, volume in cases],
)
def test_each_archetype_builds_its_golden_volume(rule: str, extents: dict, volume: float) -> None:
    from anvilate.keepouts import build_keepout

    keepout = _beam_path(tag=f"golden_{rule}", rule=_rule(rule, extents))
    _, _, built = _check("25 mm")
    body = build_keepout(keepout, built)
    assert body is not None and body.pattern == f"keepout_{rule}/1"
    assert float(body.core.volume) == pytest.approx(volume, rel=1e-6)


def test_a_keepout_regenerates_identically() -> None:
    from anvilate.keepouts import build_keepout

    _, _, built = _check("25 mm")
    first, second = build_keepout(_beam_path(), built), build_keepout(_beam_path(), built)
    assert first is not None and second is not None

    def signature(body):  # type: ignore[no-untyped-def]
        box = body.core.bounding_box()
        return (round(float(body.core.volume), 9), tuple(box.min), tuple(box.max))

    assert signature(first) == signature(second)


def test_a_plate_grown_into_the_beam_fails_the_standard_intrusion_check() -> None:
    """Optomechanical 4.1: the beam, emitted as a keepout, is caught with no optics computed."""
    from anvilate.analysis.optomechanics import BeamEnvelope

    beam = BeamEnvelope(
        tag="imaging_beam",
        reason="the imaging beam to the detector",
        source="optical prescription rev C",
        entrance_diameter=q("20 mm"),
        half_angle=q("-5 deg"),
        length=q("60 mm"),
    ).keepout(anchor="bottom", clearance_margin=q("0.5 mm"), offset=q("27 mm"))
    assert _check("25 mm", beam)[0]["keepout imaging_beam"].status is CheckStatus.PASS
    grown = _check("28 mm", beam)[0]["keepout imaging_beam"]
    assert grown.status is CheckStatus.FAIL
    assert "the imaging beam to the detector" in grown.detail and "protected core" in grown.detail


def _shelf(hole: str):  # type: ignore[no-untyped-def]
    """A shelf 30 mm above the plate's top face, with a hole over the screw."""
    from build123d import Align, Box, Cylinder, Pos

    top = 25.0
    base = (Align.CENTER, Align.CENTER, Align.MIN)
    diameter = q(hole).to("mm").magnitude
    return Pos(0, 0, top + 30) * (
        Box(200, 200, 5, align=base) - Cylinder(diameter / 2, 5, align=base)
    )


def _access(tool: str, diameter: str, reach: str):  # type: ignore[no-untyped-def]
    from anvilate.assembly import AccessRequirement, ToolEnvelope

    return AccessRequirement(
        feature="M8 cap screw",
        face="top",
        tool=ToolEnvelope(
            tool=tool,
            body_diameter=q(diameter),
            reach=q(reach),
            source="the workshop's tool catalogue",
        ),
    )


def test_a_cap_screw_whose_head_clears_and_whose_driver_does_not_is_caught() -> None:
    """Assembly 4.1: the head's own envelope clears the shelf; the socket's does not."""
    from anvilate.keepouts import screen_keepouts

    head = _access("screw head", "13 mm", "8 mm")
    driver = _access("13 mm socket", "20 mm", "50 mm")
    _, _, built = _check("25 mm")
    entries, _ = screen_keepouts(
        _plate_spec(),
        built,
        neighbours={"service shelf": _shelf("14 mm")},
        keepouts=(head.keepout(), driver.keepout()),
    )
    found = {entry.name: entry for entry in entries}
    assert found["keepout access M8 cap screw by screw head"].status is CheckStatus.PASS
    blocked = found["keepout access M8 cap screw by 13 mm socket"]
    assert blocked.status is CheckStatus.FAIL
    assert blocked.detail.startswith("service shelf intrudes")
    assert "the workshop's tool catalogue" in blocked.detail
    assert blocked.repair_hint is None  # the shelf is not a parameter of this part
    assert "against 2 bodies (bp1, service shelf)" in found["keepout intrusion"].detail


def test_widening_the_clearance_changes_the_verdict() -> None:
    """Assembly 4.4: the screen reads geometry, so a wider hole passes the socket."""
    from anvilate.keepouts import screen_keepouts

    driver = _access("13 mm socket", "20 mm", "50 mm")
    _, _, built = _check("25 mm")
    entries, _ = screen_keepouts(
        _plate_spec(),
        built,
        neighbours={"service shelf": _shelf("26 mm")},
        keepouts=(driver.keepout(),),
    )
    found = {entry.name: entry for entry in entries}
    clear = found["keepout access M8 cap screw by 13 mm socket"]
    assert clear.status is CheckStatus.PASS
    assert "service shelf clears" in clear.detail and "by 3 mm" in clear.detail
