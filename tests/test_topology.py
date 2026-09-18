"""Constraint topology: the six freedoms counted from what the document declares."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.scorecard import CheckStatus, ScorecardEntry
from anvilate.topology import (
    Constraint,
    ConstraintKind,
    ConstraintTally,
    Frame,
    Freedom,
    FreedomState,
    IntendedFreedom,
    IntentionalRedundancy,
    RedundancyMechanism,
    tally,
)

F = Freedom
K = ConstraintKind

_PLATE_FRAME = Frame(
    name="plate frame",
    x="along the dowel line",
    y="across the dowel line",
    z="the plate normal",
)


def _counted(*constraints: Constraint, intended: tuple[IntendedFreedom, ...] = ()):
    counted = tally("mount plate", _PLATE_FRAME, constraints, intended=intended)
    assert isinstance(counted, ConstraintTally)
    return counted


_FACE = Constraint(feature="machined face", kind=K.PLANAR_FACE, removes=(F.TZ, F.RX, F.RY))
_DOWEL_A = Constraint(feature="dowel A", kind=K.PIN_IN_HOLE, removes=(F.TX, F.TY))
# A second round dowel along the line also stops translation along it, which dowel A
# already does: the textbook redundancy a diamond pin or a slot exists to remove.
_DOWEL_B = Constraint(feature="dowel B", kind=K.PIN_IN_HOLE, removes=(F.TX, F.RZ))
_SLOT_B = Constraint(feature="slot B", kind=K.SLOT, removes=(F.RZ,))


def test_two_round_dowels_and_a_face_are_over_constrained_with_the_dowels_named() -> None:
    """Task 4.1: the textbook case."""
    counted = _counted(_FACE, _DOWEL_A, _DOWEL_B)
    (over,) = counted.over()
    assert over.freedom is F.TX
    assert {c.feature for c in over.by} == {"dowel A", "dowel B"}
    entry = counted.entry()
    assert entry.status is CheckStatus.FAIL
    assert "OVER-CONSTRAINED by pin in hole at dowel A, pin in hole at dowel B" in entry.detail
    assert "depends on manufacturing variation" in entry.detail
    # The arithmetic a reader checks: what each interface contributed, and the total.
    assert "planar face at machined face 3" in entry.detail and "= 7 removed" in entry.detail


def test_a_slot_in_place_of_the_second_dowel_is_exactly_constrained() -> None:
    counted = _counted(_FACE, _DOWEL_A, _SLOT_B)
    assert counted.exactly_constrained and counted.removed == 6
    assert all(t.state is FreedomState.EXACT for t in counted.freedoms)
    entry = counted.entry()
    assert entry.status is CheckStatus.PASS
    assert "all six freedoms accounted for, 6 of them constrained" in entry.detail
    assert "in plate frame" in entry.detail


def test_a_ball_vee_flat_coupling_is_exactly_constrained_with_six_accounted_for() -> None:
    """Task 4.2: the Kelvin coupling, each interface's contribution shown."""
    frame = Frame(
        name="coupling frame",
        x="from the cone toward the vee",
        y="in the plane of the balls",
        z="normal to the base",
    )
    counted = tally(
        "instrument base",
        frame,
        (
            Constraint(feature="cone", kind=K.BALL_IN_CONE, removes=(F.TX, F.TY, F.TZ)),
            Constraint(feature="vee", kind=K.BALL_IN_VEE, removes=(F.RY, F.RZ)),
            Constraint(feature="flat", kind=K.FLAT_CONTACT, removes=(F.RX,)),
        ),
    )
    assert isinstance(counted, ConstraintTally) and counted.exactly_constrained
    detail = counted.entry().detail
    assert "ball in cone at cone 3, ball in vee at vee 2, flat contact at flat 1 = 6" in detail
    assert "frame coupling frame" in str(counted) and "normal to the base" in str(counted)


def test_removing_a_constraint_changes_the_tally_and_names_the_freed_motion() -> None:
    """Task 4.4: the count is computed from the declaration, not asserted in the test."""
    counted = _counted(_DOWEL_A, _SLOT_B)
    assert {t.freedom for t in counted.free()} == {F.TZ, F.RX, F.RY}
    detail = counted.entry().detail
    assert "translation along z (the plate normal): FREE" in detail
    assert "rotation about x (along the dowel line): FREE" in detail
    assert counted.entry().status is CheckStatus.FAIL


def test_an_intended_freedom_is_reported_with_its_purpose_and_is_not_a_finding() -> None:
    slide = IntendedFreedom(freedom=F.TX, purpose="the thermal slide along the rail")
    counted = _counted(
        _FACE,
        Constraint(feature="guide pin", kind=K.SLOT, removes=(F.TY,)),
        Constraint(feature="keeper", kind=K.SLOT, removes=(F.RZ,)),
        intended=(slide,),
    )
    assert counted.exactly_constrained
    (kept,) = [t for t in counted.freedoms if t.freedom is F.TX]
    assert kept.state is FreedomState.INTENDED
    entry = counted.entry()
    assert entry.status is CheckStatus.PASS
    assert "5 of them constrained" in entry.detail
    assert "free by intent — the thermal slide along the rail" in str(counted)


def _flange(mechanism: RedundancyMechanism) -> ConstraintTally:
    declared = _DOWEL_B.model_copy(
        update={
            "redundancy": IntentionalRedundancy(
                justification="the second dowel is reamed through both parts at assembly",
                mechanism=mechanism,
            )
        }
    )
    return _counted(_FACE, _DOWEL_A, declared)


def test_a_declared_redundancy_is_not_a_finding_and_its_justification_is_shown() -> None:
    counted = _flange(RedundancyMechanism.MACHINED_AT_ASSEMBLY)
    assert counted.exactly_constrained
    (redundant,) = [t for t in counted.freedoms if t.freedom is F.TX]
    assert redundant.state is FreedomState.DECLARED_REDUNDANT
    assert counted.entry().status is CheckStatus.PASS
    assert "reamed through both parts at assembly" in str(counted)


def test_declaring_a_redundancy_does_not_silence_an_indeterminacy_it_does_not_resolve() -> None:
    reamed = _flange(RedundancyMechanism.MACHINED_AT_ASSEMBLY)
    assert [t.freedom for t in reamed.indeterminate] == [F.TX]
    assert "the load path is indeterminate along tx" in reamed.entry().detail
    compliant = _flange(RedundancyMechanism.COMPLIANT_INTERFACE)
    assert compliant.indeterminate == ()
    assert "load division is determined" in str(compliant)


def test_a_stress_on_an_over_constrained_path_never_renders_unqualified() -> None:
    """Task 4.3: a confident number on an indeterminate path carries the cause."""
    shear = ScorecardEntry.from_safety_factor("dowel shear", computed=3.1, required=2.0)
    qualified = _counted(_FACE, _DOWEL_A, _DOWEL_B).qualify(shear)
    assert qualified.status is shear.status
    assert qualified.detail.startswith(shear.detail)
    assert "on an indeterminate load path" in qualified.detail
    assert "pin in hole at dowel A, pin in hole at dowel B" in qualified.detail
    # Resolving the redundancy clears the qualifier.
    assert _counted(_FACE, _DOWEL_A, _SLOT_B).qualify(shear) == shear
    # A check that did not run has no number to qualify.
    blocked = ScorecardEntry(name="dowel shear", status=CheckStatus.NOT_EVALUATED, detail="no load")
    assert _counted(_FACE, _DOWEL_A, _DOWEL_B).qualify(blocked) == blocked


def test_a_body_with_no_constraints_is_not_evaluated_and_named() -> None:
    counted = tally("mount plate", _PLATE_FRAME, ())
    entry = counted.entry()
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "mount plate declares no constraints" in entry.detail
    assert not counted.exactly_constrained
    assert "not counted" in str(counted)


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"kind": K.BALL_IN_VEE, "removes": (F.TX, F.TY, F.TZ)}, "removes 2"),
        ({"kind": K.PIN_IN_HOLE, "removes": (F.TX, F.TY, F.RZ)}, "removes 2 or 4"),
        ({"kind": K.FLAT_CONTACT, "removes": (F.TX, F.TX)}, "names one freedom twice"),
        ({"kind": K.FLAT_CONTACT, "removes": ()}, "at least 1"),
    ],
)
def test_a_constraint_that_miscounts_its_own_interface_is_refused(
    fields: dict[str, object], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        Constraint(feature="seat", **fields)  # type: ignore[arg-type]


def test_a_redundancy_declared_with_no_justification_is_refused() -> None:
    with pytest.raises(ValidationError):
        IntentionalRedundancy(justification="  ", mechanism=RedundancyMechanism.ASSEMBLY_SEQUENCE)


def test_an_intended_freedom_a_constraint_removes_is_refused() -> None:
    with pytest.raises(ValueError, match="the declaration and the constraints disagree"):
        _counted(
            _FACE,
            _DOWEL_A,
            _SLOT_B,
            intended=(IntendedFreedom(freedom=F.RZ, purpose="rotation for alignment"),),
        )
    with pytest.raises(ValueError, match="intended twice"):
        _counted(
            _FACE,
            intended=(
                IntendedFreedom(freedom=F.TX, purpose="a slide"),
                IntendedFreedom(freedom=F.TX, purpose="the same slide"),
            ),
        )


def test_every_kind_counts_and_every_mechanism_rules_on_load_division() -> None:
    """The two total maps, read through the public behaviour rather than the tables."""
    removes = {
        K.PLANAR_FACE: 3,
        K.PIN_IN_HOLE: 2,
        K.SLOT: 1,
        K.BALL_IN_VEE: 2,
        K.BALL_IN_CONE: 3,
        K.FLAT_CONTACT: 1,
        K.BONDED: 6,
        K.FLEXURE_BLADE: 3,
    }
    assert set(removes) == set(ConstraintKind)
    for kind, count in removes.items():
        constraint = Constraint(feature="f", kind=kind, removes=tuple(Freedom)[:count])
        assert "removes" in str(constraint)
    rulings = {
        mechanism: IntentionalRedundancy(
            justification="stated", mechanism=mechanism
        ).determines_load_division
        for mechanism in RedundancyMechanism
    }
    assert rulings == {
        RedundancyMechanism.COMPLIANT_INTERFACE: True,
        RedundancyMechanism.ASSEMBLY_SEQUENCE: False,
        RedundancyMechanism.MACHINED_AT_ASSEMBLY: False,
    }
    assert str(IntendedFreedom(freedom=F.RZ, purpose="alignment")) == "rz: alignment"
