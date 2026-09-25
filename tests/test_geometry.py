"""Golden checks for the first audited B-Rep generation pattern."""

from __future__ import annotations

import base64
import re
from hashlib import sha256
from math import pi
from types import MappingProxyType
from xml.etree import ElementTree

import pytest

pytest.importorskip("build123d")

from anvilate.export.gate import authorize_export  # noqa: E402
from anvilate.geometry import (  # noqa: E402
    BASE_PLATE_PATTERN,
    COVER_PLATE_PATTERN,
    TRANSMISSION_SHAFT_PATTERN,
    GeometryError,
    HolePatternCandidate,
    UnsupportedGeometry,
    build_base_plate,
    build_cover_plate,
    build_spec,
    build_transmission_shaft,
    check_cylindrical_mate_fit,
    check_planar_gap_clearance,
    confirm_cylindrical_mate,
    confirm_planar_contact,
    confirm_planar_gap,
    confirm_step_interface,
    detect_step_interfaces,
    measure_geometry,
    read_step_validation_properties,
    render_viewport,
    verify_step_integrity,
    write_step,
)
from anvilate.packs.industrial import CoverPlate  # noqa: E402
from anvilate.packs.machinery import TransmissionShaft  # noqa: E402
from anvilate.packs.structural import BasePlate  # noqa: E402
from anvilate.scorecard import CheckStatus  # noqa: E402
from anvilate.spec import (  # noqa: E402
    AcceptanceCriteria,
    DesignSpec,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Origin,
    Provenanced,
    ValidationTier,
)
from anvilate.units import Quantity, UnitSystem  # noqa: E402

_STEP_AUTH = authorize_export(None, override=True)


def _plate(**changes) -> BasePlate:
    values = {
        "name": "bp1",
        "width": Quantity.parse("300 mm"),
        "depth": Quantity.parse("240 mm"),
        "plate_thickness": Quantity.parse("25 mm"),
        "plate_material": "ASTM-A36",
        "cantilever": Quantity.parse("50 mm"),
        "axial_load": Quantity.parse("200 kN"),
        "concrete_strength": Quantity.parse("25 MPa"),
    }
    values.update(changes)
    return BasePlate(**values)


def _cover(**changes) -> CoverPlate:
    values = {
        "name": "access-cover",
        "pressure": Quantity.parse("15 kPa"),
        "thickness": Quantity.parse("8 mm"),
        "material": "ASTM-A36",
        "length": Quantity.parse("400 mm"),
        "width": Quantity.parse("300 mm"),
    }
    values.update(changes)
    return CoverPlate(**values)


def _shaft(**changes) -> TransmissionShaft:
    values = {
        "diameter": Quantity.parse("55 mm"),
        "length": Quantity.parse("600 mm"),
        "bending_moment": Quantity.parse("250 N*m"),
        "torque": Quantity.parse("400 N*m"),
        "yield_strength": Quantity.parse("370 MPa"),
        "shear_modulus": Quantity.parse("79.3 GPa"),
        "allowable_twist": Quantity.parse("0.5 degree"),
        "endurance_limit": Quantity.parse("200 MPa"),
        "ultimate_strength": Quantity.parse("690 MPa"),
    }
    values.update(changes)
    return TransmissionShaft(**values)


def _spec(*, element_type: str = "base_plate", params=None) -> DesignSpec:
    return DesignSpec(
        name="bp1",
        description="A generated rectangular base plate.",
        units=Provenanced(value=UnitSystem.SI, origin=Origin.USER_STATED),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        element_type=element_type,
        element_params=params or _plate().model_dump(),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )


def _four_hole_step(path, *, centers=((-30, -20), (-30, 20), (30, -20), (30, 20)), locator=None):
    from build123d import Align, Box, Cylinder, Location, export_step

    shape = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x, y in centers:
        cutter = Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((x, y, 0))
        )
        shape = shape - cutter
    if locator == "bore":
        shape = shape - Cylinder(15, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    elif locator == "blind_bore":
        shape = shape - Cylinder(15, 5, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((0, 0, 5))
        )
    elif locator == "counterbore":
        shape = shape - Cylinder(15, 3, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((0, 0, 7))
        )
        shape = shape - Cylinder(8, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    elif locator == "boss":
        shape = shape + Cylinder(15, 5, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((0, 0, 10))
        )
    export_step(shape, path)
    return path


def test_base_plate_golden_dimensions_and_kernel_volume():
    built = build_base_plate(_plate())
    size = built.shape.bounding_box().size

    assert (size.X, size.Y, size.Z) == pytest.approx((300, 240, 25))
    assert built.volume_mm3 == pytest.approx(300 * 240 * 25)
    assert dict(built.dimensions_mm) == {
        "width": 300,
        "depth": 240,
        "plate_thickness": 25,
    }


def test_base_plate_is_one_valid_positive_volume_brep_solid():
    built = build_base_plate(_plate())

    assert built.is_valid
    assert built.shape.is_valid
    assert len(built.shape.solids()) == 1
    assert built.volume_mm3 > 0


def test_base_plate_carries_all_six_semantic_face_tags():
    built = build_base_plate(_plate())

    assert set(built.faces) == {"bottom", "east", "north", "south", "top", "west"}
    assert all(len(faces) == 1 for faces in built.faces.values())
    assert isinstance(built.faces, MappingProxyType)
    assert built.faces["top"][0].normal_at().Z == pytest.approx(1)
    assert built.faces["bottom"][0].normal_at().Z == pytest.approx(-1)


def test_base_plate_origin_and_orientation_are_stable():
    built = build_base_plate(_plate())
    bounds = built.shape.bounding_box()

    assert (bounds.min.X, bounds.min.Y, bounds.min.Z) == pytest.approx((-150, -120, 0))
    assert (bounds.max.X, bounds.max.Y, bounds.max.Z) == pytest.approx((150, 120, 25))


def test_regeneration_has_the_same_pattern_signature_and_geometry():
    first = build_base_plate(_plate())
    second = build_base_plate(_plate())

    assert first.signature == second.signature
    assert first.pattern == second.pattern == BASE_PLATE_PATTERN
    assert first.volume_mm3 == second.volume_mm3
    assert first.shape.bounding_box().size == second.shape.bounding_box().size


def test_viewport_is_a_deterministic_self_contained_svg_with_integrity_metadata():
    built = build_base_plate(_plate())
    first = render_viewport(built, view="iso", width_px=640)
    second = render_viewport(built, view="iso", width_px=640)
    document = first.document()

    assert first.data == second.data
    assert first.sha256 == second.sha256 == document.sha256
    assert document.mime_type == "image/svg+xml"
    assert base64.b64decode(document.image) == first.data
    root = ElementTree.fromstring(first.data)
    assert root.attrib["width"] == "640"
    assert root.attrib["height"] == "480"
    assert "href=" not in first.data.decode()
    assert {node.attrib["data-face"] for node in root if "data-face" in node.attrib} == set(
        built.faces
    )


def test_named_viewports_produce_distinct_projections():
    built = build_base_plate(_plate())
    images = {
        view: render_viewport(built, view=view).data for view in ("iso", "front", "top", "right")
    }

    assert len(set(images.values())) == 4


def test_viewport_document_refuses_an_image_that_does_not_match_its_digest():
    document = render_viewport(build_base_plate(_plate())).document().model_dump()
    document["image"] = base64.b64encode(b"different bytes").decode("ascii")

    with pytest.raises(ValueError, match="sha256 does not match image bytes"):
        from anvilate.geometry import ViewportImage

        ViewportImage.model_validate(document)


@pytest.mark.parametrize(
    ("query", "value", "unit", "feature"),
    (
        ("volume", 1_800_000, "mm^3", "solid"),
        ("width", 300, "mm", "east-west extent"),
        ("depth", 240, "mm", "north-south extent"),
        ("plate_thickness", 25, "mm", "bottom-top extent"),
        ("face_count", 6, "count", "semantic faces"),
        ("area:top", 72_000, "mm^2", "top"),
        ("area:east", 6_000, "mm^2", "east"),
    ),
)
def test_geometry_measurements_are_read_from_the_brep(query, value, unit, feature):
    measured = measure_geometry(build_base_plate(_plate()), query)

    assert measured.value == pytest.approx(value)
    assert measured.unit == unit
    assert measured.feature == feature


def test_geometry_measurement_refuses_an_unknown_query_and_lists_the_grammar():
    with pytest.raises(GeometryError, match=r"area:<semantic-face>"):
        measure_geometry(build_base_plate(_plate()), "mass")


@pytest.mark.parametrize("width", (63, 4097))
def test_viewport_refuses_widths_outside_the_published_bounds(width):
    with pytest.raises(GeometryError, match="width_px must be from 64 through 4096"):
        render_viewport(build_base_plate(_plate()), width_px=width)


def test_step_round_trip_preserves_the_valid_solid(tmp_path):
    from build123d import import_step

    path = write_step(build_base_plate(_plate()), tmp_path / "base.step", authorization=_STEP_AUTH)
    restored = import_step(path)

    text = path.read_text(encoding="utf-8")
    assert text.startswith("ISO-10303-21;")
    assert "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF" in text
    assert "10303 214" not in text
    assert "Geometric and Assembly Validation Properties---4.6---2023-04-21" in text
    assert "ANVILATE_EXPORT_STATUS=UNVALIDATED" in text
    properties = read_step_validation_properties(path)
    rebuilt = write_step(
        build_base_plate(_plate()), tmp_path / "rebuilt.step", authorization=_STEP_AUTH
    )
    assert rebuilt.read_bytes() == path.read_bytes()
    assert restored.is_valid
    assert len(restored.solids()) == 1
    assert restored.volume == pytest.approx(300 * 240 * 25, rel=1e-8)
    assert properties.volume_mm3 == pytest.approx(restored.volume)
    assert properties.surface_area_mm2 == pytest.approx(restored.area)
    assert properties.centroid_mm == pytest.approx((0, 0, 12.5))
    assert verify_step_integrity(path) == properties


def test_step_integrity_verifier_detects_a_tampered_property(tmp_path):
    path = write_step(build_base_plate(_plate()), tmp_path / "base.step", authorization=_STEP_AUTH)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("1.8E+06", "1.7E+06", 1), encoding="utf-8")

    with pytest.raises(GeometryError, match=r"volume differs by 5\.882%"):
        verify_step_integrity(path)


def test_step_writer_restores_the_process_global_schema(tmp_path):
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_Controller

    STEPControl_Controller.Init_s()
    original = Interface_Static.CVal_s("write.step.schema")
    try:
        assert Interface_Static.SetCVal_s("write.step.schema", "AP203")
        write_step(build_base_plate(_plate()), tmp_path / "base.step", authorization=_STEP_AUTH)
        assert Interface_Static.CVal_s("write.step.schema") == "AP203"
    finally:
        Interface_Static.SetCVal_s("write.step.schema", original)


def test_step_writer_refuses_an_unknown_schema_without_writing(tmp_path):
    path = tmp_path / "base.step"

    with pytest.raises(GeometryError, match="choose ap242 or ap214"):
        write_step(build_base_plate(_plate()), path, authorization=_STEP_AUTH, schema="ap203")

    assert not path.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("width", "0 mm"),
        ("depth", "0 mm"),
        ("plate_thickness", "0 mm"),
    ),
)
def test_pattern_bounds_refuse_nonpositive_dimensions(field, value):
    with pytest.raises(GeometryError, match=rf"{field} must be greater than zero"):
        build_base_plate(_plate(**{field: Quantity.parse(value)}))


def test_pattern_refuses_a_base_plate_without_thickness():
    with pytest.raises(GeometryError, match="plate_thickness"):
        build_base_plate(_plate(plate_thickness=None, plate_material=None, cantilever=None))


def test_registry_refuses_an_element_without_an_audited_pattern():
    with pytest.raises(UnsupportedGeometry, match="lifting_lug"):
        build_spec(_spec(element_type="lifting_lug"))


def test_rectangular_cover_plate_is_one_tagged_solid_with_exact_volume():
    built = build_cover_plate(_cover())

    assert built.pattern == COVER_PLATE_PATTERN
    assert built.is_valid
    assert built.volume_mm3 == pytest.approx(400 * 300 * 8)
    assert dict(built.dimensions_mm) == {"width": 300, "length": 400, "thickness": 8}
    assert set(built.faces) == {"bottom", "east", "north", "south", "top", "west"}


def test_circular_cover_plate_is_a_tagged_disk_with_exact_volume():
    built = build_cover_plate(_cover(length=None, width=None, diameter=Quantity.parse("300 mm")))

    assert built.is_valid
    assert built.volume_mm3 == pytest.approx(3.141592653589793 * 150**2 * 8)
    assert set(built.faces) == {"bottom", "perimeter", "top"}


def test_annular_cover_plate_preserves_the_semantic_bore():
    built = build_cover_plate(
        _cover(
            length=None,
            width=None,
            diameter=Quantity.parse("300 mm"),
            hole_diameter=Quantity.parse("80 mm"),
        )
    )

    assert built.volume_mm3 == pytest.approx(3.141592653589793 * (150**2 - 40**2) * 8)
    assert set(built.faces) == {"bore", "bottom", "perimeter", "top"}
    assert measure_geometry(built, "hole_diameter").value == pytest.approx(80)
    assert measure_geometry(built, "area:bore").value == pytest.approx(3.141592653589793 * 80 * 8)


def test_cover_plate_refuses_a_nonpositive_thickness():
    with pytest.raises(GeometryError, match="thickness must be greater than zero"):
        build_cover_plate(_cover(thickness=Quantity.parse("0 mm")))


def test_cover_plate_refuses_a_bore_that_consumes_the_blank():
    with pytest.raises(GeometryError, match="hole_diameter must be below diameter"):
        build_cover_plate(
            _cover(
                length=None,
                width=None,
                diameter=Quantity.parse("80 mm"),
                hole_diameter=Quantity.parse("80 mm"),
            )
        )


def test_cover_plate_regeneration_is_deterministic():
    plate = _cover(length=None, width=None, diameter=Quantity.parse("300 mm"))

    first = build_cover_plate(plate)
    second = build_cover_plate(plate)

    assert first.signature == second.signature
    assert first.summary() == second.summary()


def test_cover_plate_builds_through_the_design_spec_registry():
    built = build_spec(_spec(element_type="cover_plate", params=_cover().model_dump()))

    assert built.pattern == COVER_PLATE_PATTERN
    assert built.is_valid


def test_transmission_shaft_golden_dimensions_and_kernel_volume():
    built = build_transmission_shaft(_shaft())
    size = built.shape.bounding_box().size

    assert (size.X, size.Y, size.Z) == pytest.approx((55, 55, 600))
    assert built.volume_mm3 == pytest.approx(3.141592653589793 * 27.5**2 * 600)
    assert dict(built.dimensions_mm) == {"diameter": 55, "length": 600}


def test_transmission_shaft_is_one_valid_solid_at_the_declared_origin():
    built = build_transmission_shaft(_shaft())
    bounds = built.shape.bounding_box()

    assert built.is_valid
    assert len(built.shape.solids()) == 1
    assert (bounds.min.X, bounds.min.Y, bounds.min.Z) == pytest.approx((-27.5, -27.5, 0))
    assert (bounds.max.X, bounds.max.Y, bounds.max.Z) == pytest.approx((27.5, 27.5, 600))


def test_transmission_shaft_tags_both_ends_and_the_outside_surface():
    built = build_transmission_shaft(_shaft())

    assert set(built.faces) == {"drive_end", "driven_end", "outside_surface"}
    assert all(len(faces) == 1 for faces in built.faces.values())
    assert built.faces["drive_end"][0].normal_at().Z == pytest.approx(-1)
    assert built.faces["driven_end"][0].normal_at().Z == pytest.approx(1)


def test_transmission_shaft_regeneration_is_deterministic():
    first = build_transmission_shaft(_shaft())
    second = build_transmission_shaft(_shaft())

    assert first.signature == second.signature
    assert first.summary() == second.summary()
    assert first.pattern == TRANSMISSION_SHAFT_PATTERN


@pytest.mark.parametrize("view", ("iso", "front", "top", "right"))
def test_transmission_shaft_renders_every_named_view_with_all_semantic_tags(view):
    built = build_transmission_shaft(_shaft())
    root = ElementTree.fromstring(render_viewport(built, view=view).data)

    assert {node.attrib["data-face"] for node in root if "data-face" in node.attrib} == set(
        built.faces
    )


@pytest.mark.parametrize("view", ("iso", "front", "right"))
def test_long_transmission_shaft_viewports_fit_both_ends_inside_the_canvas(view):
    rendered = render_viewport(build_transmission_shaft(_shaft()), view=view, width_px=800)
    svg = rendered.data.decode("utf-8")
    if view == "iso":
        end_centers = [
            float(value)
            for value in re.findall(r'data-face="(?:drive|driven)_end"[^>]+ cy="([\d.]+)"', svg)
        ]
        assert min(end_centers) > 0
        assert max(end_centers) < rendered.height_px
    else:
        match = re.search(
            r'data-face="outside_surface"[^>]+ y="([\d.]+)"[^>]+ height="([\d.]+)"', svg
        )
        assert match is not None
        top, height = (float(value) for value in match.groups())
        assert top > 0
        assert top + height < rendered.height_px


@pytest.mark.parametrize(
    ("query", "value", "feature"),
    (
        ("diameter", 55, "outside diameter"),
        ("length", 600, "drive-to-driven extent"),
        ("area:drive_end", 3.141592653589793 * 27.5**2, "drive_end"),
        ("area:outside_surface", 3.141592653589793 * 55 * 600, "outside_surface"),
    ),
)
def test_transmission_shaft_measurements_come_from_the_brep(query, value, feature):
    measured = measure_geometry(build_transmission_shaft(_shaft()), query)

    assert measured.value == pytest.approx(value)
    assert measured.feature == feature


def test_transmission_shaft_builds_through_the_design_spec_registry():
    built = build_spec(_spec(element_type="transmission_shaft", params=_shaft().model_dump()))

    assert built.name == "bp1"
    assert built.pattern == TRANSMISSION_SHAFT_PATTERN
    assert built.is_valid


def test_transmission_shaft_geometry_requires_a_declared_length():
    with pytest.raises(GeometryError, match="element_params.length"):
        build_transmission_shaft(_shaft(length=None))


def test_transmission_shaft_geometry_refuses_a_non_length_dimension():
    with pytest.raises(GeometryError, match="diameter must be a length"):
        build_transmission_shaft(_shaft(diameter=Quantity.parse("55 N")))


def test_step_interface_detection_finds_planar_faces_and_the_four_hole_circle(tmp_path):
    path = _four_hole_step(tmp_path / "mating.step")

    detected = detect_step_interfaces(path)
    patterned = [face for face in detected.planar_faces if face.hole_patterns]

    assert detected.source_name == "mating.step"
    assert len(detected.planar_faces) == 6
    assert {face.normal for face in patterned} == {(0, 0, -1), (0, 0, 1)}
    assert len(patterned) == 2
    for face in patterned:
        assert not face.locating_features
        pattern = face.hole_patterns[0]
        assert pattern.hole_count == 4
        assert pattern.hole_diameter_mm == pytest.approx(10)
        assert pattern.pitch_diameter_mm == pytest.approx(2 * (30**2 + 20**2) ** 0.5)
        assert pattern.center_mm[:2] == pytest.approx((0, 0))
        assert len(pattern.hole_centers_mm) == 4


def test_step_interface_candidate_ids_and_order_are_deterministic(tmp_path):
    path = _four_hole_step(tmp_path / "mating.step")

    first = detect_step_interfaces(path)
    second = detect_step_interfaces(path)

    assert first == second
    assert len({face.id for face in first.planar_faces}) == 6
    assert first.source_sha256 == sha256(path.read_bytes()).hexdigest()


def test_a_named_person_can_confirm_one_exact_candidate_as_an_interface_contract(tmp_path):
    detected = detect_step_interfaces(_four_hole_step(tmp_path / "mating.step"))
    face = next(face for face in detected.planar_faces if face.normal == (0, 0, 1))
    pattern = face.hole_patterns[0]

    accepted = confirm_step_interface(
        detected,
        pattern_id=pattern.id,
        name="motor_mount",
        mating_plane="motor_mount_face",
        confirmed_by="R. Engineer",
    )

    assert accepted.source_sha256 == detected.source_sha256
    assert accepted.face_candidate_id == face.id
    assert accepted.pattern_candidate_id == pattern.id
    assert accepted.confirmed_by == "R. Engineer"
    assert accepted.contract.name == "motor_mount"
    assert accepted.contract.mating_plane == "motor_mount_face"
    assert accepted.contract.pattern.hole_count == 4
    assert accepted.contract.pattern.diameter.to("mm").magnitude == pytest.approx(72.111025509)
    assert accepted.contract.pattern.hole_size.to("mm").magnitude == pytest.approx(10)
    assert [
        tuple(value.to("mm").magnitude for value in center)
        for center in accepted.contract.pattern.hole_centers or ()
    ] == [(-30, -20), (-30, 20), (30, -20), (30, 20)]
    assert accepted.contract.frame is not None
    assert accepted.contract.frame.x_axis == (1, 0, 0)
    assert accepted.contract.frame.y_axis == (0, 1, 0)
    assert accepted.contract.frame.normal == (0, 0, 1)


def test_an_interface_candidate_cannot_be_accepted_without_a_named_person(tmp_path):
    detected = detect_step_interfaces(_four_hole_step(tmp_path / "mating.step"))
    pattern = next(pattern for face in detected.planar_faces for pattern in face.hole_patterns)

    with pytest.raises(GeometryError, match="names the person confirming it"):
        confirm_step_interface(
            detected,
            pattern_id=pattern.id,
            name="motor_mount",
            mating_plane="motor_mount_face",
            confirmed_by="   ",
        )


@pytest.mark.parametrize(
    ("fixture", "kind", "extent", "through_diameter"),
    (
        ("bore", "bore", 10, None),
        ("blind_bore", "bore", 5, None),
        ("boss", "boss", 5, None),
        ("counterbore", "counterbore", 3, 16),
    ),
)
def test_step_interface_detection_finds_and_confirms_a_concentric_locator(
    tmp_path, fixture, kind, extent, through_diameter
):
    detected = detect_step_interfaces(
        _four_hole_step(tmp_path / f"with-{fixture}.step", locator=fixture)
    )
    face = next(
        face
        for face in detected.planar_faces
        if face.normal == (0, 0, 1) and face.hole_patterns and face.locating_features
    )
    feature = face.locating_features[0]

    assert feature.kind == kind
    assert feature.diameter_mm == pytest.approx(30)
    assert feature.axial_extent_mm == pytest.approx(extent)
    assert feature.through_diameter_mm == through_diameter
    accepted = confirm_step_interface(
        detected,
        pattern_id=face.hole_patterns[0].id,
        name="motor_mount",
        mating_plane="motor_mount_face",
        confirmed_by="R. Engineer",
        locating_feature_id=feature.id,
    )
    assert accepted.contract.locator is not None
    assert accepted.contract.locator.kind == kind
    assert accepted.contract.locator.diameter.to("mm").magnitude == pytest.approx(30)
    assert accepted.contract.locator.axial_extent.to("mm").magnitude == pytest.approx(extent)
    if through_diameter is None:
        assert accepted.contract.locator.through_diameter is None
    else:
        assert accepted.contract.locator.through_diameter is not None
        assert accepted.contract.locator.through_diameter.to("mm").magnitude == pytest.approx(
            through_diameter
        )


def test_step_interface_detection_does_not_call_an_off_center_boss_a_locator(tmp_path):
    from build123d import Align, Box, Cylinder, Location, export_step

    shape = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x in (-30, 30):
        for y in (-20, 20):
            shape -= Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
                Location((x, y, 0))
            )
    shape += Cylinder(15, 5, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
        Location((10, 0, 10))
    )
    path = tmp_path / "off-center-boss.step"
    export_step(shape, path)

    detected = detect_step_interfaces(path)

    assert all(not face.locating_features for face in detected.planar_faces)


def test_step_interface_detection_does_not_call_nested_blind_steps_a_counterbore(
    tmp_path,
):
    from build123d import Align, Box, Cylinder, Location, export_step

    shape = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x in (-30, 30):
        for y in (-20, 20):
            shape -= Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
                Location((x, y, 0))
            )
    shape -= Cylinder(15, 3, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
        Location((0, 0, 7))
    )
    shape -= Cylinder(8, 4, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
        Location((0, 0, 3))
    )
    path = tmp_path / "nested-blind.step"
    export_step(shape, path)

    detected = detect_step_interfaces(path)
    top = next(
        face
        for face in detected.planar_faces
        if face.normal == (0, 0, 1) and face.center_mm[2] == 10
    )

    assert top.hole_patterns
    assert not top.locating_features


def test_interface_confirmation_refuses_an_unknown_candidate_and_names_the_choices(tmp_path):
    detected = detect_step_interfaces(_four_hole_step(tmp_path / "mating.step"))
    available = next(pattern.id for face in detected.planar_faces for pattern in face.hole_patterns)

    with pytest.raises(GeometryError, match=available):
        confirm_step_interface(
            detected,
            pattern_id="pattern-not-present",
            name="motor_mount",
            mating_plane="motor_mount_face",
            confirmed_by="R. Engineer",
        )


def test_step_interface_detection_does_not_call_an_outside_cylinder_a_hole(tmp_path):
    path = write_step(
        build_transmission_shaft(_shaft()),
        tmp_path / "shaft.step",
        authorization=_STEP_AUTH,
    )

    detected = detect_step_interfaces(path)

    assert len(detected.planar_faces) == 2
    assert all(not face.hole_patterns for face in detected.planar_faces)


def test_step_interface_detection_does_not_invent_a_pattern_from_one_hole(tmp_path):
    path = _four_hole_step(tmp_path / "one-hole.step", centers=((0, 0),))

    detected = detect_step_interfaces(path)

    assert len(detected.planar_faces) == 6
    assert all(not face.hole_patterns for face in detected.planar_faces)


def test_step_interface_detection_rejects_equal_holes_that_do_not_fit_one_circle(tmp_path):
    path = _four_hole_step(
        tmp_path / "irregular.step", centers=((-30, -20), (-10, 20), (20, -10), (30, 30))
    )

    detected = detect_step_interfaces(path)

    assert all(not face.hole_patterns for face in detected.planar_faces)


def test_step_interface_detection_enumerates_multi_solid_interfaces_with_stable_ids(tmp_path):
    from build123d import Align, Box, Cylinder, Location, export_step

    path = tmp_path / "assembly.step"
    plate = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x in (-30, 30):
        for y in (-20, 20):
            plate -= Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
                Location((x, y, 0))
            )
    other = Box(20, 20, 20).moved(Location((150, 0, 0)))
    export_step(plate + other, path)
    reversed_path = tmp_path / "assembly-reversed.step"
    export_step(other + plate, reversed_path)

    detected = detect_step_interfaces(path)
    reversed_detected = detect_step_interfaces(reversed_path)
    solid_ids = {face.solid_id for face in detected.planar_faces}
    patterned = [face for face in detected.planar_faces if face.hole_patterns]

    assert len(detected.planar_faces) == 12
    assert None not in solid_ids and len(solid_ids) == 2
    assert len(detected.solids) == 2
    assert sorted(solid.volume_mm3 for solid in detected.solids) == pytest.approx(
        sorted((8_000, 80_000 - 4 * pi * 5**2 * 10))
    )
    assert detected.solids == reversed_detected.solids
    plate_summary = max(detected.solids, key=lambda solid: solid.volume_mm3)
    assert plate_summary.center_mm == pytest.approx((0, 0, 5))
    assert plate_summary.bounds_min_mm == pytest.approx((-50, -40, 0))
    assert plate_summary.bounds_max_mm == pytest.approx((50, 40, 10))
    assert solid_ids == {face.solid_id for face in reversed_detected.planar_faces}
    assert {face.id for face in detected.planar_faces} == {
        face.id for face in reversed_detected.planar_faces
    }
    assert len(patterned) == 2
    assert {face.solid_id for face in patterned} == {patterned[0].solid_id}
    accepted = confirm_step_interface(
        detected,
        pattern_id=patterned[0].hole_patterns[0].id,
        name="assembly_mount",
        mating_plane="assembly_mount_face",
        confirmed_by="R. Engineer",
    )
    assert accepted.solid_id == patterned[0].solid_id


def test_single_solid_interface_output_does_not_gain_a_solid_id(tmp_path):
    detected = detect_step_interfaces(_four_hole_step(tmp_path / "mating.step"))

    dumped = detected.model_dump(mode="json", exclude_unset=True)

    assert "solids" not in dumped
    assert "planar_gaps" not in dumped
    assert "solid_interferences" not in dumped
    assert "interference_scorecard" not in dumped
    assert all("solid_id" not in face for face in dumped["planar_faces"])


def test_step_interface_detection_only_calls_exact_coplanar_overlap_a_contact(tmp_path):
    from build123d import Box, Compound, Location, export_step

    base = Box(100, 80, 10)
    touching = Box(20, 20, 20).moved(Location((40, 30, 15)))
    touching_path = tmp_path / "touching.step"
    reversed_path = tmp_path / "touching-reversed.step"
    separated_path = tmp_path / "separated.step"
    separated_reversed_path = tmp_path / "separated-reversed.step"
    coplanar_disjoint_path = tmp_path / "coplanar-disjoint.step"
    tilted_path = tmp_path / "tilted.step"
    export_step(Compound(children=[base, touching]), touching_path)
    export_step(Compound(children=[touching, base]), reversed_path)
    separated_box = touching.moved(Location((0, 0, 1)))
    export_step(Compound(children=[base, separated_box]), separated_path)
    export_step(Compound(children=[separated_box, base]), separated_reversed_path)
    export_step(
        Compound(children=[base, touching.moved(Location((100, 0, 0)))]),
        coplanar_disjoint_path,
    )
    tilted = Box(20, 20, 20).moved(Location((40, 30, 16), (5, 0, 0)))
    export_step(Compound(children=[base, tilted]), tilted_path)

    detected = detect_step_interfaces(touching_path)
    reversed_detected = detect_step_interfaces(reversed_path)
    separated = detect_step_interfaces(separated_path)
    separated_reversed = detect_step_interfaces(separated_reversed_path)
    coplanar_disjoint = detect_step_interfaces(coplanar_disjoint_path)
    tilted_detected = detect_step_interfaces(tilted_path)

    assert len(detected.planar_contacts) == 1
    contact = detected.planar_contacts[0]
    assert contact.overlap_area_mm2 == pytest.approx(400)
    assert {contact.first_solid_id, contact.second_solid_id} == {
        solid.id for solid in detected.solids
    }
    assert {contact.first_face_candidate_id, contact.second_face_candidate_id} <= {
        face.id for face in detected.planar_faces
    }
    assert detected.planar_contacts == reversed_detected.planar_contacts
    assert not separated.planar_contacts
    assert not coplanar_disjoint.planar_contacts
    assert any("do not prove intended mating" in warning for warning in detected.warnings)
    assert len(separated.planar_gaps) == 1
    gap = separated.planar_gaps[0]
    assert gap.separation_mm == pytest.approx(1)
    assert gap.overlap_area_mm2 == pytest.approx(400)
    assert sum(component**2 for component in gap.direction) == pytest.approx(1)
    assert separated.planar_gaps == separated_reversed.planar_gaps
    assert not detected.planar_gaps
    assert not coplanar_disjoint.planar_gaps
    assert not tilted_detected.planar_gaps
    assert any("do not judge clearance" in warning for warning in separated.warnings)

    accepted_gap = confirm_planar_gap(
        separated,
        gap_id=gap.id,
        name="seal_gap",
        confirmed_by="R. Engineer",
    )
    assert accepted_gap.source_sha256 == separated.source_sha256
    assert accepted_gap.gap_candidate_id == gap.id
    assert accepted_gap.first_face_candidate_id == gap.first_face_candidate_id
    assert accepted_gap.second_solid_id == gap.second_solid_id
    assert accepted_gap.separation_mm == pytest.approx(1)
    assert accepted_gap.direction == gap.direction
    assert accepted_gap.confirmed_by == "R. Engineer"

    passing_gap_check = check_planar_gap_clearance(
        accepted_gap,
        minimum_gap=Quantity.parse("500 um"),
        maximum_gap=Quantity.parse("0.06 in"),
        reference="Drawing A-101, note 7",
    )
    assert passing_gap_check.status == "pass"
    assert passing_gap_check.minimum_gap_mm == pytest.approx(0.5)
    assert passing_gap_check.maximum_gap_mm == pytest.approx(1.524)
    assert passing_gap_check.margin_above_minimum_mm == pytest.approx(0.5)
    assert passing_gap_check.margin_below_maximum_mm == pytest.approx(0.524)
    assert passing_gap_check.reference == "Drawing A-101, note 7"

    failing_gap_check = check_planar_gap_clearance(
        accepted_gap,
        minimum_gap=Quantity.parse("0.25 mm"),
        maximum_gap=Quantity.parse("0.75 mm"),
        reference="Drawing A-101, note 7",
    )
    assert failing_gap_check.status == "fail"
    assert failing_gap_check.margin_below_maximum_mm == pytest.approx(-0.25)

    with pytest.raises(GeometryError, match="minimum gap must not exceed maximum gap"):
        check_planar_gap_clearance(
            accepted_gap,
            minimum_gap=Quantity.parse("2 mm"),
            maximum_gap=Quantity.parse("1 mm"),
            reference="Drawing A-101, note 7",
        )
    with pytest.raises(GeometryError, match="must be a length"):
        check_planar_gap_clearance(
            accepted_gap,
            minimum_gap=Quantity.parse("1 kg"),
            maximum_gap=Quantity.parse("2 mm"),
            reference="Drawing A-101, note 7",
        )

    with pytest.raises(GeometryError, match="available: planar-gap-"):
        confirm_planar_gap(
            separated,
            gap_id="planar-gap-absent",
            name="seal_gap",
            confirmed_by="R. Engineer",
        )

    accepted = confirm_planar_contact(
        detected,
        contact_id=contact.id,
        name="housing_to_plate",
        confirmed_by="R. Engineer",
    )
    assert accepted.contact_candidate_id == contact.id
    assert accepted.name == "housing_to_plate"
    assert accepted.overlap_area_mm2 == pytest.approx(400)
    assert accepted.confirmed_by == "R. Engineer"
    assert accepted.first_solid_id == contact.first_solid_id
    assert accepted.second_face_candidate_id == contact.second_face_candidate_id

    with pytest.raises(GeometryError, match="not found exactly once"):
        confirm_planar_contact(
            detected,
            contact_id="contact-absent",
            name="housing_to_plate",
            confirmed_by="R. Engineer",
        )
    with pytest.raises(GeometryError, match="names the person confirming it"):
        confirm_planar_contact(
            detected,
            contact_id=contact.id,
            name="housing_to_plate",
            confirmed_by=" ",
        )


def test_step_interface_detection_measures_coaxial_bore_and_shaft_mates(tmp_path):
    from build123d import Align, Box, Compound, Cylinder, Location, export_step

    plate = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    plate -= Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))

    def write_pair(name: str, *, radius: float, x: float = 0, z: float = -5, reverse=False):
        pin = Cylinder(radius, 20, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((x, 0, z))
        )
        children = [pin, plate] if reverse else [plate, pin]
        path = tmp_path / name
        export_step(Compound(children=children), path)
        return path

    clearance = detect_step_interfaces(write_pair("clearance.step", radius=4.9))
    reversed_clearance = detect_step_interfaces(
        write_pair("clearance-reversed.step", radius=4.9, reverse=True)
    )
    interference = detect_step_interfaces(write_pair("interference.step", radius=5.1))
    offset = detect_step_interfaces(write_pair("offset.step", radius=4.9, x=1))
    disengaged = detect_step_interfaces(write_pair("disengaged.step", radius=4.9, z=15))

    assert len(clearance.cylindrical_mates) == 1
    mate = clearance.cylindrical_mates[0]
    assert mate.bore_diameter_mm == pytest.approx(10)
    assert mate.shaft_diameter_mm == pytest.approx(9.8)
    assert mate.diametral_clearance_mm == pytest.approx(0.2)
    assert mate.axial_engagement_mm == pytest.approx(10)
    assert mate.axis_origin_mm == pytest.approx((0, 0, 0))
    assert mate.axis_direction == pytest.approx((0, 0, 1))
    assert {mate.bore_solid_id, mate.shaft_solid_id} == {solid.id for solid in clearance.solids}
    assert clearance.cylindrical_mates == reversed_clearance.cylindrical_mates
    assert interference.cylindrical_mates[0].diametral_clearance_mm == pytest.approx(-0.2)
    assert not offset.cylindrical_mates
    assert not disengaged.cylindrical_mates
    assert any("do not judge fit" in warning for warning in clearance.warnings)

    confirmed = confirm_cylindrical_mate(
        clearance,
        mate_id=mate.id,
        name="bearing_journal",
        confirmed_by="R. Engineer",
    )
    assert confirmed.source_sha256 == clearance.source_sha256
    assert confirmed.mate_candidate_id == mate.id
    assert confirmed.name == "bearing_journal"
    assert confirmed.diametral_clearance_mm == pytest.approx(0.2)
    assert confirmed.axial_engagement_mm == pytest.approx(10)
    assert confirmed.confirmed_by == "R. Engineer"

    failed_fit = check_cylindrical_mate_fit(
        confirmed,
        basic_size=Quantity.parse("10 mm"),
        designation="H7/g6",
    )
    assert failed_fit.status == "fail"
    assert failed_fit.hole.within_zone is True
    assert failed_fit.shaft.within_zone is False
    assert failed_fit.minimum_design_clearance_mm == pytest.approx(0.005)
    assert failed_fit.maximum_design_clearance_mm == pytest.approx(0.029)
    assert failed_fit.measured_clearance_within_design_range is False
    assert "ISO 286-1" in failed_fit.reference

    passing = detect_step_interfaces(write_pair("passing-fit.step", radius=4.995))
    passing_mate = confirm_cylindrical_mate(
        passing,
        mate_id=passing.cylindrical_mates[0].id,
        name="bearing_journal",
        confirmed_by="R. Engineer",
    )
    passed_fit = check_cylindrical_mate_fit(
        passing_mate,
        basic_size=Quantity.parse("10 mm"),
        designation="H7/g6",
    )
    assert passed_fit.status == "pass"
    assert passed_fit.hole.within_zone is True
    assert passed_fit.shaft.within_zone is True
    assert passed_fit.measured_clearance_within_design_range is True

    with pytest.raises(GeometryError, match="available: cylindrical-mate-"):
        confirm_cylindrical_mate(
            clearance,
            mate_id="cylindrical-mate-absent",
            name="bearing_journal",
            confirmed_by="R. Engineer",
        )


def test_step_interface_detection_scores_positive_solid_interference(tmp_path):
    from build123d import Box, Compound, Location, export_step

    base = Box(100, 80, 10)

    def write_pair(name: str, *, center=(0, 0, 10), reverse=False):
        intruder = Box(20, 20, 20).moved(Location(center))
        children = [intruder, base] if reverse else [base, intruder]
        path = tmp_path / name
        export_step(Compound(children=children), path)
        return path

    detected = detect_step_interfaces(write_pair("interference.step"))
    reversed_detected = detect_step_interfaces(
        write_pair("interference-reversed.step", reverse=True)
    )
    touching = detect_step_interfaces(write_pair("touching.step", center=(0, 0, 15)))
    disjoint = detect_step_interfaces(write_pair("disjoint.step", center=(100, 0, 10)))

    assert len(detected.solid_interferences) == 1
    interference = detected.solid_interferences[0]
    assert interference.overlap_volume_mm3 == pytest.approx(2_000)
    assert interference.center_mm == pytest.approx((0, 0, 2.5))
    assert interference.bounds_min_mm == pytest.approx((-10, -10, 0))
    assert interference.bounds_max_mm == pytest.approx((10, 10, 5))
    assert detected.solid_interferences == reversed_detected.solid_interferences
    assert detected.interference_scorecard.status is CheckStatus.FAIL
    assert detected.interference_scorecard.governing().name.startswith("solid interference")
    assert "2,000" not in detected.interference_scorecard.governing().detail
    assert "2000 mm³" in detected.interference_scorecard.governing().detail
    assert not touching.solid_interferences
    assert touching.interference_scorecard.status is CheckStatus.PASS
    assert not disjoint.solid_interferences
    assert disjoint.interference_scorecard.status is CheckStatus.PASS


def test_hole_pattern_candidate_count_must_match_its_measured_centers():
    with pytest.raises(ValueError, match="hole_count is 3, but 2 centers are listed"):
        HolePatternCandidate(
            id="pattern-test",
            hole_count=3,
            hole_diameter_mm=10,
            pitch_diameter_mm=60,
            center_mm=(0, 0, 0),
            hole_centers_mm=((-30, 0, 0), (30, 0, 0)),
        )


def test_step_interface_import_does_not_leak_kernel_diagnostics_to_stdout(tmp_path, capsys):
    path = tmp_path / "broken.step"
    path.write_text("ISO-10303-21;\nBROKEN;\nEND-ISO-10303-21;\n", encoding="utf-8")

    # Refused by the reader itself since it became OCCT's plain STEPControl_Reader, which is
    # earlier and more exact than the empty shape the assembly importer used to return.
    with pytest.raises(GeometryError, match="the reader rejected it"):
        detect_step_interfaces(path)

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("view", ("iso", "front", "top", "right"))
def test_annular_cover_plate_renders_every_named_view_with_all_semantic_tags(view):
    built = build_cover_plate(
        _cover(
            length=None,
            width=None,
            diameter=Quantity.parse("300 mm"),
            hole_diameter=Quantity.parse("80 mm"),
        )
    )

    rendered = render_viewport(built, view=view, width_px=640)
    text = rendered.data.decode()

    assert rendered == render_viewport(built, view=view, width_px=640)
    assert all(f'data-face="{tag}"' in text for tag in built.faces)


def test_annular_cover_plate_named_views_are_visually_distinct():
    built = build_cover_plate(
        _cover(
            length=None,
            width=None,
            diameter=Quantity.parse("300 mm"),
            hole_diameter=Quantity.parse("80 mm"),
        )
    )

    images = {view: render_viewport(built, view=view).data for view in ("iso", "front", "top")}

    assert len(set(images.values())) == len(images)


def test_annular_cover_plate_step_round_trip_preserves_the_bore(tmp_path):
    from build123d import import_step

    built = build_cover_plate(
        _cover(
            length=None,
            width=None,
            diameter=Quantity.parse("300 mm"),
            hole_diameter=Quantity.parse("80 mm"),
        )
    )
    restored = import_step(write_step(built, tmp_path / "cover.step", authorization=_STEP_AUTH))

    assert restored.is_valid
    assert len(restored.solids()) == 1
    assert restored.volume == pytest.approx(built.volume_mm3, rel=1e-8)


def test_a_loose_plane_beside_the_part_is_set_aside_not_a_refusal(tmp_path):
    """Supplemental geometry, such as a datum or section plane, travels in AP242 files as a
    shell owned by no solid. Every planar face used to come from the whole shape, so one such
    plane refused the file ("could not be assigned to exactly one imported solid"). That
    happened to six of NIST's seventeen AP242 PMI test models."""
    from build123d import Box, Compound, Face, Plane, export_step

    path = tmp_path / "part-with-datum-plane.step"
    export_step(Compound([Box(20, 20, 10), Face.make_rect(50, 50, Plane.XY.offset(30))]), path)
    result = detect_step_interfaces(path)
    assert len(result.planar_faces) == 6  # the box's, and not the loose plane
    assert any("1 face(s) belong to no solid" in warning for warning in result.warnings)


# What each of NIST's AP242 PMI test models reads as. The files are US government work, usable
# "without any restrictions", and are fetched by the scheduled `step-referee` job rather than
# committed (14 MB). Pinned from the first clean run on 2026-09-25: one segfaulted the reader,
# one raised an internal error, and six were refused before the fixes this holds.
_NIST_AP242 = {
    "nist_ctc_01_asme1_ap242-e1": (56, 0),
    "nist_ctc_02_asme1_ap242-e2": (105, 2),
    "nist_ctc_03_asme1_ap242-e2": (62, 0),
    "nist_ctc_04_asme1_ap242-e1": (88, 1),
    "nist_ctc_05_asme1_ap242-e1": (62, 0),
    "nist_ftc_06_asme1_ap242-e2": (71, 0),
    "nist_ftc_07_asme1_ap242-e2": (73, 2),
    "nist_ftc_08_asme1_ap242-e2": (81, 0),
    "nist_ftc_09_asme1_ap242-e1": (62, 5),
    "nist_ftc_10_asme1_ap242-e2": (53, 18),
    "nist_ftc_11_asme1_ap242-e2": (26, 0),
    "nist_stc_06_asme1_ap242-e3": (71, 0),
    "nist_stc_07_asme1_ap242-e3": (73, 2),
    "nist_stc_08_asme1_ap242-e3": (81, 1),
    "nist_stc_09_asme1_ap242-e3": (62, 0),
    "nist_stc_10_asme1_ap242-e2": (77, 0),
}


def test_every_nist_ap242_pmi_model_reads_as_it_did():
    """target-ap242-e4-exports 2.2: the CAx-IF/NIST test models as reader regression fixtures.

    Each model's planar-face count and loose-face count are pinned, and the one file carrying
    only tessellated geometry is refused as having no valid solid. Skipped unless
    ``ANVILATE_NIST_PMI_STEP`` names the unpacked download; the scheduled job sets it.
    """
    import os
    from pathlib import Path

    root = os.environ.get("ANVILATE_NIST_PMI_STEP")
    if not root:
        pytest.skip("ANVILATE_NIST_PMI_STEP is not set; the scheduled step-referee job sets it")
    folder = Path(root)
    found = sorted(path.stem for path in folder.glob("*_ap242-*.stp"))
    assert set(found) == set(_NIST_AP242) | {"nist_ftc_08_asme1_ap242-e1-tg"}, found
    for stem, (planar, loose) in _NIST_AP242.items():
        result = detect_step_interfaces(folder / f"{stem}.stp")
        warned = [w for w in result.warnings if "belong to no solid" in w]
        assert (len(result.planar_faces), len(warned)) == (planar, 1 if loose else 0), stem
        if loose:
            assert warned[0].startswith(f"{loose} face(s)"), (stem, warned)
    with pytest.raises(GeometryError, match="valid positive-volume solids"):
        detect_step_interfaces(folder / "nist_ftc_08_asme1_ap242-e1-tg.stp")


def _read_semantic_pmi(path):  # type: ignore[no-untyped-def]
    """(characteristic, value in mm, zone is a diameter, datum letters) per tolerance, as
    OCCT's GD&T reader recovers them from the written file."""
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDimTolObjects import XCAFDimTolObjects_GeomToleranceTypeValue
    from OCP.XCAFDoc import (
        XCAFDoc_Datum,
        XCAFDoc_DimTolTool,
        XCAFDoc_DocumentTool,
        XCAFDoc_GeomTolerance,
    )

    document = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    XCAFApp_Application.GetApplication_s().NewDocument(
        TCollection_ExtendedString("MDTV-XCAF"), document
    )
    reader = STEPCAFControl_Reader()
    reader.SetGDTMode(True)
    reader.ReadFile(str(path))
    reader.Transfer(document)
    tool = XCAFDoc_DocumentTool.DimTolTool_s(document.Main())
    labels = TDF_LabelSequence()
    tool.GetGeomToleranceLabels(labels)
    diameter = (
        XCAFDimTolObjects_GeomToleranceTypeValue.XCAFDimTolObjects_GeomToleranceTypeValue_Diameter
    )
    found = []
    for index in range(1, labels.Length() + 1):
        label = labels.Value(index)
        definition = XCAFDoc_GeomTolerance.Set_s(label).GetObject()
        datums = TDF_LabelSequence()
        XCAFDoc_DimTolTool.GetDatumOfTolerLabels_s(label, datums)
        found.append(
            (
                definition.GetType().name.rsplit("_", 1)[-1],
                round(definition.GetValue(), 9),
                definition.GetTypeOfValue() == diameter,
                sorted(
                    XCAFDoc_Datum.Set_s(datums.Value(j)).GetObject().GetName().ToCString()
                    for j in range(1, datums.Length() + 1)
                ),
            )
        )
    return sorted(found)


def _tolerances():  # type: ignore[no-untyped-def]
    from anvilate.spec.ir import GeometricTolerance

    return [
        GeometricTolerance(characteristic="flatness", tolerance=_q("0.05 mm"), feature="top"),
        GeometricTolerance(
            characteristic="perpendicularity",
            tolerance=_q("0.1 mm"),
            feature="north",
            datums=["bottom"],
        ),
        GeometricTolerance(
            characteristic="parallelism",
            tolerance=_q("0.02 mm"),
            feature="top",
            datums=["bottom", "west"],
        ),
    ]


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_a_documents_tolerances_travel_in_the_step_as_semantic_pmi(tmp_path):
    """semantic-gdt-layer 2.2: the spec's tolerances written as AP242 semantic PMI on the
    faces their tags name, datums lettered in first-seen order, and recovered by OCCT's own
    GD&T reader with the values the document states."""
    path = tmp_path / "plate.step"
    write_step(build_base_plate(_plate()), path, authorization=_STEP_AUTH, tolerances=_tolerances())
    assert _read_semantic_pmi(path) == [
        ("Flatness", 0.05, False, []),
        ("Parallelism", 0.02, False, ["A", "B"]),
        ("Perpendicularity", 0.1, False, ["A"]),
    ]


def test_a_tolerance_is_written_in_the_unit_its_value_is_in(tmp_path):
    """OCCT states every tolerance measure in metres and does not convert what it is given,
    so a 0.05 mm flatness passed through unconverted was written as 0.05 m, a zone a thousand
    times too wide, that a reader recovering "50 mm" would take at face value. Read the
    measure and its unit out of the file itself."""
    import re

    path = tmp_path / "plate.step"
    write_step(
        build_base_plate(_plate()), path, authorization=_STEP_AUTH, tolerances=_tolerances()[:1]
    )
    text = path.read_text(encoding="utf-8")
    flatness = re.search(r"FLATNESS_TOLERANCE\('[^']*','[^']*',#(\d+)", text)
    assert flatness is not None
    measure = re.search(
        rf"#{flatness.group(1)} = LENGTH_MEASURE_WITH_UNIT\(LENGTH_MEASURE\(([^)]*)\),#(\d+)\)",
        text,
    )
    unit = re.search(
        rf"#{measure.group(2)} = \( LENGTH_UNIT\(\) NAMED_UNIT\(\*\) SI_UNIT\(([^)]*)\)", text
    )
    magnitude = float(measure.group(1))
    scale = {"$,.METRE.": 1.0, ".MILLI.,.METRE.": 1e-3}[unit.group(1)]
    assert magnitude * scale == pytest.approx(0.05e-3, rel=1e-12)


def test_semantic_pmi_is_refused_where_it_cannot_be_written(tmp_path):
    from anvilate.spec.ir import GeometricTolerance

    with pytest.raises(GeometryError, match="AP242 construct"):
        write_step(
            build_base_plate(_plate()),
            tmp_path / "a.step",
            authorization=_STEP_AUTH,
            schema="ap214",
            tolerances=_tolerances(),
        )
    stray = GeometricTolerance(characteristic="flatness", tolerance=_q("0.05 mm"), feature="bore")
    with pytest.raises(GeometryError, match="'bore', which the base_plate/1 solid does not tag"):
        write_step(
            build_base_plate(_plate()),
            tmp_path / "b.step",
            authorization=_STEP_AUTH,
            tolerances=[stray],
        )
    assert not (tmp_path / "b.step").exists(), "a refused write left a file behind"


def test_the_same_tolerances_give_the_same_bytes(tmp_path):
    first, second = tmp_path / "1.step", tmp_path / "2.step"
    write_step(
        build_base_plate(_plate()), first, authorization=_STEP_AUTH, tolerances=_tolerances()
    )
    write_step(
        build_base_plate(_plate()), second, authorization=_STEP_AUTH, tolerances=_tolerances()
    )
    assert first.read_bytes() == second.read_bytes()
