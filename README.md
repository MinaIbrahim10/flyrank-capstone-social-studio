# Social Media Studio

FlyRank Backend Track capstone.

Social Media Studio changes one stored blog post into platform-specific social
media variants, validates platform rules, requires human approval, schedules
approved variants, and later publishes them through one common adapter
interface.

## Current Status

- Phase 1 — Design: complete
- Phase 2 — Ingestion, storage, generation and constraints: complete
- Phase 3 — Human review workflow and schedule approval gate: complete
- Phase 4 — Publisher adapters and idempotent publishing: next
- Phase 5 — Durable worker, publish history and crash recovery: pending

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
 draft -> approved
       \-> rejected
          |
          v
   Schedule Gate
 approved only
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
     Phase 5
```

## Source of Truth

A post enters as either pasted Markdown or a public URL.

URL content is fetched and stored during ingestion.

After ingestion, generation reads only the stored database record. The stored
post is the single source of truth.

## Platform Constraint Profiles

### Discord

- maximum 2000 characters
- maximum 5 hashtags
- conversational tone checks

### Mock X

- maximum 280 characters
- maximum 2 hashtags
- concise tone rules

### Mock LinkedIn

- maximum 3000 characters
- maximum 3 hashtags
- professional tone rules

Constraint errors identify the exact failed rule:

- `max_length`
- `hashtag_count`
- `tone`

## Review Workflow

Every generated variant begins as:

```text
draft
```

A human reviewer can:

```text
draft -> approved
```

or:

```text
draft -> rejected
```

Editing a non-published variant runs platform validation again and returns the
variant to:

```text
draft
```

This prevents an old approval from remaining valid after content changes.

Only `approved` variants may be scheduled.

A schedule request for a `draft` or `rejected` variant returns HTTP `409`.

The final transition:

```text
approved -> published
```

will be implemented only after an actual publisher reports successful delivery
in the publishing phases.

## API

### Health

`GET /health`

### Posts

`POST /posts`

`GET /posts`

`GET /posts/{post_id}`

### Generate Variants

`POST /posts/{post_id}/variants`

`GET /posts/{post_id}/variants`

### Read a Variant

`GET /variants/{variant_id}`

### Edit a Variant

`PUT /variants/{variant_id}`

Example:

```json
{
  "content": "Reviewed and updated social post. #backend"
}
```

The edited content is validated against the platform constraint profile before
it is saved.

### Approve

`POST /variants/{variant_id}/approve`

Only a `draft` variant can be approved.

### Reject

`POST /variants/{variant_id}/reject`

Only a `draft` variant can be rejected.

### Validate Content

`POST /variants/validate`

### Schedule

`POST /variants/{variant_id}/schedule`

Example:

```json
{
  "scheduled_at": "2030-01-01T12:00:00+00:00"
}
```

Rules:

- the variant must be `approved`;
- the timestamp must include a timezone;
- the timestamp must be in the future;
- repeating the same schedule request returns the same stored slot.

### List Schedules

`GET /schedules`

### Read Schedule

`GET /schedules/{slot_id}`

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

Creating a schedule currently stores the approved future publishing slot.

The background worker does not execute that slot yet; durable execution belongs
to Phase 5.

The Discord, Mock X, and Mock LinkedIn publisher implementations are not yet
connected; they belong to Phase 4.

A variant becomes `published` only after a real publishing success in a later
phase.

Real Instagram, X, and LinkedIn publishing is intentionally outside scope.

## Publisher Adapter Layer

Phase 4 introduces one common `SocialPublisher` abstraction.

Current implementations:

- `DiscordPublisher` — real Discord webhook adapter
- `MockXPublisher` — local database-backed mock
- `MockLinkedInPublisher` — local database-backed mock

Business publishing logic calls the interface rather than platform-specific
code.

### Configuration-only adapter swap

The environment variable:

```text
PUBLISHER_OVERRIDE
```

can temporarily replace the scheduled publisher with:

```text
discord
mock_x
mock_linkedin
```

For example:

```text
PUBLISHER_OVERRIDE=mock_x
```

allows a schedule originally targeting Discord to flow through the Mock X
adapter without changing application business logic.

### Idempotent publishing

The endpoint:

```text
POST /schedules/{slot_id}/publish
```

derives a stable idempotency key from:

```text
variant + scheduled time + scheduled publisher
```

A successful publish creates one persistent receipt.

Calling the same publish endpoint again returns the original receipt and does
not execute the adapter a second time.

### Publish history

```text
GET /publish-history
```

shows successful and failed publishing attempts.

### Mock platform preview store

```text
GET /mock-posts
```

shows posts delivered through Mock X or Mock LinkedIn.

### Discord

The Discord adapter uses:

```text
DISCORD_WEBHOOK_URL
```

from the environment.

The real value belongs only in `.env`.

It must never be committed.

The adapter requests the Discord message object with `wait=true`, stores the
external message ID, and records a live Discord message URL when Discord
returns guild, channel, and message identifiers.

### Phase 4 verification status

Deterministic adapter, mock-platform, configuration-swap, failure-recording,
and retry/idempotency tests are complete.

Real Discord delivery is intentionally not claimed yet.

The Phase 4 core gate becomes complete only after a message is actually sent to
the project owner's Discord target and the returned live message is recorded as
evidence.
