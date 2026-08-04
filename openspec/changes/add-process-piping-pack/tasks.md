# Tasks: Process piping pack

## 1. Data

- [ ] 1.1 Pipe dimension tables (B36.10M/B36.19M schedules) with citations in the
      standards database
- [ ] 1.2 User-supplied allowable-stress input type with temperature and provenance

## 2. Checks

- [x] 2.1 Straight-pipe wall thickness (§304.1.2, mill tolerance, corrosion allowance) —
      `asme_b313_pipe_wall_thickness` (t = P·D/(2·(S·E + P·Y))), its rating inverse
      `asme_b313_pipe_pressure`, and `asme_b313_minimum_ordered_wall`
      (T = (t + c)/(1 − mill_tolerance), §304.1.1) so the ordered nominal wall accounts
      for the mechanical allowance and mill under-tolerance. S/E/Y user-supplied.
- [~] 2.2 Branch reinforcement area — `asme_b313_branch_required_reinforcement_area`
      (§304.3.3 A1 = t_h·d1·(2−sinβ), the required replacement area); the available
      A2+A3+A4 excess-wall/pad composition is a follow-up.
- [ ] 2.3 Miter-bend pressure screening
- [ ] 2.4 Displacement stress range vs. allowable range

## 3. Tests & examples

- [x] 3.1 Worked-example anchors — the §304.1.2 wall and its rating inverse are anchored
      against the code form and round-tripped.
- [x] 3.2 Example: schedule selection for a stated service
      (`examples/process_pipe_schedule.py`) — Schedule 10 fails and Schedule 40 passes
      the 5 MPa service once mill tolerance and corrosion are taken off the wall.
- [ ] 3.3 Not-evaluated behavior when allowables are missing — with the pack's typed
      allowable input (task 1.2).

## 4. Docs

- [ ] 4.1 Pack documentation: scope, what is screened vs. what needs full pipe stress
      analysis, where to obtain allowables legally
