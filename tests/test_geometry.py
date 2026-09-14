"""Golden checks for the first audited B-Rep generation pattern."""

from __future__ import annotations

import base64
import re
from hashlib import sha256
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


def _four_hole_step(path, *, centers=((-30, -20), (-30, 20), (30, -20), (30, 20))):
    from build123d import Align, Box, Cylinder, Location, export_step

    shape = Box(100, 80, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for x, y in centers:
        cutter = Cylinder(5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
            Location((x, y, 0))
        )
        shape = shape - cutter
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


def test_step_interface_detection_refuses_a_multi_solid_file(tmp_path):
    from build123d import Box, Location, export_step

    path = tmp_path / "assembly.step"
    export_step(Box(10, 10, 10) + Box(10, 10, 10).moved(Location((30, 0, 0))), path)

    with pytest.raises(GeometryError, match="needs one valid solid; found 2"):
        detect_step_interfaces(path)


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

    with pytest.raises(GeometryError, match="needs one valid solid"):
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
