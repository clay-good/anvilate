"""Product change control: what a change to a product touches, with its evidence.

Two revisions of a product are compared item by item, each definition matched by its id:
added, removed, unchanged, or changed, and for a changed one what changed — its
parameters, its geometry (volume and envelope), its interfaces, its ratings, its identity,
and the verdicts on it. Each changed item is classified the way a change process asks:

- **fit** when one of its published interfaces changed (kind, location, size, or the
  holes of a pattern);
- **function** when one of its ratings changed, or a verdict on it or on a connection
  naming it;
- **form** when only its geometry or other parameters changed.

A fit or function change is flagged as needing a new part number and a form change a new
revision; the flag states its evidence and never changes the identity itself. Each changed
item lists every instance path that uses it, across the product and its variants. The
comparison is a :class:`ChangeRecord`, written as Markdown or JSON, whose reason is the
user's to supply and is marked missing when it is not.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import ConfigDict, Field

from ._models import Named, StatableModel
from .product import (
    BuildCache,
    Definition,
    NodeCard,
    Product,
    _content,
    _resolved_offers,
    place_product,
    product_tree,
    resolve_variant,
)
from .refusal import RefusalError, Remedy

__all__ = ["ChangeError", "ItemChange", "ChangeRecord", "compare_products", "compare_to_release"]

_SOURCE = "the two product revisions being compared"
_VOLUME_MM3 = 1e-3
_LENGTH_MM = 1e-4


class ChangeError(RefusalError, ValueError):
    """A comparison that cannot be made as asked."""


def _refuse(message: str, *, subject: str) -> ChangeError:
    return ChangeError(
        message, remedies=(Remedy(action="correct", subject=subject, source=_SOURCE),)
    )


class ItemChange(StatableModel):
    """One item definition across the two revisions: what happened to it, and why it matters.

    ``changes`` says what changed, one line each. ``classes`` are ``fit``, ``function`` and
    ``form`` as they apply; ``flag`` is ``new_part_number`` or ``new_revision``, with
    ``evidence`` naming what forced it. ``where_used`` lists every instance path that uses
    the item in the later revision and its variants (the earlier one's, for a removed item).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named
    part_number: Named
    status: Literal["added", "removed", "unchanged", "changed"]
    changes: tuple[str, ...] = ()
    classes: tuple[Literal["fit", "function", "form"], ...] = ()
    flag: Literal["new_part_number", "new_revision"] | None = None
    evidence: tuple[str, ...] = ()
    where_used: tuple[str, ...] = Field(default=(), max_length=1024)
    # The files of the baseline release that contain or reference the item.
    affected_files: tuple[str, ...] = ()


class ChangeRecord(StatableModel):
    """The comparison of two product revisions: every item, the checks that moved, the mass.

    ``reason`` is the user's or agent's; left out, the record says the reason is missing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    before: Named
    after: Named
    items: tuple[ItemChange, ...]
    newly_failing: tuple[str, ...] = ()
    newly_passing: tuple[str, ...] = ()
    mass_before_kg: float | None
    mass_after_kg: float
    reason: str | None = None

    def changed(self) -> tuple[ItemChange, ...]:
        """The items that were added, removed or changed."""
        return tuple(item for item in self.items if item.status != "unchanged")

    def to_markdown(self) -> str:
        """The record as a Markdown change record, ready to attach to a change order."""
        lines = [
            f"# Change record: {self.before} → {self.after}",
            "",
            f"Reason: {self.reason if self.reason else '**reason missing**'}",
            "",
            (
                f"Mass: {self.mass_before_kg:.4g} kg → {self.mass_after_kg:.4g} kg "
                f"({self.mass_after_kg - self.mass_before_kg:+.4g} kg)."
                if self.mass_before_kg is not None
                else f"Mass: {self.mass_after_kg:.4g} kg; the release records none to compare."
            )
            + " Cost: not estimated.",
            "",
            "| Item | Part number | Status | Class | Flag | What changed | Evidence | Used at "
            "| Files |",
            "|" + " --- |" * 9,
        ]
        for item in self.changed():
            lines.append(
                "| "
                + " | ".join(
                    cell.replace("|", "\\|")
                    for cell in (
                        item.item,
                        item.part_number,
                        item.status,
                        ", ".join(item.classes) or "—",
                        (item.flag or "—").replace("_", " "),
                        "; ".join(item.changes) or "—",
                        "; ".join(item.evidence) or "—",
                        ", ".join(item.where_used) or "—",
                        ", ".join(item.affected_files) or "—",
                    )
                )
                + " |"
            )
        unchanged = [item.item for item in self.items if item.status == "unchanged"]
        lines += ["", f"Unchanged: {', '.join(unchanged) or 'none'}."]
        if self.newly_failing:
            lines += ["", "Newly failing: " + "; ".join(self.newly_failing) + "."]
        if self.newly_passing:
            lines += ["", "Newly passing: " + "; ".join(self.newly_passing) + "."]
        return "\n".join(lines)


def _flat(value: Any, prefix: str = "") -> dict[str, Any]:
    """A nested document as dotted paths to leaf values."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            out.update(_flat(inner, f"{prefix}.{key}" if prefix else str(key)))
        return out
    if isinstance(value, list | tuple):
        out = {}
        for index, inner in enumerate(value):
            out.update(_flat(inner, f"{prefix}[{index}]"))
        return out
    return {prefix: value}


def _parameters(definition: Definition) -> dict[str, Any]:
    if definition.spec is not None:
        return _flat(dict(definition.spec).get("element_params", {}), "element_params")
    if definition.placeholder is not None:
        held = definition.placeholder.model_dump(mode="json", exclude={"interfaces", "holes"})
        return _flat(held, "placeholder")
    if definition.component is not None:
        held = definition.component.model_dump(
            mode="json", exclude={"interfaces", "holes", "ratings"}
        )
        return _flat({**held, "demands": [d.model_dump(mode="json") for d in definition.demands]},
                     "component")  # fmt: skip
    return {"product": definition.product}


def _interfaces(definition: Definition, built: Any) -> dict[str, str]:
    """Each interface as one comparable line: kind, location, parameters, hole positions."""
    offered = _resolved_offers(definition, built, definition.id) if built is not None else {}
    holes = {}
    for feature in getattr(built, "features", ()) or ():
        holes[feature.tag] = tuple(round(float(v), 4) for v in feature.position_mm)
    lines = {}
    for name, interface in offered.items():
        where = interface.face or interface.axis or ""
        params = ", ".join(f"{k} {v}" for k, v in sorted(interface.parameters.items()))
        at = [holes.get(tag) for tag in interface.holes]
        if interface.feature is not None:
            at.append(holes.get(interface.feature))
        lines[name] = f"{interface.kind} on {where}; {params}; at {at}"
    return lines


def _built_of(product: Product, library: Mapping[str, Product]) -> tuple[Any, BuildCache]:
    cache = BuildCache()
    placed = place_product(product, library=library, cache=cache)
    return placed, cache


def _statuses(card: NodeCard) -> dict[str, str]:
    found = {}

    def walk(node: NodeCard) -> None:
        for entry in node.entries:
            found[f"{node.path}: {entry.name}"] = entry.status.value
        for child in node.children:
            walk(child)

    walk(card)
    return found


def _occurrences(product: Product, library: Mapping[str, Product]) -> dict[str, list[str]]:
    """Every item, keyed ``owner/definition`` (the top product's by its id alone), with the
    instance paths that use it, pattern members each."""
    found: dict[str, list[str]] = {}

    def walk(current: Product, prefix: str, owner: str | None) -> None:
        definitions = {d.id: d for d in current.definitions}
        for instance in current.instances:
            definition = definitions[instance.item]
            key = definition.id if owner is None else f"{owner}/{definition.id}"
            count = instance.pattern.count if instance.pattern is not None else 1
            for k in range(count):
                path = f"{prefix}/{instance.name}" + (f"[{k + 1}]" if count > 1 else "")
                found.setdefault(key, []).append(path)
                if definition.product is not None and definition.product in library:
                    walk(library[definition.product], path, definition.product)

    walk(product, product.name, None)
    return found


def _where_used(product: Product, library: Mapping[str, Product], item: str) -> list[str]:
    paths = list(_occurrences(product, library).get(item, []))
    for variant in product.variants:
        paths += _occurrences(resolve_variant(product, variant.name), library).get(item, [])
    return paths


def _definitions(product: Product, library: Mapping[str, Product]) -> dict[str, Definition]:
    """Every definition in the tree, keyed as :func:`_occurrences` keys it."""
    found = {d.id: d for d in product.definitions}
    seen: set[str] = set()
    pending = [d.product for d in product.definitions if d.product is not None]
    while pending:
        name = pending.pop()
        if name in seen or name not in library:
            continue
        seen.add(name)
        for definition in library[name].definitions:
            found[f"{name}/{definition.id}"] = definition
            if definition.product is not None:
                pending.append(definition.product)
    return found


def compare_products(
    before: Product,
    after: Product,
    *,
    library_before: Mapping[str, Product] | None = None,
    library_after: Mapping[str, Product] | None = None,
    reason: str | None = None,
    baseline: Any = None,
) -> ChangeRecord:
    """Compare two revisions of a product item by item, and classify each change.

    Items are matched by their definition id. Both revisions are placed, so geometry,
    interfaces as built and verdicts are compared as the product checks them. ``baseline``
    is the manifest of the release ``before`` was exported as; each changed item then names
    the files of that release it reaches.
    """
    if not isinstance(before, Product) or not isinstance(after, Product):
        raise _refuse("before and after must each be a Product", subject="before")
    if reason is not None and not isinstance(reason, str):
        raise _refuse("reason is the change's reason, as text", subject="reason")
    shelf_before, shelf_after = dict(library_before or {}), dict(library_after or {})
    placed_before, cache_before = _built_of(before, shelf_before)
    placed_after, cache_after = _built_of(after, shelf_after)
    old = _definitions(before, shelf_before)
    new = _definitions(after, shelf_after)
    status_before, status_after = _statuses(placed_before.card), _statuses(placed_after.card)
    numbers: dict[str, str] = {}
    for product, shelf in ((after, shelf_after), (before, shelf_before)):
        by_path = {n.path: n.part_number for n in product_tree(product, library=shelf).walk()}
        for key, paths in _occurrences(product, shelf).items():
            numbers.setdefault(key, by_path[paths[0]])
    used_after = _occurrences(after, shelf_after)
    items: list[ItemChange] = []
    for item in [*new, *(i for i in old if i not in new)]:
        if item not in old:
            used = tuple(_where_used(after, shelf_after, item))
            items.append(ItemChange(item=item, part_number=numbers[item], status="added",
                                    where_used=used))  # fmt: skip
            continue
        if item not in new:
            used = tuple(_where_used(before, shelf_before, item))
            items.append(ItemChange(item=item, part_number=numbers[item], status="removed",
                                    where_used=used))  # fmt: skip
            continue
        a, b = old[item], new[item]
        built_a = _built(a, cache_before, shelf_before)
        built_b = _built(b, cache_after, shelf_after)
        changes: list[str] = []
        fit: list[str] = []
        function: list[str] = []
        form: list[str] = []
        pa, pb = _parameters(a), _parameters(b)
        for path in sorted(set(pa) | set(pb)):
            if pa.get(path) != pb.get(path):
                line = f"{path}: {pa.get(path, 'absent')} → {pb.get(path, 'absent')}"
                changes.append(line)
                form.append(line)
        geometry = _geometry_delta(built_a, built_b)
        if geometry:
            changes.append(geometry)
            form.append(geometry)
        ia, ib = _interfaces(a, built_a), _interfaces(b, built_b)
        for name in sorted(set(ia) | set(ib)):
            if ia.get(name) != ib.get(name):
                line = f"interface {name}: {ia.get(name, 'absent')} → {ib.get(name, 'absent')}"
                changes.append(line)
                fit.append(f"interface {name}")
        if a.component is not None and b.component is not None:
            ra = {r.name: str(r.value) for r in a.component.ratings}
            rb = {r.name: str(r.value) for r in b.component.ratings}
            for name in sorted(set(ra) | set(rb)):
                if ra.get(name) != rb.get(name):
                    line = f"rating {name}: {ra.get(name, 'absent')} → {rb.get(name, 'absent')}"
                    changes.append(line)
                    function.append(f"rating {name}")
        if a.identity != b.identity:
            ida, idb = a.identity.model_dump(mode="json"), b.identity.model_dump(mode="json")
            changes += [f"identity {k}: {ida[k]} → {idb[k]}" for k in ida if ida[k] != idb[k]]
        paths = used_after.get(item, [])
        for key in sorted(set(status_before) | set(status_after)):
            node, _, entry = key.partition(": ")
            mine = node in paths
            named = any(
                node == parent and f"{leaf.split('[')[0]}." in entry
                for parent, _slash, leaf in (p.rpartition("/") for p in paths)
            )
            if (mine or named) and status_before.get(key) != status_after.get(key):
                line = (f"verdict {key}: {status_before.get(key, 'absent')} → "
                        f"{status_after.get(key, 'absent')}")  # fmt: skip
                changes.append(line)
                function.append(f"verdict {key}")
        classes: list[Literal["fit", "function", "form"]] = []
        if fit:
            classes.append("fit")
        if function:
            classes.append("function")
        if form and not classes:
            classes.append("form")
        flag: Literal["new_part_number", "new_revision"] | None = None
        evidence: tuple[str, ...] = ()
        if fit or function:
            flag, evidence = "new_part_number", tuple(fit + function)
        elif form:
            flag, evidence = "new_revision", tuple(form)
        status: Literal["changed", "unchanged"] = "changed" if changes else "unchanged"
        items.append(ItemChange(
            item=item, part_number=numbers[item], status=status, changes=tuple(changes),
            classes=tuple(classes), flag=flag, evidence=evidence,
            where_used=tuple(_where_used(after, shelf_after, item)) if changes else (),
        ))  # fmt: skip
    if baseline is not None:
        items = _with_affected(items, baseline)
    moved = [i.item for i in items if i.status != "unchanged"]
    items.insert(0, ItemChange(
        item=after.name, part_number=product_tree(after, library=shelf_after).part_number,
        status="changed" if moved else "unchanged",
        changes=(f"holds changed items: {', '.join(moved)}",) if moved else (),
        where_used=(after.name,) if moved else (),
    ))  # fmt: skip
    failing_before = {k for k, v in status_before.items() if v == "fail"}
    failing_after = {k for k, v in status_after.items() if v == "fail"}
    passing_before = {k for k, v in status_before.items() if v == "pass"}
    passing_after = {k for k, v in status_after.items() if v == "pass"}
    return ChangeRecord(
        before=_label(before), after=_label(after), items=tuple(items),
        newly_failing=tuple(sorted(failing_after - failing_before)),
        newly_passing=tuple(sorted(passing_after - passing_before)),
        mass_before_kg=placed_before.mass_kg, mass_after_kg=placed_after.mass_kg,
        reason=reason.strip() if reason and reason.strip() else None,
    )  # fmt: skip


def _label(product: Product) -> str:
    revision = product.identity.revision if product.identity is not None else None
    return f"{product.name} rev {revision}" if revision else product.name


def _built(definition: Definition, cache: BuildCache, library: Mapping[str, Product]) -> Any:
    if definition.product is not None:
        return None
    held = cache._store.get(_content(definition, library))
    return held[0] if held is not None else None


def _geometry_delta(a: Any, b: Any) -> str:
    if a is None or b is None:
        return ""
    box_a, box_b = a.shape.bounding_box(), b.shape.bounding_box()
    size_a = (box_a.size.X, box_a.size.Y, box_a.size.Z)
    size_b = (box_b.size.X, box_b.size.Y, box_b.size.Z)
    volume_a, volume_b = float(a.shape.volume), float(b.shape.volume)
    same_size = all(abs(x - y) <= _LENGTH_MM for x, y in zip(size_a, size_b, strict=True))
    if abs(volume_a - volume_b) <= _VOLUME_MM3 and same_size:
        return ""
    sizes = " × ".join(f"{v:g}" for v in size_a) + " → " + " × ".join(f"{v:g}" for v in size_b)
    return f"geometry: volume {volume_a:.6g} → {volume_b:.6g} mm^3, envelope {sizes} mm"


def _with_affected(items: list[ItemChange], baseline: Any) -> list[ItemChange]:
    from .release import Manifest

    if not isinstance(baseline, Manifest):
        raise _refuse("baseline must be the Manifest of the release compared against",
                      subject="baseline")  # fmt: skip
    files = {item.item: item.files for item in baseline.items}
    return [item.model_copy(update={"affected_files": files.get(item.item, ())})
            if item.status != "unchanged" else item for item in items]  # fmt: skip


def compare_to_release(
    product: Product,
    baseline: Any,
    *,
    library: Mapping[str, Product] | None = None,
    reason: str | None = None,
) -> ChangeRecord:
    """Compare a working product with the manifest of its last release, item by item.

    The release holds each item's content hash and parameters, not its geometry, so an item
    is changed when its content differs, with its parameters named; an item changed under
    the part number and revision it was released as says so. To classify the changes, keep
    the released product document and use :func:`compare_products` with ``baseline``.
    """
    from .release import Manifest, _items

    if not isinstance(product, Product):
        raise _refuse("product must be a Product", subject="product")
    if not isinstance(baseline, Manifest):
        raise _refuse("baseline must be the Manifest of the last release", subject="baseline")
    shelf = dict(library or {})
    tree = product_tree(product, library=shelf)
    now = {item.item: item for item in _items(product, shelf, tree)}
    then = {item.item: item for item in baseline.items}
    used = _occurrences(product, shelf)
    changes: list[ItemChange] = []
    for key in [*now, *(k for k in then if k not in now)]:
        mine, released = now.get(key), then.get(key)
        if released is None:
            assert mine is not None
            changes.append(ItemChange(item=key, part_number=mine.part_number, status="added",
                                      where_used=tuple(used.get(key, ()))))  # fmt: skip
            continue
        if mine is None:
            changes.append(ItemChange(item=key, part_number=released.part_number, status="removed",
                                      affected_files=released.files))  # fmt: skip
            continue
        if mine.content == released.content:
            changes.append(ItemChange(item=key, part_number=mine.part_number, status="unchanged"))
            continue
        keys = set(released.parameters) | set(mine.parameters)
        lines = [
            f"{k}: {released.parameters.get(k, 'absent')} → {mine.parameters.get(k, 'absent')}"
            for k in sorted(keys)
            if released.parameters.get(k) != mine.parameters.get(k)
        ]
        same = (mine.part_number, mine.revision) == (released.part_number, released.revision)
        evidence = ((f"content changed under part number {mine.part_number} revision "
                     f"{mine.revision or '-'}, as released",) if same else ())  # fmt: skip
        changes.append(ItemChange(
            item=key, part_number=mine.part_number, status="changed",
            changes=tuple(lines) or ("content",), evidence=evidence,
            where_used=tuple(used.get(key, ())), affected_files=released.files,
        ))  # fmt: skip
    placed = place_product(product, library=shelf)
    return ChangeRecord(
        before=f"{baseline.product} rev {baseline.revision}" if baseline.revision
        else baseline.product,
        after=_label(product), items=tuple(changes),
        mass_before_kg=None, mass_after_kg=placed.mass_kg,
        reason=reason.strip() if reason and reason.strip() else None,
    )  # fmt: skip
