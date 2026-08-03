# Tasks: Process piping pack

## 1. Data

- [ ] 1.1 Pipe dimension tables (B36.10M/B36.19M schedules) with citations in the
      standards database
- [ ] 1.2 User-supplied allowable-stress input type with temperature and provenance

## 2. Checks

- [~] 2.1 Straight-pipe wall thickness (§304.1.2) — `asme_b313_pipe_wall_thickness`
      (t = P·D/(2·(S·E + P·Y))) and its rating inverse `asme_b313_pipe_pressure`
      (P = 2·t·S·E/(D − 2·Y·t)) in `analysis/pressure_vessel.py`, with S/E/Y as
      user-supplied code inputs. The mill-tolerance and corrosion-allowance add-ons
      (composed on top of the pressure-design wall) are a follow-up.
- [ ] 2.2 Branch reinforcement area
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
