# Social Media Studio — Design

## Problem

A single blog post often needs several different social-media versions.

Each platform has different rules for text length, tone, and hashtags.
Publishing also has reliability problems: an unapproved post must never be
published, retries must not create duplicate posts, and scheduled work must
survive application or worker restarts.

Social Media Studio solves this by storing one original blog post, creating
platform-specific versions, requiring human approval, and publishing approved
versions safely through one common publishing interface.

## Who Uses It?

The main user is a content or marketing team member who:

1. adds a blog post;
2. generates social-media variants;
3. reviews the variants;
4. approves, edits, or rejects them;
5. schedules approved variants;
6. checks publish history.

## Core Architecture

    Blog Post
        |
        v
    Ingestion + Storage
        |
        v
    Variant Generator
        |
        v
    Constraint Validator
        |
        v
    Human Review
    draft -> approved / rejected
        |
        v
    Durable Scheduler
        |
        v
    SocialPublisher Interface
        |-- DiscordPublisher
        |-- MockXPublisher
        |-- MockLinkedInPublisher
        |
        v
    Publish History

## Technology

- Python 3.13+
- FastAPI
- SQLite
- SQLAlchemy
- APScheduler with persistent storage
- Discord webhook as the real free publishing platform
- pytest
- optional local Ollama after the deterministic core works

## Data Model

### posts

Stores the original article.

Fields:

- id
- title
- source_type
- source_url
- markdown
- created_at

The stored post is the single source of truth.

Variant generation must read from this stored post, not from temporary input.

### variants

Stores one platform-specific version of a post.

Fields:

- id
- post_id
- platform
- content
- status
- created_at
- updated_at

Allowed statuses:

- draft
- approved
- rejected
- published

### schedule_slots

Stores when an approved variant should publish.

Fields:

- id
- variant_id
- publisher
- scheduled_at
- idempotency_key
- status
- created_at

The same variant and publishing slot must not create duplicate posts.

### publish_attempts

Stores every attempt to publish.

Fields:

- id
- slot_id
- publisher
- attempted_at
- result
- external_message_id
- external_url
- error

This gives us visible publish history.

### mock_posts

Stores messages sent through fake platform adapters.

Fields:

- id
- platform
- variant_id
- content
- idempotency_key
- created_at

Mock X and Mock LinkedIn use this table instead of calling real platforms.

## Constraint Profiles

A constraint profile means the rules for one platform.

The rules are stored centrally so business logic does not contain duplicated
platform-specific checks.

### X-style

Rules include:

- short content;
- maximum text length;
- concise tone;
- limited hashtag count.

### LinkedIn-style

Rules include:

- longer professional content;
- professional tone;
- limited hashtag count.

### Discord

Rules include:

- conversational content;
- Discord message-length limit;
- limited hashtag count.

A variant that violates a rule must be rejected before human review.

The error must explain which rule failed.

## Review Workflow

Every new variant begins as:

    draft

A human can then:

    draft -> approved

or:

    draft -> rejected

An approved variant may later become:

    approved -> published

Only an approved variant may be scheduled.

If someone tries to schedule a draft or rejected variant, the API must return
a 4xx error with a useful message.

## Publisher Adapter

The application uses one interface:

    SocialPublisher

Each platform implements that same interface.

Conceptually:

    publish(
        variant,
        idempotency_key
    ) -> PublishResult

Implementations:

- DiscordPublisher — real Discord message
- MockXPublisher — records the fake post locally
- MockLinkedInPublisher — records the fake post locally

The scheduling and business logic must not care which implementation is active.

Changing an adapter should require configuration only.

## API Surface

### Health

- GET /health

### Posts

- POST /posts
- GET /posts
- GET /posts/{post_id}

### Variants

- POST /posts/{post_id}/variants
- GET /posts/{post_id}/variants
- GET /variants/{variant_id}
- PUT /variants/{variant_id}

### Review

- POST /variants/{variant_id}/approve
- POST /variants/{variant_id}/reject

### Scheduling

- POST /variants/{variant_id}/schedule
- GET /schedules
- GET /schedules/{slot_id}

Scheduling an unapproved variant returns 4xx.

### Publishing

- POST /schedules/{slot_id}/publish

Publishing is idempotent.

Retrying the same slot must not create a second successful platform post.

### History

- GET /publish-history

## Reliability Rules

1. A rule-breaking variant never reaches review.
2. An unapproved variant cannot be scheduled.
3. A repeated publish request cannot create a duplicate post.
4. Scheduled work survives restart.
5. A worker restart must continue safely.
6. Every publish attempt is recorded.
7. Platform selection happens through configuration.
8. Real Discord credentials live only in `.env`.
9. No secret is committed to Git.

## Acceptance Targets

Before submission we must prove all six reviewer scenarios.

### Probe 1

Store a sample article and generate valid platform variants.

### Probe 2

Create a variant that breaks a platform rule.

The system must reject it and identify the broken rule.

### Probe 3

Try to schedule an unapproved variant.

The system must return a 4xx response.

### Probe 4

Approve a variant and schedule it.

The scheduler must publish a real message to our Discord target.

### Probe 5

Stop the worker during publishing and restart it.

Exactly one successful post must exist.

No duplicate is allowed.

### Probe 6

Change the publisher configuration from Discord to a mock adapter.

The campaign must publish through the mock adapter without changing business
logic.

## Stretch and Bonus Plan

We will implement these only after every core acceptance probe passes.

### A/B Variants

Generate two alternatives for a platform and allow a user to choose the winner.

### Grounding Check

Check that important factual claims in generated variants are supported by the
stored source article.

### Local AI Generation

Use local Ollama to generate variants while keeping deterministic constraint
validation around the model.

### AI Cost Tracking

Track AI usage per campaign.

Local Ollama costs $0, but token and usage accounting can still be recorded.

### Multi-Tenant Support

Add agencies or clients whose posts, variants, schedules, and history are
isolated from each other.

### Additional Reliability Tests

Add deterministic tests for:

- blocked variants;
- unapproved scheduling;
- duplicate publish attempts;
- adapter switching;
- worker restart;
- dependency failure;
- AI validation failures.

## Explicit Non-Goal

The project will not publish to real Instagram, X, or LinkedIn accounts.

X and LinkedIn are represented by mock adapters.

Discord is the real publishing target.
