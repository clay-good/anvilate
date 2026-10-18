"""The release package: the files a product is handed over as, gated on its card.

:func:`export_package` writes a product into a folder as the files the engineer's PLM,
ERP, purchasing and CAD already read:

- ``bom.csv`` and ``bom.xlsx``, the indented BOM: level, find number, parent, part number,
  revision, description, quantity per parent, unit of measure, material, finish, make or
  buy, process, manufacturer, manufacturer part number, supplier part numbers, unit mass,
  and the line's files;
- ``buy.csv``, every purchased item once, its quantity summed across every instance and
  every variant exported, with the paths that use it;
- ``step/<part number>_<revision>.step`` for each catalog part, and ``step/<product>.step``
  for the assembly;
- ``parameters/<part number>.csv`` for each item that reads layout parameters: each by
  name and unit, one column per variant;
- ``manifest.json``: the product, its revision, release or draft, the card's verdict, and
  every file with its role and SHA-256. :func:`verify_package` reports any file whose
  content no longer matches.

A **release** is refused while the card fails, while an item is a placeholder, while a
component is unsourced, or while a part number is provisional, naming every blocking path.
A **draft** is written at any time, and says so: its manifest is a draft's, and every STEP
header carries the unvalidated watermark naming why it is not a release.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from ._models import Named, StatableModel
from .product import (
    Product,
    ProductNode,
    load_product,
    place_product,
    product_tree,
    resolve_variant,
    write_product_step,
)
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus

__all__ = [
    "ReleaseRefused",
    "ManifestFile",
    "Manifest",
    "release_blockers",
    "export_package",
    "verify_package",
]

_SOURCE = "the product's card, its placeholders, its components' sources and its part numbers"
BOM_COLUMNS = (
    "level", "find number", "parent part number", "part number", "revision", "description",
    "quantity per parent", "unit of measure", "material", "finish", "make/buy", "process",
    "manufacturer", "manufacturer part number", "supplier part numbers", "unit mass kg",
    "files",
)  # fmt: skip
_BUY_COLUMNS = ("designation", "manufacturer", "supplier part numbers", "quantity", "used at")


class ReleaseRefused(RefusalError, ValueError):
    """A release asked for a product that cannot be released yet, naming every blocker."""

    def __init__(self, blockers: tuple[str, ...]) -> None:
        self.blockers = blockers
        super().__init__(
            "the product cannot be released: " + "; ".join(blockers)
            + ". Export a draft instead, or clear each blocker",
            remedies=(Remedy(action="clear", subject="each blocking path", source=_SOURCE),),
        )  # fmt: skip


class ManifestFile(StatableModel):
    """One file of the package: where it is, what it is for, and its digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    role: Named
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Manifest(StatableModel):
    """What the package is: the product, release or draft, the verdict, and every file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product: Named
    revision: str | None
    kind: Literal["release", "draft"]
    verdict: CheckStatus
    blockers: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    files: tuple[ManifestFile, ...] = Field(max_length=4096)


def release_blockers(product: Product, placed: Any, tree: ProductNode) -> tuple[str, ...]:
    """Every reason ``product`` cannot be released, each naming its path."""
    blockers = []
    if placed.card.status is CheckStatus.FAIL:
        failing = sorted({path for path, e in placed.card.findings()
                          if e.status is CheckStatus.FAIL})  # fmt: skip
        blockers.append(f"the card fails at {', '.join(failing)}")
    blockers += [f"{body.path} is a placeholder" for body in placed.bodies if body.placeholder]
    for path, entry in placed.card.findings():
        if entry.name == "sourcing":
            blockers.append(f"{path} is unsourced")
    blockers += [f"{node.path} has the provisional part number {node.part_number}"
                 for node in tree.walk() if node.provisional]  # fmt: skip
    return tuple(blockers)


def export_package(
    source: Any,
    folder: Any,
    *,
    release: bool,
    library: Mapping[str, Product] | None = None,
    variants: bool = True,
) -> Manifest:
    """Write ``source`` (a Product, or a product document's path) into ``folder``.

    ``release`` asks for a release, refused with every blocker named while there is one;
    otherwise a draft is written. ``variants`` exports each declared variant's buy list
    and parameter columns with the base product's.
    """
    from .export.gate import ExportAuthorization

    if isinstance(source, Product):
        product, shelf, root = source, dict(library or {}), None
    else:
        product, found = load_product(source)
        shelf, root = {**found, **dict(library or {})}, Path(source).parent
    out = Path(folder)
    placed = place_product(product, library=shelf, root=root)
    tree = product_tree(product, library=shelf)
    blockers = release_blockers(product, placed, tree)
    if release and blockers:
        raise ReleaseRefused(blockers)
    authorization = (
        ExportAuthorization(validated=True) if release else
        ExportAuthorization(validated=False, overridden=True,
                            blocking=blockers or ("a draft, not a release",))
    )  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, str]] = []
    chosen = [(product.name, product)]
    if variants:
        chosen += [(f"{product.name}-{v.name}", resolve_variant(product, v.name))
                   for v in product.variants]  # fmt: skip
    step_files = _part_steps(product, shelf, tree, out, authorization, files)
    rows = _bom_rows(product, shelf, tree, placed, step_files)
    _write(out, "bom.csv", _csv(BOM_COLUMNS, rows), files, "bom")
    _write(out, "bom.xlsx", _xlsx(rows), files, "bom")
    _write(out, "buy.csv", _csv(_BUY_COLUMNS, _buy_rows(chosen, shelf)), files, "buy list")
    for definition_id, table in _parameter_tables(chosen).items():
        number = _safe(_number(tree, definition_id))
        _write(out, f"parameters/{number}.csv", table, files, "parameters")
    assembly = out / "step" / f"{_safe(product.name)}.step"
    assembly.parent.mkdir(parents=True, exist_ok=True)
    write_product_step(product, assembly, authorization=authorization, library=shelf)
    files.append((assembly.relative_to(out).as_posix(), "assembly step"))
    manifest = Manifest(
        product=product.name,
        revision=product.identity.revision if product.identity is not None else None,
        kind="release" if release else "draft",
        verdict=placed.card.status,
        blockers=blockers,
        variants=tuple(name for name, _p in chosen[1:]),
        files=tuple(
            ManifestFile(path=p, role=role, sha256=_digest(out / p)) for p, role in sorted(files)
        ),  # fmt: skip
    )
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_package(folder: Any) -> tuple[str, ...]:
    """Every file the package's manifest lists that is missing or no longer matches it."""
    out = Path(folder)
    try:
        manifest = Manifest.model_validate_json((out / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as failure:
        raise _refuse(
            f"{out / 'manifest.json'} cannot be read: {failure}", subject="folder"
        ) from failure
    problems = []
    for listed in manifest.files:
        path = out / listed.path
        if not path.is_file():
            problems.append(f"{listed.path} is missing")
            continue
        found = _digest(path)
        if found != listed.sha256:
            problems.append(f"{listed.path} is altered: listed {listed.sha256}, found {found}")
    return tuple(problems)


def _refuse(message: str, *, subject: str) -> RefusalError:
    return ReleaseRefusedInput(message, remedies=(Remedy(action="correct", subject=subject,
                                                         source=_SOURCE),))  # fmt: skip


class ReleaseRefusedInput(RefusalError, ValueError):
    """A package that cannot be read or written as asked."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _number(tree: ProductNode, definition_id: str) -> str:
    return next((n.part_number for n in tree.walk() if n.definition == definition_id),
                definition_id)  # fmt: skip


def _write(
    out: Path, name: str, data: str | bytes, files: list[tuple[str, str]], role: str
) -> None:
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    files.append((name, role))


def _csv(columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    from .margin_of_safety import _csv_safe

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_safe(c, cell) for c, cell in zip(columns, row, strict=True)])
    return out.getvalue()


def _xlsx(rows: list[tuple[str, ...]]) -> bytes:
    from .margin_of_safety import _workbook

    numeric = {BOM_COLUMNS.index(c) for c in ("level", "quantity per parent", "unit mass kg")}
    return _workbook((("BOM", [BOM_COLUMNS, *rows], numeric),))


def _part_steps(
    product: Product,
    shelf: Mapping[str, Product],
    tree: ProductNode,
    out: Path,
    authorization: Any,
    files: list[tuple[str, str]],
) -> dict[str, str]:
    """One STEP per catalog part definition, named by part number and revision."""
    from .geometry import build_spec, write_step
    from .spec import parse_spec

    written: dict[str, str] = {}
    for current in (product, *shelf.values()):
        for definition in current.definitions:
            if definition.spec is None or definition.id in written:
                continue
            number = _number(tree, definition.id)
            revision = definition.identity.revision or "-"
            path = out / "step" / f"{_safe(number)}_{_safe(revision)}.step"
            path.parent.mkdir(parents=True, exist_ok=True)
            spec = parse_spec(dict(definition.spec))
            write_step(build_spec(spec), path, authorization=authorization,
                       tolerances=spec.geometric_tolerances)  # fmt: skip
            written[definition.id] = path.relative_to(out).as_posix()
            files.append((written[definition.id], "part step"))
    return written


def _bom_rows(
    product: Product,
    shelf: Mapping[str, Product],
    tree: ProductNode,
    placed: Any,
    step_files: Mapping[str, str],
) -> list[tuple[str, ...]]:
    """The indented BOM: each distinct item under its parent once, with its quantity."""
    masses = {body.path: body.mass_kg for body in placed.bodies}
    owners: dict[str, Any] = {}
    for current in (product, *shelf.values()):
        for definition in current.definitions:
            owners.setdefault(definition.id, definition)
    rows: list[tuple[str, ...]] = []

    def walk(node: ProductNode, level: int) -> None:
        grouped: dict[str, list[ProductNode]] = {}
        for child in node.children:
            grouped.setdefault(child.definition, []).append(child)
        for find, (definition_id, children) in enumerate(grouped.items(), start=1):
            first = children[0]
            definition = owners[definition_id]
            spec = dict(definition.spec) if definition.spec is not None else {}
            component = definition.component
            mass = masses.get(first.path)
            rows.append((
                str(level), str(find), node.part_number, first.part_number,
                first.revision or "", first.description, str(len(children)),
                component.unit_of_measure if component is not None else "each",
                str((spec.get("material") or {}).get("ref", "")), "",
                first.source.value, str((spec.get("manufacturing") or {}).get("process", "")),
                component.manufacturer if component is not None else "",
                component.part_number if component is not None else "",
                "; ".join(f"{s.supplier} {s.number}" for s in component.suppliers)
                if component is not None else "",
                f"{mass:.6g}" if mass is not None else "",
                step_files.get(definition_id, ""),
            ))  # fmt: skip
            walk(first, level + 1)

    walk(tree, 1)
    return rows


def _buy_rows(
    chosen: list[tuple[str, Product]], shelf: Mapping[str, Product]
) -> list[tuple[str, ...]]:
    """Every purchased item once, summed across every instance of every product exported."""
    lines: dict[str, dict[str, Any]] = {}
    for _name, product in chosen:
        definitions: dict[str, Any] = {}
        for current in (product, *shelf.values()):
            for definition in current.definitions:
                definitions.setdefault(definition.id, definition)
        for node in product_tree(product, library=shelf).walk()[1:]:
            if node.source.value != "buy":
                continue
            component = definitions[node.definition].component
            key = (f"{component.manufacturer} {component.part_number}" if component is not None
                   else node.part_number)  # fmt: skip
            line = lines.setdefault(key, {
                "manufacturer": component.manufacturer if component is not None else "",
                "suppliers": "; ".join(f"{s.supplier} {s.number}" for s in component.suppliers)
                if component is not None else "",
                "quantity": 0, "paths": [],
            })  # fmt: skip
            line["quantity"] += 1
            line["paths"].append(node.path)
    return [(key, v["manufacturer"], v["suppliers"], str(v["quantity"]), "; ".join(v["paths"]))
            for key, v in sorted(lines.items())]  # fmt: skip


def _parameter_tables(chosen: list[tuple[str, Product]]) -> dict[str, str]:
    """Per item reading layout parameters: each parameter by name, one column per product."""
    readers: dict[str, list[str]] = {}
    base = chosen[0][1]
    if base.layout is None:
        return {}
    for parameter in base.layout.parameters:
        for place in parameter.read_by:
            owner = place.partition(":")[0]
            if owner != "@layout" and parameter.name not in readers.setdefault(owner, []):
                readers[owner].append(parameter.name)
    tables = {}
    for owner, names in readers.items():
        columns = ("parameter", "unit", *(name for name, _p in chosen))
        rows = []
        for name in names:
            values = []
            unit = ""
            for _label, product in chosen:
                stated = {
                    p.name: p.value for p in (product.layout.parameters if product.layout else ())
                }
                value = stated.get(name)
                unit = unit or (value.unit if value is not None else "")
                values.append(f"{value.to(unit).magnitude:g}" if value is not None else "")
            rows.append((name, unit, *values))
        tables[owner] = _csv(columns, rows)
    return tables
