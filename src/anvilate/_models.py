"""Model plumbing: a copy that re-validates, and a mapping field that is really frozen.

**Pydantic runs no ``mode="after"`` validator on ``model_copy``.** So a model that refuses
to be *constructed* in a broken state can still be *copied* into one, and the copy is a
fully typed instance that every downstream check accepts. ``Normal(mean=1.0, std=0.5)``
refuses a negative standard deviation; ``normal.model_copy(update={"std": -1.0})`` produced
one, and the sampler consuming it has no way to know.

This has been found and fixed one class at a time — the fatigue curve's segments, a
calibration certificate's distribution, an attestation's base64 signature — each time with
the same comment written again. It is one rule, so it is one base class: a class that
declares an after-validator inherits from :class:`RevalidatedModel`, and
``tests/test_revalidated_copy.py`` derives the list from the source so a new model cannot
be added without it.

The cost is paid only by models that carry an invariant. A model with no after-validator
keeps pydantic's copy, which is why this is a base class to opt into rather than a change
to every model in the library.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Self, TypeVar

from pydantic import AfterValidator, BaseModel, PlainSerializer

__all__ = [
    "EMPTY_MAP",
    "FrozenMap",
    "Named",
    "Provenance",
    "RevalidatedModel",
    "cited",
    "rebuilt_quantities",
]


def cited(states: str) -> Any:
    """A provenance field that refuses to be present and blank, with its own sentence.

    A citation, source, licence or reference identifier is what this library exists to
    carry. A *missing* one is a modelled state -- `cited(...) | None`, or a default of `""`
    where the absence has its own meaning -- but a field that is present and blank is
    neither: it reads as filled in every rendering and serialises as a citation nobody can
    follow. `Citation(standard="", edition="", clause="")` rendered as `"-"`.

    Seven models had this check written into their own after-validators, each with a
    sentence worth keeping ("the mill certificate, the ADM table read, or the project
    specification"), and thirty-two comparable fields had nothing. So the rule is one
    mechanism and the sentence stays per field: ``states`` completes "this field must
    state ...".

    The census that holds every provenance field to this is in tests/test_contract.py; it
    finds them by the marker below rather than by the annotation, since a field declared
    ``cited(...) | None`` reports a plain ``str``.
    """

    def refuse_a_blank(value: str) -> str:
        if not value.strip():
            raise ValueError(f"this field must state {states}")
        return value

    refuse_a_blank.__anvilate_provenance__ = True  # type: ignore[attr-defined]
    return Annotated[str, AfterValidator(refuse_a_blank)]


# What a thing is called. A blank one is the same failure as a blank citation seen from the
# other side: the field reads as filled, and every rendering downstream prints an entry, a
# record or a check with nothing where its name goes. `[FAIL]    : safety factor 0.8` is a
# scorecard line a reader cannot act on, and `governing()` names it as the check to look at.
Named = cited(
    "what it is called; a blank name renders as an unnamed check, record or element and "
    "gives a reader nothing to follow"
)

# The default spelling, for a field with nothing more specific to say than the rule itself.
Provenance = cited(
    "where it came from — the standard, table, certificate or record this value was read "
    "from; a blank citation is one the document carries and no reader can follow"
)


def rebuilt_quantities(value: Any) -> Any:
    """A mapping of ``Any``-typed values with the serialised quantities in it rebuilt.

    ``Any`` is the one annotation pydantic cannot reconstruct from, so a field holding a
    :class:`~anvilate.units.Quantity` writes ``{"magnitude": 5.0, "unit": "kN"}`` and reads
    back as exactly that dictionary. The model then no longer compares equal to the one it
    was written from, and whatever consumes the field is handed a mapping where it expects a
    quantity.

    Three fields need that repair — a compilation task's ``reference``, a spec's
    ``element_params``, and a structure member's — and it was written out twice before it was
    written once. Only the two-key shape this library's own serialiser emits is rebuilt, and
    a value that does not parse as a quantity is left exactly as it was found. Strings are
    **not** coerced: ``"5 kN"`` stated as a string is a string the writer meant to state.
    """
    from .units import Quantity

    if not isinstance(value, Mapping):
        return value
    rebuilt: dict[Any, Any] = {}
    for key, entry in value.items():
        if isinstance(entry, Mapping) and set(entry) == {"magnitude", "unit"}:
            try:
                entry = Quantity(magnitude=float(entry["magnitude"]), unit=str(entry["unit"]))
            except (TypeError, ValueError):  # UnitError is a ValueError, so this covers it
                pass
        rebuilt[key] = entry
    return rebuilt


class RevalidatedModel(BaseModel):
    """A model whose ``model_copy`` re-runs the validators its constructor ran."""

    def model_copy(self, *, update: Any = None, deep: bool = False) -> Self:
        """A copy with the invariants re-checked.

        A copy with no ``update`` cannot have moved — it is the same field values — so it is
        returned untouched and costs nothing. Only an update can build a state the
        constructor refuses, and that is the path that re-validates.

        Re-validation runs over the copy's **field values**, not over a serialized dump. A
        dump-and-reparse round trip is a different operation: it would coerce, drop anything
        excluded from serialization, and fail on a field whose serialized form is not its
        input form — a `pint` quantity among them. The values are already the right types;
        what has to run again is the cross-field check.
        """
        copied = super().model_copy(update=update, deep=deep)
        if update is None:
            return copied
        return type(self).model_validate(dict(copied.__dict__))


_K = TypeVar("_K")
_V = TypeVar("_V")

#: The shared empty mapping, for a ``FrozenMap`` field's ``default_factory``. A literal
#: ``{}`` default cannot be used: pydantic deep-copies defaults and a ``mappingproxy`` does
#: not pickle. It is safe to share because nothing can write to it.
EMPTY_MAP: Mapping[Any, Any] = MappingProxyType({})

#: A mapping field on a frozen model that the frozen model actually owns.
#:
#: ``model_config = ConfigDict(frozen=True)`` stops a field being *rebound*. It does not
#: reach inside the value, so a ``dict`` field on a frozen model is writable by anyone
#: holding the model — and the writes land after every validator has run. That is not a
#: theoretical gap: ``CompilationTask.reference`` names the spec fields a correct
#: compilation must carry, its constructor refuses a task that names none, and
#: ``del task.reference["material"]`` turned a compilation that got the material wrong into
#: one scoring 1 of 1 fields correct — defeating the wrong-but-valid metric the module
#: exists to report.
#:
#: The value is a ``MappingProxyType``, so it reads exactly like a dict and refuses every
#: write. It serializes as a plain object, so nothing downstream sees the difference.
FrozenMap = Annotated[
    Mapping[_K, _V],
    AfterValidator(lambda mapping: MappingProxyType(dict(mapping))),
    PlainSerializer(dict, return_type=dict),
]
