# Principles

<!-- doc-scope:start -->
Scope: The rules governing what is allowed to exist in this repository, in code
and in documentation alike. The mechanics that enforce them live in
`documentation-harness.md`; this file states the reasoning they implement.
<!-- doc-scope:end -->

## A sentence earns its place by reducing uncertainty

A sentence enters a document only if it reduces the reader's uncertainty about
the system. Otherwise it is deleted.

Useless complexity and information are hard to tell apart from the inside. Both
are negentropy: both took work to produce, and both cost energy to process and
to keep true as the system moves. What separates them is Shannon's measure —
information reduces the reader's uncertainty, complexity does not. Text that
adds structure without reducing uncertainty charges the full price of
information and delivers none of it.

The test is one question: **if this sentence were absent, what would the reader
believe or do differently?** If the answer is "nothing", it goes.

Three kinds of writing fail that test reliably.

**Process narration** — what was tried, what was found wrong and redone, which
tool was reached for, which branch was read by mistake. The reader wants the
state of the system, not the path taken to it.

**Self-certification** — "nothing here is inferred", "every claim is cited",
"confirmed, not assumed". These describe the document rather than the system,
and they invite the opposite reading of anything not so labelled.

**Discarded context** — a component that exists but is not used, a branch that
does not ship, a figure that was superseded. Naming it raises the reader's load
without changing a decision.

Uncertainty about a *fact* is information and stays. "Whether X holds in
production is unconfirmed" tells the reader something true about the world.
"I could not check X" tells them about the investigator, and goes.

## The same rule governs code

An abstraction, a flag, a configuration option, or a layer earns its place the
same way: by removing ambiguity for whoever uses it. One that merely
generalises, or anticipates a case nobody has, adds surface to maintain and
answers no question.

Delete rather than relocate. Moving unjustified code or text into another file
lowers one file's line count and raises the system's total cost.

## Logs are exempt, entirely

A log is a measurement instrument, and the name is literal: a rope thrown
overboard with knots in it, and the time written down. You do not reason about
what to record. You record everything.

Filtering at write time destroys the ability to answer questions nobody had yet
when the line was written, which is the only thing a log is for. This covers
everything log-shaped: application logs, audit trails, git history, incident
records, `active-context-archive.md`, and any dated append-only file.

The distinction is write time against read time. A log is unfiltered on write
and filtered on read, by search. A document is filtered on write, so that
reading is cheap. Confusing the two produces both failure modes this repository
keeps hitting: a document that has silently become a log, and a log someone
pruned for tidiness.
