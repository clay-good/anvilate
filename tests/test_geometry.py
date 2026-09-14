"""Golden checks for the first audited B-Rep generation pattern."""

from __future__ import annotations

from types import MappingProxyType

import pytest

pytest.importorskip("build123d")

from anvilate.geometry import (  # noqa: E402
    BASE_PLATE_PATTERN,
    GeometryError,
    UnsupportedGeometry,
    build_base_plate,
    build_spec,
    write_step,
)
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


def test_step_round_trip_preserves_the_valid_solid(tmp_path):
    from build123d import import_step

    path = write_step(build_base_plate(_plate()), tmp_path / "base.step")
    restored = import_step(path)

    assert path.read_text(encoding="utf-8").startswith("ISO-10303-21;")
    assert restored.is_valid
    assert len(restored.solids()) == 1
    assert restored.volume == pytest.approx(300 * 240 * 25, rel=1e-8)


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
