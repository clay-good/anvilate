# Tasks: Process piping pack

## 1. Data

- [x] 1.1 Pipe dimension tables (B36.10M schedules) with citations in the standards
      database — `PipeScheduleTable` / `PipeDimensions` (108 rows, 18 nominal sizes,
      schedules 10/40/80/160/STD/XS) with per-dimension citations, derived
      `inside_diameter` / `flow_area`, and `available_wall()` for the nominal wall less
      mill tolerance and corrosion. STD and XS are carried as schedules in their own
      right, NOT aliased to 40 and 80: they coincide only through NPS 10 and NPS 8
      respectively and then hold flat (STD 9.53 mm vs Schedule 40's 17.48 mm at NPS 24).
      An untabled combination raises rather than interpolating. B36.19M stainless
      schedules are a follow-up.
- [x] 1.2 User-supplied allowable-stress input type with temperature and provenance —
      `AllowableStress` (value, temperature, material, source) with `is_valid_at`, which
      refuses in BOTH directions: an allowable read cooler than the service is
      unconservative, and one read far hotter is safe but is not the code's row, and
      answering False beats interpolating between table rows we do not have.

## 2. Checks

- [x] 2.1 Straight-pipe wall thickness (§304.1.2, mill tolerance, corrosion allowance) —
      `asme_b313_pipe_wall_thickness` (t = P·D/(2·(S·E + P·Y))), its rating inverse
      `asme_b313_pipe_pressure`, and `asme_b313_minimum_ordered_wall`
      (T = (t + c)/(1 − mill_tolerance), §304.1.1) so the ordered nominal wall accounts
      for the mechanical allowance and mill under-tolerance. S/E/Y user-supplied.
- [x] 2.2 Branch reinforcement area — `asme_b313_branch_required_reinforcement_area`
      (§304.3.3 A1 = t_h·d1·(2−sinβ)) and `asme_b313_branch_reinforcement`, which puts the
      available A2+A3+A4 against it over the zone the Code defines, with
      `asme_b313_branch_reinforcement_scorecard` as the verdict.
- [x] 2.3 Miter-bend pressure screening — `asme_b313_miter_bend_pressure` (§304.2.3),
      both single-miter branches (the formula changes at a 22.5° cut angle and it is a
      step DOWN — 8.53 MPa to 4.85 MPa across the seam on an NPS 4 Sch 40 line) and the
      multiple-miter case, which takes the lesser of the cut-angle and bend-radius
      limits. Past 22.5° the code gives no multiple-miter rating and the function
      refuses rather than quoting the single-miter number as though it were one.
- [~] 2.4 Displacement stress range vs. allowable range — `asme_b313_allowable_displacement_stress_range`
      (§302.3.5 S_A = f·(1.25·S_c + 0.25·S_h)); the computed-expansion-stress side needs the
      flexibility analysis, out of screening scope.

## 3. Tests & examples

- [x] 3.1 Worked-example anchors — the §304.1.2 wall and its rating inverse are anchored
      against the code form and round-tripped.
- [x] 3.2 Example: schedule selection for a stated service
      (`examples/process_pipe_schedule.py`) — Schedule 10 fails and Schedule 40 passes
      the 5 MPa service once mill tolerance and corrosion are taken off the wall.
- [x] 3.3 Not-evaluated behavior when allowables are missing —
      `asme_b313_pressure_scorecard` returns NOT_EVALUATED three ways, each pinned: no
      allowable supplied, an allowable read at a temperature that does not match the
      design temperature, and a wall wholly consumed by its mill tolerance and corrosion
      allowance (which is not the same as a rating of zero).

## 4. Docs

- [x] 4.1 Pack documentation: scope, what is screened vs. what needs full pipe stress
      analysis, where to obtain allowables legally —
      [`docs/process-piping.md`](../../../docs/process-piping.md). Every numeric claim on
      the page was re-derived from the code before it shipped.

## Shipped 2026-08-25 — the rest of task 2.2

`BranchReinforcement`, `asme_b313_branch_reinforcement` and
`asme_b313_branch_reinforcement_scorecard` in `analysis/pressure_vessel.py`,
`examples/branch_reinforcement_zone.py`, and the §304.3.3 section of
`docs/process-piping.md`.

**The zone is set by both pipes, and reading it off the run alone over-credits.** L4 is
the *lesser* of 2.5(T_h − c) and 2.5(T_b − c) + T_r, and the obvious reading — the zone
sits on the run, so take the run's term — credits a thin branch with the run's zone
height. On the worked NPS 16 header with a 3/4" weldolet that is 10.45 mm instead of
6.275 mm and **67% more A3 than the branch earns**. d2 is the *greater* of two rules the
same way, in the other direction. Both are computed from both pipes here.

**A pad lengthens the branch's zone, so it adds A3 as well as its own A4** — until the
run's 2.5(T_h − c) cap binds and stops. Omitting `pad_thickness` credits no pad, which
understates rather than overstates.

**d2 is capped at the run's outside diameter**, and the record says when the cap bound: a
zone wider than the pipe it sits on is credit for metal that is not there. The cap is
conservative, which is why it is applied even though only one of the three anchors
mentions it.

**A4 is taken as declared and the docstring says why that is a limit rather than a
default.** The Code credits only metal inside the zone; an area alone does not say where
the metal is, so the function cannot check it.

**Anchored before it was written**: three published
calculation sheets, one imperial and two metric. The imperial one (NPS 8 Sch 40 run,
NPS 4 Sch 40 branch) reproduces exactly — A1 0.5918 in², A2 0.7046 in², A3 0.1896 in²,
d2 4.026 in, L4 0.5925 in. The two metric weldolet sheets agree inside 1%, and the
residual is accounted for rather than tolerated: their L4 of 10.46 mm implies a run wall
of 4.184 mm where the table displays 4.18, and the two roundings bracket their own A2 of
8.71 from below and above. A test asserts that bracket, so the loose tolerance is not a
free pass.

**A1 comes from the function that publishes it, not a second copy of the formula.** Two
implementations of one Code expression are two places for it to change, and the one that
moves is always the one nothing is anchored against.
