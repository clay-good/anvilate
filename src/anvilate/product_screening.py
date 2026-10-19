"""Product screening: checks that exist only for a product as a whole.

:func:`product_screening` places a product and reports what no single part can say:

- **Mass properties per node.** Every product node's mass, centre of mass, and inertia
  about its centre of mass, rolled up from its leaves. Each contribution states its basis:
  ``computed`` from the part's geometry and density, ``declared`` by a component record,
  or ``placeholder``; and its maturity: ``calculated``, ``measured`` or ``estimated``. A
  leaf with no mass makes every node above it not evaluated, naming it. Inertia treats each
  body as uniform over its own solid.
- **Mass growth.** With ``screening.mass_growth`` declared, the basic mass, the growth by
  maturity and the predicted mass; ``screening.max_mass`` is checked on the predicted mass.
- **Tip-over.** The tilt at which the centre of mass leaves the footprint (the plan
  rectangle of the bodies resting lowest), about each of its edges, against
  ``screening.min_tilt``.
- **Clearance.** The least gap between every two items that share no mate or connection,
  with where it is, against ``screening.min_clearance``.
- **Mobility.** The Grübler–Kutzbach count over the declared joints, with each joint's
  freedoms, and a caveat wherever the count is not to be trusted: zero or negative, or two
  joint axes parallel or coincident. It never states that a product cannot move.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel
from .budget import (
    Budget,
    BudgetResult,
    CombinationRule,
    Contributor,
    ContributorBasis,
    GrowthAllowance,
    LimitBasis,
)
from .derivation import DerivationAbsence, Underived
from .product import Product, _placed_leaves, _refuse, place_product
from .scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Need,
    ScorecardEntry,
    ValueSource,
)
from .units import Quantity

__all__ = [
    "Reaction",
    "LoadStep",
    "MassContribution",
    "NodeMass",
    "MaturityLine",
    "MassRollup",
    "Mobility",
    "ClosestApproach",
    "Economy",
    "CostLine",
    "NodeCost",
    "ProductScreening",
    "product_screening",
]

Basis = Literal["computed", "declared", "placeholder", "missing"]
Maturity = Literal["estimated", "calculated", "measured"]
_FREEDOMS = {"rigid": 0, "revolute": 1, "linear": 1, "cylindrical": 2, "ball": 3}
_SUMMED = Underived(
    kind=DerivationAbsence.NUMERIC_RESULT,
    reason="summed over the placed bodies, each uniform over its own solid",
)


class MassContribution(StatableModel):
    """One body's share: its mass, where it came from, and how mature it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    mass_kg: float | None
    basis: Basis
    maturity: Maturity | None


class NodeMass(StatableModel):
    """A product node's mass, centre of mass, and inertia about its centre of mass.

    ``inertia_kg_mm2`` is (Ixx, Iyy, Izz, Ixy, Iyz, Ixz) in the product's frame. With a leaf
    below it massless, the mass is ``None`` and ``missing`` names the leaves;
    ``provisional`` names the placeholders the figures rest on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    mass_kg: float | None
    center_of_mass_mm: tuple[float, float, float] | None
    inertia_kg_mm2: tuple[float, float, float, float, float, float] | None
    missing: tuple[str, ...] = ()
    provisional: tuple[str, ...] = ()


class MaturityLine(StatableModel):
    """The mass of one maturity, its growth allowance, and the growth it adds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maturity: Maturity
    basic_kg: float
    allowance: float
    growth_kg: float


class MassRollup(StatableModel):
    """Basic mass, growth by maturity, and predicted mass, with the allowances' source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    basic_kg: float
    growth_kg: float
    predicted_kg: float
    lines: tuple[MaturityLine, ...]
    source: Named


class Mobility(StatableModel):
    """The Grübler–Kutzbach count, each joint's freedoms, and why it may be wrong."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    bodies: int
    formula: str
    joints: tuple[str, ...]
    caveats: tuple[str, ...] = ()


class ClosestApproach(StatableModel):
    """Two items that share no connection: their least gap and the midpoint where it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    first: Named
    second: Named
    gap_mm: float
    at_mm: tuple[float, float, float]


class ProductScreening(StatableModel):
    """What the product as a whole weighs, where, how close its items come, how it moves."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    contributions: tuple[MassContribution, ...]
    nodes: tuple[NodeMass, ...]
    rollup: MassRollup | None = None
    mass_budget: BudgetResult | None = None
    approaches: tuple[ClosestApproach, ...] = Field(default=(), max_length=4096)
    mobility: Mobility
    load_path: tuple[LoadStep, ...] = ()
    economy: Economy | None = None
    cost_lines: tuple[CostLine, ...] = ()
    costs: tuple[NodeCost, ...] = ()
    entries: tuple[ScorecardEntry, ...] = ()


def _need(declaration: str, takes: str, dimension: str, units: tuple[str, ...]) -> Need:
    return Need(declaration=declaration, takes=takes, dimension=dimension, units=units,
                sources=(ValueSource.USER, ValueSource.STANDARD))  # fmt: skip


def _inertia(shape: Any, mass: float) -> tuple[tuple[float, float, float], list[list[float]]]:
    """A body's volume centroid and its inertia about it, at ``mass`` spread uniformly."""
    from OCP.BRepGProp import BRepGProp  # type: ignore[import-untyped]
    from OCP.GProp import GProp_GProps  # type: ignore[import-untyped]

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, props)
    volume = props.Mass()
    centre = props.CentreOfMass()
    matrix = props.MatrixOfInertia()
    scale = mass / volume if volume > 0 else 0.0
    rows = [[matrix.Value(i, j) * scale for j in (1, 2, 3)] for i in (1, 2, 3)]
    return (centre.X(), centre.Y(), centre.Z()), rows


def _roll(
    bodies: list[tuple[float, tuple[float, float, float], Any]],
) -> tuple[float, tuple[float, float, float], tuple[float, float, float, float, float, float]]:
    """Total mass, centre of mass, and inertia about it by the parallel-axis theorem.

    Each body's mass acts at its own centre of mass (a placeholder's may be declared off
    its envelope's centre); its inertia is its solid's, about the solid's centroid.
    """
    total = sum(m for m, _c, _s in bodies)
    centre = tuple(sum(m * c[i] for m, c, _s in bodies) / total for i in range(3))
    tensor = [[0.0] * 3 for _ in range(3)]
    for mass, _com, shape in bodies:
        at, own = _inertia(shape, mass)
        d = [at[i] - centre[i] for i in range(3)]
        square = sum(v * v for v in d)
        for i in range(3):
            for j in range(3):
                tensor[i][j] += own[i][j] + mass * ((square if i == j else 0.0) - d[i] * d[j])
    x, y, z = (round(v, 6) + 0.0 for v in centre)
    inertia = (tensor[0][0], tensor[1][1], tensor[2][2], tensor[0][1], tensor[1][2], tensor[0][2])
    return total, (x, y, z), tuple(round(v, 3) + 0.0 for v in inertia)  # type: ignore[return-value]


def product_screening(
    product: Product,
    *,
    library: Mapping[str, Product] | None = None,
    root: Any = None,
) -> ProductScreening:
    """Screen ``product`` as a whole: mass properties, growth, tip-over, clearance, mobility."""
    if not isinstance(product, Product):
        raise _refuse("product must be a Product from parse_product", subject="product")
    shelf = dict(library or {})
    leaves, _rebuilt, _reused, _extra, _tables, _joints = _placed_leaves(product, shelf, None, root)
    placed = place_product(product, library=shelf, root=root)
    bodies = [leaf for leaf in leaves if leaf.kind != "reference"]
    contributions = []
    for leaf in bodies:
        if leaf.mass is None:
            basis: Basis = "missing"
            maturity: Maturity | None = None
        elif leaf.kind == "placeholder":
            basis, maturity = "placeholder", "estimated"
        elif leaf.kind == "component":
            basis, maturity = "declared", "measured"
        else:
            basis, maturity = "computed", "calculated"
        contributions.append(MassContribution(path=leaf.path, mass_kg=leaf.mass, basis=basis,
                                              maturity=maturity))  # fmt: skip
    nodes = []
    for node in _walk(placed.card):
        if node.kind != "product":
            continue
        under = [leaf for leaf in bodies if leaf.path.startswith(node.path + "/")]
        missing = tuple(leaf.path for leaf in under if leaf.mass is None)
        held = tuple(leaf.path for leaf in under if leaf.kind == "placeholder")
        if missing or not under:
            nodes.append(NodeMass(
                path=node.path, mass_kg=None, center_of_mass_mm=None, inertia_kg_mm2=None,
                missing=missing, provisional=held,
            ))  # fmt: skip
            continue
        weighed = [(float(leaf.mass or 0.0), _point(leaf.com.center()), leaf.shape)
                   for leaf in under]  # fmt: skip
        mass, centre, inertia = _roll(weighed)
        nodes.append(NodeMass(path=node.path, mass_kg=mass, center_of_mass_mm=centre,
                              inertia_kg_mm2=inertia, provisional=held))  # fmt: skip
    entries: list[ScorecardEntry] = []
    declared = product.screening
    rollup = _rollup(contributions, declared)
    top = nodes[0]
    budget = None
    if declared is not None and declared.max_mass is not None:
        entry, budget = _mass_entry(top, contributions, rollup, declared)
        entries.append(entry)
    if declared is not None and declared.max_cg_height is not None:
        entries.append(_cg_height_entry(top, placed, declared.max_cg_height))
    if declared is not None and declared.min_tilt is not None:
        entries.append(_tip_entry(top, placed, declared.min_tilt))
    steps, path_entries = _load_path(product, placed)
    entries += path_entries
    entries += _rated_from_path(product, shelf, steps)
    entries += _thermal(product, placed)
    entries += _chains(product)
    from .compliance import screen_material_needs

    entries += screen_material_needs(product)
    cost_lines, costs = _costs(product, shelf)
    approaches = _approaches(product, bodies)
    if declared is not None and declared.min_clearance is not None:
        entries.append(_clearance_entry(approaches, declared.min_clearance))
    return ProductScreening(
        name=product.name, contributions=tuple(contributions), nodes=tuple(nodes),
        rollup=rollup, mass_budget=budget, approaches=approaches,
        mobility=_mobility(product, placed),
        load_path=tuple(steps),
        economy=_economy(product, shelf, bodies),
        cost_lines=tuple(cost_lines), costs=tuple(costs),
        entries=tuple(entries),
    )  # fmt: skip


def _point(vector: Any) -> tuple[float, float, float]:
    return float(vector.X), float(vector.Y), float(vector.Z)


def _walk(card: Any) -> list[Any]:
    found = [card]
    for child in card.children:
        found += _walk(child)
    return found


def _rollup(contributions: list[MassContribution], declared: Any) -> MassRollup | None:
    growth = declared.mass_growth if declared is not None else None
    if growth is None or any(c.mass_kg is None for c in contributions):
        return None
    lines = []
    for maturity in ("estimated", "calculated", "measured"):
        basic = sum(c.mass_kg or 0.0 for c in contributions if c.maturity == maturity)
        allowance = float(getattr(growth, maturity))
        lines.append(MaturityLine(maturity=maturity, basic_kg=basic, allowance=allowance,
                                  growth_kg=basic * allowance))  # fmt: skip
    basic = sum(line.basic_kg for line in lines)
    added = sum(line.growth_kg for line in lines)
    return MassRollup(basic_kg=basic, growth_kg=added, predicted_kg=basic + added,
                      lines=tuple(lines), source=growth.source)  # fmt: skip


_MASS_SOURCES = {
    "computed": "computed from its geometry and density",
    "declared": "declared by its component record",
    "placeholder": "a placeholder's estimate",
}


def _mass_budget(contributions: list[MassContribution], declared: Any) -> BudgetResult:
    """The product's mass as a budget: each body one term of its maturity, summed.

    A declared growth allowance becomes a ``GrowthAllowance`` per maturity, one plus its
    fraction, so the result ledgers the growth as growth instead of folding it into a mass.
    """
    growth = declared.mass_growth
    # Called only once every body has a mass, and a body with a mass has a maturity.
    terms = tuple(
        Contributor(name=c.path, value=Quantity(magnitude=c.mass_kg or 0.0, unit="kg"),
                    source=_MASS_SOURCES[c.basis], basis=ContributorBasis(c.maturity or ""))
        for c in contributions
    )  # fmt: skip
    present = {c.maturity for c in contributions}
    allowances = () if growth is None else tuple(
        GrowthAllowance(basis=ContributorBasis(m), factor=1.0 + float(getattr(growth, m)),
                        authority=growth.source)
        for m in ("estimated", "calculated", "measured") if m in present
    )  # fmt: skip
    return Budget(
        name="product mass", quantity="predicted mass" if growth is not None else "mass",
        limit=declared.max_mass.value, limit_basis=LimitBasis.REQUIREMENT,
        limit_source=declared.max_mass.source, rule=CombinationRule.WORST_CASE,
        contributors=terms, growth=allowances,
    ).evaluate()  # fmt: skip


def _mass_entry(
    top: NodeMass,
    contributions: list[MassContribution],
    rollup: MassRollup | None,
    declared: Any,
) -> tuple[ScorecardEntry, BudgetResult | None]:
    limit = declared.max_mass
    if top.mass_kg is None:
        return ScorecardEntry(
            name="product mass", status=CheckStatus.NOT_EVALUATED,
            detail=f"no total: {', '.join(top.missing)} carries no mass",
            needs=(_need("definitions[].spec", "a mass for every item", "[mass]", ("kg",)),),
        ), None  # fmt: skip
    result = _mass_budget(contributions, declared)
    mass = rollup.predicted_kg if rollup is not None else top.mass_kg
    basis = (f"predicted {mass:.4g} kg (basic {rollup.basic_kg:.4g} + growth "
             f"{rollup.growth_kg:.4g}, {rollup.source})" if rollup is not None
             else f"{mass:.4g} kg with no growth allowance declared")  # fmt: skip
    governing = " and ".join(result.governing)
    held = f"; provisional on {', '.join(top.provisional)}" if top.provisional else ""
    entry = result.to_entry()
    detail = f"{basis} against {limit.value} ({limit.source}); governing: {governing}{held}"
    return entry.model_copy(update={"name": "product mass", "detail": detail}), result


def _cg_height_entry(top: NodeMass, placed: Any, limit: Any) -> ScorecardEntry:
    """The centre of mass's height above the lowest point of the product, against a limit.

    A weighted mean, not a sum, so it is a limit of its own rather than a budget's terms.
    """
    if top.center_of_mass_mm is None:
        return ScorecardEntry(
            name="centre-of-mass height", status=CheckStatus.NOT_EVALUATED,
            detail="no centre of mass: " + ", ".join(top.missing),
            needs=(_need("definitions[].spec", "a mass for every item", "[mass]", ("kg",)),),
        )  # fmt: skip
    floor = min(body.box_min_mm[2] for body in placed.bodies)
    height = top.center_of_mass_mm[2] - floor
    allowed = limit.value.to("mm").magnitude
    held = f"; provisional on {', '.join(top.provisional)}" if top.provisional else ""
    return ScorecardEntry(
        name="centre-of-mass height",
        status=CheckStatus.PASS if height <= allowed else CheckStatus.FAIL,
        detail=f"the centre of mass is {height:.4g} mm above the lowest point of the product, "
        f"against {limit.value} ({limit.source}){held}",
        reference=limit.source,
        underived=_SUMMED,
        comparison=Comparison(
            measured=Quantity(magnitude=height, unit="mm"), limit=limit.value,
            sense=LimitSense.AT_MOST, measured_label="centre-of-mass height",
            limit_label="allowed",
        ),
    )  # fmt: skip


def _tip_entry(top: NodeMass, placed: Any, limit: Any) -> ScorecardEntry:
    need = _need("screening.min_tilt", "the tilt the product must stand at", "[]", ("degree",))
    if top.center_of_mass_mm is None:
        return ScorecardEntry(name="tip-over", status=CheckStatus.NOT_EVALUATED,
                              detail="no centre of mass: " + ", ".join(top.missing),
                              needs=(need,))  # fmt: skip
    floor = min(body.box_min_mm[2] for body in placed.bodies)
    resting = [b for b in placed.bodies if abs(b.box_min_mm[2] - floor) <= 1.0]
    x0 = min(b.box_min_mm[0] for b in resting)
    x1 = max(b.box_max_mm[0] for b in resting)
    y0 = min(b.box_min_mm[1] for b in resting)
    y1 = max(b.box_max_mm[1] for b in resting)
    cx, cy, cz = top.center_of_mass_mm
    height = cz - floor
    edges = {"left": cx - x0, "right": x1 - cx, "front": cy - y0, "back": y1 - cy}
    edge, inside = min(edges.items(), key=lambda pair: pair[1])
    tilt = math.degrees(math.atan2(inside, height)) if height > 0 else 90.0
    required = limit.value.to("degree").magnitude
    return ScorecardEntry(
        name="tip-over",
        status=CheckStatus.PASS if inside > 0 and tilt >= required else CheckStatus.FAIL,
        detail=f"the centre of mass, {height:.4g} mm above the footprint and {inside:.4g} mm "
        f"inside its {edge} edge, leaves it at {tilt:.3g} degrees of tilt, against "
        f"{required:g} ({limit.source})",
        underived=_SUMMED,
    )  # fmt: skip


def _approaches(product: Product, bodies: list[Any]) -> tuple[ClosestApproach, ...]:
    """The least gap between every two top-level items that share no mate or connection."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape  # type: ignore[import-untyped]

    joined = {frozenset((m.place.part, m.on.part)) for m in product.mates}
    for connection in product.connections:
        a = connection.on.rpartition(".")[0]
        b = connection.place.rpartition(".")[0]
        joined.add(frozenset((a, b)))

    def item(path: str) -> str:
        return path.split("/")[1].split("[")[0]

    found = []
    for i, first in enumerate(bodies):
        for second in bodies[i + 1 :]:
            a, b = item(first.path), item(second.path)
            if a == b or frozenset((a, b)) in joined:
                continue
            gauge = BRepExtrema_DistShapeShape(first.shape.wrapped, second.shape.wrapped)
            gauge.Perform()
            if not gauge.IsDone():
                continue
            p, q = gauge.PointOnShape1(1), gauge.PointOnShape2(1)
            mid = tuple(round((u + v) / 2, 3) + 0.0 for u, v in
                        ((p.X(), q.X()), (p.Y(), q.Y()), (p.Z(), q.Z())))  # fmt: skip
            found.append(ClosestApproach(first=first.path, second=second.path,
                                         gap_mm=round(gauge.Value(), 6), at_mm=mid))  # fmt: skip
    return tuple(sorted(found, key=lambda a: a.gap_mm))


def _clearance_entry(approaches: tuple[ClosestApproach, ...], limit: Any) -> ScorecardEntry:
    least = limit.value.to("mm").magnitude
    if not approaches:
        return ScorecardEntry(
            name="clearance", status=CheckStatus.PASS, underived=_SUMMED,
            detail="every two items share a connection, so no pair is gauged",
        )  # fmt: skip
    worst = approaches[0]
    short = [a for a in approaches if a.gap_mm < least]
    where = ", ".join(f"{v:g}" for v in worst.at_mm)
    detail = (f"{worst.first} and {worst.second} come within {worst.gap_mm:.4g} mm at "
              f"({where}) mm, against {least:g} mm ({limit.source})")  # fmt: skip
    if len(short) > 1:
        detail += f"; {len(short)} pairs are closer than that"
    return ScorecardEntry(name="clearance",
                          status=CheckStatus.FAIL if short else CheckStatus.PASS,
                          detail=detail, underived=_SUMMED)  # fmt: skip


def _mobility(product: Product, placed: Any) -> Mobility:
    """Grübler–Kutzbach, M = 6(n − 1 − j) + Σf, over bodies joined rigidly into links.

    Mates and rigid connections join items into one link, except mates between two items a
    declared joint already joins: those place the joint, they do not weld it.
    """
    names = [i.name for i in product.instances]
    parent = {name: name for name in names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    joints = []
    moving = {
        frozenset((c.on.rpartition(".")[0], c.place.rpartition(".")[0]))
        for c in product.connections
        if c.joint is not None and c.joint.kind != "rigid"
    }
    for mate in product.mates:
        # A mate places; between two items a joint joins, it is part of that joint.
        pair = frozenset((mate.place.part, mate.on.part))
        if mate.place.part in parent and mate.on.part in parent and pair not in moving:
            parent[find(mate.place.part)] = find(mate.on.part)
    for connection in product.connections:
        a = connection.on.rpartition(".")[0]
        b = connection.place.rpartition(".")[0]
        joint = connection.joint
        if joint is None or joint.kind == "rigid":
            parent[find(b)] = find(a)
        else:
            joints.append((f"{connection.on} ~ {connection.place}", joint.kind))
    links = len({find(name) for name in names})
    freedoms = sum(_FREEDOMS[kind] for _name, kind in joints)
    count = 6 * (links - 1 - len(joints)) + freedoms
    caveats = []
    if count <= 0:
        caveats.append(f"the count is {count}, which a mechanism with special geometry can "
                       "move despite; it does not show the product cannot move")  # fmt: skip
    axes = [(j.connection, j.point_mm, j.direction) for j in placed.joints
            if j.kind in ("revolute", "cylindrical", "linear")]  # fmt: skip
    for i, (a, pa, da) in enumerate(axes):
        for b, pb, db in axes[i + 1 :]:
            cross = (da[1] * db[2] - da[2] * db[1], da[2] * db[0] - da[0] * db[2],
                     da[0] * db[1] - da[1] * db[0])  # fmt: skip
            if math.hypot(*cross) > 1e-6:
                continue
            gap = [pb[k] - pa[k] for k in range(3)]
            along = sum(gap[k] * da[k] for k in range(3))
            off = math.sqrt(max(0.0, sum(g * g for g in gap) - along * along))
            how = "coincident" if off < 1e-6 else "parallel"
            caveats.append(f"{a} and {b} have {how} axes, which the count does not see; it "
                           "is unreliable for them")  # fmt: skip
    formula = f"M = 6(n − 1 − j) + Σf = 6({links} − 1 − {len(joints)}) + {freedoms} = {count}"
    return Mobility(count=count, bodies=links, formula=formula,
                    joints=tuple(f"{name}: {kind}, {_FREEDOMS[kind]} freedom"
                                 f"{'s' if _FREEDOMS[kind] != 1 else ''}" for name, kind in joints),
                    caveats=tuple(caveats))  # fmt: skip


_G = 9.80665
_TOUCH_MM = 1e-3


class Reaction(StatableModel):
    """A force one body passes down to a support, and where it acts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    support: Named
    force_n: float
    at_mm: tuple[float, float]


class LoadStep(StatableModel):
    """One body on the load path: what it carries, and how its supports carry it on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Named
    carries_n: float
    at_mm: tuple[float, float]
    reactions: tuple[Reaction, ...] = ()
    status: CheckStatus
    note: str = ""


def _overlap(a: Any, b: Any) -> tuple[float, float, float] | None:
    """The plan overlap of two bodies' boxes: its area and centre, or None."""
    x0, x1 = max(a.box_min_mm[0], b.box_min_mm[0]), min(a.box_max_mm[0], b.box_max_mm[0])
    y0, y1 = max(a.box_min_mm[1], b.box_min_mm[1]), min(a.box_max_mm[1], b.box_max_mm[1])
    if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
        return None
    return (x1 - x0) * (y1 - y0), (x0 + x1) / 2, (y0 + y1) / 2


def _load_path(product: Product, placed: Any) -> tuple[list[LoadStep], list[ScorecardEntry]]:
    """Each body's load, carried down to the bodies it rests on and from the lowest to the floor.

    Vertical equilibrium (ΣFz, ΣMx, ΣMy) at each body: one support, or two with the load
    over the line between them, or three not in a line, determine the reactions. More than
    three are reported indeterminate, naming them, unless ``screening.splits`` divides the
    load with its basis; nothing below such a body is evaluated from a guessed share.
    """
    declared = product.screening
    bodies = list(placed.bodies)
    floor = min(b.box_min_mm[2] for b in bodies)
    incoming: dict[str, list[tuple[float, float, float, str]]] = {b.path: [] for b in bodies}
    for body in bodies:
        if body.mass_kg is not None and body.mass_kg > 0:
            x, y, _z = body.center_of_mass_mm
            incoming[body.path].append((body.mass_kg * _G, x, y, "its own weight"))
    for load in declared.loads if declared is not None else ():
        base = f"{product.name}/{load.item}"
        held = [b for b in bodies if b.path == base or b.path.startswith((base + "/", base + "["))]
        if not held:
            raise _refuse(f"a load is on '{load.item}', which is not an item of "
                          f"'{product.name}'", subject="product")  # fmt: skip
        target = held[0]
        force = (load.force.to("N").magnitude if load.force is not None
                 else load.mass.to("kg").magnitude * _G)  # type: ignore[union-attr]  # fmt: skip
        cx = (target.box_min_mm[0] + target.box_max_mm[0]) / 2
        cy = (target.box_min_mm[1] + target.box_max_mm[1]) / 2
        incoming[target.path].append((force, cx, cy, f"the load on {load.item} ({load.source})"))
    splits = {split.body: split for split in (declared.splits if declared is not None else ())}
    unknown: set[str] = set()
    steps: list[LoadStep] = []
    entries: list[ScorecardEntry] = []
    for body in sorted(bodies, key=lambda b: -b.box_max_mm[2]):
        inputs = incoming[body.path]
        total = sum(f for f, _x, _y, _s in inputs)
        if total <= 0:
            continue
        xw = sum(f * x for f, x, _y, _s in inputs) / total
        yw = sum(f * y for f, _x, y, _s in inputs) / total
        supports: list[tuple[str, float, float, Any]] = []
        for other in bodies:
            if other is body or abs(body.box_min_mm[2] - other.box_max_mm[2]) > _TOUCH_MM:
                continue
            patch = _overlap(body, other)
            if patch is not None:
                supports.append((other.path, patch[1], patch[2], other))
        if abs(body.box_min_mm[2] - floor) <= _TOUCH_MM:
            supports.append(("the floor", (body.box_min_mm[0] + body.box_max_mm[0]) / 2,
                             (body.box_min_mm[1] + body.box_max_mm[1]) / 2, body))  # fmt: skip
        upstream = sorted({s for _f, _x, _y, s in inputs if s in unknown})
        status, note, forces = _solve(body, supports, total, xw, yw, splits.get(body.path))
        if upstream:
            status, note, forces = (CheckStatus.NOT_EVALUATED,
                                    f"it carries the load of {', '.join(upstream)}, whose path "
                                    "is not determined", None)  # fmt: skip
        if forces is None:
            unknown.add(body.path)
            # What rests on an undetermined body still loads its supports, by an unknown
            # share: mark them, so nothing below reads its own weight as the whole story.
            for path, _x, _y, _other in supports:
                if path != "the floor":
                    incoming[path].append((0.0, 0.0, 0.0, body.path))
        reactions = tuple(
            Reaction(support=path, force_n=round(f, 6), at_mm=(round(x, 3), round(y, 3)))
            for (path, x, y, _o), f in zip(supports, forces or [0.0] * len(supports), strict=True)
        ) if forces is not None else ()  # fmt: skip
        for reaction in reactions:
            if reaction.support != "the floor":
                incoming[reaction.support].append(
                    (reaction.force_n, reaction.at_mm[0], reaction.at_mm[1], body.path)
                )
        steps.append(LoadStep(body=body.path, carries_n=round(total, 6),
                              at_mm=(round(xw, 3), round(yw, 3)), reactions=reactions,
                              status=status, note=note))  # fmt: skip
        carried = "; ".join(f"{r.force_n:.4g} N to {r.support} at ({r.at_mm[0]:g}, "
                            f"{r.at_mm[1]:g})" for r in reactions)  # fmt: skip
        detail = (f"{body.path} carries {total:.4g} N acting at ({xw:.4g}, {yw:.4g}) mm"
                  + (f": {carried}; ΣFz, ΣMx and ΣMy balance" if reactions else "")
                  + (f"; {note}" if note else ""))  # fmt: skip
        entries.append(ScorecardEntry(
            name=f"load path {body.path}", status=status, detail=detail,
            underived=_SUMMED if status is not CheckStatus.NOT_EVALUATED else None,
            needs=(_need("screening.splits", "how this body's load divides among its supports, "
                         "with the basis", "[]", ()),) if status is CheckStatus.NOT_EVALUATED
            else (),
        ))  # fmt: skip
    return steps, entries


def _solve(
    body: Any,
    supports: list[tuple[str, float, float, Any]],
    total: float,
    xw: float,
    yw: float,
    split: Any,
) -> tuple[CheckStatus, str, list[float] | None]:
    """The reactions at ``supports`` that hold ``total`` acting at (xw, yw), and the verdict."""
    n = len(supports)
    names = [s[0] for s in supports]
    if n == 0:
        return (CheckStatus.NOT_EVALUATED, "nothing beneath it carries it; a path through a "
                "side connection is not followed", None)  # fmt: skip
    if split is not None:
        missing = sorted(set(names) - set(split.shares))
        if missing:
            return (CheckStatus.NOT_EVALUATED, f"its declared split names no share for "
                    f"{', '.join(missing)}", None)  # fmt: skip
        return (CheckStatus.PASS, f"divided as declared ({split.basis}), not by equilibrium",
                [total * split.shares[name] for name in names])  # fmt: skip
    if n > 3:
        listed = ", ".join(names)
        return (CheckStatus.NOT_EVALUATED,
                f"its {n} supports ({listed}) hold it where three would: the path is "
                f"indeterminate, with {n - 3} redundant, and no share is guessed",
                None)  # fmt: skip
    if n == 1:
        _name, x, y, other = supports[0]
        inside = (min(body.box_max_mm[0], other.box_max_mm[0]) + 1e-6 >= xw >=
                  max(body.box_min_mm[0], other.box_min_mm[0]) - 1e-6 and
                  min(body.box_max_mm[1], other.box_max_mm[1]) + 1e-6 >= yw >=
                  max(body.box_min_mm[1], other.box_min_mm[1]) - 1e-6)  # fmt: skip
        if not inside:
            return (CheckStatus.FAIL, f"its load acts outside where it rests on {names[0]}, so "
                    "it would tip", [total])  # fmt: skip
        return CheckStatus.PASS, "", [total]
    if n == 3:
        (_a, x1, y1, _o1), (_b, x2, y2, _o2), (_c, x3, y3, _o3) = supports
        det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        if abs(det) > 1e-9:
            # Barycentric weights of the load's point in the support triangle.
            w2 = ((xw - x1) * (y3 - y1) - (x3 - x1) * (yw - y1)) / det
            w3 = ((x2 - x1) * (yw - y1) - (xw - x1) * (y2 - y1)) / det
            forces = [total * (1 - w2 - w3), total * w2, total * w3]
            lifting = [names[i] for i, f in enumerate(forces) if f < -1e-9]
            if lifting:
                pulled = ", ".join(lifting)
                return (CheckStatus.FAIL, f"its load acts outside its supports: {pulled} would "
                        "have to pull, and lifts off", forces)  # fmt: skip
            return CheckStatus.PASS, "", forces
        supports = [
            supports[0],
            max(supports[1:], key=lambda s: (s[1] - x1) ** 2 + (s[2] - y1) ** 2),
        ]
    (_a, x1, y1, _o1), (_b, x2, y2, _o2) = supports[0], supports[-1]
    span = (x2 - x1) ** 2 + (y2 - y1) ** 2
    t = ((xw - x1) * (x2 - x1) + (yw - y1) * (y2 - y1)) / span if span > 0 else 0.5
    off = abs((x2 - x1) * (yw - y1) - (y2 - y1) * (xw - x1)) / math.sqrt(span) if span else 0.0
    forces = [total * (1 - t), total * t] + [0.0] * (n - 2)
    if off > 1e-6 or not -1e-9 <= t <= 1 + 1e-9:
        return (CheckStatus.FAIL, "its load acts off the line between its supports, so it would "
                "tip", forces)  # fmt: skip
    return CheckStatus.PASS, "", forces


def _rated_from_path(
    product: Product, shelf: Mapping[str, Product], steps: list[LoadStep]
) -> list[ScorecardEntry]:
    """Each purchased component on the load path, checked with the load it carries."""
    from .changes import _definitions, _occurrences
    from .components import Demand, _rating_entries

    used = _occurrences(product, shelf)
    definitions = _definitions(product, shelf)
    by_path = {path: definitions[key] for key, paths in used.items() for path in paths}
    entries = []
    for step in steps:
        definition = by_path.get(step.body)
        record = definition.component if definition is not None else None
        if record is None or record.family != "caster":
            continue
        name = f"load path {step.body}"
        if step.status is CheckStatus.NOT_EVALUATED:
            entries.append(ScorecardEntry(
                name=f"{step.body} caster load", status=CheckStatus.NOT_EVALUATED,
                detail=f"reads '{name}', which is not evaluated: {step.note}",
                needs=(_need("screening.splits", "the share of the load this caster carries",
                             "[]", ()),),
            ))  # fmt: skip
            continue
        demand = Demand(name="load", value=Quantity(magnitude=step.carries_n, unit="N"),
                        source=f"'{name}'")  # fmt: skip
        for entry in _rating_entries(record, (demand,)):
            if entry.name == "caster load":
                entries.append(entry.model_copy(update={
                    "name": f"{step.body} caster load",
                    "detail": f"{entry.detail}; reads '{name}'",
                }))  # fmt: skip
    return entries


class Economy(StatableModel):
    """Assembly economy, advisory: what a reviewer counts before asking to merge parts.

    ``parts`` counts the bodies; ``purchased`` each bought designation with how many the
    product uses; ``merge_candidates`` pairs of made parts joined by mates alone, of one
    material, neither separated for service, by the three part-count questions. None of it
    changes the verdict.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parts: int
    purchased: tuple[tuple[str, int], ...] = ()
    merge_candidates: tuple[str, ...] = ()
    note: str = ""


class CostLine(StatableModel):
    """One made part, placeholder or component, and the unit price it is costed at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    amount: float | None
    currency: str | None = None
    source: Provenance | None = None
    as_of: date | None = None


class NodeCost(StatableModel):
    """A product node's screening cost, rolled up from the items under it.

    ``priced_total`` sums the priced items when they share one currency. ``complete`` is
    true only when every item under the node is priced, in one currency; otherwise
    ``unpriced`` names the items with no price, ``currencies`` lists more than one, and
    the total is a partial sum, never the node's cost.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    complete: bool
    priced_total: float | None
    currency: str | None
    items: int = Field(ge=0)
    unpriced: tuple[str, ...] = ()
    currencies: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _labeled(self) -> NodeCost:
        whole = not self.unpriced and len(self.currencies) <= 1 and self.items > 0
        if self.complete != whole:
            raise _refuse(f"node {self.path} is labeled complete={self.complete} with "
                          f"{len(self.unpriced)} unpriced items in {len(self.currencies)} "
                          "currencies", subject="product")  # fmt: skip
        return self

    def __str__(self) -> str:
        if self.priced_total is None:
            return f"{self.path}: no total, priced in {', '.join(self.currencies) or 'nothing'}"
        total = f"{self.priced_total:,.2f} {self.currency}"
        if self.complete:
            return f"{self.path}: {total} over {self.items} items"
        return (f"{self.path}: incomplete, {total} for the priced items; no price for "
                f"{', '.join(self.unpriced)}")  # fmt: skip


def _costs(product: Product, shelf: Mapping[str, Product]) -> tuple[list[CostLine], list[NodeCost]]:
    """Each costed item's unit price, and each product node's total of the items under it."""
    from .product import product_tree

    lines: list[CostLine] = []
    nodes: list[NodeCost] = []

    def visit(node: Any, owner: Product) -> list[CostLine]:
        definitions = {d.id: d for d in owner.definitions}
        at = len(nodes)
        under: list[CostLine] = []
        for child in node.children:
            definition = definitions[child.definition]
            if child.kind == "product":
                under += visit(child, shelf[definition.product or ""])
                continue
            if child.kind == "reference":
                continue
            record = definition.component
            price = record.price if record is not None else definition.price
            line = (CostLine(path=child.path, amount=None) if price is None else
                    CostLine(path=child.path, amount=price.amount, currency=price.currency,
                             source=price.source, as_of=price.date))  # fmt: skip
            lines.append(line)
            under.append(line)
        currencies = tuple(sorted({line.currency for line in under if line.currency}))
        unpriced = tuple(line.path for line in under if line.amount is None)
        one = currencies[0] if len(currencies) == 1 else None
        total = sum(line.amount or 0.0 for line in under) if one is not None else None
        nodes.insert(at, NodeCost(
            path=node.path, complete=not unpriced and len(currencies) <= 1 and bool(under),
            priced_total=total, currency=one, items=len(under), unpriced=unpriced,
            currencies=currencies,
        ))  # fmt: skip
        return under

    visit(product_tree(product, library=shelf), product)
    return lines, nodes


def _pairs(product: Product) -> dict[frozenset[str], list[Any]]:
    """The top-level items joined by mates, each pair with its mates."""
    joined: dict[frozenset[str], list[Any]] = {}
    for mate in product.mates:
        joined.setdefault(frozenset((mate.place.part, mate.on.part)), []).append(mate)
    return joined


def _item(path: str) -> str:
    return path.split("/")[1].split("[")[0]


def _material(definition: Any) -> str | None:
    if definition is None or definition.spec is None:
        return None
    return str((dict(definition.spec).get("material") or {}).get("ref") or "") or None


def _thermal(product: Product, placed: Any) -> list[ScorecardEntry]:
    """Differential growth across each connection of two catalog parts of different materials."""
    from .geometry import build_spec
    from .spec import parse_spec

    definitions = {d.id: d for d in product.definitions}
    of = {i.name: definitions[i.item] for i in product.instances}
    declared = product.screening.thermal if product.screening is not None else None
    coefficients = {e.material: e for e in declared.coefficients} if declared else {}
    entries = []
    for pair, mates in _pairs(product).items():
        if len(pair) != 2 or not pair <= set(of):
            continue
        a, b = sorted(pair)
        ma, mb = _material(of[a]), _material(of[b])
        if ma is None or mb is None or ma == mb:
            continue
        name = f"thermal {a} ~ {b}"
        need = _need("screening.thermal", "the temperature range, the slip a connection allows, "
                     "and each material's expansion coefficient, cited", "[]", ())  # fmt: skip
        if declared is None:
            entries.append(ScorecardEntry(
                name=name, status=CheckStatus.NOT_EVALUATED, needs=(need,),
                detail=f"{a} ({ma}) meets {b} ({mb}) and no temperature range is declared",
            ))  # fmt: skip
            continue
        missing = [m for m in (ma, mb) if m not in coefficients]
        if missing:
            entries.append(ScorecardEntry(name=name, status=CheckStatus.NOT_EVALUATED,
                                          detail=f"no expansion coefficient is declared for "
                                          f"{', '.join(missing)}", needs=(need,)))  # fmt: skip
            continue
        span, how = 0.0, ""
        for mate in mates:
            if mate.kind == "hole_pattern" and len(mate.place.holes) >= 2:
                built = build_spec(parse_spec(dict(of[mate.place.part].spec or {})))
                where = {f.tag: f.position_mm for f in built.features}
                points = [where[t] for t in mate.place.holes if t in where]
                span = max((math.dist(p, q) for p in points for q in points), default=0.0)
                how = f"between the outermost of {len(points)} mated holes"
        if not span:
            first = next(x for x in placed.bodies if _item(x.path) == a)
            second = next(x for x in placed.bodies if _item(x.path) == b)
            lo = [max(first.box_min_mm[i], second.box_min_mm[i]) for i in (0, 1)]
            hi = [min(first.box_max_mm[i], second.box_max_mm[i]) for i in (0, 1)]
            span, how = max(hi[0] - lo[0], hi[1] - lo[1], 0.0), "across where they meet"
        ea, eb = coefficients[ma], coefficients[mb]
        alpha_a = ea.coefficient.to("1/K").magnitude
        alpha_b = eb.coefficient.to("1/K").magnitude
        rise = declared.range.to("K").magnitude
        growth = abs(alpha_a - alpha_b) * rise * span
        slip = declared.slip.to("mm").magnitude
        entries.append(ScorecardEntry(
            name=name, status=CheckStatus.PASS if growth <= slip else CheckStatus.FAIL,
            detail=f"{growth:.3g} mm of differential growth over {span:.4g} mm {how} and "
            f"{rise:g} K, against {slip:g} mm of slip ({declared.source}); {ma} "
            f"{alpha_a * 1e6:.4g}e-6/K ({ea.source}), {mb} {alpha_b * 1e6:.4g}e-6/K ({eb.source})",
            underived=_SUMMED,
        ))  # fmt: skip
    return entries


def _economy(product: Product, shelf: Mapping[str, Product], bodies: list[Any]) -> Economy:
    """Part count, bought designations, and pairs a designer might merge."""
    from .product import product_tree

    counts: dict[str, int] = {}
    definitions: dict[str, Any] = {}
    for current in (product, *shelf.values()):
        for definition in current.definitions:
            definitions.setdefault(definition.id, definition)
    for node in product_tree(product, library=shelf).walk()[1:]:
        if node.source.value != "buy" or node.kind == "product":
            continue
        record = definitions[node.definition].component
        key = (f"{record.manufacturer} {record.part_number}" if record is not None
               else node.part_number)  # fmt: skip
        counts[key] = counts.get(key, 0) + 1
    of = {i.name: next(d for d in product.definitions if d.id == i.item) for i in product.instances}
    moving = {
        frozenset((c.on.rpartition(".")[0], c.place.rpartition(".")[0]))
        for c in product.connections
        if c.joint is not None and c.joint.kind != "rigid"
    }
    serviced = set(product.screening.serviced) if product.screening is not None else set()
    candidates = []
    for pair in _pairs(product):
        if len(pair) != 2 or pair in moving or pair & serviced or not pair <= set(of):
            continue
        a, b = sorted(pair)
        ma, mb = _material(of[a]), _material(of[b])
        made = all(of[x].identity.source.value == "make" for x in (a, b))
        if made and ma is not None and ma == mb:
            candidates.append(f"{a} + {b}: one material ({ma}), joined without relative "
                              "motion, neither separated for service")  # fmt: skip
    return Economy(
        parts=len(bodies), purchased=tuple(sorted(counts.items())),
        merge_candidates=tuple(candidates),
        note="fasteners and the tools they need are not counted: a product declares no "
        "fastener hardware yet",
    )  # fmt: skip


def _chains(product: Product) -> list[ScorecardEntry]:
    """Each declared stack-up through the product's items, judged on its worst case."""
    from .spec import parse_spec
    from .spec.ir import ChainAnalysis
    from .tolerance import ResolvedTolerance, StackContributor, StackUp, general_tolerance

    declared = product.screening.chains if product.screening is not None else ()
    definitions = {d.id: d for d in product.definitions}
    of = {i.name: definitions[i.item] for i in product.instances}
    joints = {m.id for m in product.mates} | {f"{c.on}~{c.place}" for c in product.connections}
    entries = []
    for chain in declared:
        contributors, notes = [], []
        for index, link in enumerate(chain.links, start=1):
            if link.connection is not None:
                if link.connection not in joints:
                    raise _refuse(f"chain {chain.name} link {index} names the connection "
                                  f"{link.connection!r}, which the product does not have",
                                  subject="product")  # fmt: skip
                half = link.allowance.to("mm").magnitude  # type: ignore[union-attr]
                band = ResolvedTolerance(
                    nominal=Quantity(magnitude=0.0, unit="mm"),
                    upper=Quantity(magnitude=half, unit="mm"),
                    lower=Quantity(magnitude=-half, unit="mm"),
                    label=f"±{half:g} mm", source=link.source,
                )  # fmt: skip
                contributors.append(StackContributor(name=link.connection, tolerance=band,
                                                     direction=link.direction))  # fmt: skip
                continue
            item = str(link.item)
            if item not in of:
                raise _refuse(f"chain {chain.name} link {index} names '{item}', which is not an "
                              f"item of '{product.name}'", subject="product")  # fmt: skip
            definition = of[item]
            spec = parse_spec(dict(definition.spec)) if definition.spec is not None else None
            stated = {d.tag: d for d in spec.dimensions} if spec is not None else {}
            name = f"{item}.{link.dimension}"
            if link.dimension in stated:
                band = stated[str(link.dimension)].resolve()
            else:
                if link.nominal is None:
                    raise _refuse(
                        f"chain {chain.name} link {index}: {item} declares no tolerance for "
                        f"'{link.dimension}', and the link states no nominal to take the "
                        "general tolerance on", subject="product",
                    )  # fmt: skip
                grade = spec.general_tolerance_class() if spec is not None else "m"
                general = general_tolerance(link.nominal, grade)
                dev = general.deviation.to("mm").magnitude
                band = ResolvedTolerance(
                    nominal=link.nominal, upper=Quantity(magnitude=dev, unit="mm"),
                    lower=Quantity(magnitude=-dev, unit="mm"),
                    label=f"±{dev:g} mm general", source=general.source,
                )  # fmt: skip
                notes.append(f"{name} takes the general tolerance ±{dev:g} mm "
                             f"({general.source}), as the item declares none")  # fmt: skip
            contributors.append(StackContributor(name=name, tolerance=band,
                                                 direction=link.direction))  # fmt: skip
        stack = StackUp(contributors=tuple(contributors))
        analysis = ChainAnalysis(name=chain.name, required_min=chain.required_min,
                                 required_max=chain.required_max, worst_case=stack.worst_case(),
                                 rss=stack.rss())  # fmt: skip
        detail = str(analysis)
        governing = analysis.worst_case.contributions[0]
        detail += f"; the worst case is governed by {governing.name} ({governing.share:.0%})"
        low, high = (q.to("mm").magnitude for q in (analysis.rss.lower, analysis.rss.upper))
        fits = "fits" if analysis.rss_passes else "does not fit"
        detail += f"; RSS +{low:.3f} to +{high:.3f} mm, which {fits}"
        shares = ", ".join(f"{c.name} {c.share:.0%}" for c in analysis.worst_case.contributions)
        detail += f"; each link's share of the worst case: {shares}"
        if chain.samples is not None and chain.seed is not None:
            run = stack.monte_carlo(samples=chain.samples, seed=chain.seed)
            mean, sigma = run.mean.to("mm").magnitude, run.std.to("mm").magnitude
            detail += (f"; Monte Carlo over {run.samples} samples, seed {chain.seed}: mean "
                       f"{mean:.4g} mm, σ {sigma:.3g} mm")  # fmt: skip
        if notes:
            detail += "; " + "; ".join(notes)
        entries.append(ScorecardEntry(
            name=f"stack-up: {chain.name}",
            status=CheckStatus.PASS if analysis.worst_case_passes else CheckStatus.FAIL,
            detail=detail,
            underived=Underived(kind=DerivationAbsence.NUMERIC_RESULT,
                                reason="the stack-up itself: a sum or root-sum-square over the "
                                "chain's links, one term per link"),
        ))  # fmt: skip
    return entries


ProductScreening.model_rebuild()
