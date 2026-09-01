# Evidence

This document records proof for every required capstone behavior.

A requirement is not marked complete because code exists.

It is marked complete only after a test, API transcript, database record, or
real publish result proves it.

## Phase 1 — Design

- [x] Problem defined
- [x] User workflow defined
- [x] Data model designed
- [x] API surface designed
- [x] Constraint-profile system designed
- [x] Review workflow designed
- [x] SocialPublisher interface designed
- [x] Reliability rules designed
- [x] Explicit non-goal documented

## Core Requirements

- [x] Post ingestion stores the source of truth
- [x] Variants read from the stored source
- [x] Platform constraint profiles are enforced
- [x] Invalid variants name the broken rule
- [ ] Review supports draft / approved / rejected / published
- [x] Unapproved scheduling returns 4xx
- [ ] Discord real adapter works
- [ ] Mock X adapter works
- [ ] Mock LinkedIn adapter works
- [ ] Adapter swap requires configuration only
- [ ] Publishing is idempotent
- [ ] Scheduler survives restart
- [ ] Worker restart produces zero duplicate posts
- [ ] Publish history records attempts and results
- [ ] Secrets stay outside Git
- [ ] README clean-machine startup works

## Acceptance Probes

- [ ] Probe 1 — ingest post and generate valid variants
- [ ] Probe 2 — invalid variant blocked with named rule
- [x] Probe 3 — unapproved schedule rejected with 4xx
- [ ] Probe 4 — approved scheduled variant publishes to Discord
- [ ] Probe 5 — worker restart produces exactly one successful post
- [ ] Probe 6 — publisher swapped by configuration only

## Stretch Goals

- [ ] A/B variants
- [ ] Grounding check
- [ ] Local Ollama generation
- [ ] AI usage / cost tracking
- [ ] Multi-tenant isolation
- [ ] Additional scary-case tests

## Phase 2 — Ingestion and Generation Evidence

Phase 2 implements:

- persistent SQLite storage;
- Markdown ingestion;
- URL ingestion;
- stored source-of-truth behavior;
- Discord, Mock X, and Mock LinkedIn variants;
- deterministic length enforcement;
- deterministic hashtag enforcement;
- deterministic tone checks;
- named constraint failures;
- repeated generation without duplicate variant rows;
- persistence across application restart.

### Automated test command

```text
.venv/bin/pytest tests/test_phase2.py -q
```

### Actual automated test output

```text
..............                                                           [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 1 warning in 0.40s
```

### Actual local API probe

```text
POST INGESTION: PASS id=1 source=markdown
VARIANT GENERATION: PASS discord,mock_x,mock_linkedin
INITIAL VARIANT STATUS: PASS all=draft
BROKEN VARIANT BLOCKED: PASS status=422 rules=['max_length']
HASHTAG RULE: PASS status=422
VALID VARIANT: PASS status=200
REPEATED GENERATION: PASS no duplicate rows
PHASE 2 LOCAL ACCEPTANCE: PASS
```

### Phase 2 Gate

- [x] A post enters as Markdown or URL and is stored.
- [x] Generation reads the stored post.
- [x] The stored post is the source of truth.
- [x] Platform-specific variants are generated.
- [x] Constraint profiles enforce length.
- [x] Constraint profiles enforce hashtag limits.
- [x] Constraint profiles include deterministic tone rules.
- [x] A bad variant is blocked before review.
- [x] The error identifies the broken rule.
- [x] Repeating generation creates no duplicate rows.
- [x] SQLite data survives application restart.

Human review remains Phase 3.

## Phase 3 — Human Review Evidence

Implemented:

- `draft` initial variant state;
- human editing;
- deterministic revalidation after editing;
- invalid edit rejection with the broken rule named;
- `draft -> approved`;
- `draft -> rejected`;
- edits return reviewed content to `draft`;
- schedule requests require `approved`;
- draft scheduling returns 4xx;
- rejected scheduling returns 4xx;
- approved scheduling succeeds;
- schedule timestamps require timezone information;
- past schedule timestamps are rejected;
- repeated identical schedule requests resolve to one persistent slot;
- schedule records survive application restart.

### Phase 3 automated tests

Command:

```text
.venv/bin/pytest tests/test_phase3.py -q
```

Actual output:

```text
...............                                                          [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
15 passed, 1 warning in 0.61s
```

### Full regression after Phase 3

Command:

```text
.venv/bin/pytest -q
```

Actual output:

```text
.............................                                            [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 1 warning in 0.76s
```

### Human-review API acceptance transcript

```text
DRAFT CREATED: PASS variant=1 status=draft
UNAPPROVED SCHEDULE BLOCKED: PASS status=409
INVALID EDIT BLOCKED: PASS rules=['max_length']
VALID EDIT: PASS status=draft
REJECT WORKFLOW: PASS status=rejected
REJECTED SCHEDULE BLOCKED: PASS status=409
APPROVAL WORKFLOW: PASS status=approved
APPROVED SCHEDULE: PASS slot=1 publisher=discord
DUPLICATE SCHEDULE REQUEST: PASS same_slot=true
PHASE 3 LOCAL ACCEPTANCE: PASS
```

### Phase 3 Gate

- [x] Generated variants begin in `draft`.
- [x] A human can edit a variant.
- [x] Edited content is revalidated.
- [x] A rule-breaking edit is blocked.
- [x] Invalid edits identify the broken platform rule.
- [x] A draft can be approved.
- [x] A draft can be rejected.
- [x] Editing reviewed content requires fresh approval.
- [x] A draft variant cannot be scheduled.
- [x] A rejected variant cannot be scheduled.
- [x] An unapproved scheduling attempt returns 4xx.
- [x] An approved variant can be scheduled.
- [x] Schedule records persist in SQLite.
- [x] Repeating the same schedule request creates no duplicate slot.

Not yet claimed:

- `approved -> published` is not marked complete because no publisher has
  delivered the content yet.
- durable worker execution is not marked complete yet.
- publish history is not marked complete yet.

## Phase 3 — Final Route Registration Verification

The first auxiliary route-inspection gate used a direct route-set comparison
that did not match FastAPI's internal route representation, even though the
behavioral tests and API acceptance probe had already passed.

The corrected gate verifies registered operations through FastAPI's generated
OpenAPI schema and then repeats the critical review and scheduling behavior.

### OpenAPI registration check

```text
PUT  /variants/{variant_id}: PASS
POST /variants/{variant_id}/approve: PASS
POST /variants/{variant_id}/reject: PASS
POST /variants/{variant_id}/schedule: PASS
GET  /schedules: PASS
GET  /schedules/{slot_id}: PASS

PHASE 3 OPENAPI ROUTE VERIFICATION: PASS
```

### Critical behavior re-check

```text
DRAFT SCHEDULE BLOCKED: PASS status=409
APPROVAL: PASS status=approved
APPROVED SCHEDULE: PASS status=201
DUPLICATE SCHEDULE PROTECTION: PASS
PHASE 3 BEHAVIOR RECOVERY CHECK: PASS
```

The corrected verification confirms that the edit, approve, reject, scheduling,
and schedule-read operations are registered.

It also confirms:

- a draft variant cannot be scheduled;
- approval changes the variant to `approved`;
- an approved variant can be scheduled;
- repeating the same schedule request returns the same persistent slot.
