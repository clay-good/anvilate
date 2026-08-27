"""Scoring a spec-compiled pipeline against an external structured-spec suite.

The agent-driving half of this measurement is :mod:`anvilate.agenteval`, which scores a
transcript. This is the other half: a public text-to-CAD benchmark whose cases are
*structured design specifications* rather than free prose, so a deterministic pipeline can
be compared with the field on the same inputs.

The first suite is MUSE (arXiv:2605.28579) — code MIT, dataset CC BY 4.0, 106 cases, each
a Markdown specification under fixed headings. Its data is fetched rather than bundled,
per the licence review in ``openspec/changes/extend-benchmarking-agent-evals/design.md``.

**What this module is careful about is the denominator.** A benchmark score over a set the
pipeline cannot accept is a number about the benchmark. So every case is first read into
:class:`CaseSpecification` and then screened by :func:`scope_verdict`, which says *in
scope* or names the reason it is not — an assembly a one-part Design Spec cannot express,
or a material with nothing in the database to resolve to. :func:`suite_accounting` is that
census over a whole suite, and it is what gets published beside any score: the count and
the reason, never a percentage of cases nothing could compile.

Nothing here scores a model. It reads a case and decides whether Anvilate is entitled to
an opinion about it.
"""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict, field_validator

from .fetch import DatasetRecipe

__all__ = [
    "MUSE_CASE_INDEX",
    "CaseSpecification",
    "ScopeVerdict",
    "SuiteAccounting",
    "parse_case_specification",
    "scope_verdict",
    "suite_accounting",
]


# The dataset is pinned to a commit rather than to `main`: a benchmark with a leaderboard
# moves, and a published score has to name the version it was measured against.
MUSE_CASE_INDEX = DatasetRecipe(
    name="muse-metadata.jsonl",
    url=(
        "https://huggingface.co/datasets/dongxiaoyu/MUSE/resolve/"
        "f8a1dc45d1ea73df4161e8a1caf1d503c5358c30/metadata.jsonl"
    ),
    sha256="a2b7ac9453b3bedde6f5fd65748e5fd5258fff209896cc28da4b5c1514a83868",
    license="CC-BY-4.0",
    source="MUSE benchmark case index (arXiv:2605.28579), 106 cases",
    redistributable=False,
)

# Every one of the 106 cases carries these; two more (`Adjustable Parameters`, `Component
# Details`) do as well and one (`Component Assembly Graph (Textual)`) is in 105, so the
# parser reads what is universal and ignores the rest rather than requiring it.
_REQUIRED_HEADINGS = (
    "Design Goal",
    "Geometry and Dimensions",
    "Material",
    "Manufacturing Method",
    "Connection Method (Joint Type)",
    "Mechanical Condition",
    "Structural Features",
    "Special Requirements",
    "Planned Component Quantity",
    "Component Names",
)


class CaseSpecification(BaseModel):
    """One suite case, read out of its Markdown headings.

    The fields are the suite's own vocabulary, not Anvilate's: this is what the case
    *says*, and the translation into a Design Spec is a separate step that may refuse.
    ``component_count`` is the case's declared part count, which is the first thing that
    decides whether a one-part spec can express it at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    design_goal: str
    geometry: str
    material: str
    manufacturing_method: str
    joint_type: str
    mechanical_condition: str
    structural_features: str
    special_requirements: str
    component_count: int
    component_names: tuple[str, ...]

    @field_validator("component_count")
    @classmethod
    def _at_least_one_part(cls, value: int) -> int:
        if value < 1:
            raise ValueError(
                f"a case declares {value} components; a design with no parts is not a "
                "case this can be read as."
            )
        return value


class ScopeVerdict(BaseModel):
    """Whether Anvilate can express a case at all, and if not, why not.

    ``reason`` is empty exactly when ``in_scope`` is true. It is a sentence rather than a
    code because it is published: the accounting's whole value is that a reader can see
    *what* the pipeline could not take, and a tally of opaque labels would not show that.
    """

    # `validate_default` because the empty reason is the *default*, and pydantic does not
    # validate defaults unless told to: without it a refusal with no reason — the one
    # thing this model exists to prevent — constructs cleanly.
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    case_id: str
    in_scope: bool
    reason: str = ""

    @field_validator("reason")
    @classmethod
    def _reason_or_nothing(cls, value: str, info) -> str:
        in_scope = info.data.get("in_scope")
        if in_scope is True and value:
            raise ValueError("an in-scope case carries no reason; it was not refused")
        if in_scope is False and not value.strip():
            raise ValueError(
                "a refusal without a reason is the shape this module exists to avoid: "
                "say what could not be expressed"
            )
        return value


class SuiteAccounting(BaseModel):
    """The census a score has to be published beside.

    ``in_scope`` and ``out_of_scope`` sum to ``total``, and ``reasons`` counts the
    refusals by their sentence, so the published figure is the count and the reason
    rather than a percentage of a set the pipeline never accepted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int
    in_scope: int
    out_of_scope: int
    reasons: tuple[tuple[str, int], ...]


def parse_case_specification(case_id: str, markdown: str) -> CaseSpecification:
    """Read one case's Markdown specification into a typed record.

    Raises :class:`ValueError` naming the heading when one the format guarantees is
    missing — a case that does not carry them is not a case in this format, and guessing
    at a missing material or component count is how a benchmark comparison gets a number
    it has not earned.
    """
    sections = {
        heading.strip(): body.strip()
        for heading, body in re.findall(r"^## (.+?)\n(.*?)(?=\n## |\Z)", markdown, re.S | re.M)
    }
    missing = [heading for heading in _REQUIRED_HEADINGS if heading not in sections]
    if missing:
        raise ValueError(
            f"{case_id} is missing the heading(s) {missing}; the suite's format carries "
            "them in every case, so this is a different document."
        )

    quantity = sections["Planned Component Quantity"].splitlines()[0].strip()
    digits = re.search(r"\d+", quantity)
    if digits is None:
        raise ValueError(
            f"{case_id} states its component quantity as {quantity!r}, which has no number in it."
        )

    names = tuple(
        line.lstrip("-* ").strip()
        for line in sections["Component Names"].splitlines()
        if line.strip()
    )
    return CaseSpecification(
        case_id=case_id,
        design_goal=sections["Design Goal"],
        geometry=sections["Geometry and Dimensions"],
        material=sections["Material"].splitlines()[0].strip(),
        manufacturing_method=sections["Manufacturing Method"].splitlines()[0].strip(),
        joint_type=sections["Connection Method (Joint Type)"].splitlines()[0].strip(),
        mechanical_condition=sections["Mechanical Condition"],
        structural_features=sections["Structural Features"],
        special_requirements=sections["Special Requirements"],
        component_count=int(digits.group()),
        component_names=names,
    )


def scope_verdict(case: CaseSpecification, *, known_materials: frozenset[str]) -> ScopeVerdict:
    """Whether a Design Spec can express this case, and the reason when it cannot.

    Two refusals, in the order they bind. A Design Spec is a typed statement of intent for
    **one part**, so a multi-part case is out of scope by construction rather than by
    omission. And a material with no record in ``known_materials`` has nothing to resolve
    to — the screening checks would report `not_evaluated`, which is honest but is not a
    benchmark result, and inventing a modulus to get a number is the failure this library
    exists to refuse.

    ``known_materials`` is passed in rather than read from the bundled database, so the
    accounting moves on its own as materials are added and this module never has to know
    which database a caller is screening against.
    """
    if case.component_count > 1:
        return ScopeVerdict(
            case_id=case.case_id,
            in_scope=False,
            reason=(
                f"an assembly of {case.component_count} parts; a Design Spec states "
                "intent for one part"
            ),
        )
    if case.material not in known_materials:
        return ScopeVerdict(
            case_id=case.case_id,
            in_scope=False,
            reason=f"the material {case.material!r} has no record in the database",
        )
    return ScopeVerdict(case_id=case.case_id, in_scope=True)


def suite_accounting(verdicts: list[ScopeVerdict] | tuple[ScopeVerdict, ...]) -> SuiteAccounting:
    """Tally a suite's verdicts into the census published beside any score."""
    verdicts = tuple(verdicts)
    counted = Counter(verdict.reason for verdict in verdicts if not verdict.in_scope)
    return SuiteAccounting(
        total=len(verdicts),
        in_scope=sum(1 for verdict in verdicts if verdict.in_scope),
        out_of_scope=sum(1 for verdict in verdicts if not verdict.in_scope),
        reasons=tuple(sorted(counted.items(), key=lambda pair: (-pair[1], pair[0]))),
    )
