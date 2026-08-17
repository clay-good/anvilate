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
- [~] 2.2 Branch reinforcement area — `asme_b313_branch_required_reinforcement_area`
      (§304.3.3 A1 = t_h·d1·(2−sinβ), the required replacement area); the available
      A2+A3+A4 excess-wall/pad composition is a follow-up.
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
