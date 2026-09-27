"""Compile prose into validated Spec IR, and measure validity separately from correctness.

The compiler orchestration is backend-independent and makes no network call itself. A backend
is injected by the caller. If it supports two passes, reasoning is unconstrained and packaging
receives the Design Spec JSON Schema; otherwise the recorded fallback is one constrained pass.
Only a :class:`~anvilate.spec.DesignSpec` that passes the normal front-door validation is
returned. Reasoning is retained beside it as provenance, never inserted into the spec.

The reason it is worth building first is a specific, measured failure. Constraining every
token of a small model's output to a schema takes schema validity from about 62% to 100% —
and takes answer accuracy *down* from about 20% to 11%, while the wrong-but-schema-valid
share rises from roughly half to nearly nine in ten ("The Constraint Tax", May 2026,
arXiv:2605.26128). A confidently well-formed spec with the wrong load in it is worse than a
malformed one, because schema validation cannot catch it and everything downstream will
treat it as an input somebody meant.

So the vocabulary here refuses the summary that hides it:

**There is no success rate.** :class:`CompilationReport` reports schema validity, field
correctness and the wrong-but-valid rate as three separate numbers and offers no scalar to
collapse them into. A single "success" figure over a constrained decoder is dominated by
validity — the number constraint makes go up — and moves the *wrong* way from the number a
user cares about. A contract test asserts no such scalar exists on the model.

**A field nobody could compare is not a field that matched.** A reference that names a field
the candidate does not carry counts against correctness and says so, rather than being
skipped. Skipping is how a compiler that omits half the spec scores well.

**An unparseable candidate has no correct fields, not zero fields.** Its outcomes are
recorded as not compared, and they count in the denominator: a compiler that fails to
produce anything must not score better than one that produces something wrong.

Quantity comparison is dimensional, so "50 kN" and "50000 N" are the same answer and "50 kN"
and "50 kip" are not — which is the whole point of comparing against a reference rather than
against a string.

The task corpus is still separate. The scoring vocabulary below is the shape a result has to
have for compiler configurations to be judged honestly.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from enum import StrEnum
from functools import cache
from math import isclose
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._models import (
    FrozenMap,
    Named,
    Provenance,
    RevalidatedModel,
    StatableModel,
    rebuilt_quantities,
)
from .contracts import element_json_schemas, spec_json_schema
from .spec import SCHEMA_VERSION, DesignSpec, SpecValidationError, parse_spec
from .units import Quantity, UnitError

__all__ = [
    "CONSTRAINT_TAX_CITATION",
    "CompilationBackend",
    "CompilationFailure",
    "CompilationMode",
    "CompilationOutcome",
    "CompilationProvenance",
    "CompilationReport",
    "CompilationResult",
    "CompilationTask",
    "CompilationTaskSet",
    "COMPILATION_TASK_SET_VERSION",
    "DecodingConfiguration",
    "FieldOutcome",
    "compile_intent",
    "default_compilation_task_set",
    "field_value",
    "score_candidate",
    "score_task_set",
    "task_set_issues",
]

CONSTRAINT_TAX_CITATION = (
    "Schema-constrained decoding raises validity and lowers accuracy on small models; "
    "validity and correctness are reported separately for that reason "
    "(arXiv:2605.26128, May 2026). Screening measurement, not a certified benchmark."
)

# How close two magnitudes must be, once converted to a common unit, to count as the same
# answer. A compiler is being scored on whether it read "50 kN" out of a sentence, not on
# float formatting — but the tolerance is tight enough that 50 and 51 are different answers.
_AGREEMENT = 1e-9
COMPILATION_TASK_SET_VERSION = "1.0.0"
_SEMVER = re.compile(r"\d+\.\d+\.\d+")


class CompilationMode(StrEnum):
    """Whether reasoning and constrained packaging were separate passes."""

    TWO_PASS = "two_pass"
    SINGLE_PASS_FALLBACK = "single_pass_fallback"


class CompilationBackend(Protocol):
    """The model-specific operations required by :func:`compile_intent`.

    ``package_spec`` must apply structured-output enforcement using the supplied schema.
    Anvilate still validates the returned mapping through the ordinary Spec IR front door;
    the backend's constraint is not trusted as validation.
    """

    name: str
    model: str
    supports_two_pass: bool

    def reason(self, prompt: str) -> str: ...

    def package_spec(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        reasoning: str | None,
        validation_error: str | None,
    ) -> Mapping[str, Any]: ...


class DecodingConfiguration(StatableModel):
    """The backend, model, pass shape, schema, and retry budget behind one compilation."""

    model_config = ConfigDict(frozen=True)

    backend: Named
    model: Named
    mode: CompilationMode
    schema_version: str = SCHEMA_VERSION
    retry_budget: int = Field(ge=0, le=5)


class CompilationProvenance(StatableModel):
    """Reasoning retained for debugging, plus how packaging produced the validated spec."""

    model_config = ConfigDict(frozen=True)

    configuration: DecodingConfiguration
    reasoning: str | None
    attempts: int = Field(ge=1, le=6)
    validation_errors: tuple[str, ...] = ()
    succeeded: bool = True

    @model_validator(mode="after")
    def _reasoning_matches_the_pass_shape(self) -> CompilationProvenance:
        if self.configuration.mode is CompilationMode.TWO_PASS:
            if self.reasoning is None or not self.reasoning.strip():
                raise ValueError("a two-pass compilation must retain its reasoning output")
        elif self.reasoning is not None:
            raise ValueError("a single-pass fallback did not run a reasoning pass")
        expected_errors = self.attempts - 1 if self.succeeded else self.attempts
        if len(self.validation_errors) != expected_errors:
            raise ValueError(
                "compilation provenance has one validation error per rejected attempt; "
                f"got {len(self.validation_errors)} errors across {self.attempts} attempts"
            )
        return self


class CompilationResult(StatableModel):
    """A validated spec and compiler provenance kept outside that downstream document."""

    model_config = ConfigDict(frozen=True)

    spec: DesignSpec
    provenance: CompilationProvenance


class CompilationFailure(ValueError):
    """Constrained packaging exhausted its retry budget without a valid Design Spec."""

    def __init__(self, message: str, *, provenance: CompilationProvenance) -> None:
        self.provenance = provenance
        super().__init__(message)


def compile_intent(
    prompt: str,
    backend: CompilationBackend,
    *,
    retry_budget: int = 2,
) -> CompilationResult:
    """Compile ``prompt`` through an injected backend and return only validated Spec IR.

    A two-pass backend reasons once without a schema, then packages under the exact Design
    Spec schema. A backend that cannot do that uses one constrained pass and records the
    fallback. Invalid packaging is returned to the backend as context for the next attempt;
    it is never exposed as a candidate spec.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must state the part to compile")
    mode = (
        CompilationMode.TWO_PASS
        if backend.supports_two_pass
        else CompilationMode.SINGLE_PASS_FALLBACK
    )
    configuration = DecodingConfiguration(
        backend=backend.name,
        model=backend.model,
        mode=mode,
        retry_budget=retry_budget,
    )
    reasoning = backend.reason(prompt) if mode is CompilationMode.TWO_PASS else None
    if reasoning is not None and not reasoning.strip():
        raise ValueError("the two-pass backend returned no reasoning output to retain")

    schema = spec_json_schema()
    failures: list[str] = []
    for attempt in range(1, retry_budget + 2):
        candidate = backend.package_spec(
            prompt,
            schema=deepcopy(schema),
            reasoning=reasoning,
            validation_error=failures[-1] if failures else None,
        )
        try:
            if not isinstance(candidate, Mapping):
                raise ValueError(
                    "constrained packaging must return a mapping for Spec IR; "
                    f"got {type(candidate).__name__}"
                )
            spec = parse_spec(dict(candidate))
        except (SpecValidationError, TypeError, ValueError) as invalid:
            failures.append(str(invalid))
            continue
        return CompilationResult(
            spec=spec,
            provenance=CompilationProvenance(
                configuration=configuration,
                reasoning=reasoning,
                attempts=attempt,
                validation_errors=tuple(failures),
            ),
        )

    provenance = CompilationProvenance(
        configuration=configuration,
        reasoning=reasoning,
        attempts=retry_budget + 1,
        validation_errors=tuple(failures),
        succeeded=False,
    )
    raise CompilationFailure(
        f"intent compilation failed after {retry_budget + 1} attempts: {failures[-1]}",
        provenance=provenance,
    )


class FieldOutcome(BaseModel):
    """One reference field compared against what the compiler produced.

    ``matched`` is True only when the field was found and agreed. ``detail`` says what
    happened in every other case — absent, wrong, or not comparable — because "did not
    match" and "was never there" are different failures and a compiler that omits fields
    must not look like one that gets them wrong.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    expected: str
    actual: str | None
    matched: bool
    detail: str

    def __str__(self) -> str:
        mark = "match" if self.matched else "MISS"
        line = f"[{mark}] {self.path}: expected {self.expected}"
        # An absent field has nothing to report as "got", and the `got —` it used to print
        # said only that something was missing, not what.
        if self.actual is not None:
            line += f", got {self.actual}"
        # `detail` is the whole of the distinction this class exists to keep. Without it,
        # "not compared — the candidate did not parse" and "the candidate does not carry
        # this field" rendered identically: a compiler that never ran reading exactly like
        # one that omitted the field, which the docstring above says must not happen. A
        # match needs no reason; every other outcome carries its own.
        if not self.matched and self.detail.strip():
            line += f" — {self.detail}"
        return line


class CompilationOutcome(RevalidatedModel):
    """One task's result: whether the output parsed, and how each field fared.

    ``schema_valid`` and the field outcomes are deliberately independent. The combination
    that matters is ``schema_valid`` True with a missed field — that is the wrong-but-valid
    case, the one constrained decoding produces more of, and the one nothing downstream can
    detect.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    schema_valid: bool
    fields: tuple[FieldOutcome, ...]
    parse_error: str | None = None

    @model_validator(mode="after")
    def _valid_and_error_disagree(self) -> CompilationOutcome:
        if not self.task_id.strip():
            raise ValueError("a compilation outcome must name the task it came from")
        if self.schema_valid and self.parse_error is not None:
            raise ValueError(
                f"task {self.task_id!r} is recorded as schema-valid and also carries a parse "
                f"error ({self.parse_error!r}); one of the two is wrong, and which one "
                "decides whether the constraint tax is being measured or hidden"
            )
        if not self.schema_valid and self.parse_error is None:
            raise ValueError(
                f"task {self.task_id!r} is recorded as schema-invalid with no reason. The "
                "reason is what tells a reader whether the compiler produced nothing or "
                "produced something the schema refused"
            )
        if not self.fields:
            raise ValueError(
                f"task {self.task_id!r} compared no fields; a task whose reference names "
                "nothing cannot distinguish a right answer from a wrong one"
            )
        return self

    @property
    def correct_fields(self) -> int:
        return sum(1 for outcome in self.fields if outcome.matched)

    @property
    def fully_correct(self) -> bool:
        """Whether every referenced field was found and agreed."""
        return all(outcome.matched for outcome in self.fields)

    @property
    def wrong_but_valid(self) -> bool:
        """The case this module exists for: the schema accepted it and it is wrong.

        Not detectable downstream — the spec validates, so every consumer treats it as an
        input somebody meant.
        """
        return self.schema_valid and not self.fully_correct

    def __str__(self) -> str:
        state = "valid" if self.schema_valid else f"invalid ({self.parse_error})"
        return f"{self.task_id}: {state}, {self.correct_fields}/{len(self.fields)} fields" + (
            " — WRONG BUT VALID" if self.wrong_but_valid else ""
        )


class CompilationTask(RevalidatedModel):
    """One prompt and the spec fields a correct compilation of it must carry.

    ``reference`` maps a dotted path into the spec to the value expected there. It is
    deliberately a set of *fields* rather than a whole reference spec: two correct
    compilations can differ in the parts nobody stated, and scoring against a full document
    would count a compiler wrong for filling a default differently.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    prompt: str
    reference: FrozenMap[str, Any]
    notes: str | None = None

    @field_validator("reference", mode="before")
    @classmethod
    def _a_quantity_survives_a_round_trip(cls, value: Any) -> Any:
        """A task set this library writes, read back, used to hold dictionaries.

        ``reference`` is typed ``Any`` because a spec field can be a string, a number or a
        quantity, and ``Any`` is not told how to rebuild anything. So a task stating
        ``force`` as ``5 kN`` dumped to ``{"magnitude": 5.0, "unit": "kN"}`` and read back as
        exactly that dictionary: the reloaded task no longer compared equal to the one it was
        written from, and every report scored against it rendered its own expected value as
        ``{'magnitude': 5.0, 'unit': 'kN'}`` where the original printed ``5 kN``.

        The verdict was right either way — :func:`_compare` already recognises that shape as
        a quantity — which is what kept this quiet. Only the two-key shape Anvilate's own
        serialiser emits is rebuilt, and a value that does not parse as a quantity is left
        exactly as it was found. Strings are **not** coerced: ``"5 kN"`` stated as a string is
        a string a compiler is expected to produce, and turning it into a quantity here would
        be answering a different question than the task asked.
        """
        return rebuilt_quantities(value)

    @model_validator(mode="after")
    def _has_something_to_check(self) -> CompilationTask:
        if not self.task_id.strip():
            raise ValueError("a compilation task must have an id")
        if not self.prompt.strip():
            raise ValueError(f"task {self.task_id!r} has no prompt")
        if not self.reference:
            raise ValueError(
                f"task {self.task_id!r} states no reference fields, so every output would "
                "score as fully correct — including an empty one"
            )
        return self


class CompilationTaskSet(RevalidatedModel):
    """A versioned corpus of prompts and the fields each prompt actually states."""

    model_config = ConfigDict(frozen=True)

    version: str
    tasks: tuple[CompilationTask, ...]

    @model_validator(mode="after")
    def _is_a_named_nonempty_corpus(self) -> CompilationTaskSet:
        if _SEMVER.fullmatch(self.version) is None:
            raise ValueError(f"compilation task-set version must be semantic; got {self.version!r}")
        if not self.tasks:
            raise ValueError("a compilation task set with no tasks measures nothing")
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError(f"the compilation task set repeats task ids: {sorted(task_ids)}")
        return self


def _schema_options(schema: Mapping[str, Any], root: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Expand local references and union branches into schemas a path may traverse."""
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            return []
        resolved: Any = root
        for token in reference[2:].split("/"):
            if not isinstance(resolved, Mapping) or token not in resolved:
                return []
            resolved = resolved[token]
        return _schema_options(resolved, root) if isinstance(resolved, Mapping) else []
    branches = [
        branch
        for keyword in ("anyOf", "oneOf", "allOf")
        for branch in schema.get(keyword, [])
        if isinstance(branch, Mapping)
    ]
    if branches:
        expanded = [option for branch in branches for option in _schema_options(branch, root)]
        own = {
            key: value for key, value in schema.items() if key not in {"anyOf", "oneOf", "allOf"}
        }
        return ([own] if own else []) + expanded
    return [schema]


def _schema_has_path(schema: Mapping[str, Any], path: str) -> bool:
    options = [schema]
    for part in path.split("."):
        next_options: list[Mapping[str, Any]] = []
        for option in options:
            for expanded in _schema_options(option, schema):
                if part.isdigit():
                    item = expanded.get("items")
                    if isinstance(item, Mapping):
                        next_options.append(item)
                    continue
                properties = expanded.get("properties")
                if isinstance(properties, Mapping) and isinstance(properties.get(part), Mapping):
                    next_options.append(properties[part])
        if not next_options:
            return False
        options = next_options
    return True


def task_set_issues(task_set: CompilationTaskSet) -> tuple[str, ...]:
    """Return reference paths that no longer exist in the published Design Spec schema."""
    schema = spec_json_schema()
    element_schemas = element_json_schemas()
    issues: list[str] = []
    for task in task_set.tasks:
        element_type = task.reference.get("element_type")
        for path in task.reference:
            if path.startswith("element_params."):
                parameter = path.removeprefix("element_params.")
                element_schema = (
                    element_schemas.get(element_type) if isinstance(element_type, str) else None
                )
                if element_schema is None or not _schema_has_path(element_schema, parameter):
                    issues.append(
                        f"task {task.task_id!r} references no {element_type!r} element field "
                        f"at {path!r}"
                    )
            elif not _schema_has_path(schema, path):
                issues.append(f"task {task.task_id!r} references no Design Spec field at {path!r}")
    return tuple(issues)


@cache
def default_compilation_task_set() -> CompilationTaskSet:
    """The small, versioned corpus used to compare intent-compilation configurations."""
    return CompilationTaskSet(
        version=COMPILATION_TASK_SET_VERSION,
        tasks=(
            CompilationTask(
                task_id="structural-lifting-lug",
                prompt=(
                    "CNC-machine a lifting lug from ASTM A36 steel for a 50 kN static load "
                    "at the pin bore. Require a minimum safety factor of 2.0."
                ),
                reference={
                    "material.ref": "ASTM-A36",
                    "manufacturing.process": "cnc_milling",
                    "load_cases.0.kind": "static",
                    "load_cases.0.force": Quantity.parse("50 kN"),
                    "constraints.min_safety_factor.value": 2.0,
                },
            ),
            CompilationTask(
                task_id="mechanical-stepper-bracket",
                prompt=(
                    "Make a 6061-T6 aluminum bracket joining a NEMA 23 motor to an EXT-4040 "
                    "rail. The cantilevered motor mass is 1.1 kg and the bracket must weigh "
                    "no more than 150 g. CNC mill it."
                ),
                reference={
                    "material.ref": "AA-6061-T6",
                    "manufacturing.process": "cnc_milling",
                    "interfaces.0.ref": "NEMA23",
                    "interfaces.1.ref": "EXT-4040",
                    "load_cases.0.kind": "remote_mass",
                    "load_cases.0.remote_mass": Quantity.parse("1.1 kg"),
                    "constraints.max_mass.value": Quantity.parse("150 g"),
                },
            ),
            CompilationTask(
                task_id="structural-bolted-connection",
                prompt=(
                    "Check a single-shear 12 mm bolt joining a 10 mm ASTM A36 plate under "
                    "a 35 kN transverse load. The bolt material is ASTM-A325."
                ),
                reference={
                    "material.ref": "ASTM-A36",
                    "element_type": "bolted_connection",
                    "element_params.bolt_diameter": Quantity.parse("12 mm"),
                    "element_params.plate_thickness": Quantity.parse("10 mm"),
                    "element_params.load": Quantity.parse("35 kN"),
                    "element_params.bolt_material": "ASTM-A325",
                    "element_params.plate_material": "ASTM-A36",
                    "element_params.shear_planes": 1,
                },
            ),
            CompilationTask(
                task_id="timber-floor-beam",
                prompt=(
                    "Check a Douglas Fir-Larch No. 2 floor beam spanning 12 ft under a "
                    "uniform 40 lbf/ft live load. Use the timber beam analytical screen."
                ),
                reference={
                    "material.ref": "Douglas Fir-Larch No. 2",
                    "element_type": "timber_beam",
                    "element_params.span": Quantity.parse("12 ft"),
                    "element_params.load": Quantity.parse("40 lbf/ft"),
                },
            ),
            CompilationTask(
                task_id="hydraulic-supply-line",
                prompt=(
                    "Check 25 gal/min of water through 80 ft of 2 in pipe. Use 0.00015 ft "
                    "roughness, a summed fitting-loss coefficient of 3.5, water kinematic "
                    "viscosity of 1.1e-5 ft^2/s, and 18 ft of available head."
                ),
                reference={
                    "element_type": "pipe_run",
                    "element_params.flow_rate": Quantity.parse("25 gal/min"),
                    "element_params.diameter": Quantity.parse("2 in"),
                    "element_params.length": Quantity.parse("80 ft"),
                    "element_params.roughness": Quantity.parse("0.00015 ft"),
                    "element_params.fitting_loss_coefficient": 3.5,
                    "element_params.kinematic_viscosity": Quantity.parse("1.1e-5 ft^2/s"),
                    "element_params.available_head": Quantity.parse("18 ft"),
                },
            ),
            CompilationTask(
                task_id="metric-shaft-tolerance",
                prompt=(
                    "Turn a 25 mm steel shaft with an h6 fit. Manufacture it by turning and "
                    "validate the declared dimensional tolerance."
                ),
                reference={
                    "manufacturing.process": "turning",
                    "dimensions.0.nominal": Quantity.parse("25 mm"),
                    "dimensions.0.tolerance.designation": "h6",
                },
            ),
        ),
    )


def field_value(document: Any, path: str) -> tuple[bool, Any]:
    """Follow a dotted ``path`` into ``document``, returning ``(found, value)``.

    Handles attribute access, mapping keys, and list indices written as digits, so a path
    like ``"load_cases.0.force"`` reaches into a spec however it is represented. ``found`` is
    False when any step is missing — which is a distinct outcome from a value of ``None``,
    and the difference is the point: a compiler that omitted the field and one that set it to
    null are not the same compiler.
    """
    current = document
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, (list, tuple)):
            if not part.isdigit() or int(part) >= len(current):
                return False, None
            current = current[int(part)]
        else:
            if not hasattr(current, part):
                return False, None
            current = getattr(current, part)
    return True, current


def _as_quantity(value: Any) -> Quantity | None:
    """``value`` as a Quantity when it is one, else ``None``."""
    if isinstance(value, Quantity):
        return value
    if isinstance(value, str):
        try:
            return Quantity.parse(value)
        except UnitError:
            return None
    if isinstance(value, dict) and {"magnitude", "unit"} <= set(value):
        try:
            return Quantity(magnitude=float(value["magnitude"]), unit=str(value["unit"]))
        except (UnitError, TypeError, ValueError):
            return None
    return None


def _compare(expected: Any, actual: Any) -> tuple[bool, str]:
    """Whether ``actual`` is the same answer as ``expected``, and why not when it is not."""
    expected_quantity = _as_quantity(expected)
    actual_quantity = _as_quantity(actual)
    if expected_quantity is not None:
        if actual_quantity is None:
            return False, f"expected a quantity, got {actual!r}"
        try:
            converted = actual_quantity.to(expected_quantity.unit)
        except Exception:
            # Incommensurable units are a wrong answer, not an incomparable one: reading
            # kilonewtons as kilopounds is the failure mode a dimensional comparison exists
            # to catch, and reporting it as "could not compare" would hide it.
            return False, (
                f"{actual_quantity} is not commensurable with {expected_quantity} "
                f"({actual_quantity.dimensionality} vs {expected_quantity.dimensionality})"
            )
        if isclose(converted.magnitude, expected_quantity.magnitude, rel_tol=_AGREEMENT):
            return True, "agreed"
        return False, f"{actual_quantity} is not {expected_quantity}"
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        if isclose(float(actual), expected, rel_tol=_AGREEMENT):
            return True, "agreed"
        return False, f"{actual} is not {expected}"
    if expected == actual:
        return True, "agreed"
    return False, f"{actual!r} is not {expected!r}"


def score_candidate(
    task: CompilationTask, candidate: Any, *, parse_error: str | None = None
) -> CompilationOutcome:
    """Score one compiled candidate against its task's reference fields.

    ``candidate`` is the parsed spec — a :class:`~anvilate.spec.DesignSpec`, or any object
    or mapping the reference paths can be followed into. Pass ``parse_error`` (and a
    ``candidate`` of ``None``) when the output did not parse at all: every referenced field
    is then recorded as not compared and counts against correctness, so a compiler that
    produced nothing cannot outscore one that produced something wrong.
    """
    schema_valid = parse_error is None
    outcomes: list[FieldOutcome] = []
    for path, expected in task.reference.items():
        rendered = str(expected)
        if not schema_valid:
            outcomes.append(
                FieldOutcome(
                    path=path,
                    expected=rendered,
                    actual=None,
                    matched=False,
                    detail="not compared — the candidate did not parse",
                )
            )
            continue
        found, actual = field_value(candidate, path)
        if not found:
            outcomes.append(
                FieldOutcome(
                    path=path,
                    expected=rendered,
                    actual=None,
                    matched=False,
                    detail="the candidate does not carry this field",
                )
            )
            continue
        matched, detail = _compare(expected, actual)
        outcomes.append(
            FieldOutcome(
                path=path,
                expected=rendered,
                actual=str(actual),
                matched=matched,
                detail=detail,
            )
        )
    return CompilationOutcome(
        task_id=task.task_id,
        schema_valid=schema_valid,
        fields=tuple(outcomes),
        parse_error=parse_error,
    )


class CompilationReport(RevalidatedModel):
    """Three numbers over a task set, and deliberately not a fourth that averages them.

    There is no ``score``, no ``success_rate``, and no ``passed``. Every one of those would
    be dominated by :attr:`schema_validity` — the number schema constraint drives to 100% —
    while :attr:`field_correctness` falls and :attr:`wrong_but_valid_rate` rises. A reader
    handed one figure would see the compiler improve as it got worse, which is the whole
    finding this vocabulary is built around.
    """

    model_config = ConfigDict(frozen=True)

    outcomes: tuple[CompilationOutcome, ...]
    configuration: str  # how this run was decoded: which pass structure, which backend
    citation: Provenance = CONSTRAINT_TAX_CITATION

    @model_validator(mode="after")
    def _measures_something(self) -> CompilationReport:
        if not self.outcomes:
            raise ValueError(
                "a compilation report over no tasks has no numbers in it; an empty run is "
                "reported as not run, not as a clean sheet"
            )
        if not self.configuration.strip():
            raise ValueError(
                "a compilation report must state how it was decoded. Validity and accuracy "
                "both move with the pass structure, so a number without its configuration "
                "cannot be compared with another one"
            )
        seen = [outcome.task_id for outcome in self.outcomes]
        if len(set(seen)) != len(seen):
            raise ValueError(f"the report scores a task twice: {sorted(seen)}")
        return self

    @property
    def schema_validity(self) -> float:
        """The fraction of candidates the schema accepted. Constraint drives this up."""
        return sum(1 for o in self.outcomes if o.schema_valid) / len(self.outcomes)

    @property
    def field_correctness(self) -> float:
        """The fraction of referenced fields that were found and agreed.

        Over every field of every task, including the fields of candidates that did not
        parse — a compiler that produces nothing scores zero on them, not nothing.
        """
        total = sum(len(o.fields) for o in self.outcomes)
        return sum(o.correct_fields for o in self.outcomes) / total

    @property
    def wrong_but_valid_rate(self) -> float:
        """The fraction of candidates the schema accepted that are wrong anyway.

        The number nothing downstream can detect, and the one that rises under constraint.
        """
        return sum(1 for o in self.outcomes if o.wrong_but_valid) / len(self.outcomes)

    def wrong_but_valid(self) -> tuple[CompilationOutcome, ...]:
        """The candidates that passed the schema and are wrong — named, not just counted."""
        return tuple(o for o in self.outcomes if o.wrong_but_valid)

    def summary(self) -> str:
        """All three numbers, in one line, with none of them averaged into the others."""
        return (
            f"{len(self.outcomes)} tasks under {self.configuration}: "
            f"schema validity {self.schema_validity:.0%}, "
            f"field correctness {self.field_correctness:.0%}, "
            f"wrong-but-valid {self.wrong_but_valid_rate:.0%}"
        )

    def render(self) -> str:
        """The summary, then every task under it worst first, then the caveat they are under.

        The citation is the argument for the shape of the numbers above it: three figures
        rather than one, because a single score is dominated by schema validity and would
        show the compiler improving as it gets worse. `citation` has carried that source and
        the words "screening measurement, not a certified benchmark" since the model was
        written, and no rendering printed it — so the one reading a person actually sees was
        three percentages with nothing saying what they are or are not.

        On `render` and not on `summary`: the summary is a single line for a report pane, and
        a two-sentence citation in it would push the numbers off the end. The bundle's
        disclaimer sits in the same place for the same reason.
        """
        ranked = sorted(
            self.outcomes,
            key=lambda o: (o.schema_valid, o.correct_fields / len(o.fields)),
        )
        return "\n".join([self.summary(), *(f"  {outcome}" for outcome in ranked), self.citation])


def score_task_set(
    tasks: Sequence[CompilationTask],
    candidates: dict[str, Any],
    *,
    configuration: str,
    parse_errors: dict[str, str] | None = None,
) -> CompilationReport:
    """Score a whole task set, refusing to silently drop a task nobody attempted.

    ``candidates`` maps task id to the parsed spec; ``parse_errors`` maps task id to why the
    output did not parse. A task in neither mapping is an error rather than an omission: a
    run that skipped the hard tasks would otherwise report the easy ones' numbers.
    """
    errors = parse_errors or {}
    missing = [
        task.task_id
        for task in tasks
        if task.task_id not in candidates and task.task_id not in errors
    ]
    if missing:
        raise ValueError(
            f"{len(missing)} task(s) have neither a candidate nor a parse error: {missing}. "
            "A skipped task is not a task that scored zero, and dropping it silently "
            "reports the remaining tasks' numbers as the run's"
        )
    return CompilationReport(
        outcomes=tuple(
            score_candidate(
                task,
                candidates.get(task.task_id),
                parse_error=errors.get(task.task_id),
            )
            for task in tasks
        ),
        configuration=configuration,
    )
