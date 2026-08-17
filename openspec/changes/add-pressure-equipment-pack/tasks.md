# Tasks: Pressure equipment pack

## 1. Checks

- [x] 1.1 Ellipsoidal and torispherical head required thickness / MAWP
- [x] 1.2 Conical section screening
- [x] 1.3 UG-37 nozzle reinforcement area replacement
- [ ] 1.4 Appendix 2 flange design (bolt loads, seating/operating, flange stresses)
      composing gasket m/y

## 2. Tests & examples

- [x] 2.1 Worked-example anchors from published ASME VIII example problems
- [x] 2.2 Capstone example: vessel with head + nozzle + flange, governing component
      identified
- [x] 2.3 Not-evaluated behavior when allowables are missing

## 3. Docs

- [x] 3.1 Pack documentation: screening scope vs. full Code design, U-stamp disclaimer

## Scope as shipped

1.1 and 1.2 were already met before this change: `asme_ellipsoidal_head_thickness`,
`asme_torispherical_head_thickness` and `asme_conical_head_thickness` (with their MAWP
inverses) shipped with the earlier pressure-vessel work. This change added the two that
were missing — UG-37 opening reinforcement and the Appendix 2 flange geometry — plus the
capstone example, the tests and the doc page.

**1.4 is partial and deliberately so.** The Appendix 2 *bolt loads* ship: the effective
seating width b and diameter G from Table 2-5.2, the seating and operating loads, and the
required bolt area A_m = max(W_m1/S_b, W_m2/S_a) against its two separate allowables. The
Appendix 2 *flange stress* calculation (the longitudinal hub, radial and tangential
stresses) does not, because it runs on the shape factors T, U, Y, Z and the F/V/f curves,
which are figures inside the standard. Implementing them from memory is exactly the kind
of guess this library's citation contract exists to prevent, and no published anchor was
available to check them against. The doc page says so plainly rather than leaving a
reader to assume the flange is fully screened.

**UG-37 scope:** the radial-nozzle-in-a-cylinder case, where F = 1.0. It sums A_1
(excess shell), A_2 (excess nozzle) and A_41 (attachment fillet); it does not credit an
inward-projecting nozzle (A_3) or a reinforcing pad (A_5), and a hillside or oblique
nozzle takes a different F and is out of scope.
