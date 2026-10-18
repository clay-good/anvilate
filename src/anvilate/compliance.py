"""Material compliance: what a product's materials are made of, and what they withstand.

Materials are declared in the product's ``screening.materials``, each by the id its items
name (a catalog part's spec material, or a placeholder's or component's ``material``),
with its composition by CAS number and mass fraction, its recycled fraction, and its
attributes, every value with its source.

- :func:`composition_export` gives, for every made part and component, its material, its
  substances, its mass and its recycled fraction, and rolls recycled plastic up the
  product by mass.
- :func:`screen_material_needs` compares each declared need (service temperature,
  sterilization, vacuum outgassing, flammability class, body contact) with the attribute
  its material declares, citing both. A need's limit is the user's, with its source; an
  attribute the material does not declare is not evaluated, naming it.

Substance-list screening (REACH, RoHS, the automotive declarable list) and galvanic
compatibility wait on lists and tables fetched or read from their publishers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ConfigDict

from ._models import Named, StatableModel
from .derivation import DerivationAbsence, Underived
from .product import UL94_CLASSES, MaterialDeclaration, Product, _refuse, place_product
from .scorecard import CheckStatus, Need, ScorecardEntry, ValueSource

__all__ = [
    "CompositionLine",
    "RecycledRollup",
    "CompositionReport",
    "material_of",
    "composition_export",
    "screen_material_needs",
]

_COMPARED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the material's declared attribute against the declared need, as stated",
)


class CompositionLine(StatableModel):
    """One body's material, substances, mass and recycled fraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    material: str | None
    mass_kg: float | None
    substances: tuple[tuple[str, str, float], ...] = ()
    recycled_fraction: float | None = None
    recycled_source: str | None = None


class RecycledRollup(StatableModel):
    """Recycled plastic content by mass, and the lines it comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plastic_kg: float
    recycled_kg: float
    fraction: float | None
    lines: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()


class CompositionReport(StatableModel):
    """Every body's composition, and the product's recycled plastic content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lines: tuple[CompositionLine, ...]
    recycled: RecycledRollup


def material_of(
    product: Product, item: str, library: Mapping[str, Product] | None = None
) -> str | None:
    """The material id the instance ``item`` names: its spec's, or its definition's own."""
    definitions = {d.id: d for d in product.definitions}
    instance = next((i for i in product.instances if i.name == item), None)
    if instance is None:
        raise _refuse(f"'{item}' is not an item of '{product.name}'", subject="item")
    definition = definitions[instance.item]
    if definition.spec is not None:
        return str((dict(definition.spec).get("material") or {}).get("ref") or "") or None
    return definition.material


def _declared(product: Product) -> dict[str, MaterialDeclaration]:
    found = product.screening.materials if product.screening is not None else ()
    return {m.material: m for m in found}


def _item(path: str) -> str:
    return path.split("/")[1].split("[")[0]


def composition_export(
    product: Product, *, library: Mapping[str, Product] | None = None, root: Any = None
) -> CompositionReport:
    """Every made part's and component's composition by mass, and recycled plastic content."""
    if not isinstance(product, Product):
        raise _refuse("product must be a Product from parse_product", subject="product")
    placed = place_product(product, library=library, root=root)
    declared = _declared(product)
    lines = []
    plastic = recycled = 0.0
    contributing, undeclared = [], []
    for body in placed.bodies:
        material = material_of(product, _item(body.path))
        record = declared.get(material) if material is not None else None
        substances = (
            tuple((s.cas, s.name, s.fraction) for s in record.composition) if record else ()
        )
        fraction = source = None
        if record is not None and record.recycled_fraction is not None:
            fraction = float(record.recycled_fraction.value)
            source = record.recycled_fraction.source
        lines.append(CompositionLine(path=body.path, material=material, mass_kg=body.mass_kg,
                                     substances=substances, recycled_fraction=fraction,
                                     recycled_source=source))  # fmt: skip
        if record is not None and record.plastic and body.mass_kg is not None:
            plastic += body.mass_kg
            if fraction is None:
                undeclared.append(body.path)
            else:
                recycled += body.mass_kg * fraction
                contributing.append(
                    f"{body.path}: {body.mass_kg:.4g} kg, {fraction:.0%} ({source})"
                )
    rollup = RecycledRollup(
        plastic_kg=plastic, recycled_kg=recycled,
        fraction=recycled / plastic if plastic > 0 and not undeclared else None,
        lines=tuple(contributing), undeclared=tuple(undeclared),
    )  # fmt: skip
    return CompositionReport(lines=tuple(lines), recycled=rollup)


#: Each check: its label, the need it reads, and the material attribute it reads.
_CHECKS = (
    ("service temperature", "service_temperature", "service_max_temperature"),
    ("sterilization", "sterilization", "service_max_temperature"),
    ("vacuum outgassing", "vacuum", "total_mass_loss"),
    ("flammability", "flammability", "flammability"),
    ("body contact", "body_contact", "biocompatibility"),
)


def _need(declaration: str, takes: str) -> Need:
    return Need(
        declaration=declaration, takes=takes, sources=(ValueSource.USER, ValueSource.DATABASE)
    )


def screen_material_needs(product: Product) -> tuple[ScorecardEntry, ...]:
    """Each declared material need against the attribute each affected item's material states."""
    needs = product.screening.needs if product.screening is not None else None
    if needs is None:
        return ()
    declared = _declared(product)
    items = needs.items or tuple(i.name for i in product.instances)
    entries = []
    for item in items:
        material = material_of(product, item)
        record = declared.get(material) if material is not None else None
        for label, field, attribute in _CHECKS:
            need = getattr(needs, field)
            if need is None:
                continue
            name = f"{item} {label}"
            stated = record.attributes.get(attribute) if record is not None else None
            if stated is None:
                entries.append(ScorecardEntry(
                    name=name, status=CheckStatus.NOT_EVALUATED,
                    detail=f"{item}'s material {material or '(none named)'} declares no "
                    f"{attribute.replace('_', ' ')} to hold against the {label} need",
                    needs=(_need(f"screening.materials[{material}].attributes.{attribute}",
                                 f"the material's {attribute.replace('_', ' ')}, cited"),),
                ))  # fmt: skip
                continue
            entries.append(_compare(name, item, material or "", label, need, attribute, stated))
    return tuple(entries)


def _compare(name: str, item: str, material: str, label: str, need: Any, attribute: str,
             stated: Any) -> ScorecardEntry:  # fmt: skip
    have = stated.value
    if attribute == "service_max_temperature":
        wanted = need.temperature if label == "sterilization" else need.value
        ok = have.to("K").magnitude >= wanted.to("K").magnitude
        if label == "sterilization":
            reaches = f"{need.method} sterilization reaches {wanted} ({need.source})"
        else:
            reaches = f"the need is {wanted} ({need.source})"
        why = f"{material} is declared for service to {have} ({stated.source}); {reaches}"
    elif attribute == "total_mass_loss":
        ok = float(have) <= float(need.value)
        why = (f"{material} loses {float(have):.2%} of its mass in vacuum ({stated.source}), "
               f"against the {float(need.value):.2%} screen ({need.source})")  # fmt: skip
    elif attribute == "flammability":
        for rating in (have, need.value):
            if rating not in UL94_CLASSES:
                raise _refuse(f"{rating!r} is not a UL 94 class ({', '.join(UL94_CLASSES)})",
                              subject="product")  # fmt: skip
        ok = UL94_CLASSES.index(have) >= UL94_CLASSES.index(need.value)
        why = (f"{material} is rated {have} ({stated.source}), against the {need.value} needed "
               f"({need.source})")  # fmt: skip
    else:
        held = {c.strip() for c in str(have).split(",")}
        ok = str(need.value) in held
        why = (f"{material} is declared for {', '.join(sorted(held))} ({stated.source}), and "
               f"the need is {need.value} ({need.source})")  # fmt: skip
    return ScorecardEntry(name=name, status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                          detail=f"{item}: {why}", underived=_COMPARED)  # fmt: skip
