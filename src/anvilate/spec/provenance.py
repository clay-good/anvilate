"""Assumption provenance: where every value in a compiled spec came from.

Every value carries its origin — user-stated, database-resolved, or a
system-default — and a default must explain itself. The UI renders defaults as
editable assumption chips; a reviewer can see at a glance which numbers the
engineer stated and which the tool assumed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, model_validator

__all__ = ["Origin", "Provenanced"]

T = TypeVar("T")


class Origin(StrEnum):
    """The source of a value in a compiled Design Spec."""

    USER_STATED = "user_stated"
    DATABASE_RESOLVED = "database_resolved"
    DEFAULT = "default"


class Provenanced(BaseModel, Generic[T]):
    """A value tagged with its origin, and a rationale when it is a default."""

    value: T
    origin: Origin
    rationale: str | None = None

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
