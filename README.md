# Social Media Studio

Backend capstone for the FlyRank AI Internship.

Social Media Studio turns one stored blog post into platform-specific social
media variants, validates platform rules, requires human approval, schedules
approved variants, and publishes each scheduled item exactly once through a
clean adapter architecture.

## Core Goal

One blog post becomes multiple reviewed social posts without:

- violating platform constraints;
- publishing unapproved content;
- creating duplicate posts during retries;
- losing scheduled work after a restart.

## Planned Stack

- Python 3.13+
- FastAPI
- SQLite
- SQLAlchemy
- APScheduler
- Discord webhook for one real publishing target
- Mock X adapter
- Mock LinkedIn adapter
- pytest
- optional local Ollama

## Architecture

    Blog Post
       |
       v
    Persistent Storage
       |
       v
    Variant Generator
       |
       v
    Constraint Validation
       |
       v
    Human Review
       |
       v
    Durable Scheduler
       |
       v
    SocialPublisher
       |-- Discord
       |-- Mock X
       |-- Mock LinkedIn
       |
       v
    Publish History

## Development Status

Phase 1 — Design.

See:

- `DESIGN.md`
- `EVIDENCE.md`
- `BUILDLOG.md`

## Submission Files

The repository will contain:

- `README.md`
- `EVIDENCE.md`
- `BUILDLOG.md`
- `.env.example`

## Run

The runnable application begins in Phase 2.

Exact one-command startup and seed instructions will be added before the
project is considered submission-ready.

## Testing

Every core requirement will receive deterministic automated tests.

Real Discord publishing will also receive recorded end-to-end evidence.

## Known Limitations

The project is currently at the design phase.

No production API or scheduler has been implemented yet.

Real publishing will intentionally support only Discord. X and LinkedIn use
local mock adapters.
