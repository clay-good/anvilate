# Interaction Quality Specification (delta)

## ADDED Requirements

### Requirement: No operation waits silently

Any operation that can exceed the declared responsiveness threshold SHALL report progress
on every surface that invokes it, stating the activity currently running and, where the
work is countable, the number of units completed and the total. An operation whose size is
not known in advance SHALL report itself as indeterminate and continue to report the
activity it is performing; it MUST NOT animate a percentage it cannot compute. A silent
wait longer than the threshold SHALL be a defect, because a user cannot distinguish a slow
tool from a broken one.

#### Scenario: A long screen reports what it is doing

- **WHEN** a build runs a mesh and a solve that together take four minutes
- **THEN** the surface reports the current activity throughout, with counts where the work
  is countable

#### Scenario: Unknown-length work says so

- **WHEN** an operation's total is not knowable in advance
- **THEN** it reports as indeterminate with its current activity, rather than showing a
  progress fraction

#### Scenario: The wait states what it is waiting on

- **WHEN** an operation is blocked on an external process or a first-use data fetch
- **THEN** the progress surface names what it is waiting on

### Requirement: Time estimates are derived or absent

A remaining-time estimate SHALL be shown only when it is derived from completed work of
the same kind within the same operation, and SHALL be labeled an estimate wherever it
appears. The system MUST NOT display an estimate derived from a fixed assumption, a prior
unrelated run, or a guess, because an estimate that is wrong by an order of magnitude
costs more trust than showing none at all.

#### Scenario: Estimate appears once it is earned

- **WHEN** a sweep has evaluated a tenth of its points
- **THEN** a remaining-time estimate derived from those points appears, labeled as an
  estimate

#### Scenario: No basis, no estimate

- **WHEN** an operation has completed no comparable work
- **THEN** no remaining-time estimate is shown

### Requirement: Cancellation is always available and leaves no half-state

Every long-running operation SHALL be cancellable at any point from the surface that
started it, and cancellation SHALL terminate any subprocess solver or sandbox it started.
A cancelled operation SHALL report what it completed and SHALL leave no partial artifact
presented as complete: a partial output is either removed or marked partial in a way that
downstream consumers and export gating both read. Cancellation MUST NOT be reported as a
failure or a failing verdict, because the user chose it.

#### Scenario: Interrupt during export leaves nothing misleading

- **WHEN** a user cancels during artifact export
- **THEN** no partial artifact remains that a reader could mistake for a complete one, and
  the operation reports what it finished

#### Scenario: Subprocesses do not survive the cancel

- **WHEN** a cancellation occurs during a solver run
- **THEN** the solver subprocess and its sandbox are terminated

#### Scenario: Cancelled is its own outcome

- **WHEN** an operation is cancelled
- **THEN** the result is reported as cancelled, distinct from a pass, a failure, and an
  error

### Requirement: Every refusal carries a remedy with a concrete subject

Every refusal, rejection, and "not evaluated" result SHALL carry a remedy stating the
action to take, the concrete subject of that action, and where an acceptable value may
come from. A remedy whose imperative names no resolvable subject — an instruction to
supply, declare, remove, or configure something the message does not identify — SHALL fail
CI. The gate SHALL carry a population floor and an enumerated exclusion list with a stated
cause per exclusion, so it cannot pass by matching nothing.

#### Scenario: The refusal tells the user what to do

- **WHEN** a dynamic screen refuses for a missing quality factor
- **THEN** the message names the quantity, its dimension, its typical range, the
  declaration that carries it, and any profile that supplies it

#### Scenario: A remedy with no noun fails CI

- **WHEN** a refusal says only to supply the missing value without naming which
- **THEN** CI fails naming the message

#### Scenario: The gate cannot pass vacuously

- **WHEN** the message-quality gate runs
- **THEN** it asserts the number of refusal sites it examined against a floor, and
  enumerates every exclusion with its cause

### Requirement: Output adapts to its destination without losing content

Rendered output SHALL detect whether it is writing to a terminal and adapt — colour and
progress only on a terminal, honouring an explicit no-colour request and a terminal that
declares itself incapable, wrapping to the detected width, and falling back to ASCII where
the encoding cannot carry the preferred glyphs. Progress SHALL be written to the
diagnostic stream so the primary stream stays pipeable. Every command SHALL offer a
machine-readable form carrying the same content under a stable, versioned schema.

#### Scenario: Piping produces clean data

- **WHEN** a command's output is redirected to a file
- **THEN** the file contains the result with no progress, colour codes, or cursor control,
  and the progress appeared on the diagnostic stream

#### Scenario: Colour off loses nothing

- **WHEN** colour is disabled by request or by an incapable terminal
- **THEN** every status that colour distinguished remains distinguishable in text

#### Scenario: Machine-readable is not second-class

- **WHEN** a command is run in its machine-readable form
- **THEN** it carries the same content as the human form, including remedies and
  not-evaluated reasons

### Requirement: Exit codes distinguish refusal, failing verdict, and error

Command exit codes SHALL distinguish at least four outcomes: the command succeeded and the
verdict passed; the command succeeded and the verdict failed; the command refused the
input and named why; and the tool itself errored. The codes SHALL be documented and
stable, because a script that cannot tell a failing part from a broken tool will either
ignore real failures or block on nothing.

#### Scenario: A failing part is not a broken tool

- **WHEN** a screen runs to completion and the card fails
- **THEN** the exit code is the failing-verdict code, distinct from the internal-error code

#### Scenario: Refusal is its own code

- **WHEN** an input is rejected as invalid
- **THEN** the exit code is the refusal code and the message carries the remedy

### Requirement: No information is carried by colour alone

Every status, verdict, severity, and difference SHALL be conveyed by a word, symbol, or
position in addition to any colour used, and the palette SHALL be checked in CI for
distinguishability under common colour-vision deficiencies. Rendered reports SHALL be
readable in document order by assistive technology: tables carry headers, figures carry
text alternatives, and no verdict exists only inside an image.

#### Scenario: The card reads correctly in monochrome

- **WHEN** a scorecard is printed in monochrome
- **THEN** every verdict remains identifiable from its text

#### Scenario: A verdict is never only a picture

- **WHEN** a report includes a plot carrying a result
- **THEN** the same result is available as text in the document

### Requirement: Interactive responsiveness is budgeted and measured

The system SHALL declare a responsiveness budget for interactive operations, measure it
per release on the reference hardware profile alongside the existing time-to-first-part
budget, and treat a sustained regression as release-blocking. Repeated loads of bundled
data SHALL be cached, and the cache's effectiveness SHALL be asserted by measurement
rather than by the cache's existence, because a cache nobody hits is indistinguishable
from none.

#### Scenario: The budget is a measured gate

- **WHEN** a release candidate is prepared
- **THEN** interactive responsiveness is measured on the reference profile and recorded,
  and a sustained regression blocks the release

#### Scenario: The cache is asserted by its effect

- **WHEN** the caching test runs
- **THEN** it asserts the number of avoided loads, not merely that a cache object exists

### Requirement: The system can say what it is able to screen

A user SHALL be able to ask, for a given spec or element class, which screens apply, which
of them can run on what is currently declared, and what each of the rest still needs —
without running a build. Unknown names SHALL produce near-miss suggestions resolved
against the real registry rather than a static list, and every command's help SHALL carry
at least one runnable example.

#### Scenario: Capability is discoverable before commitment

- **WHEN** a user asks what applies to a partially declared spec
- **THEN** the answer lists the applicable screens, which can run now, and what the others
  need

#### Scenario: A typo suggests the real name

- **WHEN** a user names a check or material that does not exist
- **THEN** the nearest real names are suggested from the live registry

#### Scenario: Help shows, not only tells

- **WHEN** any command's help is displayed
- **THEN** it includes at least one example that runs as written
