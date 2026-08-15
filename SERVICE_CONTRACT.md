# Adaptix-Contracts Service Contract

## Purpose

Publish shared request/response/event schemas used across Adaptix services.

## Contract Rules

- Schemas must be versioned.
- Breaking changes must be coordinated across consumers.
- Runtime services must import the real package, not a local mock.
- Contract tests must cover required fields, optional fields, validation errors,
  and backwards compatibility where promised.
- Workspace release checks must fail if a shadow `adaptix_contracts` package is
  detected outside this repo.
- Event contracts must not stop at `event_type` registration when payloads cross
  service boundaries; any generic `payload: dict[str, Any]` path must have an
  exact producer/consumer schema contract or be recorded as a rollout blocker for
  the producer and consumer repos.

## Data Ownership

This package owns schema definitions only. It does not own persisted domain data.

## Failure Contract

Import failures, mismatched schema versions, and mock package usage are
production blockers.
