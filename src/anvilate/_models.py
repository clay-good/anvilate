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

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, Self, TypeVar

from pydantic import AfterValidator, BaseModel, PlainSerializer

__all__ = [
    "EMPTY_MAP",
    "FrozenMap",
    "ItemCollection",
    "Named",
    "Provenance",
    "RevalidatedModel",
    "cited",
    "rebuilt_quantities",
]


#: How long a citation, a source or a name may be, in characters.
#:
#: The other end of the range `cited` already refuses. A field that is present and blank is
#: refused because it reads as filled in every rendering and follows nowhere — and a field of
#: a hundred thousand characters reads as filled too, renders as a wall, and is the subject
#: `anvilate.standards.effectivity.parse_citation` scans. That scan is linear now, but linear
#: in a string nothing bounded: a scorecard arrives from the subject store and out of an
#: attestation envelope, where `reference` is free text. Measured across every citation and
#: name this suite builds, the longest is 153 characters — Shigley's Marin surface factor —
#: and a rule in tests/test_contract.py holds the bound clear of that.
_LONGEST_CITED = 1_024


#: Prefixes pydantic puts on a validator's own message, which a reader did not write and
#: does not need. `msg` for a `ValueError` raised inside a validator is "Value error, " plus
#: the sentence the validator wrote — so every refusal this library composes with care
#: reached the shell wearing pydantic's label: `anvilate check: name: Value error, this field
#: is 5,000 characters`. The sentences are the product here; the label is scaffolding.
#:
#: Only the two pydantic prepends to a message the library itself wrote. A type error's
#: message ("Input should be a valid integer") is pydantic's own sentence, has no prefix, and
#: is left exactly as it is.
_PYDANTIC_PREFIXES = ("Value error, ", "Assertion failed, ")


def _refusal_line(location: str, message: str) -> str:
    """One validation failure as a reader should see it: the path, then the sentence.

    Two things are dropped. The prefix above, and the **empty location**: a rule that holds
    for the whole document has no field to name, and the obvious `f"{loc}: {msg}"` then reads
    `anvilate check: : Value error, description is 5,000 characters` — a doubled colon with
    nothing between. Every document-level rule lands there: the finite-number rule, the depth
    bound, the string bound and the collection bound all belong to the document rather than
    to one of its fields.
    """
    for prefix in _PYDANTIC_PREFIXES:
        if message.startswith(prefix):
            message = message[len(prefix) :]
            break
    return f"{location}: {message}" if location else message


def cited(states: str) -> Any:
    """A provenance field that refuses to be present and blank — or an unbounded wall.

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

    Both ends of the range, because only one of them was written. A citation is read back out
    of a subject store and out of an attestation envelope — neither of which this library
    wrote — and every rendering, export and signature downstream carries whatever it says.
    :data:`_LONGEST_CITED` is what a citation can be and still be one.
    """

    def refuse_a_blank(value: str) -> str:
        if not value.strip():
            raise ValueError(f"this field must state {states}")
        if len(value) > _LONGEST_CITED:
            # The blank refusal's sentence, from the other end. `cited` states BOTH rules for
            # a citation and for a name, so a message hard-coding "a citation" told a reader
            # whose spec has a 5,000-character `name` that their name was a citation.
            raise ValueError(
                f"this field is {len(value):,} characters, and nothing longer than "
                f"{_LONGEST_CITED:,} is one a reader can follow; it must state {states}"
            )
        return value

    refuse_a_blank.__anvilate_provenance__ = True  # type: ignore[attr-defined]
    return Annotated[str, AfterValidator(refuse_a_blank)]


# What a thing is called. A blank one is the same failure as a blank citation seen from the
# other side: the field reads as filled, and every rendering downstream prints an entry, a
# record or a check with nothing where its name goes. `[FAIL]    : safety factor 0.8` is a
# scorecard line a reader cannot act on, and `governing()` names it as the check to look at.
#: A type checker reads these two as `str`, which is what the value is.
#:
#: `cited` returns an `Annotated` alias built from a per-field sentence, so its return
#: annotation is `Any` — and a *call expression* is not something a type checker can read as
#: a type. Without this branch every provenance and name field in the library is `Any` to a
#: consumer: `takes_an_int(record.ref)` type-checked clean under `mypy --strict` while
#: `record.sources` beside it was correctly `tuple[str, ...]`. Seventy-four fields, in a
#: library whose stated purpose is carrying provenance.
#:
#: Found on the far side of an install — a downstream package importing the wheel — because
#: nothing inside the package notices a field it declared itself as `Any`.
if TYPE_CHECKING:
    Named = str
    Provenance = str
else:
    Named = cited(
        "what it is called; a blank name renders as an unnamed check, record or element and "
        "gives a reader nothing to follow"
    )

    # The default spelling, for a field with nothing more specific to say than the rule.
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


class ItemCollection:
    """A model whose one field IS the items, made to answer Python's container protocol.

    Pydantic gives every model an ``__iter__`` over its ``(field, value)`` pairs and nothing
    else. On a model whose single field is the collection — a scorecard's entries, a
    structure's members — that is not a missing feature, it is a **wrong answer that does
    not raise**::

        list(card)      -> [("entries", (entry, entry))]   one item, for a two-check card
        len(card)       -> TypeError: object of type 'Scorecard' has no len()
        entry in card   -> False, for an entry the card is holding
        bool(card)      -> True, for a card with no checks in it

    ``entry in card`` is the one that matters: membership falls through to ``__iter__``, so
    it compared a ``ScorecardEntry`` against the tuple ``("entries", ...)`` and answered
    False about a check the card contains. A caller who writes it gets no error and the
    wrong answer, which is the shape this library refuses everywhere else.

    Mixed in ahead of ``BaseModel`` so these win the MRO. The items field is **derived** and
    not declared: the whole premise is a model that is one collection, so a class with two
    fields is not one of these and says so rather than picking a field.
    """

    def _items(self) -> tuple[Any, ...]:
        fields = list(type(self).model_fields)  # type: ignore[attr-defined]
        if len(fields) != 1:
            raise TypeError(
                f"{type(self).__name__} mixes in ItemCollection and carries "
                f"{len(fields)} fields ({', '.join(fields)}); the protocol below answers "
                f"for a model that IS one collection, and there is no way to choose here "
                f"which of several fields a caller meant by len() or iteration"
            )
        return tuple(getattr(self, fields[0]))

    def __len__(self) -> int:
        return len(self._items())

    def __iter__(self) -> Iterator[Any]:
        return iter(self._items())

    def __getitem__(self, index: Any) -> Any:
        return self._items()[index]


class RevalidatedModel(BaseModel):
    """A model whose ``model_copy`` re-runs the validators its constructor ran.

    **What counts as a validator here is every kind**, and that took three widenings to get
    right. A ``mode="after"`` model validator, a ``field_validator``, and a rule carried in a
    field's *annotation* — which is how :func:`named`, :func:`provenance` and :data:`FrozenMap`
    below state theirs. The ratchet in ``tests/test_revalidated_copy.py`` read only the first
    for a long time, so a model whose whole invariant arrived through one of these aliases had
    no decorator in its own file and looked like a model with nothing to protect. Forty-two
    were in that gap.

    The sharpest of them is ``FrozenMap``. ``frozen=True`` stops attribute assignment; the
    annotation's validator is what stops mutation *through* the value, by wrapping the mapping
    in a ``MappingProxyType``. Without this base, ``model_copy`` handed back a plain ``dict``
    in a frozen model's field, and it could then be mutated in place — an object every reader
    has been told is immutable, quietly changing.
    """

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
