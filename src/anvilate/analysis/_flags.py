"""A declared yes-or-no fact, refused when it is anything but ``True`` or ``False``.

A flag like ``plane_strain`` or ``passive`` picks a branch by its truth, and Python finds
truth in anything: ``"no"``, ``[]`` read as false and ``"false"``, ``nan`` and ``[0]`` as
true. A caller who wrote ``passive="false"`` got the passive Rankine coefficient, and every
comparison downstream of it was correct arithmetic on the branch nobody asked for.
"""

from __future__ import annotations

__all__: list[str] = []


def require_flag(value: object, *, name: str) -> bool:
    """``value``, having refused anything that is not a ``bool`` by name."""
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be True or False; got {value!r}")
    return value
