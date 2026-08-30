# ADR-003: Location hierarchy — adjacency list + materialized path

Status: Accepted · Date: 2026-08-29

## Context
FR-LOC-001/005/007: arbitrary-depth tree with efficient children, ancestor and
subtree queries, safe moves, and campaign targeting of whole subtrees.
Candidates: pure adjacency list (cheap writes, recursive reads), PostgreSQL
ltree (powerful but PG-extension-coupled and label-restricted), closure table
(fast reads, heavy writes), materialized path (fast subtree reads, path
rewrite on move).

## Decision
`locations.parent_id` (adjacency, source of structural truth) plus a
`path` materialized column of ancestor UUIDs (e.g. `/a/b/c/`), maintained
transactionally by the location service. Subtree queries use
`path LIKE '<node.path>%'` with a pattern-ops index; ancestors are decoded
from the node's own path without extra queries. Moves rewrite the subtree's
paths in one transaction and reject cycles (new parent's path may not contain
the moved node).

## Consequences
- Reads (tree render, subtree targeting, inheritance resolution) are single
  indexable queries — the dominant access pattern for campaign resolution.
- Moves are O(subtree) writes — acceptable: moves are rare admin operations.
- No dependence on PG extensions; SQLite-compatible for the test suite.
