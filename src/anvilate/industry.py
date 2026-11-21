"""Industry profiles: how an industry or a company screens, declared once and attributed.

The same bracket is screened differently by a spacecraft engineer, an automotive engineer
and a machine builder. The physics is the same; the rules around it are not: which factors
apply, which checks are mandatory for a class of item, which records must come out, which
drawing standard governs. An :class:`IndustryProfile` is that set of rules as data, each
rule citing its source or labeled a practice-based default, so nothing it adds is
anonymous.

Three things a profile does, and one it never does:

- **Required checks appear even when nothing triggered them.**
  :func:`apply_profile` puts every check the profile requires for an item's class on its
  card. One the screens did not run is *not evaluated*, naming the inputs it needs; one
  this installation cannot run (its pack or its analysis is missing) is *not available*,
  naming what to install. Neither is ever dropped.
- **Every rule is attributed.** Each entry a profile adds names the profile, its version
  and the rule; :meth:`ResolvedProfile.changes` lists everything the profile adds relative
  to the general profile, which adds nothing.
- **A company profile layers on an industry profile** (:func:`layer`), adding rules and
  overriding factors with their sources. An override that lowers a factor is a
  **relaxation**, reported with both values and the override's source.
- **A profile is never a compliance claim.** :data:`SCREENING_NOT_CERTIFICATION` goes on
  every rendering: a profile is a screening configuration, and compliance is decided by
  the user's quality system and regulator.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from typing import Literal

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ._models import Named, Provenance, StatableModel
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard, ScorecardEntry

__all__ = [
    "SCREENING_NOT_CERTIFICATION",
    "ProfileRule",
    "FactorRule",
    "RequiredCheck",
    "RequiredArtifact",
    "AwaitedValue",
    "IndustryProfile",
    "Relaxation",
    "ResolvedProfile",
    "ProfiledCard",
    "ProfileListing",
    "GENERAL",
    "layer",
    "resolve",
    "apply_profile",
    "load_profile",
    "bundled_profiles",
    "industry_profile",
]

_SOURCE = "the industry profile: each rule with its source or a practice-default label"

#: Printed on every card, report header and listing produced under a profile.
SCREENING_NOT_CERTIFICATION = (
    "a profile is a screening configuration, not a certification or a regulatory "
    "determination: compliance is decided by your quality system and your regulator"
)


class _ProfileInputError(RefusalError, ValueError):
    """An industry-profile input that cannot be used without correction."""


def _refuse(message: str, *, subject: str) -> _ProfileInputError:
    return _ProfileInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),)
    )


class ProfileRule(StatableModel):
    """What every rule shares: an id, and either a source or a practice-default label.

    ``source`` cites the document and clause the rule comes from. ``practice_default``
    says the rule is a common practice with no single citable source; the card then says
    so rather than lending it a citation it does not have. A rule with neither is refused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    source: Provenance | None = None
    practice_default: bool = False

    @model_validator(mode="after")
    def _sourced(self) -> ProfileRule:
        if self.source is None and not self.practice_default:
            raise _refuse(
                f"rule '{self.id}' has neither a source nor a practice-default label; cite "
                "the document and clause, or set practice_default",
                subject=f"rule {self.id}",
            )  # fmt: skip
        return self

    @property
    def basis(self) -> str:
        """The rule's source, or its practice-default label."""
        return self.source if self.source is not None else "practice-based default, no source"


class FactorRule(ProfileRule):
    """A named factor the profile sets, such as ``ultimate`` or ``fitting``.

    Larger is stricter: a factor multiplies the load or divides the allowable. A layered
    override with a lower value is reported as a relaxation.
    """

    name: Named
    value: float = Field(gt=0, allow_inf_nan=False)


class RequiredCheck(ProfileRule):
    """A check the profile requires for every item of a class.

    ``satisfied_by`` names the card entries that are this check, by ``check_id`` or by
    name (an entry named ``"bracket random vibration"`` matches ``"random vibration"``:
    equal, or ending in a space then it). ``needs`` names the inputs the check reads,
    for the not-evaluated entry when it did not run. ``pack`` names the module the check
    lives in and ``analysis`` the function that computes it; either missing from this
    installation makes the check not available, with ``install`` as the remedy.
    ``implemented: false`` says no screen in this library computes the check yet, which
    is shown as not available too: a requirement the library cannot meet is stated, never
    dropped.
    """

    item_class: Named
    check: Named
    satisfied_by: tuple[Named, ...] = Field(min_length=1, max_length=32)
    needs: tuple[Named, ...] = ()
    pack: Named | None = None
    analysis: Named | None = None
    install: Named | None = None
    implemented: bool = True


class RequiredArtifact(ProfileRule):
    """A record the profile requires to come out, such as a margin table or a DFMEA."""

    artifact: Literal[
        "margin_table", "dfmea", "dvpr", "risk_file", "characteristic_accountability",
        "control_plan_seed", "requirement_trace",
    ]  # fmt: skip


class AwaitedValue(StatableModel):
    """A rule the profile cannot fill because its value lives in a paid standard.

    Named rather than invented: ``standard`` says where your organization's licensed copy
    gives the value, and the profile ships without it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    what: Named
    standard: Named


class IndustryProfile(StatableModel):
    """A declared bundle of rules, identified by URN and version.

    ``extends`` names the URN of the profile this one layers on; :func:`layer` applies it.
    ``item_classes`` is the profile's own vocabulary: an item is screened under the profile
    by declaring one of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    urn: str = Field(pattern=r"^urn:[a-z0-9][a-z0-9-]{0,31}:\S+$", max_length=256)
    name: Named
    version: Named
    extends: str | None = Field(default=None, pattern=r"^urn:", max_length=256)
    item_classes: tuple[Named, ...] = ()
    factor_set: ProfileRule | None = None
    factors: tuple[FactorRule, ...] = ()
    required_checks: tuple[RequiredCheck, ...] = ()
    required_artifacts: tuple[RequiredArtifact, ...] = ()
    drawing_standard: ProfileRule | None = None
    awaiting: tuple[AwaitedValue, ...] = ()

    @model_validator(mode="after")
    def _coherent(self) -> IndustryProfile:
        ids = [r.id for r in self._rules()] + [a.id for a in self.awaiting]
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            raise _refuse(f"profile {self.urn} declares rules {twice} twice",
                          subject="factors, required_checks, required_artifacts")  # fmt: skip
        names = [f.name for f in self.factors]
        doubled = sorted({n for n in names if names.count(n) > 1})
        if doubled:
            raise _refuse(f"profile {self.urn} sets factors {doubled} twice", subject="factors")
        stray = sorted({r.item_class for r in self.required_checks} - set(self.item_classes))
        if stray and self.extends is None:  # a layered profile inherits its parent's classes
            raise _refuse(f"profile {self.urn} requires checks for item classes {stray} it "
                          f"does not declare ({list(self.item_classes)})",
                          subject="item_classes")  # fmt: skip
        return self

    def _rules(self) -> tuple[ProfileRule, ...]:
        single = tuple(r for r in (self.factor_set, self.drawing_standard) if r is not None)
        return (*single, *self.factors, *self.required_checks, *self.required_artifacts)

    @property
    def label(self) -> str:
        return f"{self.name} {self.version} ({self.urn})"


class Relaxation(StatableModel):
    """A factor an override lowered below the value of the profile it extends."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor: Named
    parent_value: float
    parent_basis: Provenance
    value: float
    source: Provenance

    def __str__(self) -> str:
        return (f"RELAXED {self.factor}: {self.value:g} ({self.source}) below "
                f"{self.parent_value:g} ({self.parent_basis})")  # fmt: skip


class ResolvedProfile(StatableModel):
    """A profile with its parents applied: the rules that hold, and what was relaxed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: IndustryProfile
    chain: tuple[Named, ...]
    relaxations: tuple[Relaxation, ...] = ()

    def changes(self) -> tuple[str, ...]:
        """Everything this profile adds or changes relative to the general profile, each
        naming its rule and basis. The general profile adds nothing, so it lists nothing."""
        p = self.profile
        lines = []
        if p.factor_set is not None:
            lines.append(f"factor set: {p.factor_set.id} [{p.factor_set.basis}]")
        lines += [f"factor {f.name} = {f.value:g}: {f.id} [{f.basis}]" for f in p.factors]
        lines += [f"required check for {c.item_class}: {c.check}: {c.id} [{c.basis}]"
                  for c in p.required_checks]  # fmt: skip
        lines += [f"required artifact: {a.artifact}: {a.id} [{a.basis}]"
                  for a in p.required_artifacts]  # fmt: skip
        if p.drawing_standard is not None:
            lines.append(f"drawing standard: {p.drawing_standard.id} "
                         f"[{p.drawing_standard.basis}]")  # fmt: skip
        lines += [f"awaiting your value: {a.what} ({a.standard}): {a.id}" for a in p.awaiting]
        lines += [str(r) for r in self.relaxations]
        return tuple(lines)

    def header(self) -> str:
        """The line a report under this profile opens with."""
        return f"screened under {self.profile.label}; {SCREENING_NOT_CERTIFICATION}"

    def __str__(self) -> str:
        return "\n".join([self.header(), *(f"  {line}" for line in self.changes())])


#: Today's behavior: no factors, no required checks, no artifacts. Binding it changes
#: nothing on any card, which a regression over every example holds.
GENERAL = IndustryProfile(urn="urn:anvilate:profile:general", name="General", version="1.0.0")


def layer(parent: IndustryProfile, child: IndustryProfile) -> ResolvedProfile:
    """``child`` applied over ``parent``: its rules added, its factors overriding.

    ``child.extends`` must name ``parent``. A child rule with a parent rule's id replaces
    it; a required check cannot be dropped, only added to. A child factor lower than the
    parent's is a relaxation, reported with both values and both bases.
    """
    for name, value in (("parent", parent), ("child", child)):
        if not isinstance(value, IndustryProfile):
            raise _refuse(f"{name} must be an IndustryProfile", subject=name)
    if child.extends != parent.urn:
        raise _refuse(f"profile {child.urn} extends {child.extends!r}, not {parent.urn}",
                      subject="extends")  # fmt: skip
    others = {r.id for r in child._rules() if not isinstance(r, RequiredCheck)}
    dropped = sorted({c.id for c in parent.required_checks} & others)
    if dropped:
        raise _refuse(f"profile {child.urn} reuses required-check ids {dropped} for other "
                      "rules; a layered profile adds required checks and never removes "
                      "them", subject="required_checks")  # fmt: skip
    old = {f.name: f for f in parent.factors}
    relaxations = tuple(
        Relaxation(factor=f.name, parent_value=old[f.name].value, parent_basis=old[f.name].basis,
                   value=f.value, source=f.basis)
        for f in child.factors if f.name in old and f.value < old[f.name].value
    )  # fmt: skip
    factors = {**old, **{f.name: f for f in child.factors}}

    def merged(mine: Sequence[ProfileRule], theirs: Sequence[ProfileRule]) -> tuple:
        ids = {r.id for r in theirs}
        return (*(r for r in mine if r.id not in ids), *theirs)

    profile = IndustryProfile(
        urn=child.urn, name=child.name, version=child.version, extends=child.extends,
        item_classes=tuple(dict.fromkeys((*parent.item_classes, *child.item_classes))),
        factor_set=child.factor_set or parent.factor_set,
        factors=tuple(factors.values()),
        required_checks=merged(parent.required_checks, child.required_checks),
        required_artifacts=merged(parent.required_artifacts, child.required_artifacts),
        drawing_standard=child.drawing_standard or parent.drawing_standard,
        awaiting=tuple({a.id: a for a in (*parent.awaiting, *child.awaiting)}.values()),
    )  # fmt: skip
    return ResolvedProfile(profile=profile, chain=(parent.urn, child.urn),
                           relaxations=relaxations)  # fmt: skip


def resolve(profile: IndustryProfile) -> ResolvedProfile:
    """A profile that extends nothing, as a :class:`ResolvedProfile`; one that extends
    another must be resolved with :func:`layer`, which needs the parent."""
    if not isinstance(profile, IndustryProfile):
        raise _refuse("profile must be an IndustryProfile", subject="profile")
    if profile.extends is not None:
        raise _refuse(f"profile {profile.urn} extends {profile.extends}; resolve it with "
                      "layer(parent, profile)", subject="profile")  # fmt: skip
    return ResolvedProfile(profile=profile, chain=(profile.urn,))


class ProfileListing(StatableModel):
    """What a profile did to one card: its header, every rule it changed relative to the
    general profile, and the required checks it added or could not run here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    urn: Named
    label: Named
    item_class: Named | None = None
    header: Named
    changes: tuple[Named, ...] = ()
    added: tuple[Named, ...] = ()
    not_available: tuple[Named, ...] = ()


class ProfiledCard(StatableModel):
    """A card with the profile's required checks on it, and the profile it was read under."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    card: Scorecard
    profile: Named
    item_class: Named | None = None
    added: tuple[Named, ...] = ()
    not_available: tuple[Named, ...] = ()
    listing: ProfileListing

    def __str__(self) -> str:
        lines = [f"screened under {self.profile}; {SCREENING_NOT_CERTIFICATION}"]
        if self.added:
            lines.append(f"  required by the profile and not on the card: {', '.join(self.added)}")
        if self.not_available:
            lines.append(f"  not available in this installation: {', '.join(self.not_available)}")
        return "\n".join(lines)


def _matches(entry: ScorecardEntry, names: Sequence[str]) -> bool:
    return any(entry.check_id == n or entry.name == n or entry.name.endswith(f" {n}")
               for n in names)  # fmt: skip


def _missing(rule: RequiredCheck) -> str | None:
    """What this installation lacks to run the check, or ``None`` when nothing."""
    if not rule.implemented:
        return "screen"
    for kind, dotted in (("pack", rule.pack), ("analysis", rule.analysis)):
        if dotted is None:
            continue
        module, _, attribute = dotted.rpartition(".") if kind == "analysis" else (dotted, "", "")
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if found and attribute:
            found = hasattr(importlib.import_module(module), attribute)
        if not found:
            return f"{kind} {dotted}"
    return None


def apply_profile(
    card: Scorecard, profile: ResolvedProfile, *, item_class: str | None = None
) -> ProfiledCard:
    """``card`` with every check ``profile`` requires for ``item_class`` on it.

    A required check already on the card stays as it is. One that is not is added: *not
    evaluated*, naming the inputs it needs, or, when this installation lacks its pack or its
    analysis, *not evaluated* as **not available**, naming what is missing and how to
    install it. Each added entry's reference names the profile, its version and the rule.
    ``item_class`` must be one the profile declares; with none, nothing is required and the
    card is unchanged.
    """
    if not isinstance(card, Scorecard):
        raise _refuse("card must be a Scorecard", subject="card")
    if not isinstance(profile, ResolvedProfile):
        raise _refuse("profile must be a ResolvedProfile from resolve or layer",
                      subject="profile")  # fmt: skip
    p = profile.profile
    if item_class is not None and item_class not in p.item_classes:
        raise _refuse(f"item class {item_class!r} is not one {p.label} declares "
                      f"({list(p.item_classes)})", subject="item_class")  # fmt: skip
    rules = [r for r in p.required_checks if r.item_class == item_class]
    added, absent, entries = [], [], list(card.entries)
    for rule in rules:
        if any(_matches(entry, rule.satisfied_by) for entry in card.entries):
            continue
        reference = f"required by {p.label}, rule {rule.id} [{rule.basis}]"
        lacking = _missing(rule)
        if lacking is not None:
            how = f"; install with: {rule.install}" if rule.install else ""
            detail = (f"not available — the {lacking} this check needs is not in this "
                      f"installation{how}")  # fmt: skip
            absent.append(rule.check)
        else:
            inputs = ", ".join(rule.needs) if rule.needs else "the inputs its screen reads"
            detail = (f"not evaluated — required for every {item_class} under {p.name}, and "
                      f"nothing on the card ran it; it needs {inputs}")  # fmt: skip
        added.append(rule.check)
        entries.append(ScorecardEntry(name=rule.check, status=CheckStatus.NOT_EVALUATED,
                                      detail=detail, reference=reference))  # fmt: skip
    return ProfiledCard(
        card=Scorecard(entries=tuple(entries)) if added else card, profile=p.label,
        item_class=item_class, added=tuple(added), not_available=tuple(absent),
        listing=ProfileListing(
            urn=p.urn, label=p.label, item_class=item_class, header=profile.header(),
            changes=profile.changes(), added=tuple(added), not_available=tuple(absent),
        ),
    )  # fmt: skip


def load_profile(text: str) -> IndustryProfile:
    """A profile from its YAML or JSON text, validated against the published schema.

    A rule that cites nothing and is not labeled a practice default is refused naming the
    rule, as is every other incoherence, with the refusal itself rather than a wrapper.
    """
    import yaml

    from ._models import parse_yaml

    if not isinstance(text, str) or not text.strip():
        raise _refuse("the profile text is empty; give the profile as YAML or JSON",
                      subject="text")  # fmt: skip
    try:
        data = parse_yaml(text)
    except yaml.YAMLError as error:
        raise _refuse(f"the profile text is not YAML or JSON: {error}", subject="text") from None
    if not isinstance(data, dict):
        raise _refuse("the profile text must hold one mapping, the profile", subject="text")
    return _validated(data)


def _validated(data: dict) -> IndustryProfile:
    """``data`` as a profile, raising a refusal its validators raised as itself."""
    try:
        return IndustryProfile.model_validate(data)
    except ValidationError as error:
        for detail in error.errors():
            cause = (detail.get("ctx") or {}).get("error")
            if isinstance(cause, RefusalError):
                raise cause from None
        raise


def bundled_profiles() -> tuple[IndustryProfile, ...]:
    """The profiles shipped with the library, general first, each read from public documents.

    Each is a starting point to layer your company's profile on, never a program's
    requirements: the rules it could not fill from a public document are listed in its
    ``awaiting``.
    """
    from importlib.resources import files

    from ._models import parse_yaml

    folder = files("anvilate.standards") / "data" / "profiles"
    shipped = sorted(p.name for p in folder.iterdir() if p.name.endswith(".yaml"))
    profiles = []
    for name in shipped:
        text = (files("anvilate.standards") / "data" / "profiles" / name).read_text("utf-8")
        data = parse_yaml(text)
        # The dataset block is the bundled file's provenance and licence, which every YAML
        # file in the package carries; it is not part of the profile a user writes.
        data.pop("dataset")
        profiles.append(_validated(data))
    return (GENERAL, *profiles)


def industry_profile(name: str) -> IndustryProfile:
    """One shipped profile by its short name (the last part of its URN, such as
    ``spaceflight``) or by its full URN."""
    profiles = bundled_profiles()
    for profile in profiles:
        if name in (profile.urn, profile.urn.rpartition(":")[2]):
            return profile
    known = [p.urn.rpartition(":")[2] for p in profiles]
    raise _refuse(f"no shipped profile is named {name!r}; the shipped ones are {known}",
                  subject="name")  # fmt: skip
