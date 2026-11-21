"""IFC export: a checked structural part as the element a building model holds.

IFC (ISO 16739-1:2018 is IFC4; ISO 16739-1:2024 is IFC 4.3) is how a structural part reaches
a building model. A STEP solid arrives as a lump of faces and loses what it is; an IFC
element arrives as a beam, a column or a plate, with its material, its mass, its part
number and, here, the verdict that was reached on it.

Four positions, each of them a refusal or a record:

* **A part is the class its element maps to, or it is refused.** :data:`IFC_ELEMENT_CLASSES`
  maps an element to an IFC class and predefined type. An element with no mapping is
  refused naming it, never written as an ``IfcBuildingElementProxy``: a proxy is a lump
  with a label, which is the loss this format exists to avoid.
* **A predefined type the declared schema lacks is not invented.** IFC 4.3 added
  ``BASE_PLATE``, ``GUSSET_PLATE`` and ``COVER_PLATE`` to ``IfcPlateTypeEnum``; IFC4 has
  none of them. In IFC4 such a plate is ``USERDEFINED`` with the name in ``ObjectType``,
  which is the schema's own rule for a type it does not enumerate. Both enumerations were
  read from the schemas IfcOpenShell 0.9.0 ships, not recalled.
* **The verdict travels with the element.** The ``Anvilate_Screening`` property set holds
  the part number, material, mass, validation status and card digest, and an unvalidated
  export carries its watermark there and in the file header both.
* **The same parts give the same bytes.** Every ``GlobalId`` is derived from the part's
  identity and the header's timestamp is fixed, so a file's digest identifies its content.

Geometry is a faceted boundary representation (``IfcFacetedBrep``) of the closed, welded,
outward-facing mesh the 3MF writer is held to. A standard profile with an extrusion, for a
member on a rolled section, is the next slice (add-ifc-structural-export 1.2).

IfcOpenShell (LGPL-3.0-or-later) is the optional ``ifc`` extra; nothing else imports it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from dataclasses import replace as _replace
from typing import Any, Literal

from .. import __version__
from ..capabilities import install_remedy
from ..refusal import RefusalError, Remedy
from .gate import ExportAuthorization

__all__ = [
    "IFC_ELEMENT_CLASSES",
    "IFC_SCHEMAS",
    "IfcElementMeasure",
    "IfcPart",
    "IfcSweptProfile",
    "combination_ifc_parts",
    "ifc_class_for",
    "ifc_part",
    "measure_ifc",
    "render_ifc",
]

#: The schemas a file may declare: IFC4 (ISO 16739-1:2018), the default, and IFC 4.3
#: (ISO 16739-1:2024) as IfcOpenShell names its second addendum.
IFC_SCHEMAS = ("IFC4", "IFC4X3_ADD2")
IfcSchema = Literal["IFC4", "IFC4X3_ADD2"]

#: Each element an IFC file can hold, as (IFC class, predefined type). A predefined type
#: that is not in the declared schema's enumeration is written ``USERDEFINED`` with the
#: name in ``ObjectType`` (see :func:`ifc_class_for`).
IFC_ELEMENT_CLASSES: Mapping[str, tuple[str, str]] = {
    "base_plate": ("IfcPlate", "BASE_PLATE"),
    "beam_column_member": ("IfcColumn", "COLUMN"),
    "beam_member": ("IfcBeam", "BEAM"),
    "column_member": ("IfcColumn", "COLUMN"),
    "cover_plate": ("IfcPlate", "COVER_PLATE"),
    "gusset_plate": ("IfcPlate", "GUSSET_PLATE"),
    "shear_plate": ("IfcPlate", "SHEAR_PLATE"),
    "tension_member": ("IfcMember", "MEMBER"),
    "tube": ("IfcMember", "MEMBER"),
    # A combination's hardware, by the kind it is drawn as. IFC enumerates bolts and dowels;
    # a nut, a washer and a key are fasteners it has no member for.
    "bolt": ("IfcMechanicalFastener", "BOLT"),
    "key": ("IfcMechanicalFastener", "KEY"),
    "nut": ("IfcMechanicalFastener", "NUT"),
    "pin": ("IfcMechanicalFastener", "DOWEL"),
    "washer": ("IfcMechanicalFastener", "WASHER"),
}

# The predefined types each schema enumerates for the classes above, as IfcOpenShell
# 0.9.0's schema reports them. A test reads them back from the toolkit, so this cannot
# drift from what the writer is checked against.
_ENUMERATED: Mapping[str, Mapping[str, frozenset[str]]] = {
    "IFC4": {
        "IfcMechanicalFastener": frozenset(
            {
                "ANCHORBOLT",
                "BOLT",
                "DOWEL",
                "NAIL",
                "NAILPLATE",
                "RIVET",
                "SCREW",
                "SHEARCONNECTOR",
                "STAPLE",
                "STUDSHEARCONNECTOR",
            }
        ),
        "IfcBeam": frozenset({"BEAM", "JOIST", "HOLLOWCORE", "LINTEL", "SPANDREL", "T_BEAM"}),
        "IfcColumn": frozenset({"COLUMN", "PILASTER"}),
        "IfcMember": frozenset(
            {
                "BRACE",
                "CHORD",
                "COLLAR",
                "MEMBER",
                "MULLION",
                "PLATE",
                "POST",
                "PURLIN",
                "RAFTER",
                "STRINGER",
                "STRUT",
                "STUD",
            }
        ),
        "IfcPlate": frozenset({"CURTAIN_PANEL", "SHEET"}),
    },
    "IFC4X3_ADD2": {
        "IfcMechanicalFastener": frozenset(
            {
                "ANCHORBOLT",
                "BOLT",
                "CHAIN",
                "COUPLER",
                "DOWEL",
                "NAIL",
                "NAILPLATE",
                "RAILFASTENING",
                "RAILJOINT",
                "RIVET",
                "ROPE",
                "SCREW",
                "SHEARCONNECTOR",
                "STAPLE",
                "STUDSHEARCONNECTOR",
            }
        ),
        "IfcBeam": frozenset(
            {
                "BEAM",
                "CORNICE",
                "DIAPHRAGM",
                "EDGEBEAM",
                "GIRDER_SEGMENT",
                "HATSTONE",
                "HOLLOWCORE",
                "JOIST",
                "LINTEL",
                "PIERCAP",
                "SPANDREL",
                "T_BEAM",
            }
        ),
        "IfcColumn": frozenset(
            {"COLUMN", "PIERSTEM", "PIERSTEM_SEGMENT", "PILASTER", "STANDCOLUMN"}
        ),
        "IfcMember": frozenset(
            {
                "ARCH_SEGMENT",
                "BRACE",
                "CHORD",
                "COLLAR",
                "MEMBER",
                "MULLION",
                "PLATE",
                "POST",
                "PURLIN",
                "RAFTER",
                "STAY_CABLE",
                "STIFFENING_RIB",
                "STRINGER",
                "STRUCTURALCABLE",
                "STRUT",
                "STUD",
                "SUSPENDER",
                "SUSPENSION_CABLE",
                "TIEBAR",
            }
        ),
        "IfcPlate": frozenset(
            {
                "BASE_PLATE",
                "COVER_PLATE",
                "CURTAIN_PANEL",
                "FLANGE_PLATE",
                "GUSSET_PLATE",
                "SHEET",
                "SPLICE_PLATE",
                "STIFFENER_PLATE",
                "WEB_PLATE",
            }
        ),
    },
}

#: The custom property set every element carries. Not ``Pset_``: that prefix is the
#: standard's own and a custom set may not use it.
SCREENING_PSET = "Anvilate_Screening"

_EXPORT_GATE_SOURCE = "the authorization authorize_export issued for this part's scorecard"
_MAPPING_SOURCE = "anvilate.export.ifc.IFC_ELEMENT_CLASSES"
_MESH_SOURCE = "the part's tessellated CAD model (vertices and triangles in mm)"
# 2000-01-01, fixed, so identical content is identical bytes. The header field is the time
# the file was written, and a digest that changed every run would identify nothing.
_TIMESTAMP = "2000-01-01T00:00:00"


class _IfcInputError(RefusalError, ValueError):
    """An IFC export input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str, action: str = "replace") -> _IfcInputError:
    return _IfcInputError(
        message, remedies=(Remedy(action=action, subject=subject, source=source),)
    )


@dataclass(frozen=True)
class IfcSweptProfile:
    """A rolled section swept along a straight axis, as IFC's own profile definitions.

    ``kind`` is ``I`` (``IfcIShapeProfileDef``: ``width``, ``depth``, ``web``, ``flange``,
    ``fillet``), ``rectangle_hollow`` (``IfcRectangleHollowProfileDef``: ``width``,
    ``depth``, ``wall``, ``inner_fillet``, ``outer_fillet``) or ``circle_hollow``
    (``IfcCircleHollowProfileDef``: ``diameter``, ``wall``), every size in millimetres.
    The profile's ``width`` lies along ``across``, and the section is swept ``length`` mm
    along ``axis`` from ``start``, the point on the axis where the member begins.
    """

    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    designation: str
    dimensions: Mapping[str, float]
    length: float
    axis: tuple[float, float, float]
    across: tuple[float, float, float]
    start: tuple[float, float, float]


@dataclass(frozen=True)
class IfcPart:
    """One part to export: its identity, its mesh in millimetres, and what was found on it.

    ``tag`` identifies this instance within the file: it is the element's ``Tag``. The
    part number, which several instances may share, is ``part_number``. ``vertices`` and
    ``triangles`` are a closed, outward-facing mesh in millimetres in the part's own frame,
    which is the file's unless ``placement`` moves it; a ``profile`` replaces the mesh as
    the written geometry. ``card_digest`` is the digest of this part's own scorecard.
    """

    tag: str
    name: str
    element_type: str
    vertices: Sequence[tuple[float, float, float]]
    triangles: Sequence[tuple[int, int, int]]
    material: str | None = None
    mass_kg: float | None = None
    part_number: str | None = None
    card_digest: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)
    profile: IfcSweptProfile | None = None
    # Where the part is: its rotation's rows and its shift in mm, from its own frame (the
    # one its mesh and profile are in) to the file's. ``None`` is where it was built.
    placement: tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]] | None = (
        None
    )


@dataclass(frozen=True)
class IfcElementMeasure:
    """An element read back from a file: its class, tag, volume (mm³) and centroid (mm)."""

    ifc_class: str
    tag: str
    predefined_type: str
    object_type: str | None
    volume_mm3: float
    centroid_mm: tuple[float, float, float]
    bounds_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    representation: str


def ifc_class_for(element_type: str, schema: IfcSchema = "IFC4") -> tuple[str, str, str | None]:
    """``(class, PredefinedType, ObjectType)`` for an element in the declared schema.

    A predefined type the schema enumerates is written as itself; one it does not is
    written ``USERDEFINED`` with the name in ``ObjectType``. An element with no mapping is
    refused naming it.
    """
    if schema not in IFC_SCHEMAS:
        raise _refuse(
            f"schema {schema!r} is not one this writer declares; it writes {list(IFC_SCHEMAS)}",
            subject="schema",
            source="IFC_SCHEMAS",
            action="select",
        )
    if element_type not in IFC_ELEMENT_CLASSES:
        raise _refuse(
            f"the element {element_type!r} has no IFC class here, and is not exported as a "
            f"proxy; the mapped elements are {sorted(IFC_ELEMENT_CLASSES)}",
            subject=f"the {element_type} element",
            source=_MAPPING_SOURCE,
            action="select",
        )
    ifc_class, predefined = IFC_ELEMENT_CLASSES[element_type]
    if predefined in _ENUMERATED[schema][ifc_class]:
        return ifc_class, predefined, None
    return ifc_class, "USERDEFINED", predefined


def _content_digest(name: str, schema: str, assembly: str | None, parts: Sequence[IfcPart]) -> str:
    """A digest of everything a file is written from, which its GlobalIds are seeded by."""
    digest = hashlib.sha256(f"{name}\x1e{schema}\x1e{assembly}".encode())
    for part in parts:
        digest.update(
            repr(
                (
                    part.tag, part.name, part.element_type, part.material, part.mass_kg,
                    part.part_number, part.card_digest, sorted(part.extra.items()),
                    part.profile, part.placement, tuple(map(tuple, part.vertices)),
                    tuple(map(tuple, part.triangles)),
                )
            ).encode()
        )  # fmt: skip
    return digest.hexdigest()


def _guid(*seed: str) -> str:
    import ifcopenshell.guid

    return ifcopenshell.guid.compress(hashlib.sha256("\x1f".join(seed).encode()).hexdigest()[:32])


def _toolkit() -> Any:
    try:
        import ifcopenshell
    except ImportError as missing:  # pragma: no cover - exercised without the extra
        raise _refuse(
            f"IFC export needs IfcOpenShell; {install_remedy('ifc')}",
            subject="the ifc extra",
            source="pyproject.toml [project.optional-dependencies] ifc",
            action="add",
        ) from missing
    return ifcopenshell


def _checked(part: IfcPart) -> None:
    if not isinstance(part, IfcPart):
        raise _refuse(
            f"each part must be an IfcPart; got {part!r}", subject="parts", source=_MESH_SOURCE
        )
    if not part.tag.strip() or not part.name.strip():
        raise _refuse("a part needs a tag and a name", subject="parts", source=_MESH_SOURCE)
    if len(part.vertices) < 4 or len(part.triangles) < 4:
        raise _refuse(
            f"part {part.tag!r} has {len(part.vertices)} vertices and {len(part.triangles)} "
            "triangles; a closed solid needs at least 4 of each",
            subject=f"the {part.tag} mesh",
            source=_MESH_SOURCE,
        )
    for point in part.vertices:
        if len(point) != 3 or not all(math.isfinite(c) for c in point):
            raise _refuse(
                f"part {part.tag!r} has a vertex {point} that is not three finite numbers",
                subject=f"the {part.tag} mesh",
                source=_MESH_SOURCE,
            )
    for face in part.triangles:
        if len(set(face)) != 3 or not all(0 <= v < len(part.vertices) for v in face):
            raise _refuse(
                f"part {part.tag!r} has a triangle {face} that does not name three of its vertices",
                subject=f"the {part.tag} mesh",
                source=_MESH_SOURCE,
            )
    if part.profile is not None:
        _checked_profile(part.tag, part.profile)
    if part.placement is not None:
        _checked_placement(part.tag, part.placement)
    if part.mass_kg is not None and not (math.isfinite(part.mass_kg) and part.mass_kg > 0):
        raise _refuse(
            f"part {part.tag!r} states a mass of {part.mass_kg} kg; a mass is positive",
            subject=f"the {part.tag} mass",
            source=_MESH_SOURCE,
        )


def _unit(vector: Sequence[float]) -> bool:
    return (
        len(vector) == 3
        and all(map(math.isfinite, vector))
        and (abs(math.fsum(c * c for c in vector) - 1.0) < 1e-9)
    )


def _checked_profile(tag: str, profile: IfcSweptProfile) -> None:
    sizes = {**profile.dimensions, "length": profile.length}
    # A fillet may be zero (a welded box's square corner); every other size is positive.
    bad = [
        key
        for key, value in sizes.items()
        if not math.isfinite(value) or value < 0 or (value == 0 and "fillet" not in key)
    ]
    axis, across = profile.axis, profile.across
    square = (
        _unit(axis)
        and _unit(across)
        and abs(sum(a * b for a, b in zip(axis, across, strict=True))) < 1e-9
    )
    if bad or not square or not all(map(math.isfinite, profile.start)):
        what = f"sizes {bad}" if bad else "its axis and across directions or its start"
        raise _refuse(
            f"part {tag!r} has a profile whose {what} cannot be swept: sizes are finite and "
            "positive, and the axis and the across direction are perpendicular unit vectors",
            subject=f"the {tag} profile",
            source=_MESH_SOURCE,
        )


def _checked_placement(tag: str, placement: Any) -> None:
    rows, shift = placement
    columns = [tuple(row[i] for row in rows) for i in range(3)] if len(rows) == 3 else []
    orthonormal = len(columns) == 3 and all(
        abs(sum(a * b for a, b in zip(columns[i], columns[j], strict=True)) - (i == j)) < 1e-6
        for i in range(3)
        for j in range(3)
    )
    if not orthonormal or len(shift) != 3 or not all(map(math.isfinite, shift)):
        raise _refuse(
            f"part {tag!r} has a placement that is not a rotation and a finite shift; an IFC "
            "placement cannot scale or shear a part",
            subject=f"the {tag} placement",
            source="the rotation and translation the combination's mates solved",
        )


def render_ifc(
    parts: Sequence[IfcPart],
    *,
    name: str,
    authorization: ExportAuthorization,
    schema: IfcSchema = "IFC4",
    assembly: str | None = None,
) -> bytes:
    """``parts`` as the bytes of one IFC file of the declared ``schema``.

    With ``assembly`` the parts are aggregated under one ``IfcElementAssembly`` of that
    name, and the assembly, not each part, is what the storey contains.

    Each part is one element of the class its element maps to (:func:`ifc_class_for`),
    with its swept profile or, without one, a faceted B-rep of its mesh, its material, the
    schema's common property set and the ``Anvilate_Screening`` set, contained in one
    storey of one building on one site.
    Lengths are millimetres and masses kilograms, declared in the file's unit assignment.
    """
    if not isinstance(authorization, ExportAuthorization):
        raise _refuse(
            f"authorization must be an ExportAuthorization; got {authorization!r}",
            subject="authorization",
            source=_EXPORT_GATE_SOURCE,
        )
    if not isinstance(name, str) or not name.strip():
        raise _refuse("name must label the file's project", subject="name", source=_MESH_SOURCE)
    if not parts:
        raise _refuse("an IFC file holds at least one part", subject="parts", source=_MESH_SOURCE)
    if assembly is not None and not assembly.strip():
        raise _refuse("an assembly needs a name", subject="assembly", source=_MESH_SOURCE)
    classes = []
    for part in parts:
        _checked(part)
        classes.append(ifc_class_for(part.element_type, schema))
    tags = [part.tag for part in parts]
    repeated = sorted({tag for tag in tags if tags.count(tag) > 1})
    if repeated:
        raise _refuse(
            f"these part tags are used twice: {repeated}; each element is one part",
            subject="parts",
            source=_MESH_SOURCE,
        )

    ifcopenshell = _toolkit()
    f = ifcopenshell.file(schema=schema)
    _header(f, name.strip(), authorization)
    project_name = name.strip()

    # Every GlobalId is seeded by what the file holds, not only by its name: two exports
    # that share a name and a tag are different objects and must not share an id, and the
    # same parts still give the same ids, so the same bytes.
    content = _content_digest(project_name, schema, assembly, parts)

    def owned(entity: str, seed: str, **attributes: Any) -> Any:
        return f.create_entity(entity, GlobalId=_guid(content, entity, seed), **attributes)

    units = f.create_entity(
        "IfcUnitAssignment",
        Units=[
            f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"),
            f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
            f.create_entity("IfcSIUnit", UnitType="MASSUNIT", Prefix="KILO", Name="GRAM"),
            f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"),
        ],
    )
    origin = f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    world = f.create_entity("IfcAxis2Placement3D", Location=origin)
    context = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=world,
    )
    body = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=context,
        TargetView="MODEL_VIEW",
    )
    project = owned(
        "IfcProject", "", Name=project_name, UnitsInContext=units, RepresentationContexts=[context]
    )
    placement = f.create_entity("IfcLocalPlacement", RelativePlacement=world)
    site = owned("IfcSite", "", Name="Site", ObjectPlacement=placement)
    building = owned("IfcBuilding", "", Name="Building", ObjectPlacement=placement)
    storey = owned("IfcBuildingStorey", "", Name="Storey", ObjectPlacement=placement)
    owned("IfcRelAggregates", "project", RelatingObject=project, RelatedObjects=[site])
    owned("IfcRelAggregates", "site", RelatingObject=site, RelatedObjects=[building])
    owned("IfcRelAggregates", "building", RelatingObject=building, RelatedObjects=[storey])

    elements = []
    materials: dict[str, Any] = {}
    for part, (ifc_class, predefined, object_type) in zip(parts, classes, strict=True):
        if part.profile is not None:
            solid, kind = _swept(f, part.profile), "SweptSolid"
        else:
            solid, kind = _faceted(f, part), "Brep"
        shape = f.create_entity(
            "IfcProductDefinitionShape",
            Representations=[
                f.create_entity(
                    "IfcShapeRepresentation",
                    ContextOfItems=body,
                    RepresentationIdentifier="Body",
                    RepresentationType=kind,
                    Items=[solid],
                )
            ],
        )
        element = owned(
            ifc_class,
            part.tag,
            Name=part.name,
            Tag=part.tag,
            ObjectType=object_type,
            PredefinedType=predefined,
            ObjectPlacement=f.create_entity(
                "IfcLocalPlacement",
                PlacementRelTo=placement,
                RelativePlacement=_placed(f, part.placement) or world,
            ),
            Representation=shape,
        )
        elements.append(element)
        if part.material:
            if part.material not in materials:
                materials[part.material] = f.create_entity("IfcMaterial", Name=part.material)
        _property_sets(f, owned, element, part, ifc_class, authorization)
    for material_name, material in sorted(materials.items()):
        users = [e for e, p in zip(elements, parts, strict=True) if p.material == material_name]
        owned(
            "IfcRelAssociatesMaterial",
            f"material:{material_name}",
            RelatingMaterial=material,
            RelatedObjects=users,
        )
    contained = elements
    if assembly is not None:
        whole = owned(
            "IfcElementAssembly",
            "assembly",
            Name=assembly.strip(),
            ObjectPlacement=placement,
            PredefinedType="NOTDEFINED",
        )
        owned("IfcRelAggregates", "assembly", RelatingObject=whole, RelatedObjects=elements)
        contained = [whole]
    owned(
        "IfcRelContainedInSpatialStructure",
        "storey",
        RelatingStructure=storey,
        RelatedElements=contained,
    )
    return f.to_string().encode("utf-8")


def _placed(f: Any, placement: Any) -> Any:
    """A part's rotation and shift as an axis placement: its z and x axes, and its origin."""
    if placement is None:
        return None
    rows, shift = placement
    column = [tuple(float(row[i]) for row in rows) for i in range(3)]
    return f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=tuple(map(float, shift))),
        Axis=f.create_entity("IfcDirection", DirectionRatios=column[2]),
        RefDirection=f.create_entity("IfcDirection", DirectionRatios=column[0]),
    )


def _faceted(f: Any, part: IfcPart) -> Any:
    """The part's mesh as a faceted B-rep, one face per triangle on shared points."""
    points = [
        f.create_entity("IfcCartesianPoint", Coordinates=tuple(map(float, v)))
        for v in part.vertices
    ]
    faces = [
        f.create_entity(
            "IfcFace",
            Bounds=[
                f.create_entity(
                    "IfcFaceOuterBound",
                    Bound=f.create_entity("IfcPolyLoop", Polygon=[points[i] for i in tri]),
                    Orientation=True,
                )
            ],
        )
        for tri in part.triangles
    ]
    return f.create_entity(
        "IfcFacetedBrep", Outer=f.create_entity("IfcClosedShell", CfsFaces=faces)
    )


def _swept(f: Any, profile: IfcSweptProfile) -> Any:
    """The profile definition the receiving tool keeps as a section, extruded along its axis."""
    size = profile.dimensions
    centre = f.create_entity(
        "IfcAxis2Placement2D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0)),
    )
    common = {"ProfileType": "AREA", "ProfileName": profile.designation, "Position": centre}
    if profile.kind == "I":
        area = f.create_entity(
            "IfcIShapeProfileDef",
            **common,
            OverallWidth=size["width"],
            OverallDepth=size["depth"],
            WebThickness=size["web"],
            FlangeThickness=size["flange"],
            FilletRadius=size["fillet"] or None,
        )
    elif profile.kind == "rectangle_hollow":
        area = f.create_entity(
            "IfcRectangleHollowProfileDef",
            **common,
            XDim=size["width"],
            YDim=size["depth"],
            WallThickness=size["wall"],
            InnerFilletRadius=size["inner_fillet"] or None,
            OuterFilletRadius=size["outer_fillet"] or None,
        )
    else:
        area = f.create_entity(
            "IfcCircleHollowProfileDef",
            **common,
            Radius=size["diameter"] / 2,
            WallThickness=size["wall"],
        )
    position = f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=tuple(profile.start)),
        Axis=f.create_entity("IfcDirection", DirectionRatios=tuple(profile.axis)),
        RefDirection=f.create_entity("IfcDirection", DirectionRatios=tuple(profile.across)),
    )
    return f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=area,
        Position=position,
        ExtrudedDirection=f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=float(profile.length),
    )


def _header(f: Any, name: str, authorization: ExportAuthorization) -> None:
    header = f.header
    header.file_description.description = (
        "ViewDefinition [ReferenceView]",
        *authorization.watermark(),
    )
    header.file_name.name = name
    header.file_name.time_stamp = _TIMESTAMP
    header.file_name.preprocessor_version = "IfcOpenShell"
    header.file_name.originating_system = f"anvilate {__version__}"
    header.file_name.authorization = authorization.status


def _property_sets(
    f: Any,
    owned: Any,
    element: Any,
    part: IfcPart,
    ifc_class: str,
    authorization: ExportAuthorization,
) -> None:
    def single(prop: str, value: Any) -> Any:
        return f.create_entity("IfcPropertySingleValue", Name=prop, NominalValue=value)

    common = [
        single("Reference", f.create_entity("IfcIdentifier", part.part_number or part.tag)),
        single("LoadBearing", f.create_entity("IfcBoolean", True)),
    ]
    common_name = f"Pset_{ifc_class.removeprefix('Ifc')}Common"
    screening = [
        single("ElementType", f.create_entity("IfcLabel", part.element_type)),
        single("ValidationStatus", f.create_entity("IfcLabel", authorization.status)),
    ]
    for key, value in authorization.metadata():
        screening.append(single(key, f.create_entity("IfcText", value)))
    if part.part_number:
        screening.append(single("PartNumber", f.create_entity("IfcIdentifier", part.part_number)))
    if part.material:
        screening.append(single("Material", f.create_entity("IfcLabel", part.material)))
    if part.mass_kg is not None:
        screening.append(single("Mass", f.create_entity("IfcMassMeasure", float(part.mass_kg))))
    if part.card_digest:
        screening.append(single("CardDigest", f.create_entity("IfcIdentifier", part.card_digest)))
    for key, value in sorted(part.extra.items()):
        screening.append(single(key, f.create_entity("IfcText", value)))
    # The common set the schema defines for a beam, column, member or plate holds a
    # reference and whether it bears load. A fastener's holds its nominal sizes instead (and
    # IFC 4.3 has none), so a fastener gets only the screening set.
    sets = [(SCREENING_PSET, screening)]
    if ifc_class != "IfcMechanicalFastener":
        sets.insert(0, (common_name, common))
    for pset_name, properties in sets:
        pset = owned(
            "IfcPropertySet", f"{part.tag}:{pset_name}", Name=pset_name, HasProperties=properties
        )
        owned(
            "IfcRelDefinesByProperties",
            f"{part.tag}:{pset_name}:rel",
            RelatingPropertyDefinition=pset,
            RelatedObjects=[element],
        )


def measure_ifc(data: bytes) -> list[IfcElementMeasure]:
    """Every element in an IFC file, re-read: its class, tag, volume and centroid.

    The geometry is evaluated by IfcOpenShell's own kernel from the file, not from the mesh
    that wrote it, and the volume and centroid are the mesh integrals of what it returns.
    """
    _toolkit()
    import ifcopenshell
    import ifcopenshell.geom

    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    measured = []
    for element in model.by_type("IfcElement"):
        nan = (math.nan, math.nan, math.nan)
        bounds = (nan, nan)
        kind = ""
        if element.Representation is None:
            volume, centroid = 0.0, nan
        else:
            kind = element.Representation.Representations[0].RepresentationType
            shape: Any = ifcopenshell.geom.create_shape(settings, element)
            verts, faces = shape.geometry.verts, shape.geometry.faces
            # The kernel works in metres whatever the file declares.
            scale = 1000.0
            points = [
                (verts[i] * scale, verts[i + 1] * scale, verts[i + 2] * scale)
                for i in range(0, len(verts), 3)
            ]
            volume, centroid = _integrals(
                points,
                [(faces[i], faces[i + 1], faces[i + 2]) for i in range(0, len(faces), 3)],
            )
            low = tuple(min(p[axis] for p in points) for axis in range(3))
            high = tuple(max(p[axis] for p in points) for axis in range(3))
            bounds = (low, high)  # type: ignore[assignment]
        measured.append(
            IfcElementMeasure(
                ifc_class=element.is_a(),
                tag=element.Tag,
                predefined_type=element.PredefinedType,
                object_type=element.ObjectType,
                volume_mm3=volume,
                centroid_mm=centroid,
                bounds_mm=bounds,
                representation=kind,
            )
        )
    return measured


def _integrals(
    vertices: Sequence[tuple[float, float, float]], triangles: Sequence[tuple[int, int, int]]
) -> tuple[float, tuple[float, float, float]]:
    """The enclosed volume and its centroid, by the divergence theorem over the triangles."""
    volume = 0.0
    moment = [0.0, 0.0, 0.0]
    for a, b, c in triangles:
        p, q, r = vertices[a], vertices[b], vertices[c]
        signed = (
            p[0] * (q[1] * r[2] - q[2] * r[1])
            - p[1] * (q[0] * r[2] - q[2] * r[0])
            + p[2] * (q[0] * r[1] - q[1] * r[0])
        ) / 6.0
        volume += signed
        for axis in range(3):
            moment[axis] += signed * (p[axis] + q[axis] + r[axis]) / 4.0
    if volume == 0.0:
        return 0.0, (math.nan, math.nan, math.nan)
    return volume, (moment[0] / volume, moment[1] / volume, moment[2] / volume)


def ifc_part(
    spec: Any,
    built: Any,
    card: Any,
    *,
    tag: str | None = None,
    part_number: str | None = None,
) -> IfcPart:
    """The :class:`IfcPart` a built spec exports as: its mesh, identity, mass and verdict.

    A member on a section the bundled table names as a rolled I shape or HSS also carries
    that section as an :class:`IfcSweptProfile`, framed from the built solid, so the file
    holds the profile and its extrusion rather than the faces. ``card`` is the part's
    scorecard; its digest is the one a review of it would cite.
    """
    from .. import __version__ as version
    from ..combination import _mass
    from ..geometry import _mesh_for_3mf
    from ..review import artifact_digest

    vertices, triangles = _mesh_for_3mf(built)
    material = getattr(getattr(spec, "material", None), "ref", None)
    mass = _mass(spec, built) if material else None
    return IfcPart(
        tag=tag or built.name,
        name=built.name,
        element_type=spec.element_type,
        vertices=vertices,
        triangles=triangles,
        material=str(material) if material else None,
        mass_kg=mass,
        part_number=part_number,
        card_digest="sha256:" + artifact_digest(card, toolchain=f"anvilate {version}"),
        profile=_profile_of(spec, built),
    )


def _profile_of(spec: Any, built: Any) -> IfcSweptProfile | None:
    """The rolled section a member is drawn from, as a swept profile, or ``None``."""
    named = (spec.element_params or {}).get("section")
    if not isinstance(named, str):
        return None
    from ..packs.structural import _hollow_bar, _pipe_record
    from ..standards.profiles import resolve_profile

    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    # A tube, a box or a pipe named by its dimensions or its schedule needs no table. The
    # box is welded from plates, so its corners are square, as it is drawn.
    hollow = _hollow_bar(named)
    pipe = _pipe_record(named)
    if hollow is not None and len(hollow) == 2:
        kind, dimensions = "circle_hollow", {"diameter": hollow[0], "wall": hollow[1]}
    elif hollow is not None:
        kind = "rectangle_hollow"
        dimensions = {
            "width": hollow[0],
            "depth": hollow[1],
            "wall": hollow[2],
            "inner_fillet": 0.0,
            "outer_fillet": 0.0,
        }
    elif pipe is not None:
        outside, inside = _mm(pipe.outside_diameter), _mm(pipe.inside_diameter)
        kind, dimensions = "circle_hollow", {"diameter": outside, "wall": (outside - inside) / 2}
    else:
        try:
            profile = resolve_profile(named)
        except (KeyError, ValueError):
            return None
        return _rolled(named, profile, built)
    return _framed(named, kind, dimensions, built)


def _mm(value: Any) -> float:
    return float(getattr(value, "quantity", value).to("mm").magnitude)


def _rolled(named: str, profile: Any, built: Any) -> IfcSweptProfile | None:
    """A table profile: a rolled I shape, or an AISC HSS (which needs the fetched table)."""
    from ..standards.profiles import HollowProfile, RolledProfile

    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    if isinstance(profile, RolledProfile):
        kind = "I"
        dimensions = {
            "width": _mm(profile.flange_width),
            "depth": _mm(profile.depth),
            "web": _mm(profile.web_thickness),
            "flange": _mm(profile.flange_thickness),
            "fillet": _mm(profile.root_radius),
        }
    elif isinstance(profile, HollowProfile) and profile.breadth is not None:
        wall = _mm(profile.wall_thickness)
        kind = "rectangle_hollow"
        # AISC's rolled HSS corner: an outside radius of twice the design wall, the rule
        # the section's own properties are computed on.
        dimensions = {
            "width": _mm(profile.breadth),
            "depth": _mm(profile.depth),
            "wall": wall,
            "inner_fillet": wall,
            "outer_fillet": 2 * wall,
        }
    elif isinstance(profile, HollowProfile):
        kind = "circle_hollow"
        dimensions = {"diameter": _mm(profile.depth), "wall": _mm(profile.wall_thickness)}
    else:
        return None
    return _framed(named, kind, dimensions, built)


def _framed(
    named: str,
    kind: Literal["I", "rectangle_hollow", "circle_hollow"],
    dimensions: dict[str, float],
    built: Any,
) -> IfcSweptProfile:
    """The profile placed as the built member is: along its length, width across its width."""
    box = built.shape.bounding_box()
    low, high = (box.min.X, box.min.Y, box.min.Z), (box.max.X, box.max.Y, box.max.Z)
    extent = [b - a for a, b in zip(low, high, strict=True)]
    length = float(built.dimensions_mm.get("length", max(extent)))
    width = dimensions.get("width", dimensions.get("diameter", 0.0))
    depth = dimensions.get("depth", dimensions.get("diameter", 0.0))

    def misfit(along: int, side: int) -> float:
        # Every extent has to agree, not only the length: a stub as long as its flange is
        # wide would otherwise be swept across the flange.
        (other,) = {0, 1, 2} - {along, side}
        return abs(extent[along] - length) + abs(extent[side] - width) + abs(extent[other] - depth)

    area = built.dimensions_mm.get("section_area")

    def end_misfit(along: int) -> float:
        # A box can fit two ways (a stub as long as its flange is wide), and only the true
        # axis has an end face as big as the section.
        if area is None:
            return 0.0
        end = 0.0
        for face in built.shape.faces():
            centre = face.center()
            normal = tuple(face.normal_at(centre))
            if (
                abs(abs(normal[along]) - 1.0) < 1e-6
                and abs(tuple(centre)[along] - low[along]) < 1e-6
            ):
                end += face.area
        return abs(end - area)

    along, side = min(
        ((a, b) for a in range(3) for b in range(3) if a != b),
        key=lambda pair: (round(misfit(*pair), 6), end_misfit(pair[0])),
    )
    unit = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    start = [(a + b) / 2 for a, b in zip(low, high, strict=True)]
    start[along] = low[along]
    return IfcSweptProfile(
        kind=kind,
        designation=named,
        dimensions=dimensions,
        length=length,
        axis=unit[along],
        across=unit[side],
        start=(start[0], start[1], start[2]),
    )


def combination_ifc_parts(built: Any) -> list[IfcPart]:
    """A built combination's parts and hardware, each where its mates put it.

    Each part is exported as :func:`ifc_part` makes it, in its own frame, with the
    rotation and shift the combination solved for it as its placement. Each fastener is an
    ``IfcMechanicalFastener`` from its tabulated envelope, placed the same way and tagged by
    the mate it sits in (its designation is its part number). Each part carries its own
    card's digest and status. Pass the result to :func:`render_ifc` with ``assembly=`` the
    combination's name; the export gate is the combination's card.
    """
    from ..geometry import BuiltGeometry, _mesh_for_3mf
    from ..screening import screen_spec

    parts = []
    for placed in built.parts:
        # Each part's own card: the combination's verdict covers the assembly, and an
        # element's property set says what was found on that element.
        card = screen_spec(placed.spec)
        part = ifc_part(placed.spec, placed.built, card, tag=placed.id, part_number=placed.id)
        rows = tuple(tuple(row) for row in placed.rotation)
        parts.append(
            _replace(
                part,
                placement=(rows, tuple(placed.translation)),
                extra={"CardStatus": card.status.value, "Assembly": built.name},
            )
        )
    counts: dict[str, int] = {}
    for body in built.hardware:
        counts[body.mate] = counts.get(body.mate, 0) + 1
        tag = f"{body.mate}:{body.kind}:{counts[body.mate]}"
        envelope = BuiltGeometry(
            name=tag, pattern="hardware", shape=body.solid, faces={}, dimensions_mm={},
            envelope=True,
        )  # fmt: skip
        vertices, triangles = _mesh_for_3mf(envelope)
        rows = tuple(tuple(row) for row in body.rotation)
        parts.append(
            IfcPart(
                tag=tag,
                name=body.designation,
                element_type=body.kind,
                vertices=vertices,
                triangles=triangles,
                part_number=body.designation,
                placement=(rows, tuple(body.translation)),
                extra={"Envelope": "the tabulated envelope, not the threaded form"},
            )
        )
    return parts
