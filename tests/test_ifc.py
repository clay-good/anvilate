"""IFC export: add-ifc-structural-export 1.1, 1.3, 2.1 and 3.1.

Every mapped element's worked example is written, validated against its schema with
IfcOpenShell's open checker (EXPRESS rules included), re-read, and each element's volume
and centroid compared with the built solid it came from.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

pytest.importorskip("build123d")
pytest.importorskip("ifcopenshell")

import ifcopenshell  # noqa: E402
import ifcopenshell.ifcopenshell_wrapper  # noqa: E402
import ifcopenshell.validate  # noqa: E402

from anvilate.export.gate import authorize_export  # noqa: E402
from anvilate.export.ifc import (  # noqa: E402
    _ENUMERATED,
    IFC_ELEMENT_CLASSES,
    IFC_SCHEMAS,
    SCREENING_PSET,
    IfcPart,
    ifc_class_for,
    measure_ifc,
    render_ifc,
)
from anvilate.geometry import _mesh_for_3mf, build_spec  # noqa: E402
from anvilate.refusal import RefusalError  # noqa: E402
from anvilate.screening import screen_spec  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]

# IfcOpenShell 0.9.0's EXPRESS-rule loader opens its generated rules module and never
# closes it. That is the toolkit's leak, not the writer's, so only that warning is let by.
pytestmark = [
    pytest.mark.filterwarnings("ignore:unclosed file.*ifcopenshell:ResourceWarning"),
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]


def _example(element_type: str) -> Path:
    parts = _REPO / "examples" / "parts" / f"{element_type}.spec.yaml"
    return parts if parts.exists() else _REPO / "examples" / f"{element_type}.spec.yaml"


def _part(element_type: str, tag: str = "p1"):
    spec = load_spec_yaml(_example(element_type).read_text(encoding="utf-8"))
    built = build_spec(spec)
    card = screen_spec(spec)
    vertices, triangles = _mesh_for_3mf(built)
    part = IfcPart(
        tag=tag,
        name=built.name,
        element_type=spec.element_type,
        vertices=vertices,
        triangles=triangles,
        material="ASTM-A36",
        mass_kg=1.5,
        part_number=f"PN-{tag}",
        card_digest="sha256:" + "0" * 64,
    )
    return part, built, card


def _authorized(card):
    return authorize_export(card, override=not card.passed)


def _problems(data: bytes) -> list:
    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    log = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, log, express_rules=True)
    return log.statements


def test_the_enumerations_are_the_toolkits_own():
    """The predefined types the writer trusts are read back from the schemas it writes."""
    for schema in IFC_SCHEMAS:
        declared = ifcopenshell.ifcopenshell_wrapper.schema_by_name(schema)
        for ifc_class, types in _ENUMERATED[schema].items():
            items = set(declared.declaration_by_name(f"{ifc_class}TypeEnum").enumeration_items())
            assert types == items - {"USERDEFINED", "NOTDEFINED"}, (schema, ifc_class)


def test_a_base_plate_is_userdefined_in_ifc4_and_its_own_type_in_ifc4x3():
    """IFC 4.3 added BASE_PLATE to IfcPlateTypeEnum; IFC4 has no such member."""
    assert ifc_class_for("base_plate", "IFC4") == ("IfcPlate", "USERDEFINED", "BASE_PLATE")
    assert ifc_class_for("base_plate", "IFC4X3_ADD2") == ("IfcPlate", "BASE_PLATE", None)
    assert ifc_class_for("beam_member", "IFC4") == ("IfcBeam", "BEAM", None)


def test_an_element_with_no_class_is_refused_and_not_written_as_a_proxy():
    with pytest.raises(RefusalError, match="'spur_gear_mesh' has no IFC class here"):
        ifc_class_for("spur_gear_mesh")
    with pytest.raises(RefusalError, match="not one this writer declares"):
        ifc_class_for("base_plate", "IFC2X3")  # type: ignore[arg-type]


@pytest.mark.parametrize("schema", IFC_SCHEMAS)
@pytest.mark.parametrize("element_type", sorted(IFC_ELEMENT_CLASSES))
def test_each_mapped_element_is_valid_and_reads_back_as_the_solid_it_came_from(
    element_type, schema
):
    part, built, card = _part(element_type)
    data = render_ifc([part], name="check", authorization=_authorized(card), schema=schema)
    assert _problems(data) == []
    (measured,) = measure_ifc(data)
    ifc_class, predefined, object_type = ifc_class_for(element_type, schema)
    assert (measured.ifc_class, measured.predefined_type, measured.object_type) == (
        ifc_class,
        predefined,
        object_type,
    )
    assert measured.tag == "PN-p1"
    # The same 1% the 3MF mesh is held to against the solid, and the centroid within a
    # thousandth of the part's size.
    assert measured.volume_mm3 == pytest.approx(built.volume_mm3, rel=0.01)
    box = built.shape.bounding_box()
    size = math.dist(tuple(box.min), tuple(box.max))
    centre = tuple(built.shape.center())
    assert math.dist(measured.centroid_mm, centre) < 1e-3 * size, (measured.centroid_mm, centre)


def test_the_verdict_is_on_the_element_and_the_watermark_in_the_header_and_the_set():
    part, _built, card = _part("beam_member")
    authorization = _authorized(card)
    data = render_ifc([part], name="mezzanine", authorization=authorization)
    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    (beam,) = model.by_type("IfcBeam")
    import ifcopenshell.util.element as element_util

    sets = element_util.get_psets(beam)
    screening = sets[SCREENING_PSET]
    assert screening["PartNumber"] == "PN-p1"
    assert screening["Material"] == "ASTM-A36"
    assert screening["Mass"] == 1.5
    assert screening["CardDigest"] == "sha256:" + "0" * 64
    assert screening["ValidationStatus"] == authorization.status
    assert sets["Pset_BeamCommon"]["Reference"] == "PN-p1"
    assert sets["Pset_BeamCommon"]["LoadBearing"] is True
    header = model.header.file_description.description
    for line in authorization.watermark():
        assert line in header
    assert [m.Name for m in element_util.get_materials(beam)] == ["ASTM-A36"]


def test_an_override_writes_unvalidated_on_the_element_and_in_the_header(tmp_path):
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    part, _built, _card = _part("beam_member")
    failing = Scorecard(
        entries=[
            ScorecardEntry(
                name="bending",
                status=CheckStatus.FAIL,
                detail="utilization 1.4",
            )
        ]
    )
    authorization = authorize_export(failing, override=True)
    data = render_ifc([part], name="mezzanine", authorization=authorization)
    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    import ifcopenshell.util.element as element_util

    screening = element_util.get_psets(model.by_type("IfcBeam")[0])[SCREENING_PSET]
    assert screening["ValidationStatus"] == "UNVALIDATED"
    assert any("bending" in str(value) for value in screening.values())
    assert any("bending" in line for line in model.header.file_description.description)
    assert model.header.file_name.authorization == "UNVALIDATED"


def test_the_same_parts_give_the_same_bytes_and_a_different_part_a_different_id():
    part, _built, card = _part("gusset_plate")
    authorization = _authorized(card)
    first = render_ifc([part], name="same", authorization=authorization)
    assert render_ifc([part], name="same", authorization=authorization) == first
    other, _b, _c = _part("gusset_plate", tag="p2")
    second = render_ifc([other], name="same", authorization=authorization)
    one = ifcopenshell.file.from_string(first.decode()).by_type("IfcPlate")[0].GlobalId
    two = ifcopenshell.file.from_string(second.decode()).by_type("IfcPlate")[0].GlobalId
    assert one != two


def test_several_parts_are_one_storey_with_one_material_shared():
    plate, _b1, card = _part("base_plate", tag="plate")
    beam, _b2, _c2 = _part("beam_member", tag="beam")
    data = render_ifc([plate, beam], name="two", authorization=_authorized(card))
    assert _problems(data) == []
    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    (contained,) = model.by_type("IfcRelContainedInSpatialStructure")
    assert sorted(e.is_a() for e in contained.RelatedElements) == ["IfcBeam", "IfcPlate"]
    assert len(model.by_type("IfcMaterial")) == 1
    units = {u.UnitType: (u.Prefix, u.Name) for u in model.by_type("IfcSIUnit")}
    assert units["LENGTHUNIT"] == ("MILLI", "METRE") and units["MASSUNIT"] == ("KILO", "GRAM")


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"tag": " "}, "needs a tag and a name"),
        ({"triangles": [(0, 1, 2)]}, "at least 4 of each"),
        ({"triangles": [(0, 0, 1)] * 4}, "does not name three"),
        ({"mass_kg": -1.0}, "a mass is positive"),
        ({"mass_kg": math.nan}, "a mass is positive"),
    ],
)
def test_a_part_that_cannot_be_written_is_refused_naming_why(change, match):
    import dataclasses

    part, _built, card = _part("base_plate")
    with pytest.raises(RefusalError, match=match):
        render_ifc([dataclasses.replace(part, **change)], name="x", authorization=_authorized(card))


def test_two_parts_with_one_tag_are_refused():
    part, _built, card = _part("base_plate")
    with pytest.raises(RefusalError, match="used twice"):
        render_ifc([part, part], name="x", authorization=_authorized(card))


@pytest.mark.parametrize(
    ("section", "kind", "profile_def"),
    [
        ("IPE 200", "I", "IfcIShapeProfileDef"),
        ("HEA 200", "I", "IfcIShapeProfileDef"),
        ("BOX 100x50x4", "rectangle_hollow", "IfcRectangleHollowProfileDef"),
        ("TUBE 60x4", "circle_hollow", "IfcCircleHollowProfileDef"),
        ("NPS 4 SCH 40", "circle_hollow", "IfcCircleHollowProfileDef"),
    ],
)
def test_a_rolled_member_keeps_its_section_as_a_profile_and_an_extrusion(
    section, kind, profile_def
):
    """add-ifc-structural-export 1.2: the receiving tool reports the section, not faces.

    The bounds are held to the built member's on every axis, so a section laid in on its
    side, which volume and centroid alone would not notice, fails here.
    """
    import yaml

    from anvilate.export.ifc import ifc_part

    document = yaml.safe_load(_example("beam_member").read_text(encoding="utf-8"))
    document["element_params"]["section"] = section
    spec = load_spec_yaml(yaml.safe_dump(document))
    built = build_spec(spec)
    card = screen_spec(spec)
    part = ifc_part(spec, built, card, part_number="B-1")
    assert part.profile is not None and part.profile.kind == kind
    data = render_ifc([part], name="frame", authorization=_authorized(card))
    assert _problems(data) == []
    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    (profile,) = model.by_type(profile_def)
    assert profile.ProfileName == section
    assert len(model.by_type("IfcExtrudedAreaSolid")) == 1
    assert not model.by_type("IfcFacetedBrep")
    (measured,) = measure_ifc(data)
    assert measured.representation == "SweptSolid"
    box = built.shape.bounding_box()
    # A round section is read back as the reader's polygon, whose corners fall inside the
    # circle; a flat-sided one is held to the micrometre.
    slack = 0.01 * part.profile.dimensions["diameter"] if kind == "circle_hollow" else 1e-6
    for got, want in zip(measured.bounds_mm, (tuple(box.min), tuple(box.max)), strict=True):
        assert got == pytest.approx(want, abs=slack)
    assert measured.volume_mm3 == pytest.approx(built.volume_mm3, rel=0.01)


def test_the_adapter_carries_the_parts_identity_mass_and_card_digest():
    from anvilate import __version__
    from anvilate.export.ifc import ifc_part
    from anvilate.review import artifact_digest

    spec = load_spec_yaml(_example("base_plate").read_text(encoding="utf-8"))
    built = build_spec(spec)
    card = screen_spec(spec)
    part = ifc_part(spec, built, card, tag="bp", part_number="BP-100")
    assert (part.tag, part.part_number, part.element_type) == ("bp", "BP-100", "base_plate")
    assert part.material == str(spec.material.ref)
    # ASTM A36 at 7,850 kg/m³: the plate's own volume times the bundled density.
    assert part.mass_kg == pytest.approx(built.volume_mm3 * 7.85e-6, rel=1e-3)
    assert part.card_digest == "sha256:" + artifact_digest(
        card, toolchain=f"anvilate {__version__}"
    )
    # A plate names no rolled section, so it is its faces.
    assert part.profile is None
