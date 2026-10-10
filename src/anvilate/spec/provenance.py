"""Assumption provenance: where every value in a compiled spec came from.

Every value carries its origin — user-stated, database-resolved, or a
system-default — and a default must explain itself. The UI renders defaults as
editable assumption chips; a reviewer can see at a glance which numbers the
engineer stated and which the tool assumed.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import model_validator

from .._models import StatableModel
from ..refusal import RefusalError, Remedy

_RATIONALE_SOURCE = "why the value was defaulted, naming the profile that supplied it if any"


class _ProvenanceInputError(RefusalError, ValueError):
    """A provenance record that cannot be used without correction."""


def _provenance_refusal(message: str, *, subject: str, source: str) -> _ProvenanceInputError:
    return _ProvenanceInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = ["Origin", "Provenanced"]


class _BareValue(ValueError):
    """A provenanced field written as a bare value. It keeps the value, so the refusal's
    structured remedy can show the line to write instead (spec.validate._remedy)."""

    def __init__(self, message: str, value: Any) -> None:
        super().__init__(message)
        self.value = value


T = TypeVar("T")


class Origin(StrEnum):
    """The source of a value in a compiled Design Spec."""

    USER_STATED = "user_stated"
    DATABASE_RESOLVED = "database_resolved"
    DEFAULT = "default"
    # Supplied by a bound `anvilate.profile.Profile`. Neither the engineer's statement nor the
    # library's choice: a cited, versioned record somebody chose to apply, and the rationale
    # names which one — a profile-supplied number that governs a verdict must never read as
    # one the engineer stated.
    PROFILE_SUPPLIED = "profile_supplied"
    # Taken from a file. Measured: Anvilate read a CAD file and this is what it measured.
    # Agent-read: the user's agent read it off a picture, a scan or a PDF. Either way the
    # document's `sources` names the file, and an agent-read value is a draft until a
    # named person confirms it. Neither is something the engineer stated.
    MEASURED_FROM_FILE = "measured_from_file"
    AGENT_READ = "agent_read"


class Provenanced(StatableModel, Generic[T]):
    """A value tagged with its origin, and a rationale when it is a default."""

    value: T
    origin: Origin
    rationale: str | None = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Make each parametrization findable by name, so a spec can be pickled.

        pickle stores a class as its module and qualified name. pydantic registers a
        parametrized generic there only when it is written at module scope, and the IR
        writes ``Provenanced[UnitSystem]`` inside a class body, so every `DesignSpec`
        refused to pickle and `multiprocessing` could not hand one to a worker. Two
        parametrizations can display the same name (``Provenanced[Mass]`` and
        ``Provenanced[Length]`` both read ``Annotated[Quantity, AfterValidator]``), so a
        taken name gets a numbered suffix rather than pointing pickle at the wrong class.
        """
        super().__pydantic_init_subclass__(**kwargs)
        namespace = sys.modules[cls.__module__].__dict__
        name, number = cls.__qualname__, 1
        while namespace.setdefault(name, cls) is not cls:
            number += 1
            name = f"{cls.__qualname__}#{number}"
        cls.__qualname__ = name

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
        raise _BareValue(
            f"a provenanced value is written as "
            f"{{value: {data!r}, origin: user_stated}}, not as a bare {data!r}. "
            f"Origin is one of {', '.join(sorted(o.value for o in Origin))}, and "
            f"{Origin.DEFAULT.value!r} and {Origin.PROFILE_SUPPLIED.value!r} also need a "
            "rationale. It is not filled in for you: "
            "where a value came from is what this records",
            data,
        )

    @model_validator(mode="after")
    def _default_needs_rationale(self) -> Provenanced[T]:
        if self.origin is Origin.DEFAULT and not self.rationale:
            raise _provenance_refusal(
                "a defaulted value must carry a human-readable rationale",
                subject="rationale",
                source=_RATIONALE_SOURCE,
            )
        if self.origin is Origin.PROFILE_SUPPLIED and not self.rationale:
            raise _provenance_refusal(
                "a profile-supplied value must name the profile it came from in its rationale",
                subject="rationale",
                source=_RATIONALE_SOURCE,
            )
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
