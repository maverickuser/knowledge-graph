# Project Constitution

This constitution governs all design, implementation, testing, and review decisions for `knowledge-graph`.

- Version: `1.0.0`
- Ratified: `2026-06-09`
- Last Amended: `2026-06-09`

## Principle I: Code Quality Is the Default

- Code MUST be readable before it is clever.
- Every module, function, and class MUST have a single clear purpose.
- Public behavior MUST be expressed with descriptive names, explicit control flow, and minimal hidden side effects.
- New code MUST remove dead paths, duplication, and ad hoc workaround logic unless there is a documented reason to keep them.
- Formatting and linting MUST pass before merge.
- Rationale: simple, explicit code is easier to review, test, and change safely.

## Principle II: Tests Prove Behavior

- New behavior MUST be covered by automated tests before merge.
- Bug fixes MUST include regression tests that fail before the fix and pass after it.
- Tests MUST be deterministic, isolated, and runnable in the default local development environment.
- Critical flows and previously fragile paths MUST have direct coverage, not just indirect coverage through broad smoke tests.
- When a change alters data contracts, error handling, or edge cases, the test suite MUST prove the new behavior.
- Rationale: code is not complete until its behavior is verified repeatedly.

## Principle III: User Experience Must Stay Consistent

- User-facing text, CLI output, documentation examples, and error messages MUST use the same terminology for the same concept.
- Similar actions MUST produce similar response shapes, exit codes, and failure messages.
- The project MUST prefer clear, predictable interactions over surprising shortcuts.
- Any change that affects a user-visible flow MUST update the matching docs, examples, or help text in the same change set.
- Rationale: predictable behavior reduces confusion and makes the project easier to adopt and support.

## Principle IV: Performance Must Be Measured

- New features MUST define an explicit performance expectation before implementation when the change can affect latency, throughput, memory use, or startup time.
- Hot paths MUST avoid unnecessary repeated work, unbounded allocations, and avoidable synchronous I/O.
- Changes that can impact runtime cost MUST be validated with a benchmark, profiling note, or a targeted performance test when practical.
- Regressions in user-facing responsiveness or resource use MUST be explained and justified before merge.
- Entry points and import paths MUST stay lightweight; expensive work MUST be deferred until it is actually needed.
- Rationale: performance problems are easiest to prevent when they are treated as requirements, not surprises.

## Governance

- This constitution is binding for specification, planning, implementation, testing, and review.
- When principles conflict, prioritize correctness first, then testability, then user experience consistency, then performance.
- Any amendment MUST include a written rationale, a version bump, and updates to dependent guidance when needed.
- Semantic versioning applies to this document: `MAJOR` for removed or redefined principles, `MINOR` for added principles or materially expanded guidance, and `PATCH` for clarifications.
- Reviews MUST reject changes that violate a principle unless the change includes a documented exception and a follow-up plan.
- This constitution should be revised only when a new constraint is durable enough to guide future work.
