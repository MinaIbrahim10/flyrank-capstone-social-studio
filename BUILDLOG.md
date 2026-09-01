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
