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
