"""Worked example: an RFQ sheet does not become a design until somebody signs for it.

A customer sends a requirement sheet. Eight labelled lines, and the extraction pass takes
five of them — every one a draft, and the pipeline gets nothing at all until a named
person has been through them.

What the pass does with the other three is the point. `Part number: LUG-4471` and
`Finish: black oxide` are not quantities. `Quantity: 4` is a *count*, and no amount of
context turns an unlabelled 4 into a physical value. All three are recorded as unparsed
with the reason, so the pass is auditable by subtraction — a reader can see what it did
not take, rather than assuming it took everything.

Then the sheet contradicts itself, as real ones do: the table says the design load is
50 kN and a note further down says 45 kN. Both are kept. Neither is chosen. Picking the
first, the last, or the larger would be a silent decision about the design, so the
conflict is reported and the release stays blocked — **even after both sides are
confirmed**, because two values for one field is not a field.

The engineer works it: confirms the four they accept, rejects the stale 45 kN. A rejection
is a decision and stays in the record — "somebody looked at this and refused it" is
different information from "nobody has looked at this yet", which is why there are three
states here and not a boolean.

Only then does `release()` hand over a mapping, and every value in it names the person who
signed for it and the line of the document it came from.

Run it directly (``python examples/rfq_sheet_to_confirmed_inputs.py``);
:func:`ingest_the_rfq` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.ingest import ConfirmationState, extract_requirements

RFQ = """# RFQ 2026-114 — below-the-hook lifting lug
Part number:         LUG-4471
Design load:         50 kN
Rated capacity =     5 t
Service temperature: -20 degC
Bore diameter        25 mm
Finish:              black oxide
Quantity:            4
# note from the buyer, 2026-08-14: derate to 45 kN pending the sling review
Design load:         45 kN
"""

ENGINEER = "A. Engineer, P.E."


def ingest_the_rfq():
    """The draft, the conflict, the confirmations, and the released mapping."""
    draft = extract_requirements(
        RFQ, document="rfq-2026-114.txt", informational_fields=("part number",)
    )
    conflicts = draft.conflicts()

    # Confirm what the engineer accepts. `design_load` is left alone for now: confirming a
    # field confirms every extraction of it, and there are two that disagree.
    confirmed = draft
    for field in ("rated_capacity", "service_temperature", "bore_diameter"):
        confirmed = confirmed.with_confirmation(field, by=ENGINEER)

    # Confirming both sides of the conflict does NOT unblock it.
    both = confirmed.with_confirmation("design_load", by=ENGINEER)
    try:
        both.release()
        blocked_reason = None
    except ValueError as refusal:
        blocked_reason = str(refusal)

    # The engineer resolves it: the 50 kN stands, the buyer's note is rejected pending the
    # sling review it names.
    resolved = confirmed.model_copy(
        update={
            "values": tuple(
                value.confirmed(ENGINEER)
                if value.field == "design_load" and value.quantity.magnitude == 50.0
                else value.rejected(ENGINEER)
                if value.field == "design_load"
                else value
                for value in confirmed.values
            )
        }
    )
    return draft, conflicts, blocked_reason, resolved, resolved.release()


def main() -> None:
    draft, conflicts, blocked_reason, resolved, released = ingest_the_rfq()
    print("AS EXTRACTED")
    print(f"  {draft.summary()}")
    for value in draft.values:
        print(f"    {value}")
    print("\n  not taken:")
    for line in draft.unparsed:
        print(f"    {line}")

    print("\nCONFLICT")
    for conflict in conflicts:
        print(f"  {conflict}")
    print(f"  confirming both sides does not help: {blocked_reason}")

    print("\nAFTER THE ENGINEER WORKS IT")
    print(f"  {resolved.summary()}")
    for value in resolved.values:
        if value.state is not ConfirmationState.DRAFT:
            print(f"    {value}")
    print("\nRELEASED TO THE PIPELINE")
    for field, quantity in sorted(released.items()):
        print(f"    {field} = {quantity}")


if __name__ == "__main__":
    main()
