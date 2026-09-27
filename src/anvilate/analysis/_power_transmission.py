"""Shared structured refusal for belt, chain, and worm-drive inputs."""

from __future__ import annotations

from ..refusal import RefusalError, Remedy

__all__: list[str] = []


class _DriveInputError(RefusalError, ValueError):
    """A power-transmission input that cannot be used without correction."""


def _drive_refusal(message: str, *, subject: str, source: str) -> _DriveInputError:
    return _DriveInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )
