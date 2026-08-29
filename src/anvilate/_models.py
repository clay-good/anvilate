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

__all__ = ["EMPTY_MAP", "FrozenMap", "RevalidatedModel"]


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
