"""Confirmations that must be a person's, and the channel each one arrived through.

Four decisions in Anvilate are a person's by design: confirming a value an agent read off a
picture, a scan or a PDF; writing a file past a failing gate; recording a review or
accepting a failure as an exception; and agreeing to a dataset download. Over the MCP server
every one of them could otherwise be a tool argument, and the agent fills in tool arguments.
An agent that reads 80 mm off a sketch and then writes the engineer's name into
``confirmed_by`` has produced a document indistinguishable from one the engineer confirmed.

So the list is closed (:class:`PersonOnlyConfirmation`), no tool input carries a field that
supplies one (:data:`PERSON_ONLY_ARGUMENT_NAMES`, held over the tool catalog), and a
confirmation the server honours is a :class:`ConfirmationRecord` found where only a person's
channel puts one:

* **elicitation**: the user's MCP client showed a form and relayed the answer. The record
  names the client and version. It proves what the client relayed, not who answered, and
  every rendering says "answered through" rather than "confirmed by".
* **interactive terminal**: ``anvilate confirm`` typed at a terminal, which refuses to run
  without one. This is the only channel recorded as attesting a person, and it attests no
  more than that somebody was at the keyboard.
* **confirmation file**: a file the person writes in the output folder's ``confirmations``
  directory. Anvilate cannot see who wrote it and says so.

Records the server or the terminal command writes live under the dataset cache root
(:func:`confirmation_root`), keyed by the content digest of what they confirm, so any server
instance reads them and none needs to remember a call. A record confirms one exact thing: a
field's value read from one file, or one artifact of one spec. Change either and the digest
changes, and the old confirmation confirms nothing.

This module records what each channel can attest and no more. It verifies no identity.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, StatableModel, parse_json
from .refusal import RefusalError, Remedy

__all__ = [
    "PERSON_ONLY_ARGUMENT_NAMES",
    "ConfirmationChannel",
    "ConfirmationRecord",
    "PersonOnlyConfirmation",
    "apply_confirmations",
    "confirmation_file_form",
    "confirmation_root",
    "confirmations_disclosure",
    "draft_value_subject",
    "export_subject",
    "find_confirmation",
    "record_confirmation",
    "record_decline",
    "unbacked_confirmations",
    "was_declined",
]

_SOURCE = "the person-only confirmation rule: a confirmation is a person's act, never an argument"


class _ConfirmationInputError(RefusalError, ValueError):
    """A confirmation record or request that cannot be what it claims to be."""


def _refusal(message: str, *, subject: str) -> _ConfirmationInputError:
    return _ConfirmationInputError(
        message, remedies=(Remedy(action="correct", subject=subject, source=_SOURCE),)
    )


class PersonOnlyConfirmation(StrEnum):
    """The closed list of decisions only a person may make. Nothing else is on it."""

    # A value the user's agent read from a picture, a scan or a PDF, accepted as correct.
    DRAFT_VALUE = "draft_value"
    # A CAD or quality file written although its card does not pass, marked unvalidated.
    UNVALIDATED_EXPORT = "unvalidated_export"
    # A review recorded, or a failing check accepted as an exception.
    REVIEW_RECORD = "review_record"
    # A dataset Anvilate may read and not ship, downloaded once.
    DATASET_CONSENT = "dataset_consent"


class ConfirmationChannel(StrEnum):
    """How a confirmation reached Anvilate, which decides how much it attests."""

    ELICITATION = "elicitation"
    TERMINAL = "interactive_terminal"
    FILE = "confirmation_file"


# Property names no MCP tool input may carry at any depth outside the published document
# contracts it embeds. Each would let the caller supply a person-only confirmation as an
# argument. The Design Spec's own `confirmed_by` lives inside the embedded contract, where a
# document a person wrote at the shell carries it; over MCP a confirmation in a document is
# refused unless a record backs it (`unbacked_confirmations`).
PERSON_ONLY_ARGUMENT_NAMES = frozenset(
    {
        "accept_exception",
        "accepted_by",
        "confirmed",
        "confirmed_by",
        "confirmed_on",
        "confirmed_via",
        "consent",
        "override",
        "reviewed_by",
        "reviewer",
        "unvalidated",
    }
)


class ConfirmationRecord(StatableModel):
    """One person-only confirmation of one exact thing, with the channel it came through.

    ``subject`` is the content digest of what is confirmed (:func:`draft_value_subject`,
    :func:`export_subject`). ``client`` names the MCP client and version that relayed an
    elicitation, and is refused on any other channel, because only an elicitation passes
    through a client.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    confirms: PersonOnlyConfirmation
    subject: str = Field(pattern=r"^[0-9a-f]{64}$")
    person: Named
    on: date
    via: ConfirmationChannel
    client: Named | None = None

    @model_validator(mode="after")
    def _a_client_only_for_an_elicitation(self) -> ConfirmationRecord:
        if (self.via is ConfirmationChannel.ELICITATION) != (self.client is not None):
            raise _refusal(
                "an elicitation names the client and version that relayed it, and no other "
                "channel passes through a client",
                subject="client",
            )
        return self

    @property
    def attests_a_person(self) -> bool:
        """Whether the channel itself shows a person acted: only a terminal does."""
        return self.via is ConfirmationChannel.TERMINAL

    def __str__(self) -> str:
        if self.via is ConfirmationChannel.ELICITATION:
            return f"answered through {self.client} on {self.on}, naming {self.person}"
        where = (
            "at an interactive terminal"
            if self.via is ConfirmationChannel.TERMINAL
            else "in a confirmation file"
        )
        return f"confirmed by {self.person} on {self.on} {where}"


def _digest(payload: Mapping[str, Any]) -> str:
    from .attestation import canonical_json, sha256_hex

    return sha256_hex(canonical_json(dict(payload)).encode("utf-8"))


def _value_in(document: Any, path: str) -> Any:
    """The value at ``path`` (``element_params.holes[0].diameter``) in a dumped document."""
    import re

    node = document
    for part in path.split("."):
        name, _, rest = part.partition("[")
        node = node[name]
        for index in re.findall(r"\d+", rest):
            node = node[int(index)]
    return node


def draft_value_subject(spec: Any, field: str) -> str:
    """The digest a confirmation of ``field``'s agent-read value in ``spec`` is keyed by.

    Over the field's path, the cited file's SHA-256 and the value as the document states it,
    so the same reading of the same file confirms once, and a changed value or a changed
    file is a new thing to confirm.
    """
    source = next((s for s in spec.sources if s.field == field), None)
    if source is None:
        raise _refusal(f"the document cites no source for '{field}'", subject="field")
    value = _value_in(spec.model_dump(mode="json"), field)
    return _digest(
        {
            "confirms": PersonOnlyConfirmation.DRAFT_VALUE.value,
            "field": field,
            "file_sha256": source.sha256,
            "value": value,
        }
    )


def export_subject(spec: Any, artifact: str) -> str:
    """The digest a confirmation to write ``artifact`` for ``spec`` unvalidated is keyed by."""
    return _digest(
        {
            "confirms": PersonOnlyConfirmation.UNVALIDATED_EXPORT.value,
            "artifact": artifact,
            "spec": spec.model_dump(mode="json"),
        }
    )


def confirmation_root(explicit: str | Path | None = None) -> Path:
    """Where the server and the terminal command record confirmations and declines."""
    from .fetch import cache_root

    return Path(explicit) if explicit is not None else cache_root() / "confirmations"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, staging = tempfile.mkstemp(dir=path.parent, prefix=".anvilate-", suffix=".partial")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as staged:
            json.dump(dict(payload), staged, sort_keys=True, indent=2)
        os.replace(staging, path)
    except BaseException:
        Path(staging).unlink(missing_ok=True)
        raise


def record_confirmation(record: ConfirmationRecord, *, root: str | Path | None = None) -> Path:
    """Record ``record`` where every server instance finds it. A file is never written here."""
    if record.via is ConfirmationChannel.FILE:
        raise _refusal(
            "a confirmation file is written by the person in the output folder, not recorded "
            "by Anvilate",
            subject="via",
        )
    path = confirmation_root(root) / f"{record.subject}.json"
    _write_json(path, record.model_dump(mode="json"))
    return path


def record_decline(subject: str, *, client: str, on: date, root: str | Path | None = None) -> Path:
    """Record that the person declined or dismissed ``subject``, so they are not asked again."""
    path = confirmation_root(root) / "declined" / f"{subject}.json"
    _write_json(path, {"subject": subject, "client": client, "on": on.isoformat()})
    return path


def was_declined(subject: str, *, root: str | Path | None = None) -> bool:
    """Whether the person declined ``subject`` through an elicitation before."""
    return (confirmation_root(root) / "declined" / f"{subject}.json").is_file()


def _read(path: Path) -> Mapping[str, Any] | None:
    try:
        loaded = parse_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return loaded if isinstance(loaded, Mapping) else None


def _files(folder: Path | None) -> Iterable[ConfirmationRecord]:
    """Confirmation files a person wrote in the output folder. Unreadable ones are skipped.

    The channel is decided by where the file is, never by what it says: a file claiming to be
    an elicitation is still a file, because anything that can write here could write that.
    """
    if folder is None or not (folder / "confirmations").is_dir():
        return
    for path in sorted((folder / "confirmations").glob("*.json")):
        loaded = _read(path)
        if loaded is None:
            continue
        try:
            yield ConfirmationRecord(
                confirms=loaded.get("confirms"),
                subject=loaded.get("subject"),
                person=loaded.get("person"),
                on=loaded.get("date"),
                via=ConfirmationChannel.FILE,
            )
        except (ValueError, TypeError):
            continue


def find_confirmation(
    subject: str,
    confirms: PersonOnlyConfirmation,
    *,
    root: str | Path | None = None,
    output: Path | None | bool = True,
) -> ConfirmationRecord | None:
    """The record confirming ``subject``, recorded or written as a file, or ``None``.

    ``output`` is the output folder to look for confirmation files in; ``True`` uses the
    server's, ``None`` or ``False`` looks for none.
    """
    loaded = _read(confirmation_root(root) / f"{subject}.json")
    if loaded is not None:
        try:
            record = ConfirmationRecord.model_validate(loaded)
        except ValueError:
            record = None
        if record is not None and record.subject == subject and record.confirms is confirms:
            return record
    if output is True:
        from ._outputs import output_folder

        folder = output_folder()
    else:
        folder = output or None
    for record in _files(folder):
        if record.subject == subject and record.confirms is confirms:
            return record
    return None


def _confirmed(spec: Any, confirmations: Mapping[str, ConfirmationRecord]) -> Any:
    """``spec`` with each named source confirmed by its record, re-validated whole."""
    from .spec import parse_spec

    document = spec.model_dump(mode="json")
    for source in document.get("sources") or []:
        record = confirmations.get(source["field"])
        if record is None:
            continue
        source["confirmed_by"] = record.person
        source["confirmed_on"] = record.on.isoformat()
        source["confirmed_via"] = record.via.value
        source["confirmed_through"] = record.client
    # Re-validated rather than `model_copy`, which would skip the validators that hold a
    # confirmation to naming its person, its date and, for an elicitation, its client.
    return parse_spec(document)


def apply_confirmations(spec: Any, *, root: str | Path | None = None) -> Any:
    """``spec`` with every agent reading a record confirms stamped with that record.

    The record's person, date, channel and client replace whatever the document said, so a
    channel is always the one the record came through and never one a document claimed. A
    reading no record confirms is left as it is. The result is a new spec; the argument is
    not changed.
    """
    found: dict[str, ConfirmationRecord] = {}
    for source in spec.sources:
        if source.origin != "agent_read":
            continue
        record = find_confirmation(
            draft_value_subject(spec, source.field),
            PersonOnlyConfirmation.DRAFT_VALUE,
            root=root,
        )
        if record is not None:
            found[source.field] = record
    return _confirmed(spec, found) if found else spec


def unbacked_confirmations(spec: Any, *, root: str | Path | None = None) -> tuple[str, ...]:
    """The fields whose confirmation in the document no record backs.

    Over MCP the document arrives from the agent, so a ``confirmed_by`` in it is something
    the agent wrote. It counts only when a record from a person's channel confirms the same
    value under the same name, and any channel or client the document states is the
    record's; otherwise the field is returned, to be refused by name.
    """
    unbacked: list[str] = []
    for source in spec.sources:
        if source.origin != "agent_read" or source.confirmed_by is None:
            continue
        record = find_confirmation(
            draft_value_subject(spec, source.field),
            PersonOnlyConfirmation.DRAFT_VALUE,
            root=root,
        )
        if (
            record is None
            or record.person != source.confirmed_by
            or (source.confirmed_via not in (None, record.via.value))
            or (source.confirmed_through not in (None, record.client))
        ):
            unbacked.append(source.field)
    return tuple(unbacked)


def confirmation_file_form(confirms: PersonOnlyConfirmation, subject: str) -> str:
    """The file a person writes to confirm ``subject``, as a sentence with its JSON."""
    body = json.dumps(
        {
            "confirms": confirms.value,
            "subject": subject,
            "person": "your name",
            "date": "YYYY-MM-DD",
        },
        sort_keys=True,
    )
    return (
        f"write {body} as a .json file in the output folder's confirmations directory, with "
        "your own name and today's date"
    )


def confirmations_disclosure(spec: Any) -> tuple[str, ...]:
    """The lines a bundle states about the person-only confirmations its spec rests on.

    Each confirmed agent reading with its channel, then one line saying whether any of them
    is attested to a person by its channel. Empty when the spec rests on no agent reading.
    """
    readings = [source for source in spec.sources if source.origin == "agent_read"]
    if not readings:
        return ()
    lines = [f"  {source}" for source in readings]
    attested = [s for s in readings if s.confirmed_via == ConfirmationChannel.TERMINAL.value]
    unconfirmed = [s for s in readings if s.confirmed_by is None]
    if unconfirmed:
        tail = f"{len(unconfirmed)} reading(s) are unconfirmed drafts"
    elif attested:
        tail = (
            f"{len(attested)} of {len(readings)} confirmation(s) were typed at an "
            "interactive terminal"
        )
    else:
        tail = (
            "no confirmation this bundle rests on is attested to a person by its channel: "
            "each was answered through a client, written in a file, or written into the "
            "document itself"
        )
    return ("person-only confirmations:", *lines, f"  {tail}")
