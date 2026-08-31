"""Assumption provenance: where every value in a compiled spec came from.

Every value carries its origin — user-stated, database-resolved, or a
system-default — and a default must explain itself. The UI renders defaults as
editable assumption chips; a reviewer can see at a glance which numbers the
engineer stated and which the tool assumed.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import model_validator

from .._models import RevalidatedModel

__all__ = ["Origin", "Provenanced"]

T = TypeVar("T")


class Origin(StrEnum):
    """The source of a value in a compiled Design Spec."""

    USER_STATED = "user_stated"
    DATABASE_RESOLVED = "database_resolved"
    DEFAULT = "default"


class Provenanced(RevalidatedModel, Generic[T]):
    """A value tagged with its origin, and a rationale when it is a default."""

    value: T
    origin: Origin
    rationale: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _a_bare_value_records_no_origin(cls, data: Any) -> Any:
        """The refusal a spec author actually gets for the likeliest mistake.

        Writing ``units: SI`` in a spec document is the natural thing to write and the
        wrong thing: pydantic answered it with ``Input should be a valid dictionary or
        instance of Provenanced[UnitSystem]``, which names a Python generic at somebody
        holding a YAML file. Every provenanced field in the IR reaches this, so the message
        is here rather than in each of them.

        A bare value is not coerced to ``user_stated``. Where a number came from is the
        entire reason this wrapper exists, and inventing an origin for one that states none
        is the same silent green the scorecard refuses to give.
        """
        if isinstance(data, (Mapping, Provenanced)):
            return data
        raise ValueError(
            f"a provenanced value is written as "
            f"{{value: {data!r}, origin: user_stated}}, not as a bare {data!r}. "
            f"Origin is one of {', '.join(sorted(o.value for o in Origin))}, and "
            f"{Origin.DEFAULT.value!r} also needs a rationale. It is not filled in for you: "
            "where a value came from is what this records"
        )

    @model_validator(mode="after")
    def _default_needs_rationale(self) -> Provenanced[T]:
        if self.origin is Origin.DEFAULT and not self.rationale:
            raise ValueError("a defaulted value must carry a human-readable rationale")
        return self

    @classmethod
    def stated(cls, value: T) -> Provenanced[T]:
        """A value the user stated explicitly."""
        return cls(value=value, origin=Origin.USER_STATED)

    @classmethod
    def resolved(cls, value: T) -> Provenanced[T]:
        """A value resolved from a curated database."""
        return cls(value=value, origin=Origin.DATABASE_RESOLVED)

    @classmethod
    def default(cls, value: T, rationale: str) -> Provenanced[T]:
        """A value the system defaulted, with the reason it chose it."""
        return cls(value=value, origin=Origin.DEFAULT, rationale=rationale)
