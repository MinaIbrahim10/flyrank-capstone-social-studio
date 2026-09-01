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

- [ ] Post ingestion stores the source of truth
- [ ] Variants read from the stored source
- [ ] Platform constraint profiles are enforced
- [ ] Invalid variants name the broken rule
- [ ] Review supports draft / approved / rejected / published
- [ ] Unapproved scheduling returns 4xx
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
- [ ] Probe 3 — unapproved schedule rejected with 4xx
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
