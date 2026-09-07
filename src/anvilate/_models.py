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
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self, TypeVar

from pydantic import AfterValidator, BaseModel, PlainSerializer, model_validator

__all__ = [
    "EMPTY_MAP",
    "FrozenMap",
    "ItemCollection",
    "Named",
    "Provenance",
    "RevalidatedModel",
    "StatableModel",
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


#: How deep a document is allowed to nest, measured from a model's own field.
#:
#: A fact about the data: the deepest Design Spec this repository ships is five levels, and
#: the free-form parts of one are `{"magnitude": ..., "unit": ...}` under a named parameter.
#: The bound exists because a document that nests past what any consumer can serialise fails
#: at the far end of the call instead of at its front door: `canonical_json` gave
#: `-32603 Internal error: compile_spec raised ValueError: Circular reference detected` for a
#: 400-deep document over MCP — an internal error for a client's input, naming a circular
#: reference that does not exist, because that is what Python's JSON encoder says when it
#: runs out of depth. A document is refused here instead, naming the path.
_MAX_DOCUMENT_DEPTH = 32

#: How long a string a document is allowed to state, in characters.
#:
#: The third bound on the same walk, and the one the other two imply. A number has to be
#: finite and a document has to nest inside 32 levels because a consumer at the far end of
#: the call has to be able to answer it — and a string has the same far end. Nothing bounded
#: one: `description` set to two megabytes of "A" was accepted here, cost 14.6 seconds at the
#: front door alone, and then travelled into every rendering, both exports and the signed
#: attestation. The longest string any Design Spec in this repository states is the
#: nema23_bracket description at 64 characters, and the longest a scorecard states is 432
#: characters over the 7,018 entries this suite builds; rules in the test suite hold the
#: bound clear of both.
_MAX_STRING_LENGTH = 4_096

#: How many items a collection in a document may hold.
#:
#: The fourth bound on the same walk, and the last axis a document has. Depth, magnitude and
#: string length were all bounded on the argument that something at the far end of the call
#: has to be able to answer the document — and breadth is the one that was left. 500,000
#: `load_cases` were accepted, and every one of them then went on to be screened, rendered,
#: exported and signed. Same shape as the 400-deep document and the 1e400 width: a stateless
#: MCP server takes these from a client it does not control.
#:
#: What this does **not** buy is the cost of reading the document. Those 500,000 load cases
#: are 17.7 MB of YAML, and parsing them is 22 of the 23 seconds the front door spends —
#: building the models from the parsed data is the other 1.2, so refusing earlier would save
#: nothing. The bound is about what happens *after*: a document nothing can act on is refused
#: before anything acts on it. The widest collection any document in this repository states is
#: eleven keys, and rules in the test suite hold the bound clear of that.
_MAX_COLLECTION_ITEMS = 1_024


#: :class:`~anvilate.units.Quantity`, resolved on first use and kept.
#:
#: The walk below cannot import it at module scope — `units` imports this module — and it
#: cannot import it per call either: a `from .units import Quantity` inside the recursion is
#: a `sys.modules` lookup and a `getattr` at every node of every field of every model, and it
#: made `screen_spec` eighteen times slower the day the walk started running on scorecards.
_QUANTITY: type | None = None


def _quantity() -> type:
    global _QUANTITY
    if _QUANTITY is None:
        from .units import Quantity

        _QUANTITY = Quantity
    return _QUANTITY


class _TooDeep(ValueError):
    """A document nested past :data:`_MAX_DOCUMENT_DEPTH`, carrying the path it got to."""


def _not_a_number(where: str, magnitude: float) -> str:
    return (
        f"{where} is {magnitude}, which is not a number a document can state; "
        f"a requirement that is infinite or undefined is not a requirement"
    )


def _too_long(where: str, length: int) -> str:
    return (
        f"{where} is {length:,} characters, and a document does not state a string longer "
        f"than {_MAX_STRING_LENGTH:,}; text no consumer can render or sign is refused here "
        f"rather than at the far end of the call"
    )


def _too_many(where: str, count: int) -> str:
    return (
        f"{where} holds {count:,} items, and a document does not state a collection of more "
        f"than {_MAX_COLLECTION_ITEMS:,}; a document larger than anything can screen, render "
        f"or sign is refused here rather than at the far end of the call"
    )


def _first_unstatable(
    where: str, value: object, depth: int = 0, *, requirements: bool = True
) -> str | None:
    """What is wrong with the first value a document may not state — or ``None``.

    Four rules share this one walk because they share a premise: a document states what a
    consumer at the far end of the call can answer. A string longer than
    :data:`_MAX_STRING_LENGTH` fails it, a collection of more than
    :data:`_MAX_COLLECTION_ITEMS` fails it, nesting past :data:`_MAX_DOCUMENT_DEPTH` fails it,
    and — for a document that states *requirements* — so does a number that is infinite or
    undefined. The returned string is the whole refusal, so the path it built is in the
    sentence: `element_params.width is inf, ...`.

    ``requirements`` is what the fourth rule turns on, and it is off by default because the
    three size bounds are the ones that hold for anything. `max_mass: .inf kg` is a
    requirement that reads as stated and means nothing. An infinite *result* is a different
    object: a check with zero demand reports an infinite safety factor, and this library
    computes, records, typesets and round-trips one on purpose — `fatigue` writes
    `SymbolValue(value=inf)` and `tests/test_report.py` pins the record reloading. So a
    scorecard is held to the three, and a Design Spec to all four.

    A stated bound is wrapped: `max_mass` is a `Provenanced[Quantity]`, so the number is two
    layers in. Unwrapping by attribute rather than by type keeps this from importing the
    provenance module.

    Mappings and sequences are walked because a document's free-form parts are containers —
    `element_params` above all — and the path is built as it goes, so the message names
    `element_params.width.magnitude` rather than `element_params`. A mapping's **keys** are
    checked too, since a key is a string the document states as much as a value is.

    Sub-models are **not** walked: each is expected to be a :class:`StatableModel` and to have
    already run this rule on itself. That expectation is not free — it is exactly what was
    wrong with bounding a scorecard's own two models and leaving `Derivation` and friends
    open — so `tests/test_contract.py` walks the annotation graph of every front door that
    mixes this in and fails on a reachable model that does not.
    """
    if depth > _MAX_DOCUMENT_DEPTH:
        raise _TooDeep(where)
    if isinstance(value, BaseModel):
        # A stated bound is wrapped — `max_mass` is a `Provenanced[Quantity]` — so the number
        # is a layer in. Unwrapped by DECLARED FIELD rather than by `getattr(value, "value",
        # value)`: pydantic answers a missing attribute by building and raising an
        # AttributeError, which costs 14 microseconds on a `Quantity` and made `screen_spec`
        # thirty times slower the day this walk started running over scorecards.
        if "value" in type(value).model_fields:
            return _first_unstatable(where, value.value, depth, requirements=requirements)
        if isinstance(value, _quantity()):
            # The one model the walk reads rather than trusts. A `Quantity` on its own is
            # allowed to hold an infinity — intermediate arithmetic produces them and each
            # consumer guards its own — so the rule cannot live on the quantity; it is
            # *stating* one in a document that is refused. That is why `Quantity` is the
            # graph gate's single recorded exemption.
            if requirements and not isfinite(value.magnitude):
                return _not_a_number(where, value.magnitude)
            return None
        # Every other model here is a `StatableModel` and has run this rule on itself. The
        # gate in tests/test_contract.py is what holds the graph to that.
        return None
    if isinstance(value, Enum):
        value = value.value
    # Before the container branches, since `str` is a sequence: an enum's `.value` arrives
    # here too, and is held to the same bound as any other string a document states.
    if isinstance(value, str):
        return _too_long(where, len(value)) if len(value) > _MAX_STRING_LENGTH else None
    # Before the float branch: `bool` is a subclass of `int`, not of `float`, so it never
    # reaches it — but a mapping's keys and values are `object` here and being explicit is
    # cheaper than working that out again.
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return _not_a_number(where, value) if requirements and not isfinite(value) else None
    if isinstance(value, Mapping):
        if len(value) > _MAX_COLLECTION_ITEMS:
            return _too_many(where, len(value))
        for key, item in value.items():
            if isinstance(key, str) and len(key) > _MAX_STRING_LENGTH:
                return _too_long(f"a key of {where}", len(key))
            found = _first_unstatable(f"{where}.{key}", item, depth + 1, requirements=requirements)
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple, set, frozenset)):
        if len(value) > _MAX_COLLECTION_ITEMS:
            return _too_many(where, len(value))
        for index, item in enumerate(value):
            found = _first_unstatable(
                f"{where}[{index}]", item, depth + 1, requirements=requirements
            )
            if found is not None:
                return found
    return None


#: Each model's field names, kept because reading them is not the cheap operation it looks.
#:
#: `for name in type(self).model_fields` reads as a dict iteration and costs 11.7 microseconds
#: under pydantic 2.13, which is most of what the validator below spends. The names cannot
#: change after the class is built, so they are read once.
_FIELD_NAMES: dict[type, tuple[str, ...]] = {}


def _field_names(model: type[BaseModel]) -> tuple[str, ...]:
    names = _FIELD_NAMES.get(model)
    if names is None:
        names = _FIELD_NAMES[model] = tuple(model.model_fields)
    return names


class StatableModel(RevalidatedModel):
    """A model that refuses to hold what nothing at the far end of the call can answer.

    Three axes always, one walk: a string longer than :data:`_MAX_STRING_LENGTH`, a
    collection wider than :data:`_MAX_COLLECTION_ITEMS`, and a value nested deeper than
    :data:`_MAX_DOCUMENT_DEPTH`. The premise is one sentence — a document states what a
    consumer at the far end of the call can answer — and each axis was added to it in turn,
    after a document that was unbounded on that axis reached a renderer, an exporter or a
    signature and failed there instead of here.

    :attr:`states_requirements` adds the fourth, and it is a separate switch because the
    fourth rule is a different claim. An infinite *requirement* is not a requirement; an
    infinite *result* is an answer this library computes on purpose, records in a derivation
    and reloads from a calc record — a check with zero demand has an infinite safety factor,
    and saying so is the honest report.

    **This was the Design Spec's private base class**, and the premise never was. A
    :class:`~anvilate.scorecard.Scorecard` is read back out of a signed attestation predicate
    and out of a subject store — neither of which this library wrote — by
    ``anvilate verify`` and by two MCP tools, and it was unbounded on all four axes: a
    2 MB ``detail`` was accepted, and 200,000 entries in 2.2 seconds. It is the same front
    door as a spec's, reached by a different route, so it is the same rule.

    Opt-in, like :class:`RevalidatedModel` above it, and for the same reason: the cost is
    paid by the models that are read from outside. What opting in commits a class to is its
    whole reachable graph — the walk trusts a sub-model to have checked itself — and
    ``tests/test_contract.py`` is what holds a graph to that rather than a comment.
    """

    #: Whether the numbers this model holds are requirements, and so must be finite.
    states_requirements: ClassVar[bool] = False

    @model_validator(mode="after")
    def _every_value_is_one_a_document_can_state(self) -> Self:
        requirements = type(self).states_requirements
        for name in _field_names(type(self)):
            value = getattr(self, name, None)
            # The four shapes most fields actually hold, answered without a call. This walk
            # runs on every model a screen builds — `screen_spec` is the library's hottest
            # function — and a Python call per field is most of what it costs. A string is
            # its own check; nothing else here can violate any of the four rules, and a
            # float only can where the model states requirements.
            kind = type(value)
            if kind is str:
                if len(value) <= _MAX_STRING_LENGTH:
                    continue
            elif value is None or kind is bool or kind is int:
                continue
            elif kind is float and (not requirements or isfinite(value)):
                continue
            try:
                problem = _first_unstatable(name, value, requirements=requirements)
            except _TooDeep:
                # The field, not the path it got to: thirty-two `[0]`s is not something a
                # reader acts on, and the field is where they have to look.
                raise ValueError(
                    f"{name} nests more than {_MAX_DOCUMENT_DEPTH} levels deep, and a "
                    f"document that nests past what any consumer can serialise is refused "
                    f"here rather than at the far end of the call"
                ) from None
            if problem is not None:
                raise ValueError(problem)
        return self
