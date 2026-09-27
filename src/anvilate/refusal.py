"""Structured remedies for raised refusals.

A message is for a person; a remedy record is for a caller that needs to present or act on
the next step without parsing prose. The three fields are deliberately required: an action
without its subject is vague, and a subject without a source leaves the caller to invent the
replacement value.
"""

from __future__ import annotations

from typing import Self

from pydantic import ConfigDict, PrivateAttr

from ._models import Named, RevalidatedModel

__all__ = ["RefusalError", "Remedy"]


class Remedy(RevalidatedModel):
    """One actionable next step: what to do, to what, using which authority or input."""

    model_config = ConfigDict(frozen=True)

    action: Named
    subject: Named
    source: Named
    _rendered: str | None = PrivateAttr(default=None)

    @classmethod
    def rendered(cls, *, action: str, subject: str, source: str, text: str) -> Self:
        """Build a typed remedy while preserving an established presentation string."""
        if not text.strip():
            raise ValueError("a rendered remedy cannot be blank")
        remedy = cls(action=action, subject=subject, source=source)
        remedy._rendered = text
        return remedy

    def __str__(self) -> str:
        if self._rendered is not None:
            return self._rendered
        return f"{self.action} {self.subject} using {self.source}"


class RefusalError(RuntimeError):
    """A raised refusal whose remedies remain machine-readable beside its message."""

    def __init__(self, message: str, *, remedies: tuple[Remedy, ...]) -> None:
        if not remedies:
            raise ValueError("a raised refusal must carry at least one structured remedy")
        self.remedies = remedies
        super().__init__(message)
