"""A project folder as context: what is in it, and measured facts from the CAD files in it.

The common setup is an engineer pointing their agent at a folder: last year's STEP models,
DXF profiles, a datasheet, a photo of a sketch. The agent is good at reading the prose and
the pictures, and it cannot read a CAD file: a STEP file is thousands of lines of
coordinates, and an agent that "reads" one is guessing. This module is the other half. It
says which files are whose to read, and it measures the ones a kernel can measure.

**What comes back is facts, never the file.** A read returns sizes, volumes, holes and
profiles with the file's name and SHA-256, so a value taken from it can cite it. No
geometry data is returned and nothing is written.

**Units are stated twice.** Every length is reported in millimetres, and the result says
which unit the file was written in. A DXF that declares no unit is refused until the caller
states one, because a drawing in inches read as millimetres is wrong by a factor nobody
sees. An STL has no unit at all, and says so.

**Reading is confined.** The MCP server reads only inside the folders it was started with
(``anvilate-mcp --context DIR``), resolves links before it checks, and treats the folders as
read-only. Formats that need a proprietary converter (DWG, IGES, Parasolid, native CAD) are
refused by name with the one step that fixes it: export STEP or DXF from the CAD tool.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from ._models import FrozenMap, Named, Provenance, StatableModel
from .refusal import RefusalError, Remedy

__all__ = [
    "CadFacts",
    "ContextError",
    "ContextFile",
    "ContextInventory",
    "CylinderFacts",
    "DimensionFacts",
    "HolePatternFacts",
    "PartSeed",
    "PlaneFacts",
    "ProfileFacts",
    "ProfileHole",
    "ReadingComparison",
    "ReadingReport",
    "SolidFacts",
    "compare_readings",
    "context_roots",
    "inventory",
    "read_cad_file",
    "resolve_in_context",
    "seed_part",
    "set_context_roots",
]

#: The largest file a reader opens, by kind. A read is one tool call with a time limit, and a
#: file past these is refused with its size rather than started and abandoned.
MAX_BYTES = {"step": 64 * 1024 * 1024, "dxf": 32 * 1024 * 1024, "mesh": 128 * 1024 * 1024}

#: How many of each thing one result lists before it counts the rest.
LISTED = 60

_INVENTORY_FILES = 200
_INVENTORY_DEPTH = 4

_STEP_SUFFIXES = (".step", ".stp")
_READ = {
    ".step": ("step", "STEP solid model"),
    ".stp": ("step", "STEP solid model"),
    ".dxf": ("dxf", "DXF drawing"),
    ".stl": ("mesh", "STL triangle mesh"),
    ".3mf": ("mesh", "3MF triangle mesh"),
}
_AGENT = {
    ".pdf": "PDF document",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".svg": "vector image",
    ".md": "text",
    ".txt": "text",
    ".rtf": "text",
    ".docx": "document",
    ".csv": "table",
    ".xlsx": "spreadsheet",
}
_STEP_FIX = "export STEP (AP214 or AP242) from the CAD tool that wrote it"
_UNSUPPORTED = {
    ".dwg": ("AutoCAD DWG drawing", "export DXF from the CAD tool that wrote it"),
    ".igs": ("IGES model", _STEP_FIX),
    ".iges": ("IGES model", _STEP_FIX),
    ".x_t": ("Parasolid model", _STEP_FIX),
    ".x_b": ("Parasolid model", _STEP_FIX),
    ".sat": ("ACIS model", _STEP_FIX),
    ".sldprt": ("SolidWorks part", _STEP_FIX),
    ".sldasm": ("SolidWorks assembly", _STEP_FIX),
    ".ipt": ("Inventor part", _STEP_FIX),
    ".iam": ("Inventor assembly", _STEP_FIX),
    ".f3d": ("Fusion design", _STEP_FIX),
    ".catpart": ("CATIA part", _STEP_FIX),
    ".catproduct": ("CATIA assembly", _STEP_FIX),
    ".prt": ("NX or Creo part", _STEP_FIX),
    ".asm": ("Creo or Solid Edge assembly", _STEP_FIX),
    ".par": ("Solid Edge part", _STEP_FIX),
    ".fcstd": ("FreeCAD document", _STEP_FIX),
    ".3dm": ("Rhino model", _STEP_FIX),
    ".jt": ("JT model", _STEP_FIX),
}

_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
_DXF_UNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
_UNIT_NAMES = {
    "mm": "millimetres",
    "cm": "centimetres",
    "m": "metres",
    "in": "inches",
    "ft": "feet",
}
Point3 = tuple[float, float, float]


class ContextError(RefusalError, ValueError):
    """A file or folder that cannot be read as asked, with what would let it be."""


def _refuse(message: str, *, action: str, subject: str, source: str) -> ContextError:
    return ContextError(message, remedies=(Remedy(action=action, subject=subject, source=source),))


_ROOTS: tuple[Path, ...] | None = None


def set_context_roots(paths: Iterable[str | Path] | None) -> None:
    """Name the folders the server may read; ``None`` leaves it to ``ANVILATE_CONTEXT``."""
    global _ROOTS
    _ROOTS = None if paths is None else tuple(Path(path).expanduser().resolve() for path in paths)


def context_roots() -> tuple[Path, ...]:
    """The folders the server may read, from ``set_context_roots`` or ``ANVILATE_CONTEXT``."""
    if _ROOTS is not None:
        return _ROOTS
    configured = os.environ.get("ANVILATE_CONTEXT", "")
    return tuple(
        Path(entry).expanduser().resolve() for entry in configured.split(os.pathsep) if entry
    )


def resolve_in_context(path: str | Path) -> Path:
    """``path`` as a real path inside a context folder, or a refusal naming the folders.

    A relative path is looked for under each folder in turn. Links are resolved before the
    check, so a link inside a folder that points outside it is outside.
    """
    roots = context_roots()
    if not roots:
        raise _refuse(
            "this server was started without a context folder, so it reads no files. Start "
            "it as `anvilate-mcp --context DIR` with the project folder to read",
            action="set",
            subject="--context",
            source="the folder of drawings and models the user wants read, named at launch",
        )
    asked = Path(path).expanduser()
    candidates = [asked] if asked.is_absolute() else [root / asked for root in roots]
    for candidate in candidates:
        try:
            real = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if any(real == root or root in real.parents for root in roots):
            return real
    raise _refuse(
        f"{str(path)!r} is not a file inside a context folder; this server reads only "
        f"inside {', '.join(str(root) for root in roots)}",
        action="replace",
        subject="path",
        source="a path inside one of the context folders the server was started with",
    )


class ContextFile(StatableModel):
    """One file in a context folder: what it is, and whose it is to read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Provenance
    format: Named
    bytes: int = Field(ge=0)
    # `anvilate`: read_cad_file measures it. `agent`: prose or a picture, which the agent
    # reads itself. `unsupported`: a format that needs converting first; `note` says how.
    reader: Literal["anvilate", "agent", "unsupported"]
    note: str | None = Field(default=None, exclude_if=lambda value: value is None)


class ContextInventory(StatableModel):
    """A context folder's engineering files, bounded, with what was left out counted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    folder: Provenance
    files: tuple[ContextFile, ...]
    # Files past the listing limit or deeper than it descends, and files of no known
    # engineering format. Counted, so a short listing is not read as a complete one.
    not_listed: int = Field(default=0, ge=0)
    other_files: int = Field(default=0, ge=0)

    def __str__(self) -> str:
        lines = [f"{self.folder}: {len(self.files)} engineering files"]
        for file in self.files:
            note = f" ({file.note})" if file.note else ""
            lines.append(f"  {file.reader:<11} {file.format:<22} {file.path}{note}")
        if self.not_listed:
            lines.append(f"  and {self.not_listed} more past the listing limit")
        if self.other_files:
            lines.append(f"  {self.other_files} files of other kinds are not listed")
        return "\n".join(lines)


def inventory(folder: str | Path) -> ContextInventory:
    """List a folder's engineering files and whose each is to read.

    Nothing is opened: a file is classified by its name. The listing stops at
    200 files and four folders deep, and counts what it left out.
    """
    root = Path(folder)
    if not root.is_dir():
        raise _refuse(
            f"{str(folder)!r} is not a folder",
            action="replace",
            subject="folder",
            source="a folder inside the context the server was started with",
        )
    files: list[ContextFile] = []
    not_listed = other = 0
    for current, directories, names in os.walk(root):
        directories[:] = sorted(name for name in directories if not name.startswith("."))
        depth = len(Path(current).relative_to(root).parts)
        if depth >= _INVENTORY_DEPTH:
            not_listed += sum(len(found) for _dir, _dirs, found in os.walk(current))
            directories[:] = []
            continue
        for name in sorted(names):
            if name.startswith("."):
                continue
            path = Path(current) / name
            suffix = path.suffix.lower()
            if suffix in _READ:
                reader, fmt, note = "anvilate", _READ[suffix][1], None
            elif suffix in _AGENT:
                reader, fmt, note = "agent", _AGENT[suffix], None
            elif suffix in _UNSUPPORTED:
                reader, (fmt, note) = "unsupported", _UNSUPPORTED[suffix]
            else:
                other += 1
                continue
            if len(files) >= _INVENTORY_FILES:
                not_listed += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files.append(
                ContextFile(
                    path=path.relative_to(root).as_posix(),
                    format=fmt,
                    bytes=size,
                    reader=reader,  # type: ignore[arg-type]
                    note=note,
                )
            )
    return ContextInventory(
        folder=str(root), files=tuple(files), not_listed=not_listed, other_files=other
    )


class PlaneFacts(StatableModel):
    """One planar face: its area and the way it faces."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    area_mm2: float = Field(gt=0)
    normal: tuple[float, float, float]


class CylinderFacts(StatableModel):
    """One round feature: every cylindrical face about one axis at one radius, as one feature.

    A hole modelled as two half-cylinders is one hole. A ``hole`` or a ``boss`` goes all
    the way round its axis. A ``fillet`` (concave) or a ``round`` (convex) covers part of
    the turn: a plate's rounded corner, the end of a slot, an inside corner radius.
    ``position_mm`` is the middle of the feature on its axis, and ``depth_mm`` its extent
    along it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["hole", "boss", "fillet", "round"]
    diameter_mm: float = Field(gt=0)
    depth_mm: float = Field(ge=0)
    axis: tuple[float, float, float]
    position_mm: tuple[float, float, float]


class HolePatternFacts(StatableModel):
    """Several equal holes on parallel axes: how many, how far apart, and their circle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int = Field(ge=2)
    diameter_mm: float = Field(gt=0)
    axis: tuple[float, float, float]
    # The smallest distance between two of the holes' axes.
    pitch_mm: float = Field(gt=0)
    # Present when three or more of the holes lie on one circle.
    bolt_circle_diameter_mm: float | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SolidFacts(StatableModel):
    """One solid of a STEP file, measured."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    size_mm: tuple[float, float, float]
    volume_mm3: float = Field(gt=0)
    # The file's product name, where it has one solid and one product and so says which is
    # which; and the solid's mass, where the call named the material it is made of.
    name: str | None = Field(default=None, exclude_if=lambda value: value is None)
    mass_kg: float | None = Field(default=None, exclude_if=lambda value: value is None)
    faces: int = Field(ge=1)
    planes: tuple[PlaneFacts, ...] = ()
    cylinders: tuple[CylinderFacts, ...] = ()
    hole_patterns: tuple[HolePatternFacts, ...] = ()
    # Faces that are neither planes nor cylinders (cones, fillets, free-form surfaces),
    # and listed kinds past the listing limit. Counted, never dropped.
    unclassified_faces: int = Field(default=0, ge=0)
    planes_not_listed: int = Field(default=0, ge=0)
    cylinders_not_listed: int = Field(default=0, ge=0)


class ProfileHole(StatableModel):
    """A closed profile inside another: a circle by its diameter, anything else by its box."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["circle", "profile"]
    # From the centre of the profile it is in.
    x_mm: float
    y_mm: float
    diameter_mm: float | None = Field(default=None, exclude_if=lambda value: value is None)
    width_mm: float | None = Field(default=None, exclude_if=lambda value: value is None)
    height_mm: float | None = Field(default=None, exclude_if=lambda value: value is None)


class ProfileFacts(StatableModel):
    """One outer closed profile of a drawing, with the closed profiles inside it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: Provenance
    kind: Literal["circle", "rectangle", "profile"]
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    # The area the outline encloses, before its holes are taken out.
    area_mm2: float = Field(gt=0)
    holes: tuple[ProfileHole, ...] = ()
    holes_not_listed: int = Field(default=0, ge=0)


class DimensionFacts(StatableModel):
    """One dimension entity: what its geometry measures, and what its text says instead."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: Provenance
    measured_mm: float
    # The text typed over the measurement, when there is any.
    override: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # True when the override is a number and it is not the measurement.
    disagrees: bool = Field(default=False, exclude_if=lambda value: not value)


class CadFacts(StatableModel):
    """What one CAD file holds, measured. Lengths are millimetres unless the file had no unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Provenance
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)
    kind: Literal["step", "dxf", "mesh"]
    # The unit the file was written in, or None when it states none. Values are reported in
    # `unit_reported`: millimetres, or the file's own unstated unit for a mesh with none.
    unit_written: str | None
    unit_reported: Literal["mm", "file units"]
    size_mm: tuple[float, float, float]
    volume_mm3: float | None = Field(default=None, exclude_if=lambda value: value is None)
    # The material the call named for a STEP file, its density from the bundled materials
    # database, and the mass of every solid at that density. A file never states these.
    material: str | None = Field(default=None, exclude_if=lambda value: value is None)
    density_kg_m3: float | None = Field(default=None, exclude_if=lambda value: value is None)
    mass_kg: float | None = Field(default=None, exclude_if=lambda value: value is None)
    notes: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)
    # A STEP file.
    products: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)
    solids: tuple[SolidFacts, ...] = Field(default=(), exclude_if=lambda value: not value)
    solids_not_listed: int = Field(default=0, exclude_if=lambda value: not value)
    # A DXF drawing.
    layers: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)
    profiles: tuple[ProfileFacts, ...] = Field(default=(), exclude_if=lambda value: not value)
    profiles_not_listed: int = Field(default=0, exclude_if=lambda value: not value)
    dimensions: tuple[DimensionFacts, ...] = Field(default=(), exclude_if=lambda value: not value)
    open_entities: int = Field(default=0, exclude_if=lambda value: not value)
    # A mesh.
    triangles: int | None = Field(default=None, exclude_if=lambda value: value is None)
    closed: bool | None = Field(default=None, exclude_if=lambda value: value is None)

    def __str__(self) -> str:
        unit = "mm" if self.unit_reported == "mm" else "file units"
        written = _UNIT_NAMES.get(self.unit_written or "", "no stated unit")
        size = " x ".join(f"{value:g}" for value in self.size_mm if value or self.kind != "dxf")
        lines = [
            f"{self.file}: {self.kind}, written in {written}, {size} {unit}",
            f"  sha256 {self.sha256}",
        ]
        if self.volume_mm3 is not None:
            lines.append(f"  volume {self.volume_mm3:g} {unit}^3")
        if self.mass_kg is not None:
            lines.append(
                f"  mass {self.mass_kg:.4g} kg as {self.material}, at {self.density_kg_m3:g} kg/m^3"
            )
        if self.products:
            lines.append(f"  products: {', '.join(self.products)}")
        for number, solid in enumerate(self.solids, start=1):
            box = " x ".join(f"{value:g}" for value in solid.size_mm)
            named = f" ({solid.name})" if solid.name is not None else ""
            mass = f", {solid.mass_kg:.4g} kg" if solid.mass_kg is not None else ""
            lines.append(
                f"  solid {number}{named}: {box} mm, {solid.volume_mm3:g} mm^3{mass}, "
                f"{solid.faces} faces, {solid.unclassified_faces} unclassified"
            )
            for cylinder in solid.cylinders:
                at = ", ".join(f"{value:g}" for value in cylinder.position_mm)
                lines.append(
                    f"    {cylinder.kind} dia {cylinder.diameter_mm:g} x "
                    f"{cylinder.depth_mm:g} at ({at})"
                )
            for pattern in solid.hole_patterns:
                circle = (
                    f", on a {pattern.bolt_circle_diameter_mm:g} mm circle"
                    if pattern.bolt_circle_diameter_mm is not None
                    else ""
                )
                lines.append(
                    f"    {pattern.count} holes dia {pattern.diameter_mm:g}, nearest "
                    f"{pattern.pitch_mm:g} apart{circle}"
                )
        if self.solids_not_listed:
            lines.append(f"  and {self.solids_not_listed} more solids")
        for profile in self.profiles:
            lines.append(
                f"  {profile.kind} {profile.width_mm:g} x {profile.height_mm:g} mm on layer "
                f"{profile.layer}, {len(profile.holes) + profile.holes_not_listed} inside"
            )
            for hole in profile.holes:
                what = (
                    f"circle dia {hole.diameter_mm:g}"
                    if hole.diameter_mm is not None
                    else f"profile {hole.width_mm:g} x {hole.height_mm:g}"
                )
                lines.append(f"    {what} at ({hole.x_mm:g}, {hole.y_mm:g}) from its centre")
        for dimension in self.dimensions:
            said = f', text "{dimension.override}"' if dimension.override else ""
            flag = " — DISAGREES with what it measures" if dimension.disagrees else ""
            lines.append(f"  dimension {dimension.measured_mm:g} mm{said}{flag}")
        if self.open_entities:
            lines.append(f"  {self.open_entities} entities are not part of a closed profile")
        if self.triangles is not None:
            state = "closed" if self.closed else "not closed"
            lines.append(f"  {self.triangles:,} triangles, {state}")
        lines += [f"  note: {note}" for note in self.notes]
        return "\n".join(lines)


def _digest(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _rounded(values: Iterable[float], places: int = 6) -> tuple[float, ...]:
    return tuple(
        0.0 if abs(value) < 10**-places else round(float(value), places) for value in values
    )


def _kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _READ:
        return _READ[suffix][0]
    if suffix in _UNSUPPORTED:
        fmt, fix = _UNSUPPORTED[suffix]
        raise _refuse(
            f"{path.name} ({fmt}) is a format Anvilate does not read and does not convert: {fix}",
            action="replace",
            subject="path",
            source=f"a STEP or DXF file: {fix}",
        )
    if suffix in _AGENT:
        raise _refuse(
            f"{path.name} ({_AGENT[suffix]}) is the agent's to read, not Anvilate's. A value "
            "read from it enters a spec as agent-read, naming this file",
            action="replace",
            subject="path",
            source="a STEP, DXF, STL or 3MF file",
        )
    raise _refuse(
        f"{path.name} is not a format Anvilate reads; it reads STEP, DXF, STL and 3MF",
        action="replace",
        subject="path",
        source="a STEP, DXF, STL or 3MF file",
    )


def read_cad_file(
    path: str | Path, *, unit: str | None = None, material: str | None = None
) -> CadFacts:
    """Measure one STEP, DXF, STL or 3MF file and return what it holds.

    ``unit`` states the drawing unit of a DXF that declares none (``mm``, ``cm``, ``m``,
    ``in`` or ``ft``), and the unit of an STL, which never has one. It is refused for a
    file that states its own and disagrees.

    ``material`` names what a STEP file's solids are made of, by its id in the bundled
    materials database. Each solid's mass is then its volume at that material's density.
    A STEP file carries no material this reader trusts, so none is ever assumed.
    """
    source = Path(path)
    if not source.is_file():
        raise _refuse(
            f"{str(path)!r} is not a file",
            action="replace",
            subject="path",
            source="a STEP, DXF, STL or 3MF file",
        )
    kind = _kind_of(source)
    if unit is not None and unit not in _TO_MM:
        raise _refuse(
            f"unit {unit!r} is not one of {', '.join(_TO_MM)}",
            action="replace",
            subject="unit",
            source="the drawing's unit: mm, cm, m, in or ft",
        )
    size = source.stat().st_size
    if size > MAX_BYTES[kind]:
        raise _refuse(
            f"{source.name} is {size / 1e6:.0f} MB, past the {MAX_BYTES[kind] / 1e6:.0f} MB "
            f"a {kind} read accepts in one call",
            action="replace",
            subject="path",
            source="a smaller export: one part or one sheet rather than the whole project",
        )
    density = _density(material, kind)
    sha256, counted = _digest(source)
    common = {"file": source.name, "sha256": sha256, "bytes": counted, "kind": kind}
    if kind == "step":
        return CadFacts(**common, **_step_facts(source, unit, material, density))
    if kind == "dxf":
        return CadFacts(**common, **_dxf_facts(source, unit))
    return CadFacts(**common, **_mesh_facts(source, unit))


def _density(material: str | None, kind: str) -> float | None:
    """The named material's density in kg/m^3, refused for a file with no solid to weigh."""
    if material is None:
        return None
    if kind != "step":
        raise _refuse(
            f"material gives a STEP file's solids a mass, and this is a {kind} file",
            action="remove",
            subject="material",
            source="a STEP file of the solid, whose volume the mass is worked from",
        )
    from .standards.materials import default_materials_db

    materials = default_materials_db()
    if not materials.has_material(material):
        raise _refuse(
            f"no bundled material has the id {material!r}; the ids are "
            f"{', '.join(materials.known_materials())}",
            action="select",
            subject="material",
            source="an id in the bundled materials database",
        )
    return float(materials.get(material).density.quantity.to("kg/m**3").magnitude)


# --- STEP ------------------------------------------------------------------------------


def _step_unit(text: str) -> str | None:
    """The length unit a STEP file declares, read from its unit entities."""
    upper = text.upper()
    for marker, unit in (
        ("CONVERSION_BASED_UNIT('INCH'", "in"),
        ("CONVERSION_BASED_UNIT('FOOT'", "ft"),
        ("SI_UNIT(.MILLI.,.METRE.)", "mm"),
        ("SI_UNIT(.CENTI.,.METRE.)", "cm"),
        ("SI_UNIT($,.METRE.)", "m"),
    ):
        if marker in upper.replace(" ", ""):
            return unit
    return None


def _step_products(text: str) -> tuple[str, ...]:
    import re

    names = re.findall(r"PRODUCT\s*\(\s*'((?:[^']|'')*)'", text)
    seen = dict.fromkeys(name.replace("''", "'") for name in names if name)
    return tuple(list(seen)[:LISTED])


def _step_facts(
    path: Path, unit: str | None, material: str | None = None, density: float | None = None
) -> dict[str, Any]:
    from . import geometry

    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as failure:
        raise _refuse(
            f"could not read {path.name}: {failure}",
            action="replace",
            subject="path",
            source="a readable STEP file",
        ) from failure
    written = _step_unit(text)
    if unit is not None and written is not None and unit != written:
        raise _refuse(
            f"{path.name} declares its unit as {written}, and the call states {unit}",
            action="remove",
            subject="unit",
            source="the unit the STEP file itself declares",
        )
    try:
        compound = geometry._read_step_geometry(path)
    except ImportError as failure:
        raise _refuse(
            "reading STEP needs the geometry kernel; install anvilate[geometry]",
            action="install",
            subject="path",
            source="the anvilate[geometry] optional dependency",
        ) from failure
    except geometry.GeometryError as failure:
        raise _refuse(
            str(failure), action="replace", subject="path", source="a STEP file"
        ) from failure
    solids = list(compound.solids())
    if not solids:
        raise _refuse(
            f"{path.name} holds no solid: it has {len(compound.faces())} faces and "
            f"{len(compound.edges())} edges, which is a surface or wireframe model",
            action="replace",
            subject="path",
            source="a STEP export of the solid body, not of its surfaces or sketches",
        )
    box = compound.bounding_box()
    notes = []
    if written is None:
        notes.append(
            "the file declares no length unit this reader recognises; values are as the "
            "kernel read them"
        )
    elif written != "mm":
        notes.append(
            f"the file was written in {_UNIT_NAMES[written]}; every value here is converted to mm"
        )
    if len(solids) > 1:
        notes.append(
            f"{len(solids)} solids: an assembly or a multi-body part, each measured separately"
        )
    products = _step_products(text)
    volume = sum(float(solid.volume) for solid in solids)
    listed = [_solid_facts(solid) for solid in solids[:LISTED]]
    # One solid and one product name each other. With more of either, which name belongs to
    # which solid is the assembly structure's to say, and this reader does not read it.
    if len(solids) == 1 and len(products) == 1:
        listed[0] = listed[0].model_copy(update={"name": products[0]})
    weighed: dict[str, Any] = {}
    if density is not None:
        # mm^3 to m^3 is 1e-9. Each solid is weighed from its unrounded volume.
        listed = [
            facts.model_copy(update={"mass_kg": float(solid.volume) * 1e-9 * density})
            for facts, solid in zip(listed, solids, strict=False)
        ]
        weighed = {
            "material": material,
            "density_kg_m3": density,
            "mass_kg": volume * 1e-9 * density,
        }
        notes.append(
            f"mass is each solid's volume at the density of {material} in the bundled "
            "materials database; the file states no material, and every solid is taken "
            "to be that one"
        )
    return {
        "unit_written": written,
        "unit_reported": "mm",
        "size_mm": _rounded((box.size.X, box.size.Y, box.size.Z)),
        "volume_mm3": round(volume, 6),
        **weighed,
        "notes": tuple(notes),
        "products": products,
        "solids": tuple(listed),
        "solids_not_listed": max(0, len(solids) - LISTED),
    }


def _solid_facts(solid: Any) -> SolidFacts:
    from . import geometry

    faces = list(solid.faces())
    box = solid.bounding_box()
    planes, groups, unclassified = [], defaultdict(list), 0
    for face in faces:
        kind = face.geom_type.name
        if kind == "PLANE":
            planes.append(
                PlaneFacts(
                    area_mm2=round(float(face.area), 6),
                    normal=_rounded(geometry._coordinates(face.normal_at())),
                )
            )
        elif kind == "CYLINDER" and face.axis_of_rotation is not None and face.radius:
            axis = face.axis_of_rotation
            direction = geometry._coordinates(axis.direction)
            origin, unit = geometry._canonical_axis(geometry._coordinates(axis.position), direction)
            centre = geometry._coordinates(face.center())
            along = geometry._dot(geometry._subtract(centre, origin), unit)
            radial = geometry._subtract(centre, geometry._point_along(origin, unit, along))
            inward = geometry._dot(radial, geometry._coordinates(face.normal_at())) < 0
            groups[(inward, round(float(face.radius), 5), origin, unit)].append(face)
        else:
            unclassified += 1
    cylinders = []
    for (inward, radius, origin, unit), members in groups.items():
        spans = [
            geometry._dot(geometry._coordinates(vertex), unit)
            for face in members
            for vertex in face.vertices()
        ]
        start, end = min(spans), max(spans)
        middle = geometry._point_along(origin, unit, (start + end) / 2)
        # The share of a full turn these faces cover: their area over the whole wall's.
        wall = 2 * math.pi * radius * (end - start)
        whole = wall > 0 and sum(float(face.area) for face in members) >= 0.999 * wall
        kind = ("hole" if inward else "boss") if whole else ("fillet" if inward else "round")
        cylinders.append(
            CylinderFacts(
                kind=kind,  # type: ignore[arg-type]
                diameter_mm=round(2 * radius, 5),
                depth_mm=round(end - start, 6),
                axis=_rounded(unit),
                position_mm=_rounded(middle),
            )
        )
    cylinders.sort(key=lambda c: (c.kind, c.diameter_mm, c.position_mm))
    planes.sort(key=lambda plane: (-plane.area_mm2, plane.normal))
    return SolidFacts(
        size_mm=_rounded((box.size.X, box.size.Y, box.size.Z)),
        volume_mm3=round(float(solid.volume), 6),
        faces=len(faces),
        planes=tuple(planes[:LISTED]),
        cylinders=tuple(cylinders[:LISTED]),
        hole_patterns=_hole_patterns(cylinders),
        unclassified_faces=unclassified,
        planes_not_listed=max(0, len(planes) - LISTED),
        cylinders_not_listed=max(0, len(cylinders) - LISTED),
    )


def _hole_patterns(cylinders: Sequence[CylinderFacts]) -> tuple[HolePatternFacts, ...]:
    """Equal holes on parallel axes, grouped: their count, nearest pitch and common circle."""
    grouped: dict[tuple[float, Point3], list[CylinderFacts]] = defaultdict(list)
    for cylinder in cylinders:
        if cylinder.kind == "hole":
            grouped[(cylinder.diameter_mm, cylinder.axis)].append(cylinder)
    patterns = []
    for (diameter, axis), holes in sorted(grouped.items()):
        if len(holes) < 2:
            continue
        # The holes' positions in the plane square to their axis.
        flat = [_drop_axis(hole.position_mm, axis) for hole in holes]
        pitch = min(
            math.dist(first, second)
            for index, first in enumerate(flat)
            for second in flat[index + 1 :]
        )
        if pitch <= 1e-6:
            continue
        patterns.append(
            HolePatternFacts(
                count=len(holes),
                diameter_mm=diameter,
                axis=axis,
                pitch_mm=round(pitch, 6),
                bolt_circle_diameter_mm=_common_circle(flat),
            )
        )
    return tuple(patterns[:LISTED])


def _drop_axis(point: Point3, axis: Point3) -> tuple[float, float]:
    """``point`` in two coordinates square to ``axis``."""
    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit(_cross(axis, helper))
    v = _cross(axis, u)
    return (
        sum(a * b for a, b in zip(point, u, strict=True)),
        sum(a * b for a, b in zip(point, v, strict=True)),
    )


def _cross(a: Point3, b: Point3) -> Point3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(vector: Point3) -> Point3:
    length = math.sqrt(sum(component**2 for component in vector)) or 1.0
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _common_circle(points: Sequence[tuple[float, float]]) -> float | None:
    """The diameter of the one circle three or more points lie on, or ``None``.

    The circle through the first three is found exactly, and every point is then held to
    it: holes on a grid lie on no common circle, and a square of four lies on one.
    """
    if len(points) < 3:
        return None
    (ax, ay), (bx, by), (cx, cy) = points[0], points[1], points[2]
    twice = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(twice) < 1e-9:
        return None
    ux = (
        (ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)
    ) / twice
    uy = (
        (ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)
    ) / twice
    radius = math.dist((ux, uy), points[0])
    if all(abs(math.dist((ux, uy), point) - radius) <= 1e-4 * max(1.0, radius) for point in points):
        return round(2 * radius, 5)
    return None


# --- DXF -------------------------------------------------------------------------------


def _dxf_facts(path: Path, unit: str | None) -> dict[str, Any]:
    try:
        import ezdxf
        from ezdxf import path as ezpath
    except ImportError as failure:
        raise _refuse(
            "reading DXF needs the optional dependency; install anvilate[export]",
            action="install",
            subject="path",
            source="the anvilate[export] optional dependency",
        ) from failure
    try:
        document = ezdxf.readfile(str(path))
    except (OSError, ezdxf.DXFError, ValueError) as failure:
        raise _refuse(
            f"{path.name} is not a DXF file this reader can open: {failure}",
            action="replace",
            subject="path",
            source="a DXF file saved from the CAD tool, R12 or later",
        ) from failure
    written = _DXF_UNITS.get(int(document.header.get("$INSUNITS", 0) or 0))
    if unit is None and written is None:
        raise _refuse(
            f"{path.name} declares no drawing unit, and a drawing in inches read as "
            "millimetres is wrong by 25.4; state the unit it was drawn in",
            action="declare",
            subject="unit",
            source="the drawing's unit: mm, cm, m, in or ft",
        )
    if unit is not None and written is not None and unit != written:
        raise _refuse(
            f"{path.name} declares its unit as {written}, and the call states {unit}",
            action="remove",
            subject="unit",
            source="the unit the DXF file itself declares",
        )
    scale = _TO_MM[unit or written]  # type: ignore[index]
    loops: list[tuple[str, str, list[tuple[float, float]], float | None]] = []
    strands: list[tuple[str, list[tuple[float, float]]]] = []
    dimensions: list[DimensionFacts] = []
    ignored = 0

    def take(entity: Any) -> None:
        nonlocal ignored
        kind, layer = entity.dxftype(), str(entity.dxf.get("layer", "0"))
        if kind == "CIRCLE":
            centre, radius = entity.dxf.center, float(entity.dxf.radius) * scale
            points = [
                (
                    centre.x * scale + radius * math.cos(2 * math.pi * step / 72),
                    centre.y * scale + radius * math.sin(2 * math.pi * step / 72),
                )
                for step in range(72)
            ]
            loops.append((layer, "circle", points, 2 * radius))
        elif kind == "INSERT":
            for inner in entity.virtual_entities():
                take(inner)
        elif kind == "DIMENSION":
            dimensions.append(_dimension(entity, layer, scale))
        elif kind == "LINE":
            start, end = entity.dxf.start, entity.dxf.end
            strands.append(
                (layer, [(start.x * scale, start.y * scale), (end.x * scale, end.y * scale)])
            )
        elif kind == "ARC":
            strands.append((layer, _arc_points(entity, scale)))
        elif kind in {"LWPOLYLINE", "POLYLINE"}:
            # Exploded into its lines and arcs, so a bulge is measured as the arc it is.
            try:
                pieces = list(entity.virtual_entities())
            except (TypeError, ValueError, AttributeError):
                ignored += 1
                return
            for piece in pieces:
                take(piece)
        elif kind in {"SPLINE", "ELLIPSE"}:
            try:
                outline = ezpath.make_path(entity)
            except (TypeError, ValueError):
                ignored += 1
                return
            points = [(v.x * scale, v.y * scale) for v in outline.flattening(0.001 / scale)]
            if len(points) < 2:
                ignored += 1
            elif outline.is_closed or math.dist(points[0], points[-1]) <= 1e-6:
                loops.append((layer, "profile", points, None))
            else:
                strands.append((layer, points))
        else:
            ignored += 1

    for entity in document.modelspace():
        take(entity)
    chained, loose = _chain(strands)
    loops += chained
    profiles, profiles_not_listed = _profiles(loops)
    every = [point for _layer, _kind, points, _d in loops for point in points]
    if every:
        xs, ys = [p[0] for p in every], [p[1] for p in every]
        size = (max(xs) - min(xs), max(ys) - min(ys), 0.0)
    else:
        size = (0.0, 0.0, 0.0)
    notes = []
    if written is None:
        notes.append(
            f"the file declares no unit; read as {_UNIT_NAMES[unit or 'mm']} because the call "
            "says so"
        )
    elif written != "mm":
        notes.append(
            f"the file was drawn in {_UNIT_NAMES[written]}; every value here is converted to mm"
        )
    if any(dimension.disagrees for dimension in dimensions):
        notes.append(
            "a dimension's text does not match what it measures; a person settles which is right"
        )
    return {
        "unit_written": written,
        "unit_reported": "mm",
        "size_mm": _rounded(size),
        "notes": tuple(notes),
        "layers": tuple(sorted(layer.dxf.name for layer in document.layers))[:LISTED],
        "profiles": profiles,
        "profiles_not_listed": profiles_not_listed,
        "dimensions": tuple(dimensions[:LISTED]),
        "open_entities": loose + ignored,
    }


def _arc_points(entity: Any, scale: float) -> list[tuple[float, float]]:
    """An arc as points on it, close enough that no chord strays a micrometre from it.

    Sampled on the circle itself. The general path flattener draws an arc as Bezier
    curves, which bulge outside it by a few parts in ten thousand: enough to overstate
    the area of a round-ended outline.
    """
    centre, radius = entity.dxf.center, float(entity.dxf.radius) * scale
    start = math.radians(float(entity.dxf.start_angle))
    sweep = (math.radians(float(entity.dxf.end_angle)) - start) % (2 * math.pi) or 2 * math.pi
    step = 2 * math.acos(max(-1.0, 1 - 0.001 / radius)) if radius > 0.001 else sweep
    count = min(2000, max(2, math.ceil(sweep / step)))
    turned = [sweep * index / count for index in range(count + 1)]
    # And the arc's own extremes, exactly: where it is farthest left, right, up and down.
    # Without them a round end's box came out a micrometre short of the radius.
    quarter = math.pi / 2
    first = math.ceil(start / quarter)
    turned += [
        k * quarter - start for k in range(first, first + 5) if 0 < k * quarter - start < sweep
    ]
    return [
        (
            centre.x * scale + radius * math.cos(start + angle),
            centre.y * scale + radius * math.sin(start + angle),
        )
        for angle in sorted(turned)
    ]


def _dimension(entity: Any, layer: str, scale: float) -> DimensionFacts:
    try:
        measured = float(entity.get_measurement())
    except (TypeError, ValueError, AttributeError):
        measured = float(entity.dxf.get("actual_measurement", 0.0) or 0.0)
    measured *= scale
    text = str(entity.dxf.get("text", "") or "").strip()
    override = text if text and text != "<>" and "<>" not in text else None
    disagrees = False
    if override is not None:
        import re

        number = re.search(r"-?\d+(?:[.,]\d+)?", override)
        if number is not None:
            stated = float(number.group().replace(",", "."))
            # The override is in drawing units as typed; compare it both ways, so a
            # drawing in inches whose text says 2.5 is held to 63.5 mm.
            disagrees = not any(
                math.isclose(stated * factor, measured, rel_tol=1e-6, abs_tol=1e-6)
                for factor in (1.0, scale)
            )
    return DimensionFacts(
        layer=layer, measured_mm=round(measured, 6), override=override, disagrees=disagrees
    )


def _chain(
    strands: Sequence[tuple[str, list[tuple[float, float]]]],
) -> tuple[list[tuple[str, str, list[tuple[float, float]], float | None]], int]:
    """Join open lines and arcs that meet end to end into closed profiles.

    A plate outline drawn as four lines and four arcs is one profile. Ends are matched to
    a micrometre. What does not close is counted and returned as loose.
    """

    def key(point: tuple[float, float]) -> tuple[int, int]:
        return (round(point[0] * 1000), round(point[1] * 1000))

    remaining = list(strands)
    closed, loose = [], 0
    while remaining:
        layer, points = remaining.pop()
        points = list(points)
        grew = True
        while grew and key(points[0]) != key(points[-1]):
            grew = False
            for index, (_other_layer, other) in enumerate(remaining):
                if key(other[0]) == key(points[-1]):
                    points += other[1:]
                elif key(other[-1]) == key(points[-1]):
                    points += other[-2::-1]
                else:
                    continue
                del remaining[index]
                grew = True
                break
        if len(points) >= 3 and key(points[0]) == key(points[-1]):
            closed.append((layer, "profile", points, None))
        else:
            loose += 1
    return closed, loose


def _area(points: Sequence[tuple[float, float]]) -> float:
    return abs(
        sum(
            a[0] * b[1] - b[0] * a[1] for a, b in zip(points, [*points[1:], points[0]], strict=True)
        )
        / 2
    )


def _inside(point: tuple[float, float], polygon: Sequence[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(polygon, [*polygon[1:], polygon[0]], strict=True):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def _is_rectangle(points: Sequence[tuple[float, float]], width: float, height: float) -> bool:
    """Whether the outline is its own bounding box, to a micrometre of area."""
    return math.isclose(_area(points), width * height, rel_tol=1e-6, abs_tol=1e-6)


def _profiles(
    loops: Sequence[tuple[str, str, list[tuple[float, float]], float | None]],
) -> tuple[tuple[ProfileFacts, ...], int]:
    """The outer profiles, each with the closed profiles drawn directly inside it."""
    measured = []
    for layer, kind, points, diameter in loops:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        if width <= 0 or height <= 0:
            continue
        area = math.pi * diameter**2 / 4 if diameter else _area(points)
        centre = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2)
        measured.append((area, layer, kind, points, diameter, width, height, centre))
    measured.sort(key=lambda item: (-item[0], item[1], item[7]))
    outer: list[int] = []
    holes: dict[int, list[int]] = defaultdict(list)
    for index, item in enumerate(measured):
        parent = next((other for other in outer if _inside(item[7], measured[other][3])), None)
        if parent is None:
            outer.append(index)
        else:
            holes[parent].append(index)
    profiles = []
    for index in outer:
        area, layer, kind, points, diameter, width, height, centre = measured[index]
        inner = []
        for hole in holes[index]:
            _a, _layer, hole_kind, _points, hole_diameter, hole_width, hole_height, at = measured[
                hole
            ]
            inner.append(
                ProfileHole(
                    kind="circle" if hole_kind == "circle" else "profile",
                    x_mm=round(at[0] - centre[0], 6),
                    y_mm=round(at[1] - centre[1], 6),
                    diameter_mm=round(hole_diameter, 6) if hole_diameter else None,
                    width_mm=None if hole_diameter else round(hole_width, 6),
                    height_mm=None if hole_diameter else round(hole_height, 6),
                )
            )
        inner.sort(key=lambda hole: (hole.kind, hole.x_mm, hole.y_mm))
        shape = (
            "circle"
            if kind == "circle"
            else "rectangle"
            if _is_rectangle(points, width, height)
            else "profile"
        )
        profiles.append(
            ProfileFacts(
                layer=layer,
                kind=shape,  # type: ignore[arg-type]
                width_mm=round(width, 6),
                height_mm=round(height, 6),
                area_mm2=round(area, 6),
                holes=tuple(inner[:LISTED]),
                holes_not_listed=max(0, len(inner) - LISTED),
            )
        )
    return tuple(profiles[:LISTED]), max(0, len(profiles) - LISTED)


# --- meshes ----------------------------------------------------------------------------

_MAX_TRIANGLES = 2_000_000


def _mesh_facts(path: Path, unit: str | None) -> dict[str, Any]:
    if path.suffix.lower() == ".3mf":
        triangles, written = _read_3mf(path)
        if unit is not None and unit != written:
            raise _refuse(
                f"{path.name} declares its unit as {written}, and the call states {unit}",
                action="remove",
                subject="unit",
                source="the unit the 3MF file itself declares",
            )
        scale, reported = _TO_MM[written], "mm"
    else:
        triangles, written = _read_stl(path), None
        scale, reported = (_TO_MM[unit], "mm") if unit else (1.0, "file units")
    if not triangles:
        raise _refuse(
            f"{path.name} holds no triangles",
            action="replace",
            subject="path",
            source="a mesh export of the part",
        )
    low = [min(vertex[axis] for triangle in triangles for vertex in triangle) for axis in range(3)]
    high = [max(vertex[axis] for triangle in triangles for vertex in triangle) for axis in range(3)]
    edges: dict[tuple[Point3, Point3], int] = defaultdict(int)
    volume = 0.0
    for a, b, c in triangles:
        volume += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6
        for first, second in ((a, b), (b, c), (c, a)):
            edges[(first, second) if first <= second else (second, first)] += 1
    closed = all(count == 2 for count in edges.values())
    notes = ["a mesh: it has a size and a volume, and no faces, holes or design intent to read"]
    if written is None and unit is None:
        notes.append(
            "an STL states no unit; values are in the file's own units until the call states one"
        )
    if not closed:
        notes.append("the mesh is not closed, so it encloses no volume")
    return {
        "unit_written": written,
        "unit_reported": reported,
        "size_mm": _rounded((high[axis] - low[axis]) * scale for axis in range(3)),
        "volume_mm3": round(abs(volume) * scale**3, 6) if closed else None,
        "notes": tuple(notes),
        "triangles": len(triangles),
        "closed": closed,
    }


def _too_many(path: Path, count: int) -> ContextError:
    return _refuse(
        f"{path.name} holds {count:,} triangles, past the {_MAX_TRIANGLES:,} one read measures",
        action="replace",
        subject="path",
        source="a coarser mesh export, or the STEP file the mesh was made from",
    )


def _read_stl(path: Path) -> list[tuple[Point3, Point3, Point3]]:
    data = path.read_bytes()
    if len(data) >= 84:
        (count,) = struct.unpack_from("<I", data, 80)
        if len(data) == 84 + 50 * count:
            if count > _MAX_TRIANGLES:
                raise _too_many(path, count)
            triangles = []
            for index in range(count):
                values = struct.unpack_from("<9f", data, 84 + 50 * index + 12)
                triangles.append((values[0:3], values[3:6], values[6:9]))
            return _finite(path, triangles)
    vertices: list[Point3] = []
    for line in data.decode("ascii", errors="replace").splitlines():
        words = line.split()
        if len(words) == 4 and words[0] == "vertex":
            try:
                vertices.append((float(words[1]), float(words[2]), float(words[3])))
            except ValueError as failure:
                raise _refuse(
                    f"{path.name} is not a readable STL: a vertex is not three numbers",
                    action="replace",
                    subject="path",
                    source="a binary or ASCII STL export of the part",
                ) from failure
            if len(vertices) > 3 * _MAX_TRIANGLES:
                raise _too_many(path, len(vertices) // 3)
    if len(vertices) % 3:
        raise _refuse(
            f"{path.name} is not a readable STL: its vertices do not come in threes",
            action="replace",
            subject="path",
            source="a binary or ASCII STL export of the part",
        )
    return _finite(
        path,
        [tuple(vertices[i : i + 3]) for i in range(0, len(vertices), 3)],  # type: ignore[misc]
    )


def _finite(path: Path, triangles: list[Any]) -> list[tuple[Point3, Point3, Point3]]:
    for triangle in triangles:
        if not all(math.isfinite(value) for vertex in triangle for value in vertex):
            raise _refuse(
                f"{path.name} holds a vertex that is not a finite number",
                action="replace",
                subject="path",
                source="a mesh export with finite coordinates",
            )
    return triangles


def _read_3mf(path: Path) -> tuple[list[tuple[Point3, Point3, Point3]], str]:
    import zipfile
    from xml.etree import ElementTree

    bad = _refuse(
        f"{path.name} is not a readable 3MF package",
        action="replace",
        subject="path",
        source="a 3MF export of the part",
    )
    try:
        with zipfile.ZipFile(path) as package:
            models = [
                info for info in package.infolist() if info.filename.lower().endswith(".model")
            ]
            if not models:
                raise bad
            info = models[0]
            # The declared size is checked before anything is inflated: a package is small
            # on disk and can claim any size inside.
            if info.file_size > 4 * MAX_BYTES["mesh"]:
                raise _refuse(
                    f"{path.name} unpacks to {info.file_size / 1e6:.0f} MB, past what one "
                    "read accepts",
                    action="replace",
                    subject="path",
                    source="a coarser mesh export of the part",
                )
            data = package.read(info)
    except (zipfile.BadZipFile, OSError, KeyError) as failure:
        raise bad from failure
    if b"<!DOCTYPE" in data[:4096] or b"<!ENTITY" in data[:4096]:
        raise bad
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as failure:
        raise bad from failure
    unit = {"millimeter": "mm", "centimeter": "cm", "meter": "m", "inch": "in", "foot": "ft"}.get(
        root.get("unit", "millimeter")
    )
    if unit is None:
        raise _refuse(
            f"{path.name} states its unit as {root.get('unit')!r}, which this reader does "
            "not convert",
            action="replace",
            subject="path",
            source="a 3MF export in millimetres, centimetres, metres, inches or feet",
        )
    triangles: list[tuple[Point3, Point3, Point3]] = []
    for mesh in root.iter():
        if not mesh.tag.endswith("}mesh") and mesh.tag != "mesh":
            continue
        vertices = [
            (float(v.get("x", "nan")), float(v.get("y", "nan")), float(v.get("z", "nan")))
            for v in mesh.iter()
            if v.tag.endswith("vertex")
        ]
        for t in mesh.iter():
            if not t.tag.endswith("triangle"):
                continue
            try:
                indices = [int(t.get(name, "-1")) for name in ("v1", "v2", "v3")]
                # A negative index would read from the end of the list instead of failing.
                if min(indices) < 0:
                    raise bad
                corners = tuple(vertices[index] for index in indices)
            except (IndexError, ValueError) as failure:
                raise bad from failure
            triangles.append(corners)  # type: ignore[arg-type]
            if len(triangles) > _MAX_TRIANGLES:
                raise _too_many(path, len(triangles))
    return _finite(path, triangles), unit


# --- starting a part from what was read ------------------------------------------------


class PartSeed(StatableModel):
    """A catalog part's parameters, filled from a measured file, to finish and build.

    ``element_params`` holds what the file gives, each quantity as it is written in a spec.
    ``sources`` cite the file for each value, ready to go into the spec's ``sources``.
    ``missing`` are the required fields a file of this kind cannot give: a drawing has no
    thickness. They are the user's to state, and are never filled in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    element_type: Named
    element_params: FrozenMap[str, Any]
    sources: tuple[FrozenMap[str, str], ...]
    missing: tuple[Named, ...] = ()

    def __str__(self) -> str:
        need = f"; still needs {', '.join(self.missing)}" if self.missing else ""
        return f"seeds a {self.element_type} with {', '.join(self.element_params)}{need}"


def _mm(value: float) -> dict[str, Any]:
    return {"magnitude": round(float(value), 6), "unit": "mm"}


def seed_part(facts: CadFacts) -> PartSeed | None:
    """The catalog part ``facts`` describes, with its parameters filled in, or ``None``.

    A drawing of one rectangle with round holes seeds a mounting plate. A drawing of one
    disc with a bore and a ring of equal holes seeds a plate flange. A solid that is a tube
    seeds a spacer, and one that is a rectangular plate with holes through its thickness a
    mounting plate. Anything else seeds nothing: a shape is not forced into a pattern it
    does not match.
    """

    def cite(field: str, where: str) -> dict[str, str]:
        return {
            "field": f"element_params.{field}",
            "origin": "measured_from_file",
            "file": facts.file,
            "sha256": facts.sha256,
            "locator": where,
        }

    if facts.kind == "dxf" and len(facts.profiles) == 1:
        (profile,) = facts.profiles
        circles = [hole for hole in profile.holes if hole.kind == "circle"]
        if len(circles) != len(profile.holes) or profile.holes_not_listed:
            return None
        layer = f"layer {profile.layer}"
        if profile.kind == "rectangle":
            holes = [
                {
                    "tag": f"h{number}",
                    "x": _mm(hole.x_mm),
                    "y": _mm(hole.y_mm),
                    "diameter": _mm(hole.diameter_mm or 0.0),
                }
                for number, hole in enumerate(circles, start=1)
            ]
            params: dict[str, Any] = {
                "width": _mm(profile.width_mm),
                "length": _mm(profile.height_mm),
            }
            sources = [
                cite("width", f"{layer}, the closed profile's width"),
                cite("length", f"{layer}, the closed profile's height"),
            ]
            if holes:
                params["holes"] = holes
                sources += [
                    cite(f"holes[{index}].diameter", f"circle {index + 1} inside the profile")
                    for index in range(len(holes))
                ]
            return PartSeed(
                element_type="mounting_plate",
                element_params=params,
                sources=tuple(sources),
                missing=("name", "thickness"),
            )
        if profile.kind == "circle":
            centred = [h for h in circles if math.hypot(h.x_mm, h.y_mm) <= 1e-6]
            ring = [h for h in circles if math.hypot(h.x_mm, h.y_mm) > 1e-6]
            radii = {round(math.hypot(h.x_mm, h.y_mm), 4) for h in ring}
            sizes = {round(h.diameter_mm or 0.0, 4) for h in ring}
            if len(centred) == 1 and len(ring) >= 2 and len(radii) == 1 and len(sizes) == 1:
                return PartSeed(
                    element_type="plate_flange",
                    element_params={
                        "outer_diameter": _mm(profile.width_mm),
                        "bore_diameter": _mm(centred[0].diameter_mm or 0.0),
                        "bolt_circle_diameter": _mm(2 * radii.pop()),
                        "bolt_count": len(ring),
                        "bolt_hole_diameter": _mm(sizes.pop()),
                    },
                    sources=(
                        cite("outer_diameter", f"{layer}, the outer circle"),
                        cite("bore_diameter", "the circle at the centre"),
                        cite("bolt_circle_diameter", f"the {len(ring)} equal circles round it"),
                        cite("bolt_hole_diameter", f"the {len(ring)} equal circles round it"),
                    ),
                    missing=("name", "thickness"),
                )
        return None

    if facts.kind == "step" and len(facts.solids) == 1 and not facts.solids_not_listed:
        (solid,) = facts.solids
        if solid.unclassified_faces or solid.cylinders_not_listed:
            return None
        holes = [c for c in solid.cylinders if c.kind == "hole"]
        bosses = [c for c in solid.cylinders if c.kind == "boss"]
        partial = [c for c in solid.cylinders if c.kind in ("fillet", "round")]
        if partial:
            return None
        if len(bosses) == 1 and len(holes) == 1 and len(solid.planes) == 2:
            outer, bore = bosses[0], holes[0]
            if outer.axis == bore.axis and math.dist(outer.position_mm, bore.position_mm) <= 1e-6:
                return PartSeed(
                    element_type="spacer",
                    element_params={
                        "outer_diameter": _mm(outer.diameter_mm),
                        "inner_diameter": _mm(bore.diameter_mm),
                        "length": _mm(outer.depth_mm),
                    },
                    sources=(
                        cite("outer_diameter", "the outside cylinder"),
                        cite("inner_diameter", "the bore"),
                        cite("length", "the outside cylinder's length"),
                    ),
                    missing=("name",),
                )
        if len(bosses) == 1 and len(solid.planes) == 2 and len(holes) >= 3:
            outer = bosses[0]
            bore = [h for h in holes if math.dist(h.position_mm, outer.position_mm) <= 1e-6]
            ring = [h for h in holes if h not in bore]
            flat = [_drop_axis(h.position_mm, outer.axis) for h in ring]
            middle = _drop_axis(outer.position_mm, outer.axis)
            radii = {round(math.dist(point, middle), 4) for point in flat}
            sizes = {round(h.diameter_mm, 4) for h in ring}
            parallel = all(h.axis == outer.axis for h in holes)
            if len(bore) == 1 and len(radii) == 1 and len(sizes) == 1 and parallel:
                return PartSeed(
                    element_type="plate_flange",
                    element_params={
                        "outer_diameter": _mm(outer.diameter_mm),
                        "bore_diameter": _mm(bore[0].diameter_mm),
                        "thickness": _mm(outer.depth_mm),
                        "bolt_circle_diameter": _mm(2 * radii.pop()),
                        "bolt_count": len(ring),
                        "bolt_hole_diameter": _mm(sizes.pop()),
                    },
                    sources=(
                        cite("outer_diameter", "the outside cylinder"),
                        cite("bore_diameter", "the hole on the axis"),
                        cite("thickness", "the outside cylinder's length"),
                        cite("bolt_circle_diameter", f"the {len(ring)} equal holes round it"),
                        cite("bolt_hole_diameter", f"the {len(ring)} equal holes round it"),
                    ),
                    missing=("name",),
                )
        if not bosses and len(solid.planes) == 6:
            sizes = sorted(solid.size_mm)
            thin = solid.size_mm.index(sizes[0])
            axis = tuple(1.0 if index == thin else 0.0 for index in range(3))
            # A plain plate: its box less its holes is its volume, and every hole runs
            # through its thickness.
            through = all(
                hole.axis == axis and abs(hole.depth_mm - sizes[0]) <= 1e-6 for hole in holes
            )
            removed = sum(math.pi * hole.diameter_mm**2 / 4 * hole.depth_mm for hole in holes)
            box = solid.size_mm[0] * solid.size_mm[1] * solid.size_mm[2]
            if through and math.isclose(box - removed, solid.volume_mm3, rel_tol=1e-6):
                first, second = (index for index in range(3) if index != thin)
                if _off_centre(holes, solid, first, second):
                    return None
                return _plate_seed(solid, holes, first, second, thin, cite)
    return None


def _off_centre(holes: Sequence[CylinderFacts], solid: SolidFacts, first: int, second: int) -> bool:
    """Whether the hole positions cannot be read as measured from the plate's middle.

    The reader reports where a hole is in the file's coordinates and the size of the solid,
    not where the solid sits. A plate modelled about its own middle is the only case in
    which the two agree without the solid's position, so that is the only one seeded.
    """
    return any(
        abs(hole.position_mm[first]) > solid.size_mm[first] / 2
        or abs(hole.position_mm[second]) > solid.size_mm[second] / 2
        for hole in holes
    )


def _plate_seed(
    solid: SolidFacts,
    holes: Sequence[CylinderFacts],
    first: int,
    second: int,
    thin: int,
    cite: Any,
) -> PartSeed:
    params: dict[str, Any] = {
        "width": _mm(solid.size_mm[first]),
        "length": _mm(solid.size_mm[second]),
        "thickness": _mm(solid.size_mm[thin]),
    }
    sources = [
        cite("width", "the solid's overall size"),
        cite("length", "the solid's overall size"),
        cite("thickness", "the solid's overall size"),
    ]
    if holes:
        params["holes"] = [
            {
                "tag": f"h{number}",
                "x": _mm(hole.position_mm[first]),
                "y": _mm(hole.position_mm[second]),
                "diameter": _mm(hole.diameter_mm),
            }
            for number, hole in enumerate(holes, start=1)
        ]
        sources += [
            cite(f"holes[{index}].diameter", f"hole {index + 1} through the thickness")
            for index in range(len(holes))
        ]
    return PartSeed(
        element_type="mounting_plate",
        element_params=params,
        sources=tuple(sources),
        missing=("name",),
    )


# --- a reading beside a measurement ----------------------------------------------------


class ReadingComparison(StatableModel):
    """One length an agent read, beside what a file measures for the same field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: Provenance
    read_mm: float
    read_from: Named
    read_locator: str | None = Field(default=None, exclude_if=lambda value: value is None)
    measured_mm: float
    # The entry that cites the measurement, ready to replace the reading's in `sources`.
    measured_source: FrozenMap[str, str]
    difference_mm: float
    agrees: bool

    def __str__(self) -> str:
        read_at = f" ({self.read_locator})" if self.read_locator else ""
        measured_at = self.measured_source.get("locator")
        measured_at = f" ({measured_at})" if measured_at else ""
        verdict = (
            "agree"
            if self.agrees
            else f"DISAGREE by {abs(self.difference_mm):g} mm: the measurement is the one to "
            "use, and the reading is the person's to settle"
        )
        return (
            f"{self.field}: read {self.read_mm:g} mm from {self.read_from}{read_at}, measured "
            f"{self.measured_mm:g} mm from {self.measured_source['file']}{measured_at} — {verdict}"
        )


class ReadingReport(StatableModel):
    """A spec's agent-read lengths held against one measured file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Provenance
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compared: tuple[ReadingComparison, ...] = ()
    # Agent-read values this file gives no measurement for, by field. Not a finding: a
    # drawing has no thickness, and a load is in no file.
    not_measured: tuple[Provenance, ...] = Field(default=(), exclude_if=lambda value: not value)
    note: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @property
    def disagreements(self) -> tuple[ReadingComparison, ...]:
        """The readings the file contradicts."""
        return tuple(line for line in self.compared if not line.agrees)

    def __str__(self) -> str:
        lines = [
            f"{len(self.compared)} agent-read values compared with {self.file}, "
            f"{len(self.disagreements)} disagree"
        ]
        lines += [f"  {line}" for line in self.compared]
        if self.not_measured:
            lines.append(f"  not measured by this file: {', '.join(self.not_measured)}")
        if self.note is not None:
            lines.append(f"  note: {self.note}")
        return "\n".join(lines)


def _value_at(params: Any, path: str) -> Any:
    """The value at ``path`` under ``element_params``, or ``None`` when there is none."""
    import re

    node = params
    try:
        for part in path.split("."):
            name, _, rest = part.partition("[")
            node = node[name]
            for index in re.findall(r"\d+", rest):
                node = node[int(index)]
    except (KeyError, IndexError, TypeError):
        return None
    return node


def _length_mm(value: Any) -> float | None:
    from collections.abc import Mapping

    from .units import Quantity

    if isinstance(value, Mapping) and {"magnitude", "unit"} <= set(value):
        try:
            value = Quantity(magnitude=value["magnitude"], unit=value["unit"])
        except (ValueError, TypeError):
            return None
    if not isinstance(value, Quantity) or not value.has_dimension("[length]"):
        return None
    return float(value.to("mm").magnitude)


def compare_readings(spec: Any, facts: CadFacts) -> ReadingReport:
    """Hold every length ``spec`` cites as agent-read against what ``facts`` measures.

    A value an agent read off a picture or a PDF is a draft. Where a file Anvilate measures
    gives the same field, the measurement is offered beside it with the entry that cites it,
    and a difference is flagged for the person to settle. The two are the same field when
    the file seeds the spec's own element type (:func:`seed_part`) and the seed fills the
    path the reading is cited at; a path is matched as written, so a plate read with its
    width and length the other way round shows as two disagreements, with both sources.

    A reading is held to the measurement the way a dimension's text is held to its geometry:
    equal to a millionth, or it disagrees.
    """
    read = [
        source
        for source in getattr(spec, "sources", ())
        if source.origin == "agent_read" and source.field.startswith("element_params.")
    ]
    seed = seed_part(facts)
    common = {"file": facts.file, "sha256": facts.sha256}
    fields = tuple(source.field for source in read)
    if seed is None or seed.element_type != getattr(spec, "element_type", None):
        what = "no catalog part" if seed is None else f"a {seed.element_type}"
        return ReadingReport(
            **common,
            not_measured=fields,
            note=(
                f"{facts.file} measures as {what}, and the spec declares a "
                f"{getattr(spec, 'element_type', None) or 'part with no element_type'}; "
                "nothing in it is the same field as a reading"
            ),
        )
    cited = {source["field"]: source for source in seed.sources}
    compared, unmeasured = [], []
    for source in read:
        path = source.field.removeprefix("element_params.")
        stated = _length_mm(_value_at(spec.element_params, path))
        measured = _length_mm(_value_at(seed.element_params, path))
        if stated is None or measured is None or source.field not in cited:
            unmeasured.append(source.field)
            continue
        compared.append(
            ReadingComparison(
                field=source.field,
                read_mm=stated,
                read_from=source.file,
                read_locator=source.locator,
                measured_mm=measured,
                measured_source=cited[source.field],
                difference_mm=round(stated - measured, 6),
                agrees=math.isclose(stated, measured, rel_tol=1e-6, abs_tol=1e-6),
            )
        )
    return ReadingReport(**common, compared=tuple(compared), not_measured=tuple(unmeasured))
