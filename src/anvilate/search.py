"""Search: the best design found under a stated budget, never "the optimum".

A sweep (:mod:`anvilate.explore`) evaluates a grid or a low-discrepancy sample and draws the
exact front over what it saw. A search spends the same kind of budget where it matters: a
seeded evolutionary search over mixed variables, or a derivative-free local refinement from
a declared start. It keeps every rule a sweep keeps:

- **Feasibility is the scorecard's.** The caller's evaluator returns the objective and a
  card; a card that does not pass is infeasible, and a check that did not run counts as not
  passing. Nothing here estimates a value.
- **The same study, seed and code give the same points in the same order**, on one worker
  or several: every candidate of a generation is drawn before any is evaluated, and results
  are committed in draw order.
- **Every evaluated point is recorded**, feasible or not, with what stopped it.

The result is the best feasible design found, and it is checked: each variable is moved a
declared step either way (a choice to its adjacent table entries) and every neighbor is
evaluated for real. A feasible neighbor that is better is named, and the result is then
labeled *not locally confirmed*. The word "optimal" appears nowhere in what this returns.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel
from .explore import ObjectiveSense, StudyEvaluation
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard

__all__ = [
    "VariableKind",
    "SearchStrategy",
    "SearchVariable",
    "SearchStudy",
    "SearchPoint",
    "SearchResult",
    "BEST_FOUND",
    "run_search",
    "violation",
    "SearchDiff",
    "TABLES",
    "table_choice",
    "search_diff",
    "apply_search_diff",
]

_SOURCE = "the search study: its variables, objective, strategy, seed and budget"

#: What a search result is called, wherever it is rendered.
BEST_FOUND = "the best design found under the stated budget"

# Differential evolution's two constants, fixed so a study's seed alone decides its points.
_WEIGHT, _CROSSOVER = 0.5, 0.9


class _Stream:
    """SplitMix64 (Steele, Lea and Flood, 2014): a seeded stream of 64-bit integers.

    Written out rather than taken from :mod:`random`, whose ``sample`` and ``randrange``
    algorithms have changed between Python releases: the same study and seed must give the
    same points on every interpreter this package supports, not only on the one it ran on.
    """

    _MASK = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        self._state = seed & self._MASK

    def _next(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & self._MASK
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self._MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self._MASK
        return z ^ (z >> 31)

    def unit(self) -> float:
        """A float in [0, 1), from the top 53 bits."""
        return (self._next() >> 11) / float(1 << 53)

    def below(self, n: int) -> int:
        """An integer in [0, n), by rejection so every value is equally likely."""
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            drawn = self._next()
            if drawn < limit:
                return drawn % n

    def distinct(self, pool: Sequence[int], k: int) -> list[int]:
        """``k`` distinct members of ``pool``, by a partial Fisher-Yates shuffle."""
        items = list(pool)
        for i in range(k):
            j = i + self.below(len(items) - i)
            items[i], items[j] = items[j], items[i]
        return items[:k]


class _SearchInputError(RefusalError, ValueError):
    """A search input that cannot be used without correction."""


def _refuse(message: str, *, subject: str) -> _SearchInputError:
    return _SearchInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),)
    )


class VariableKind(StrEnum):
    """What values a variable takes."""

    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CHOICE = "choice"


class SearchStrategy(StrEnum):
    """How the search moves: a population over the whole box, or a refinement from a start."""

    EVOLUTIONARY = "evolutionary"
    LOCAL = "local"


class SearchVariable(StatableModel):
    """One variable: continuous or integer between bounds, or a choice from a sourced list.

    A choice takes only the values its list holds, and the list must say where it comes
    from (``source``), so an invented stock size cannot enter a design. ``step`` is how far
    the neighborhood check moves a continuous variable either way; it defaults to 1% of the
    range. An integer moves by one, a choice to its adjacent entries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    kind: VariableKind = VariableKind.CONTINUOUS
    low: float | None = None
    high: float | None = None
    choices: tuple[float, ...] = ()
    source: Provenance | None = None
    step: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    # For a choice read from a bundled table: the table rows each choice comes from, in
    # the same order as ``choices``, so a result can cite the row it chose.
    rows: tuple[Named, ...] = ()

    @model_validator(mode="after")
    def _well_formed(self) -> SearchVariable:
        if self.kind is VariableKind.CHOICE:
            if len(self.choices) < 2 or any(not isfinite(c) for c in self.choices):
                raise _refuse(f"{self.name}: a choice needs at least two finite values",
                              subject="choices")  # fmt: skip
            if list(self.choices) != sorted(set(self.choices)):
                raise _refuse(f"{self.name}: list the choices once each, in increasing order, "
                              "so adjacent entries are neighbors", subject="choices")  # fmt: skip
            if self.source is None:
                raise _refuse(
                    f"{self.name}: the choices {list(self.choices)} name no source; cite the "
                    "table or catalogue each value comes from, or a design can be built on a "
                    "size nobody stocks", subject="source",
                )  # fmt: skip
            if self.rows and len(self.rows) != len(self.choices):
                raise _refuse(f"{self.name}: rows name the table row of each choice, one per "
                              "choice", subject="rows")  # fmt: skip
            return self
        if self.choices or self.rows:
            raise _refuse(f"{self.name}: choices belong to a choice variable",
                          subject="choices")  # fmt: skip
        if (
            self.low is None
            or self.high is None
            or not (isfinite(self.low) and isfinite(self.high))
        ):
            raise _refuse(f"{self.name}: give finite low and high bounds", subject="low, high")
        if self.low >= self.high:
            raise _refuse(f"{self.name}: low ({self.low}) must be below high ({self.high})",
                          subject="low, high")  # fmt: skip
        if self.kind is VariableKind.INTEGER and not (
            self.low.is_integer() and self.high.is_integer()
        ):
            raise _refuse(f"{self.name}: an integer variable's bounds are whole numbers",
                          subject="low, high")  # fmt: skip
        return self

    # The search works in one coordinate per variable: the value itself, or a choice's index.
    def _span(self) -> tuple[float, float]:
        if self.kind is VariableKind.CHOICE:
            return 0.0, float(len(self.choices) - 1)
        return float(self.low or 0.0), float(self.high or 0.0)

    def _snap(self, coordinate: float) -> float:
        low, high = self._span()
        clipped = min(max(coordinate, low), high)
        return float(round(clipped)) if self.kind is not VariableKind.CONTINUOUS else clipped

    def _value(self, coordinate: float) -> float:
        return self.choices[int(coordinate)] if self.kind is VariableKind.CHOICE else coordinate

    def _coordinate(self, value: float) -> float:
        if self.kind is VariableKind.CHOICE:
            if value not in self.choices:
                raise _refuse(f"{self.name}: {value} is not one of its choices "
                              f"{list(self.choices)}", subject="starts")  # fmt: skip
            return float(self.choices.index(value))
        return self._snap(value)

    def _neighbors(self, coordinate: float) -> tuple[float, ...]:
        low, high = self._span()
        if self.kind is VariableKind.CONTINUOUS:
            step = self.step if self.step is not None else (high - low) / 100
        else:
            step = 1.0
        return tuple(dict.fromkeys(
            c for c in (self._snap(coordinate - step), self._snap(coordinate + step))
            if c != coordinate
        ))  # fmt: skip


class SearchStudy(StatableModel):
    """A declared search: the variables, the one objective, the strategy, seed and budget.

    ``evaluations`` is the budget for the search itself; the neighborhood check runs after
    it and its evaluations are counted separately, so the check is never what the budget
    cut short. ``population`` is the evolutionary search's size; ``start`` is where a local
    refinement begins, and is required for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    variables: tuple[SearchVariable, ...] = Field(min_length=1, max_length=64)
    objective: Named
    sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    strategy: SearchStrategy = SearchStrategy.EVOLUTIONARY
    seed: int = Field(default=0, ge=0)
    evaluations: int = Field(ge=4, le=1_000_000)
    population: int = Field(default=20, ge=4, le=1000)
    start: FrozenMap[str, float] | None = None

    @model_validator(mode="after")
    def _coherent(self) -> SearchStudy:
        names = [v.name for v in self.variables]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise _refuse(f"variables {twice} are declared twice", subject="variables")
        if self.strategy is SearchStrategy.LOCAL:
            if self.start is None:
                raise _refuse("a local refinement starts from a declared design; give start",
                              subject="start")  # fmt: skip
            if any(v.kind is not VariableKind.CONTINUOUS for v in self.variables):
                raise _refuse("a local refinement moves continuous variables only; search "
                              "integer and choice variables evolutionarily",
                              subject="strategy")  # fmt: skip
        if self.start is not None and set(self.start) != set(names):
            raise _refuse(f"start gives {sorted(self.start)}; it must give every variable "
                          f"{sorted(names)}", subject="start")  # fmt: skip
        return self


class SearchPoint(StatableModel):
    """One evaluated design, in the order it was committed to the record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0)
    origin: str = Field(pattern=r"^(start|initial|offspring|refinement|neighbor)$")
    values: FrozenMap[str, float]
    objective: float
    status: CheckStatus
    feasible: bool
    violation: float = Field(ge=0)
    governing_check: str | None = None


class SearchResult(BaseModel):
    """Every point the search evaluated, the best feasible one, and its neighborhood.

    A plain model, like the sweep's ``StudyResult``: a search records every point it
    evaluated, thousands of them, which is more than a tool result may carry; a surface
    returning one summarizes it.

    ``best`` is ``None`` when no feasible design was found. ``history`` is the best
    feasible objective after each search evaluation (``None`` until one is found).
    ``confirmed`` is False when a neighbor of the best is feasible and better, which
    ``better_neighbor`` names. ``exhausted`` says the evaluation budget ended the search.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    study: SearchStudy
    points: tuple[SearchPoint, ...]
    best: int | None = None
    history: tuple[float | None, ...] = ()
    neighbors: tuple[int, ...] = ()
    confirmed: bool = False
    better_neighbor: int | None = None
    exhausted: bool = True

    @property
    def label(self) -> str:
        """What the result is, in the only words it is allowed: never "optimal"."""
        if self.best is None:
            return f"no feasible design found in {len(self.history)} evaluations"
        state = "locally confirmed" if self.confirmed else "not locally confirmed"
        return f"{BEST_FOUND} ({len(self.history)} evaluations), {state}"

    def cited(self, index: int) -> tuple[str, ...]:
        """For each table-bound choice in point ``index``, the value and the row it is."""
        point = self.points[index]
        return tuple(
            f"{v.name} = {point.values[v.name]:g}: {v.rows[v.choices.index(point.values[v.name])]} "
            f"[{v.source}]"
            for v in self.study.variables if v.rows
        )  # fmt: skip

    def __str__(self) -> str:
        lines = [f"{self.study.name}: {self.label}"]
        if self.best is not None:
            point = self.points[self.best]
            values = ", ".join(f"{k}={v:g}" for k, v in point.values.items())
            lines.append(f"  {self.study.objective} = {point.objective:g} at {values}; "
                         f"governing: {point.governing_check}")  # fmt: skip
            lines.extend(f"  {line}" for line in self.cited(self.best))
        if self.better_neighbor is not None:
            better = self.points[self.better_neighbor]
            values = ", ".join(f"{k}={v:g}" for k, v in better.values.items())
            lines.append(f"  a feasible neighbor is better: {self.study.objective} = "
                         f"{better.objective:g} at {values}")  # fmt: skip
        return "\n".join(lines)


def violation(card: Scorecard) -> float:
    """How far a card is from passing: the summed shortfall of its failing safety factors,
    plus one for each check that failed with no factor or did not run. Zero when it passes."""
    total = 0.0
    for entry in card.entries:
        if entry.status is CheckStatus.FAIL:
            computed, required = entry.safety_factor, entry.required_safety_factor
            if computed is not None and required and computed >= 0:
                total += max(0.0, 1.0 - computed / required) or 1e-12
            else:
                total += 1.0
        elif entry.status is CheckStatus.NOT_EVALUATED:
            total += 1.0
    return total


_PASSING = (
    CheckStatus.PASS,
    CheckStatus.OVER_MARGIN,
    CheckStatus.WARNING,
    CheckStatus.OUT_OF_DEPTH,
)


def run_search(
    study: SearchStudy,
    evaluate: Callable[[Mapping[str, float]], StudyEvaluation],
    *,
    starts: Sequence[Mapping[str, float]] = (),
    workers: int = 1,
) -> SearchResult:
    """Search ``study`` through the caller's ``evaluate`` and check the best design's neighbors.

    ``starts`` are designs to begin from, evaluated first: the base design, and the design
    its inverse repairs propose, when the caller has one. ``workers`` evaluates a batch in
    parallel; the record does not depend on it.
    """
    if not isinstance(study, SearchStudy):
        raise _refuse("study must be a SearchStudy", subject="study")
    if not callable(evaluate):
        raise _refuse("evaluate is the function from a design to its StudyEvaluation",
                      subject="evaluate")  # fmt: skip
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise _refuse(f"workers is a whole number of at least 1; got {workers!r}",
                      subject="workers")  # fmt: skip
    if isinstance(starts, Mapping):
        raise _refuse("starts is a list of designs; wrap a single one in a list",
                      subject="starts")  # fmt: skip
    variables = study.variables
    sign = 1.0 if study.sense is ObjectiveSense.MINIMIZE else -1.0
    rng = _Stream(study.seed)
    points: list[SearchPoint] = []
    history: list[float | None] = []
    best: int | None = None

    def better(a: SearchPoint, b: SearchPoint) -> bool:
        """Deb's rules: feasible beats infeasible; then the objective; else less violation."""
        if a.feasible != b.feasible:
            return a.feasible
        if a.feasible:
            return sign * a.objective < sign * b.objective
        return a.violation < b.violation

    def evaluated(batch: list[tuple[float, ...]], origin: str, *, count: bool) -> list[int]:
        nonlocal best
        designs = [{v.name: v._value(c) for v, c in zip(variables, coords, strict=True)}
                   for coords in batch]  # fmt: skip
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(evaluate, designs))
        else:
            results = [evaluate(design) for design in designs]
        indices = []
        for design, result in zip(designs, results, strict=True):
            if not isinstance(result, StudyEvaluation):
                raise _refuse("evaluate must return a StudyEvaluation", subject="evaluate")
            if study.objective not in result.objectives:
                raise _refuse(f"evaluate returned no value for the objective "
                              f"{study.objective!r}; got {sorted(result.objectives)}",
                              subject="evaluate")  # fmt: skip
            value = result.objectives[study.objective]
            if not isfinite(value):
                raise _refuse(f"evaluate returned {value} for {study.objective!r} at "
                              f"{design}; an objective is a finite number",
                              subject="evaluate")  # fmt: skip
            card = result.scorecard
            governing = card.governing()
            point = SearchPoint(
                index=len(points), origin=origin, values=design, objective=value,
                status=card.status, feasible=card.status in _PASSING,
                violation=violation(card),
                governing_check=None if governing is None else governing.name,
            )  # fmt: skip
            points.append(point)
            indices.append(point.index)
            if count:
                if point.feasible and (best is None or better(point, points[best])):
                    best = point.index
                history.append(None if best is None else points[best].objective)
        return indices

    def coords_of(design: Mapping[str, float]) -> tuple[float, ...]:
        missing = sorted({v.name for v in variables} - set(design))
        if missing:
            raise _refuse(f"a start design gives no value for {missing}", subject="starts")
        return tuple(v._coordinate(float(design[v.name])) for v in variables)

    budget = study.evaluations
    seeds = [coords_of(design) for design in (*((study.start,) if study.start else ()), *starts)]
    seeds = seeds[:budget]
    seeded = evaluated(seeds, "start", count=True) if seeds else []

    if study.strategy is SearchStrategy.EVOLUTIONARY:
        population = [points[i] for i in seeded][: study.population]
        fill = min(study.population - len(population), budget - len(history))
        draws = [
            tuple(
                v._snap(lo + (hi - lo) * rng.unit()) for v in variables for lo, hi in (v._span(),)
            )
            for _ in range(fill)
        ]
        population += [points[i] for i in evaluated(draws, "initial", count=True)]
        while len(history) < budget and len(population) >= 4:
            trials = []
            for i in range(len(population)):
                if len(history) + len(trials) >= budget:
                    break
                a, b, c = rng.distinct([j for j in range(len(population)) if j != i], 3)
                forced = rng.below(len(variables))
                base = coords_of(population[i].values)
                ca, cb, cc = (coords_of(population[k].values) for k in (a, b, c))
                trial = tuple(
                    v._snap(ca[d] + _WEIGHT * (cb[d] - cc[d]))
                    if (d == forced or rng.unit() < _CROSSOVER) else base[d]
                    for d, v in enumerate(variables)
                )  # fmt: skip
                trials.append((i, trial))
            made = evaluated([t for _, t in trials], "offspring", count=True)
            for (i, _), index in zip(trials, made, strict=True):
                if not better(population[i], points[index]):
                    population[i] = points[index]
    else:
        current = points[seeded[0]]
        steps = [(v._span()[1] - v._span()[0]) / 10 for v in variables]
        floor = [(v._span()[1] - v._span()[0]) * 1e-6 for v in variables]
        while len(history) < budget and any(s > f for s, f in zip(steps, floor, strict=True)):
            moved = False
            for d, v in enumerate(variables):
                for direction in (-1.0, 1.0):
                    if len(history) >= budget:
                        break
                    coords = list(coords_of(current.values))
                    coords[d] = v._snap(coords[d] + direction * steps[d])
                    (index,) = evaluated([tuple(coords)], "refinement", count=True)
                    if better(points[index], current):
                        current, moved = points[index], True
                        break
            if not moved:
                steps = [s / 2 for s in steps]

    exhausted = len(history) >= budget
    neighbors: tuple[int, ...] = ()
    confirmed, better_neighbor = False, None
    if best is not None:
        center = coords_of(points[best].values)
        batch = []
        for d, v in enumerate(variables):
            for moved in v._neighbors(center[d]):
                coords = list(center)
                coords[d] = moved
                batch.append(tuple(coords))
        neighbors = tuple(evaluated(batch, "neighbor", count=False))
        winners = [i for i in neighbors if points[i].feasible and better(points[i], points[best])]
        if winners:
            better_neighbor = min(winners, key=lambda i: sign * points[i].objective)
        confirmed = not winners
    return SearchResult(
        study=study, points=tuple(points), best=best, history=tuple(history),
        neighbors=neighbors, confirmed=confirmed, better_neighbor=better_neighbor,
        exhausted=exhausted,
    )  # fmt: skip


class SearchDiff(StatableModel):
    """A search result as a proposed edit: each variable's base value and found value.

    Variables are named by their path in the Design Spec document (``element_params.
    thickness``). Nothing changes until :func:`apply_search_diff` is called; the diff
    carries the study, its seed and the digest of its record, so the edit can say where
    it came from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    study: Named
    seed: int = Field(ge=0)
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    changes: tuple[tuple[Named, float, float], ...] = ()

    def __str__(self) -> str:
        if not self.changes:
            return f"{self.study}: the best design found is the base design; nothing to apply"
        moved = "; ".join(f"{path}: {old:g} -> {new:g}" for path, old, new in self.changes)
        return f"{self.study} (seed {self.seed}) proposes {moved}"


def _record_digest(result: SearchResult) -> str:
    from .attestation import canonical_json, sha256_hex

    return sha256_hex(canonical_json(result.model_dump(mode="json")).encode("utf-8"))


def search_diff(result: SearchResult, base: Mapping[str, float]) -> SearchDiff:
    """The edit ``result`` proposes against ``base``, the variables' values in the base
    document. Refused when the search found no feasible design: there is nothing to apply."""
    if not isinstance(result, SearchResult):
        raise _refuse("result must be a SearchResult from run_search", subject="result")
    if result.best is None:
        raise _refuse(f"{result.study.name} found no feasible design, so it proposes no edit",
                      subject="result")  # fmt: skip
    found = result.points[result.best].values
    missing = sorted(set(found) - set(base))
    if missing:
        raise _refuse(f"base gives no value for {missing}; give each variable's value in the "
                      "base document", subject="base")  # fmt: skip
    changes = tuple((name, float(base[name]), value) for name, value in found.items()
                    if float(base[name]) != value)  # fmt: skip
    return SearchDiff(study=result.study.name, seed=result.study.seed,
                      record_sha256=_record_digest(result), changes=changes)  # fmt: skip


def apply_search_diff(document: Mapping[str, object], diff: SearchDiff) -> dict[str, object]:
    """``document`` (a Design Spec as data) with ``diff`` applied, and the edit recorded.

    Each path is set to its found value; a quantity written as ``{magnitude, unit}`` keeps
    its unit. The document's ``study_derived`` gains one entry naming the study, its seed,
    its record digest and the paths it changed. A path the document does not hold is
    refused: a study can only move a value the document states.
    """
    import copy

    if not isinstance(diff, SearchDiff):
        raise _refuse("diff must be a SearchDiff from search_diff", subject="diff")
    if not isinstance(document, Mapping):
        raise _refuse("document is a Design Spec as data", subject="document")
    edited = copy.deepcopy(dict(document))
    for path, _old, new in diff.changes:
        *parents, leaf = path.split(".")
        node: Any = edited
        for key in parents:
            node = node.get(key) if isinstance(node, dict) else None
        if not isinstance(node, dict) or leaf not in node:
            raise _refuse(f"the document holds no value at {path}; a study moves a value the "
                          "document states", subject="diff")  # fmt: skip
        held = node[leaf]
        node[leaf] = (
            {**held, "magnitude": new} if isinstance(held, dict) and "magnitude" in held else new
        )
    if diff.changes:
        record = {"study": diff.study, "seed": diff.seed, "record_sha256": diff.record_sha256,
                  "changed": [path for path, _old, _new in diff.changes]}  # fmt: skip
        edited["study_derived"] = [*list(edited.get("study_derived") or ()), record]
    return edited


#: The bundled tables a choice variable can be bound to, and the numeric fields each has.
TABLES: dict[str, tuple[str, ...]] = {
    "bearings": ("bore", "outer_diameter", "width"),
    "nema_frames": ("faceplate_width", "bolt_spacing", "pilot_diameter"),
}


def table_choice(name: str, *, table: str, field: str, step: float | None = None) -> SearchVariable:
    """A choice variable over every value ``field`` takes in the bundled ``table``.

    The source is the table's own dataset record (name, version and the standard it was
    read from), and each value carries the rows that hold it (``6005, 6205`` for a 25 mm
    bore), so a result cites the row it chose. Values are in the table's unit, millimetres
    for both tables today. A table or field that does not exist is refused, naming the
    ones that do.
    """
    from importlib.resources import files

    from ._models import parse_yaml

    if table not in TABLES:
        raise _refuse(f"no bundled table is named {table!r}; the tables a choice can bind to "
                      f"are {sorted(TABLES)}", subject="table")  # fmt: skip
    if field not in TABLES[table]:
        raise _refuse(f"table {table!r} has no numeric field {field!r}; it has "
                      f"{list(TABLES[table])}", subject="field")  # fmt: skip
    text = (files("anvilate.standards") / "data" / f"{table}.yaml").read_text("utf-8")
    document = parse_yaml(text)
    records = document["bearings"] if table == "bearings" else document["frames"]
    found: dict[float, list[str]] = {}
    for row, record in records.items():
        cell = record[field]
        value = float(cell["quantity"]["magnitude"] if isinstance(cell, dict) else cell)
        found.setdefault(value, []).append(str(row))
    dataset = document["dataset"]
    source = (f"{table}.yaml ({dataset['name']} {dataset['version']}), "
              f"{dataset['source']}: {field}")  # fmt: skip
    values = sorted(found)
    return SearchVariable(name=name, kind=VariableKind.CHOICE, choices=tuple(values),
                          source=source, step=step,
                          rows=tuple(", ".join(found[v]) for v in values))  # fmt: skip
