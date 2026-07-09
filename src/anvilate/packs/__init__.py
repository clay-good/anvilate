"""Anvilate discipline packs: domain-specific member models and their screens.

A pack layers a discipline's vocabulary (its members, load cases, and code-cited
checks) over the deterministic T1 analysis library, keeping the core Design Spec
IR lean. The first is :mod:`anvilate.packs.structural`, which declares structural
members and auto-dispatches each to the right beam check, rolling the results
into a scorecard.
"""

from __future__ import annotations
