# Build Log

## Phase 1 — Design

AI assistance was used to translate the Social Media Studio brief into a
concrete architecture, data model, API surface, reliability rules, acceptance
checklist, and staged implementation plan.

### Decisions

The project owner selected:

- Python + FastAPI for the backend;
- SQLite for persistent application data;
- SQLAlchemy for database access;
- APScheduler for durable scheduling;
- Discord as the real free publishing target;
- Mock X and Mock LinkedIn as local adapters;
- pytest for deterministic testing;
- local Ollama as an optional enhancement after the core system passes.

### AI Corrections / Boundaries

AI-generated code or suggestions are not considered evidence.

A requirement will only be marked complete after executable tests or real
runtime evidence verifies it.

Optional AI generation will not be allowed to weaken deterministic platform
constraint enforcement.

The core project will be completed before stretch goals are added.

## Phase 2 — Ingestion, Storage and Constraint Validation

AI assistance was used to scaffold the FastAPI service, SQLAlchemy models,
platform constraint profiles, deterministic generator, and automated tests.

Implementation decisions:

- SQLite persistently stores the original post.
- Markdown input is stored directly.
- URL input is fetched once and converted to stored text.
- Generation reads only the stored post.
- Constraint validation is deterministic rather than delegated to an LLM.
- Validation exposes named failures such as `max_length`, `hashtag_count`, and
  `tone`.
- One variant per `(post, platform)` is enforced.
- Repeating variant generation returns the existing variants instead of
  creating duplicates.
- The X-style generator deliberately produces concise content that fits its
  constraint profile.
- AI generation remains optional and does not control validation.

The URL ingestion test mocks HTTP so the automated test suite remains
deterministic and does not depend on external internet access.

The restart-persistence test creates data with one FastAPI application,
destroys it, starts another application against the same SQLite file, and
verifies the stored post still exists.

## Phase 3 — Human Review Workflow

AI assistance was used to implement and test the explicit review state
transitions and the approval gate before scheduling.

Implemented decisions:

- generated variants begin as `draft`;
- a draft can be changed to `approved`;
- a draft can be changed to `rejected`;
- only draft variants may be approved or rejected;
- editing re-runs deterministic platform validation;
- an invalid edit is rejected without changing persisted content;
- editing an approved or rejected variant returns it to `draft`, forcing fresh
  human approval after content changes;
- published variants will be immutable once Phase 4/5 creates that state;
- scheduling is refused unless the variant is `approved`;
- invalid schedule requests use explicit 4xx responses;
- schedule timestamps must include timezone information and be in the future;
- schedule slots are stored persistently in SQLite;
- repeating the same `(variant, time, publisher)` schedule request returns the
  existing slot rather than creating a duplicate.

The actual scheduler worker and publishing side effects are intentionally not
claimed as complete in this phase. Phase 3 only implements the persistent
future slot and the required approval gate.

Phase 3 evidence includes deterministic tests and a local API transcript
showing both the blocked unapproved path and successful approved scheduling.

## Phase 4A — Publisher Adapter Layer

AI assistance was used to implement the common `SocialPublisher` interface,
Discord adapter, two project-owned mock adapters, persistent publish receipts,
publish history, and idempotency tests.

Important design decisions:

- business publishing logic depends on `SocialPublisher`;
- platform selection is resolved by a factory;
- `PUBLISHER_OVERRIDE` proves an adapter can be changed through configuration
  without modifying campaign business logic;
- Mock X and Mock LinkedIn write previews to the database;
- Discord uses a webhook URL read from the environment only;
- the real Discord credential is never stored in source code;
- each schedule derives one stable idempotency key;
- successful publishing creates one unique persistent receipt per schedule;
- sequential retries return the existing receipt and do not invoke the adapter
  again;
- a schedule is atomically changed from `scheduled` to `publishing` before the
  adapter call so a second concurrent worker cannot claim the same scheduled
  item at the same time;
- failed provider calls are recorded and return the slot to `scheduled` for a
  later retry;
- a successful publish changes both the slot and the variant to `published`.

The Discord adapter is tested with a deterministic fake HTTP client. This
proves request construction and response parsing but is not presented as proof
of a real Discord delivery.

A separate real-platform gate is still required before Phase 4 itself is
declared complete.
