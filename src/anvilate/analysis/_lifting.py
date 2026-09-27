"""Shared structured refusal for lifting-mechanics inputs."""

from __future__ import annotations

from ..refusal import RefusalError, Remedy

__all__: list[str] = []


class _LiftingInputError(RefusalError, ValueError):
    """A lifting input that cannot be used without a concrete correction."""

    def __init__(self, message: str, *, action: str, subject: str, source: str) -> None:
        super().__init__(
            message,
            remedies=(Remedy(action=action, subject=subject, source=source),),
        )
