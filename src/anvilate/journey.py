"""The next step: what a result says to do, derived from the result alone.

An agent that has just screened a part has a card and no plan. Left to itself it stops at
the first green line, or retries the same call, or asks the person what to do about a
failure the card already knows how to repair. :func:`next_steps` turns a card into an
ordered list of typed steps, each naming the tool to call, what to pass it, and why, by
one fixed precedence:

1. a refusal's own remedies;
2. failed checks whose design inverse solved a corrective value (re-validate with it);
3. failed checks with no solved value (re-validate after moving the named parameter);
4. tiers the document demands that did not run (build the solid; run the FEA);
5. checks held back by a value nobody declared, one step per missing declaration;
6. when nothing holds the result back, the export of the review package.

The list is a function of the result: the same card gives the same steps, and it is never
empty, because a result short of review always has something left to do, even if that is
exporting a draft. Every tool it names is one the server publishes, which a test holds
against the live catalog.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import ConfigDict, Field

from ._models import EMPTY_MAP, FrozenMap, ItemCollection, Named, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard

__all__ = [
    "JOURNEY_STAGES",
    "StageState",
    "JourneyState",
    "journey_state",
    "write_review_package",
    "NEXT_STEP_TOOLS",
    "NextStep",
    "NextSteps",
    "next_steps",
]

#: Every tool a step may name. A test holds each against the server's published catalog.
NEXT_STEP_TOOLS = (
    "run_validation",
    "build_combination",
    "build_part",
    "run_fea_validation",
    "export_artifact",
)

# The tools a result is re-checked with, and the export each result's subject supports.
_RECHECK_TOOLS = ("run_validation", "build_combination")
_EXPORTS = ("review_package", "step")

# A tier the card reports as an entry of its own when the document demands it and it did
# not run, and the tool that runs it.
_TIER_TOOLS = {"T0 geometry": "build_part", "T3 FEA": "run_fea_validation"}


class _JourneyInputError(RefusalError, ValueError):
    """A next-step input that cannot be used without correction."""


class NextStep(StatableModel):
    """One step: the tool to call, what to pass it beyond the subject, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Named
    arguments: FrozenMap[str, str] = Field(default_factory=lambda: EMPTY_MAP)
    reason: Named

    def __str__(self) -> str:
        passed = ", ".join(f"{k}={v}" for k, v in self.arguments.items())
        return f"{self.tool}({passed}): {self.reason}"


class NextSteps(ItemCollection, StatableModel):
    """The ordered steps a result names, first the one that matters most."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: tuple[NextStep, ...] = Field(min_length=1)


def _value(value: float, unit: str | None) -> str:
    return f"{value:.4g} {unit}".strip() if unit else f"{value:.4g}"


def next_steps(
    card: Scorecard,
    *,
    remedies: Sequence[str] = (),
    tool: str = "run_validation",
    export_format: str = "review_package",
) -> tuple[NextStep, ...]:
    """The steps ``card`` calls for, by the precedence in this module's docstring.

    ``tool`` is the call that produced the card and re-checks it once changed:
    ``run_validation`` for a spec, ``build_combination`` for a combination. ``remedies`` are
    a refusal's own remedies, when that call was refused; each becomes a step re-calling
    ``tool`` with that correction, ahead of everything else. ``export_format`` is what the
    result's subject exports as when nothing holds it back: ``review_package`` for a
    screening (``draft`` when a check has no verdict nothing here can supply), ``step`` for
    a combination.
    """
    if export_format not in _EXPORTS:
        raise _JourneyInputError(
            f"export_format {export_format!r} is not one a step may name ({list(_EXPORTS)})",
            remedies=(Remedy(action="replace", subject="export_format", source="the tool result"),),
        )
    if not isinstance(card, Scorecard):
        raise _JourneyInputError(
            "card must be a Scorecard",
            remedies=(Remedy(action="replace", subject="card", source="the tool result"),),
        )
    if tool not in _RECHECK_TOOLS:
        raise _JourneyInputError(
            f"tool {tool!r} is not one a step may name to re-check ({list(_RECHECK_TOOLS)})",
            remedies=(Remedy(action="replace", subject="tool", source="the tool result"),),
        )
    remedies = each_one(remedies, str, named="remedies")
    steps = [NextStep(tool=tool, reason=f"the call was refused: {remedy}") for remedy in remedies]
    failed = [e for e in card.entries if e.status is CheckStatus.FAIL]
    for entry in failed:
        hint = entry.repair_hint
        if hint is not None and hint.corrective_value is not None:
            value = _value(hint.corrective_value, hint.unit)
            steps.append(NextStep(
                tool=tool, arguments={"set": hint.parameter, "to": value},
                reason=f"{entry.name} fails; its inverse solves {hint.parameter} = {value}",
            ))  # fmt: skip
    for entry in failed:
        hint = entry.repair_hint
        if hint is None or hint.corrective_value is None:
            move = (f"{hint.direction.value} {hint.parameter}" if hint is not None
                    else "revise the design")  # fmt: skip
            reason = f"{entry.name} fails; {move}, then re-validate"
            steps.append(NextStep(tool=tool, arguments={"change": move}, reason=reason))
    unrun = [e for e in card.entries if e.status is CheckStatus.NOT_EVALUATED]
    for entry in unrun:
        if entry.name in _TIER_TOOLS and not entry.needs:
            steps.append(NextStep(tool=_TIER_TOOLS[entry.name],
                                  reason=f"the document demands {entry.name}, which did not "
                                         "run"))  # fmt: skip
    declared: dict[str, list[str]] = {}
    for entry in unrun:
        for need in entry.needs:
            declared.setdefault(need.declaration, []).append(entry.name)
    first = {}
    for entry in unrun:
        for need in entry.needs:
            first.setdefault(need.declaration, need.takes)
    for declaration, held in declared.items():
        steps.append(NextStep(
            tool=tool, arguments={"declare": declaration},
            reason=f"declare {declaration} ({first[declaration]}); it holds back "
                   f"{', '.join(dict.fromkeys(held))}",
        ))  # fmt: skip
    if not steps:
        silent = [e.name for e in unrun]
        reason = ("every check has a verdict; write the review package" if not silent
                  else f"nothing here can supply what {', '.join(silent)} need; write the "
                       "review package as a draft, those checks marked not evaluated")  # fmt: skip
        arguments = {"format": export_format}
        if silent and export_format == "review_package":
            arguments["draft"] = "true"
        steps.append(NextStep(tool="export_artifact", arguments=arguments, reason=reason))
    return tuple(steps)


#: The stages a design passes through, in order.
JOURNEY_STAGES = ("described", "screened", "simulated", "optimized", "review_ready")


class StageState(StatableModel):
    """One stage: reached, not reached (with the gaps that hold it back), or not applicable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Named
    state: str = Field(pattern=r"^(reached|not_reached|not_applicable)$")
    gaps: tuple[Named, ...] = ()

    def __str__(self) -> str:
        held = f": {'; '.join(self.gaps)}" if self.gaps else ""
        return f"{self.stage} {self.state.replace('_', ' ')}{held}"


class JourneyState(StatableModel):
    """The furthest stage a result has reached, and each stage's state.

    ``stage`` is the last stage reached with every applicable stage before it reached too:
    a stage that does not apply is passed over, never counted as reached.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Named
    stages: tuple[StageState, ...] = Field(min_length=len(JOURNEY_STAGES))

    def __str__(self) -> str:
        return "\n".join([f"journey: {self.stage}", *(f"  {s}" for s in self.stages)])


def journey_state(card: Scorecard, *, package_written: bool = False) -> JourneyState:
    """How far ``card``'s design has come, and what holds back each later stage.

    ``described``: the document parsed into a card. ``screened``: every check but the FEA
    tier has a verdict; the gaps name those that do not. ``simulated``: the FEA tier the
    document demands has a verdict; not applicable when it demands none. ``optimized``: not
    applicable until a study is declared, which this release cannot run. ``review_ready``:
    every check has a verdict and the review package has been written for this content
    (``package_written``, which only the export that wrote it can say).
    """
    if not isinstance(card, Scorecard):
        raise _JourneyInputError(
            "card must be a Scorecard",
            remedies=(Remedy(action="replace", subject="card", source="the tool result"),),
        )
    open_ = [e.name for e in card.entries if e.status is CheckStatus.NOT_EVALUATED]
    fea = [e for e in card.entries if e.name == "T3 FEA"]
    unscreened = [n for n in open_ if n != "T3 FEA"]
    stages = [StageState(stage="described", state="reached")]
    stages.append(StageState(stage="screened", state="not_reached" if unscreened else "reached",
                             gaps=tuple(f"{n} has no verdict" for n in unscreened)))  # fmt: skip
    if not fea:
        stages.append(StageState(stage="simulated", state="not_applicable",
                                 gaps=("the document demands no FEA",)))  # fmt: skip
    elif fea[0].status is CheckStatus.NOT_EVALUATED:
        stages.append(StageState(stage="simulated", state="not_reached",
                                 gaps=("T3 FEA has not run",)))  # fmt: skip
    else:
        stages.append(StageState(stage="simulated", state="reached"))
    stages.append(StageState(stage="optimized", state="not_applicable",
                             gaps=("no study is declared",)))  # fmt: skip
    ready_gaps = tuple(f"{n} has no verdict" for n in open_) + (
        () if package_written else ("the review package is not written for this content",)
    )
    stages.append(StageState(stage="review_ready",
                             state="not_reached" if ready_gaps else "reached",
                             gaps=ready_gaps))  # fmt: skip
    furthest = "described"
    for state in stages:
        if state.state == "not_reached":
            break
        if state.state == "reached":
            furthest = state.stage
    return JourneyState(stage=furthest, stages=tuple(stages))


def write_review_package(
    spec: Any,
    card: Scorecard,
    sections: Any,
    *,
    stem: str,
    draft: bool,
    toolchain: str,
    write: Callable[[str, bytes], dict[str, Any]],
) -> dict[str, Any]:
    """The review package for one content digest: the bundle, the dossier and a manifest.

    Refused while a check has no verdict, unless ``draft``; a draft is marked draft in every
    file it writes (its file names, the bundle's ``draft`` key, the dossier's first line and
    the manifest). Writing it records no review: the dossier still reads "not yet reviewed"
    until a named reviewer records one, and the manifest says so. ``write(name, data)``
    writes one file and returns where it went (``path``, ``bytes``, ``sha256``).
    """
    import json

    from .attestation import canonical_json, sha256_hex
    from .review import build_dossier

    unrun = [e.name for e in card.entries if e.status is CheckStatus.NOT_EVALUATED]
    if unrun and not draft:
        raise _JourneyInputError(
            f"a review package is written once every check has a verdict, and "
            f"{', '.join(unrun)} have none. Supply what they need, or ask for a draft, "
            "written marked as one in every file",
            remedies=(Remedy(action="add", subject="draft", source="the export request"),),
        )  # fmt: skip
    digest = sha256_hex(canonical_json(
        {"spec": spec.model_dump(mode="json"), "scorecard": card.model_dump(mode="json")}
    ).encode("utf-8"))  # fmt: skip
    mark = "draft." if draft else ""
    bundle = sections.model_copy(update={"draft": True}) if draft else sections
    dossier = build_dossier(card, toolchain=toolchain)
    head = (f"DRAFT: not review-ready; no verdict for {', '.join(unrun)}" if draft
            else f"Review-ready for content sha256:{digest}")  # fmt: skip
    lines = [head, _RECORDS_NO_REVIEW, "", dossier.summary(), "",
             *(item.headline for item in dossier.items)]  # fmt: skip
    files = [
        write(f"{stem}.review.{mark}bundle.json",
              canonical_json(bundle.to_document_dict()).encode("utf-8")),
        write(f"{stem}.review.{mark}dossier.txt", ("\n".join(lines) + "\n").encode("utf-8")),
    ]  # fmt: skip
    state = journey_state(card, package_written=not draft)
    manifest = {
        "package": "anvilate review package",
        "content_sha256": digest,
        "draft": draft,
        "records_review": False,
        "statement": _RECORDS_NO_REVIEW,
        "journey": state.model_dump(mode="json"),
        "files": [{"name": _name(f["path"]), "sha256": f["sha256"]} for f in files],
    }
    listed = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    files.append(write(f"{stem}.review.{mark}manifest.json", listed.encode("utf-8")))
    return {"files": tuple(files), "draft": draft, "journey": state.model_dump(mode="json"),
            "content_sha256": digest}  # fmt: skip


_RECORDS_NO_REVIEW = "Writing this package records no review, approval or sign-off."


def _name(path: str) -> str:
    from pathlib import PurePath

    return PurePath(path).name
