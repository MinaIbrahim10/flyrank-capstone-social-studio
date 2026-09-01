# Social Media Studio

FlyRank Backend Track capstone.

Social Media Studio changes one stored blog post into platform-specific social
media variants, validates each platform's rules, requires human approval before
publishing, schedules approved variants, and publishes through one common
adapter interface.

## Current Status

- Phase 1 — Design: complete
- Phase 2 — Ingestion, storage, generation and constraints: complete
- Phase 3 — Human review workflow: next
- Phase 4 — Publishing adapters and idempotency: pending
- Phase 5 — Durable scheduler and publish history: pending

## Stack

- Python 3.13+
- FastAPI
- SQLite
- SQLAlchemy
- APScheduler
- httpx
- pytest
- Discord as the real publishing target
- Mock X adapter
- Mock LinkedIn adapter
- optional local Ollama

## Architecture

```text
Blog Post: Markdown or URL
          |
          v
   Ingest + Store
          |
          v
   Variant Generator
          |
          v
 Constraint Validation
          |
          v
    Human Review
      Phase 3
          |
          v
  Durable Scheduler
      Phase 5
          |
          v
   SocialPublisher
    /     |      \
Discord Mock X Mock LinkedIn
      Phase 4
          |
          v
   Publish History
```

## Source of Truth

A post enters as either:

- pasted Markdown; or
- a public URL.

URL content is fetched and stored during ingestion.

After that point, generation reads the stored database record only. The stored
post is the single source of truth.

## Constraint Profiles

### Discord

- maximum 2000 characters
- maximum 5 hashtags
- conversational tone rules

### Mock X

- maximum 280 characters
- maximum 2 hashtags
- concise tone rules

### Mock LinkedIn

- maximum 3000 characters
- maximum 3 hashtags
- professional tone rules

Validation errors identify the exact failed rule:

- `max_length`
- `hashtag_count`
- `tone`

## API

### Health

`GET /health`

### Posts

`POST /posts`

`GET /posts`

`GET /posts/{post_id}`

Markdown example:

```json
{
  "title": "Reliable Publishing",
  "markdown": "# Reliable Publishing\n\nRetries must be safe."
}
```

URL example:

```json
{
  "title": "Example Article",
  "url": "https://example.com/article"
}
```

Exactly one of `markdown` or `url` must be supplied.

### Variants

`POST /posts/{post_id}/variants`

`GET /posts/{post_id}/variants`

`GET /variants/{variant_id}`

Generation creates:

- `discord`
- `mock_x`
- `mock_linkedin`

Every generated variant starts with status `draft`.

### Validate a Variant

`POST /variants/validate`

Example:

```json
{
  "platform": "mock_x",
  "content": "Reliable systems retry safely. #backend"
}
```

A broken platform rule returns HTTP `422` and names the failed rule.

## Setup

```bash
./scripts/setup.sh
```

## Run

```bash
./scripts/run.sh
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Tests

```bash
.venv/bin/pytest -q
```

## Evidence

See `EVIDENCE.md`.

## AI Usage

See `BUILDLOG.md`.

## Known Limitations

The human approve/edit/reject workflow is not implemented yet.

Publishing adapters are not implemented yet.

Durable scheduling and publish history are not implemented yet.

Real Discord publishing will be implemented only after the deterministic core
and review workflow pass.

Real Instagram, X, and LinkedIn publishing is intentionally outside scope.
