"""Scoring a compiled spec: validity and correctness are two numbers, and stay two numbers.

Anvilate's intent compiler will one day turn prose into Spec IR with a small local model.
This module is the half of that which can exist before the compiler does, and it is the half
that decides whether the compiler is any good: **the measurement.**

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

The compiler itself, its two-pass structure, and the task corpus are not here. What is here
is the shape a result has to have for those to be judged honestly.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isclose
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ._models import FrozenMap, RevalidatedModel, rebuilt_quantities
from .units import Quantity, UnitError

__all__ = [
    "CONSTRAINT_TAX_CITATION",
    "CompilationOutcome",
    "CompilationReport",
    "CompilationTask",
    "FieldOutcome",
    "field_value",
    "score_candidate",
    "score_task_set",
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
    citation: str = CONSTRAINT_TAX_CITATION

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
        """The summary, then every task under it, worst first."""
        ranked = sorted(
            self.outcomes,
            key=lambda o: (o.schema_valid, o.correct_fields / len(o.fields)),
        )
        return "\n".join([self.summary(), *(f"  {outcome}" for outcome in ranked)])


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
