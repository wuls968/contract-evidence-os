# ADR-072 Maintenance Analytics Loop

## Status

Accepted

## Decision

Every background maintenance execution now emits analytics covering:

- resumed loop count
- applied repair count
- shared artifact repair count
- fallback action count

## Why

Milestone 20 closes the loop from diagnostics to recommendation to action and then to measurable outcome, which makes future promotion and rollback decisions more evidence-backed.

