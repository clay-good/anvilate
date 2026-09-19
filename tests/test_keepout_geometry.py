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


def test_material_in_the_margin_band_is_not_a_pass() -> None:
    entries, _, _ = _check("26.7 mm")
    entry = entries["keepout beam_path"]
    assert entry.status is CheckStatus.FAIL
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
