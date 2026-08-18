# Tasks: Pressure equipment pack

## 1. Checks

- [x] 1.1 Ellipsoidal and torispherical head required thickness / MAWP
- [x] 1.2 Conical section screening
- [x] 1.3 UG-37 nozzle reinforcement area replacement
- [x] 1.4 Appendix 2 flange design (bolt loads, seating/operating, flange stresses)
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

**1.4 ships the bolt loads and the no-hub flange stress; hub flanges stay out.** The
Appendix 2 *bolt loads* were already here: the effective seating width b and diameter G
from Table 2-5.2, the seating and operating loads, and the required bolt area
A_m = max(W_m1/S_b, W_m2/S_a) against its two separate allowables.

The *flange stress* half now ships for the case that is genuinely closed-form. The
earlier note lumped the T/U/Y/Z shape factors in with the F/V/f curves and deferred both;
that was wrong about T, U, Y and Z, which are published *equations* in Appendix 2-7.1,
not figures. They were anchored before shipping — a published worked calculation at
K = 1.41939 reports T = 1.74578 and Z = 2.97106 against these equations' 1.74572 and
2.97110, and the identity U = Y/0.910 holds at every K, which cross-checks the two
constant sets against each other. All of it is asserted in the suite.

With Y in hand, Appendix 2-7(b) — loose-type flanges without a hub, where S_H and S_R are
zero by definition — reduces to S_T = Y·M_o/(t²·B), and that is shipped end to end:
`asme_appendix_2_shape_factors`, `asme_appendix_2_flange_moments` (the Table 2-6
loose-type arms with every load and lever reported), `asme_appendix_2_ring_flange_stress`
(both conditions against their own allowables) and its scorecard wrapper.

**Hub-credited flanges remain out of scope**, and now say so structurally: the scorecard
wrapper reports NOT_EVALUATED with the reason, because a hub flange needs the F, V and f
*figures* and takes different moment arms, so the no-hub number would be unconservative
rather than merely absent. The bolt-spacing correction B_sc and the rigidity index are
also out of scope. The doc page states all three.

**UG-37 scope:** the radial-nozzle-in-a-cylinder case, where F = 1.0. It sums A_1
(excess shell), A_2 (excess nozzle) and A_41 (attachment fillet); it does not credit an
inward-projecting nozzle (A_3) or a reinforcing pad (A_5), and a hillside or oblique
nozzle takes a different F and is out of scope.
