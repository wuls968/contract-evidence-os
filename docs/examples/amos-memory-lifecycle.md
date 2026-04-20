# AMOS Memory Lifecycle Example

## Scenario

A task stores:

- raw request episode
- working memory snapshot
- semantic facts for constraints and preferences
- matrix pointers for associative recall

## Consolidation

An operator runs memory consolidation after several temporal updates.

The runtime:

- reconstructs durative memory for repeated subject/predicate histories
- deduplicates repeated associative pointers
- records a consolidation run

## Rebuild

The runtime rebuilds matrix pointers from surviving semantic facts so retrieval stays source grounded.

## Deletion

If the user asks to forget the task memory scope:

- tombstones are written for raw episodes, semantic facts, matrix pointers, and durative records
- evidence packs stop returning the deleted material
- dashboards go empty for that scope

This gives AMOS a governed forgetting path without breaking audit lineage.
