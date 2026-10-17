# Change: Industry profiles — one declaration that sets up Anvilate for how your industry works

## Why

The same bracket is checked differently by a spacecraft engineer, a transport-aircraft
engineer, a Tier 1 automotive engineer, a medical-device engineer and a machine builder.
The differences are not in the physics. They are in five things:

- the factors applied;
- the allowable basis accepted;
- the checks that are mandatory for a class of item (random vibration for any box on a
  launch vehicle, outgassing for anything in vacuum, a duty cycle for any chassis part);
- the records that must come out (margin table, DFMEA and DVP&R, risk file,
  first-article characteristic table);
- the drawing standard.

Today an agent has to know all of this and declare it piece by piece. It won't. The
result is either a clean card that a reviewer in that industry rejects, or a wall of
"not evaluated" nobody can act on.

Engineers already work this way: a program or company sets its rules once, and every
analysis inherits them. A profile is that, made explicit and cited.

## What Changes

| Area | Change |
| --- | --- |
| Profile | A declared bundle: factor set, allowable-basis rules, required checks by item class, default material needs, required artifacts, drawing and tolerancing standard. A product binds one profile; a company profile may layer on an industry profile. |
| Shipped profiles | Starting points, each cited clause by clause from public sources: spaceflight hardware, transport aircraft, automotive, medical device, industrial machinery, consumer product, and general (today's behavior). |
| Required checks | A check the profile requires for an item's class appears on the card even when nothing triggered it. Until it runs, it shows as not evaluated, naming what it needs. |
| Attribution | Every rule a profile adds shows on the card as coming from the profile, so nothing changes silently. |
| No compliance claims | A profile is a screening configuration. The card says which profile was applied and that it is not a certification. |

## Impact

- New capability: `industry-profiles`. Delta: `discipline-packs` (ADDED).
- Draws on the changes it configures:
  - `add-margin-of-safety-reporting` (factor sets, basis)
  - `add-structural-hand-methods`
  - `add-durability-and-sealing`
  - `add-geometric-dfm-rules`
  - `add-quality-artifacts`
  - `add-material-compliance`
  - `add-cae-handoff`
  - `add-declaration-completeness`, which keeps required inputs drivable
- A profile can only switch on what exists. A required check that is not implemented yet
  is shown as not available, never dropped.
- Explicitly out:
  - Program-specific requirements a user has not declared.
  - Jurisdiction-specific legal advice.
  - Paid-standard values. These are entered by the user with a citation.
