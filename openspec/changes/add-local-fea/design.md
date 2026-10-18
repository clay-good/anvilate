# Design notes: Local FEA

Research done on 2026-10-17.

## Versions and channels

| Component | Version | Channels | License |
| --- | --- | --- | --- |
| CalculiX ccx | 2.23 (manual dated 2025-10-19); 2.24 unreleased, roughly yearly cadence | conda-forge `calculix` 2.23 (linux-64/aarch64, osx-64/arm64, win-64); Debian forky/sid 2.23; Homebrew third-party tap only; official Windows zip. **No PyPI wheel, no maintained Docker image.** | GPL-2.0+ |
| Gmsh | 4.15.2 (2026-03-24) | PyPI wheel (Windows x64, Linux x64, macOS arm64/x64), conda-forge, Homebrew core | GPL-2.0+ |

Sources: https://www.dhondt.de/ , https://anaconda.org/conda-forge/calculix ,
https://pypi.org/project/gmsh/ , https://github.com/costerwi/homebrew-calculix

**Version traps.** ccx 2.24's development log changes the binary `.frd` format to double
precision, so the reader is gated on the pinned version. Gmsh 4.15.0 changed
`getBoundary` to default `oriented=False` and dropped signed tags; 4.14 renamed
`mesh/tetrahedralize`. Pin both minor versions.

**Solver build.** conda-forge's ccx links only arpack, BLAS/LAPACK and OpenMP, so it is the
SPOOLES build: free, in-core only (the manual puts the ceiling near 1,000,000 equations on
32 GB), adequate for bracket- and housing-class models. PARDISO is proprietary; a
CalculiX-modified PaStiX is free and faster. Record which solver ran in the bundle.

## Keywords this change uses (ccx 2.23 manual sections)

`*STATIC`; `*HEAT TRANSFER, STEADY STATE` (7.73); `*TEMPERATURE, FILE=…, BSTEP=n` (7.132)
for sequential thermal stress, on the same mesh (it reads by node); `*FREQUENCY` (7.63);
`*TIE` (7.133, 3D elements only, position tolerance 2.5% of element size by default,
unconnected slave nodes written to `jobname_WarnNodeMissMasterIntersect.nam`, which the
pipeline must read and fail on); `*BUCKLE` (7.5, later). Out of the first phase:
`*CONTACT PAIR` (7.22, all pairs in one deck must share a TYPE) and `*PRE-TENSION SECTION`
(7.107).

## Tags to physical groups

Carrying STEP face names through Gmsh is fragile: the maintainer called it "still a little
bit tricky" (2020), and whether names survive `occ.fragment` is unconfirmed. So the build
records each tagged face's area, centroid and normal, and the mesher matches by signature
after import, using `fragment`'s `outDimTagsMap` for products. The match is verified,
never assumed (the spec's setup-failure rule).

## Benchmarks (targets re-derived from public reproductions)

| Benchmark | Target | Source |
| --- | --- | --- |
| NAFEMS LE1 elliptic membrane | σyy = 92.7 MPa at D | Altair OptiStruct verification page |
| NAFEMS LE10 thick plate | σyy = −5.38 MPa at D; a coarse-mesh tripwire | Abaqus benchmarks guide |
| NAFEMS T4 2D conduction with convection | 18.3 °C at E | Abaqus benchmarks guide |
| CalculiX test suite | per deck | `ccx_2.23.test.tar.bz2` |
| Closed form | cantilever, Lamé thick cylinder, plate with a hole | existing T1 library |

Mesh convergence follows the GCI procedure (Celik, Ghia, Roache & Freitas, *J. Fluids
Eng.* 130(7), 2008): three systematically refined meshes and the apparent order. That
matches `validation-gauntlet`'s "at least two refinements". There is no standard
singularity detector; the practice is a peak that keeps rising with refinement, read
away from the feature instead.

## Prior art

| Project | License | Note |
| --- | --- | --- |
| Casys-AI `mcp-calculix` | MIT | STEP → Gmsh → ccx over MCP; faces by bounding box; refuses to call a design "safe" |
| pyccx | BSD | Gmsh + ccx in Python; closest library |
| FreeCAD FEM (ccxtools) | LGPL-2.1 | Most complete CAD-to-CalculiX automation |
| ccx2paraview | GPL-3.0 | `.frd` to VTK; reference only |
| CalculiX-Examples | MIT | Bolt preload and contact examples for the later phase |

## Open decision for the owner

pip cannot install CalculiX. The options are:

1. The solver stays a user install, and `doctor` and every refusal name the
   one command for the platform (`conda install -c conda-forge calculix gmsh`, the
   Debian package, the Homebrew tap, or the official zip). This needs no new decision.
2. `anvilate fetch` may install a digest-pinned conda-forge build with the user's consent,
   extending D3 from datasets to one solver binary. That needs a new design decision and
   a security review.
3. An official container that bundles both, which nobody else maintains for 2.23.

The spec permits all three and forbids only a silent download. The tasks start with option
1 and leave 2 and 3 to the owner.
