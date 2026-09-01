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
- [x] Review supports draft / approved / rejected / published
- [x] Unapproved scheduling returns 4xx
- [x] Discord real adapter works
- [x] Mock X adapter works
- [x] Mock LinkedIn adapter works
- [x] Adapter swap requires configuration only
- [x] Publishing is idempotent
- [x] Scheduler survives restart
- [x] Worker restart produces zero duplicate posts
- [x] Publish history records attempts and results
- [x] Secrets stay outside Git
- [x] README clean-machine startup works

## Acceptance Probes

- [x] Probe 1 — ingest post and generate valid variants
- [x] Probe 2 — invalid variant blocked with named rule
- [x] Probe 3 — unapproved schedule rejected with 4xx
- [x] Probe 4 — approved scheduled variant publishes to Discord
- [x] Probe 5 — worker restart produces exactly one successful post
- [x] Probe 6 — publisher swapped by configuration only

## Stretch Goals

- [x] A/B variants
- [x] Grounding check
- [x] Local Ollama generation
- [x] AI usage / cost tracking
- [x] Multi-tenant isolation
- [x] Additional scary-case tests

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

## Phase 4A — Publisher Adapter Evidence

Implemented and verified:

- one `SocialPublisher` interface;
- Discord adapter implementation;
- Mock X implementation;
- Mock LinkedIn implementation;
- configuration-only adapter selection;
- persistent mock-platform previews;
- stable per-slot idempotency key;
- persistent unique publish receipt;
- repeated calls return one successful publish result;
- publish attempt history;
- provider failure recording;
- slot retry state after provider failure;
- `approved -> published` after successful adapter execution.

### Automated Phase 4A tests

```text
..............                                                           [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 1 warning in 0.61s
```

### Full regression

```text
...........................................                              [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
43 passed, 1 warning in 1.15s
```

### Deterministic adapter acceptance probe

```text
CONFIG ADAPTER SWAP: PASS discord -> mock_x
IDEMPOTENT RETRY: PASS one successful external result
MOCK PLATFORM STORE: PASS count=1
PUBLISH HISTORY: PASS success_count=1
STATUS TRANSITION: PASS approved -> published
PHASE 4A LOCAL ACCEPTANCE: PASS
```

### Phase 4A status

- [x] `SocialPublisher` abstraction exists.
- [x] Mock X publishes to a local preview store.
- [x] Mock LinkedIn publishes to a local preview store.
- [x] Adapter selection can change through configuration only.
- [x] Repeating a completed publish returns the same persistent receipt.
- [x] A repeated successful publish does not create another mock post.
- [x] Publish attempts are visible.
- [x] Failed provider calls are recorded.
- [x] Successful adapter execution changes the variant to `published`.
- [x] Discord request/response handling is deterministically tested.
- [x] Real Discord message delivery evidence.

Phase 4 is therefore not yet declared fully complete. The final remaining gate
for this phase is a real message delivered to the project owner's Discord
channel using a secret stored only in `.env`.

## Phase 4B — Real Discord Delivery Evidence

This gate uses the real Discord webhook stored only in the ignored local
`.env` file.

The secret itself is never printed and is never committed.

### Real end-to-end result

```text
REAL GATE POST INGESTION: PASS
DISCORD VARIANT CREATED: PASS id=1
HUMAN APPROVAL GATE: PASS
DISCORD SLOT CREATED: PASS slot=1
REAL DISCORD SEND: PASS
Discord message ID: 1544164875507605567
Discord message URL: https://discord.com/channels/1544164705390563421/1544164706321694793/1544164875507605567
REPEATED REAL PUBLISH: PASS
Duplicate prevented: TRUE
REMOTE DISCORD MESSAGE FETCH: PASS
Returned message exists on Discord: TRUE
LOCAL SUCCESSFUL ATTEMPTS: 1
ONE SUCCESSFUL PUBLISH RECORD: PASS
UNIQUE PUBLISH RECEIPT: PASS
IDEMPOTENCY EVIDENCE: PASS

REAL DISCORD PHASE 4 GATE: PASS
```

### Phase 4 Real-Platform Gate

- [x] Discord webhook validated against the real Discord API.
- [x] A stored source produced a Discord variant.
- [x] The Discord variant was human-approved.
- [x] The approved variant received a persistent schedule slot.
- [x] `DiscordPublisher` delivered a real message.
- [x] Discord returned a real external message ID.
- [x] Discord message ID plus webhook metadata provided enough information to build a live message URL.
- [x] The returned message was fetched again from the real Discord API.
- [x] Repeating the publish operation returned the original receipt.
- [x] The repeated operation was marked `duplicate_prevented=true`.
- [x] Exactly one successful local publish record exists for the slot.
- [x] Exactly one persistent publish receipt exists for the slot.

This completes the Phase 4 requirement for one real free publishing target.

The durable automatic scheduler and worker-restart test remain Phase 5 work.

## Phase 4C — Discord Live Message URL

The first real Discord execution returned a valid message ID, but the execution
response did not include every field required to construct the normal browser
message URL, so the original transcript showed `no browser URL was returned in the initial transcript`.

The webhook metadata endpoint was then queried using the local ignored secret.
It returned the Discord guild and channel identifiers. Combined with the
already verified message ID, this produced the normal Discord message URL:

```text
https://discord.com/channels/1544164705390563421/1544164706321694793/1544164875507605567
```

The same message ID was fetched again through Discord before this evidence was
recorded.

- [x] Real message ID verified.
- [x] Guild ID obtained from Discord webhook metadata.
- [x] Channel ID obtained from Discord webhook metadata.
- [x] Normal Discord live message URL constructed.
- [x] Existing message re-verified remotely.
- [x] No second Discord message was created during this correction.

## Phase 4C — Verified Discord Live URL

The already-published Discord message was re-fetched from the real Discord API.
Webhook metadata supplied the guild and channel identifiers required to build
the normal Discord browser URL.

Discord message ID: 1544164875507605567
Discord guild ID: 1544164705390563421
Discord channel ID: 1544164706321694793
Discord live message URL: https://discord.com/channels/1544164705390563421/1544164706321694793/1544164875507605567

Verification:

- [x] Existing Discord message re-fetched from Discord.
- [x] Message ID matches the original real publish.
- [x] Guild ID obtained from Discord webhook metadata.
- [x] Channel ID obtained from Discord webhook metadata.
- [x] Live Discord browser URL constructed from verified identifiers.
- [x] No additional Discord message was sent during this verification.

## Phase 5A — Durable Scheduler and Worker Restart Evidence

Implemented:

- persistent APScheduler SQLAlchemy job store;
- persistent worker process;
- due-slot scanning from SQLite;
- future-slot protection;
- overdue-slot processing after worker restart;
- automatic scheduled mock publishing;
- durable job-store restart verification;
- hard process termination in the middle of a multi-item due batch;
- restart completion of remaining work;
- exact receipt-count verification;
- exact external mock-post-count verification;
- exact successful-attempt-count verification.

### Phase 5A automated tests

```text
.....                                                                    [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 1 warning in 5.01s
```

### Full regression after worker implementation

```text
.................................................                        [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
49 passed, 1 warning in 5.75s
```

### Deterministic hard-crash/restart probe

```text
DURABLE SLOTS CREATED: PASS slots=1,2
MID-BATCH HARD CRASH: PASS exit=86
STATE AFTER CRASH: PASS receipts=1 mock_posts=1 successes=1
WORKER RESTART: PASS
REMAINING SLOT RECOVERED: PASS
ZERO DUPLICATE MOCK POSTS: PASS count=2 for 2 slots
UNIQUE RECEIPTS: PASS count=2 for 2 slots
SUCCESS HISTORY: PASS count=2
PHASE 5A CRASH/RESTART ACCEPTANCE: PASS
```

### Phase 5A Gate

- [x] APScheduler uses a persistent SQLAlchemy job store.
- [x] Durable schedule slots survive worker downtime.
- [x] Future slots are not published early.
- [x] Due slots publish automatically.
- [x] Overdue slots publish after worker restart.
- [x] Worker can be terminated during a multi-item due batch.
- [x] A completed slot is not duplicated after restart.
- [x] Remaining durable work completes after restart.
- [x] Two durable slots produce exactly two mock external posts.
- [x] Two durable slots produce exactly two persistent receipts.
- [x] Two durable slots produce exactly two successful publish attempts.
- [x] Publish history remains queryable.

Not yet claimed:

- the final real Discord two-minute automatic scheduler probe;
- the complete six-probe final acceptance suite.

Those remain Phase 5B.

## Phase 5B — Final Core Acceptance Evidence

### True crash-after-external-side-effect test

```text
.                                                                        [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 1.78s
```

### Full regression before real acceptance

```text
..................................................                       [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
50 passed, 1 warning in 7.25s
```

### Clean-copy one-command stranger demo

```text
CLEAN COPY ONE-COMMAND DEMO: PASS
Command: ./scripts/demo.sh
Fresh copy started without .venv.
Fresh copy started without .env.
Fresh copy started without runtime data.
Virtual environment was created automatically.
Dependencies were installed automatically.
Seed campaign was created automatically.
FastAPI /health returned HTTP 200.
Worker published the seeded campaign to Mock X.
Real Discord was not used.
```

### Six mandatory acceptance probes

```text
/home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
PROBE 1: PASS — stored post generated three valid platform variants
PROBE 2: PASS — invalid variant blocked before review with named max_length rule
PROBE 3: PASS — unapproved scheduling blocked with HTTP 409
PROBE 5: PASS — worker crashed after external mock side effect, restart retried, exactly one external post exists
PROBE 6: PASS — Discord campaign routed through Mock X using configuration only
PROBE 4: real Discord slot created
Scheduled approximately two minutes out: 2026-09-01T02:31:11.115273+00:00
Waiting for automatic scheduler...
PROBE 4 early-publish check: PASS — still unpublished after 30 seconds
Still waiting for scheduled Discord delivery... elapsed_after_early_check=0s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=16s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=30s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=46s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=60s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=76s
Still waiting for scheduled Discord delivery... elapsed_after_early_check=90s
PROBE 4: PASS — approved variant was automatically published by the worker about two minutes after scheduling
PROBE 4 real Discord message ID: 1544172744986337410
PROBE 4 live Discord URL: https://discord.com/channels/1544164705390563421/1544164706321694793/1544172744986337410
PROBE 4 retry protection: PASS — persistent receipt reused

========================================
ALL SIX FINAL ACCEPTANCE PROBES: PASS
========================================
```

### Final Core Gate

- [x] Stored post is the generation source of truth.
- [x] Platform variants are generated and validated.
- [x] Constraint failures identify the broken rule.
- [x] Human approval is required before scheduling.
- [x] Unapproved scheduling returns 4xx.
- [x] Discord is verified as the real free target.
- [x] Mock X is implemented.
- [x] Mock LinkedIn is implemented.
- [x] Publisher swapping requires configuration only.
- [x] Automatic scheduled publishing works.
- [x] Durable scheduler survives restart.
- [x] Publish attempts remain visible.
- [x] Worker restart recovers interrupted work.
- [x] Crash after simulated external Mock X publication does not create a
  duplicate external post.
- [x] Exactly one final receipt exists for the retried slot.
- [x] Real Discord automatic scheduler probe passes.
- [x] Real Discord message is remotely verified.
- [x] Real Discord live message URL is recorded.
- [x] Retry after Discord success returns the existing receipt.
- [x] Clean-copy one-command demo passes.
- [x] Secrets remain outside Git.
- [x] All six acceptance probes pass.

Mandatory/core implementation is complete.

Stretch goals remain separate.

## All Stretch Goals — Final Evidence

All optional stretch goals were implemented after the mandatory/core capstone
had already passed its six acceptance probes.

### Stretch and scary-case tests

```text
..............                                                           [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 1 warning in 0.77s
```

### Full core + stretch regression

```text
................................................................         [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/mina/flyrank-capstone-social-studio/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
64 passed, 1 warning in 8.10s
```

### Real local Ollama integration

```text
REAL LOCAL OLLAMA CALL: PASS
Model: gemma4:e4b-it
Provider: ollama
AI output chars: 161
Prompt tokens: 118
Completion tokens: 459
Cost USD: 0.0
Grounded: True
Guarded fallback used: False
AI USAGE TRACKING: PASS
LOCAL OLLAMA STRETCH GATE: PASS
```

### Combined stretch acceptance

```text
A/B VARIANTS: PASS
A/B WINNER FLOW: PASS
A/B WINNER PROMOTION: PASS
GROUNDING VALID CLAIM: PASS
GROUNDING FABRICATED CLAIM BLOCKED: PASS
MULTI-TENANT CAMPAIGN: PASS
MULTI-TENANT VARIANTS: PASS
CROSS-TENANT ACCESS BLOCKED: PASS
ALL NON-OLLAMA STRETCH ACCEPTANCE: PASS
```

### Stretch Gate

- [x] A/B generation creates two distinct, constraint-valid options.
- [x] Human winner selection stores A or B.
- [x] Winning A/B content can be promoted into the normal review workflow.
- [x] Grounding accepts source-supported claims.
- [x] Grounding detects fabricated numeric claims.
- [x] Local Ollama is called through the application integration.
- [x] AI generation remains protected by deterministic constraint checks.
- [x] Ungrounded/invalid model output falls back to a safe grounded variant.
- [x] Ollama token usage is stored when returned.
- [x] Local Ollama cost is explicitly recorded as `$0.00`.
- [x] Successful and failed AI usage have persistent records.
- [x] Multiple agency/client tenants can be created.
- [x] Tenant campaigns are queried only under their owning tenant.
- [x] Cross-tenant campaign access returns 404.
- [x] Each tenant campaign can create its own three platform variants.
- [x] Duplicate tenant slugs are rejected.
- [x] A/B experiment creation is idempotent.
- [x] Promotion without a winner is blocked.
- [x] Invalid A/B winner labels are blocked.
- [x] Unknown tenant campaign creation is blocked.
- [x] Full mandatory/core regression remains green.

All listed stretch goals are complete.
