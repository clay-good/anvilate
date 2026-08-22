"""The first-party agent skill, shipped inside the package so it is available offline.

An agent with tool access and no procedural guidance gets Anvilate wrong in four
predictable ways: it recalls a standard dimension instead of retrieving it, it reports
success without reading the scorecard, it reads "not evaluated" as a pass, and it
presents a screening result as a certified analysis. None of those is a bug in the
library, and all four produce an artifact carrying Anvilate's evidence bundle.

The skill is the cheapest available lever on that, and it is the only one that reaches
agents whose operators never read the documentation. It is **documentation and nothing
else**: it grants no capability, loosens no gate, and changes no result. Everything it
says is enforced by the library whether or not it was loaded — which is why the skill can
be shipped as plain text with no privilege attached to it.

The content lives in :data:`SKILL_PATH` (``skills/anvilate/SKILL.md``, the open SKILL.md
convention) and is verified in CI against the real public surface: every ``anvilate``
symbol it names must exist, and every worked example it contains is executed with its
claimed output compared byte for byte. A skill that describes a function that no longer
exists fails the build rather than shipping stale.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

__all__ = ["SKILL_NAME", "SKILL_PATH", "skill_text"]

SKILL_NAME = "anvilate"

# Resolved through importlib.resources rather than __file__ so it works from a wheel, a
# zip, or a source tree alike — the skill has to be there in every installation, because
# an agent that cannot find it is an agent operating without it.
SKILL_PATH = Path(str(files("anvilate.skills") / SKILL_NAME / "SKILL.md"))


def skill_text() -> str:
    """The skill's Markdown source. No network, no filesystem outside the package."""
    return (files("anvilate.skills") / SKILL_NAME / "SKILL.md").read_text(encoding="utf-8")
