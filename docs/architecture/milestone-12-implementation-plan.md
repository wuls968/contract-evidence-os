# Milestone 12 Implementation Plan

## Goal

Deepen AMOS from a layered memory substrate into an operational memory lifecycle system with:

- governed deletion and tombstones
- sleep-time consolidation
- index rebuild and pointer refresh
- operator-visible lifecycle controls
- lifecycle-oriented evaluation metrics

## Scope

This milestone keeps the existing AMOS lanes and adds lifecycle depth around them.
The focus is not broader memory breadth, but stronger correctness over time:

- forgetting safely
- consolidating without losing provenance
- rebuilding without drifting away from source grounding

## Core Additions

1. **Memory tombstones**
   - Tombstone records hide deleted raw episodes, semantic facts, matrix pointers, durative records, and procedural patterns from retrieval and dashboards.

2. **Memory lifecycle runs**
   - Deletion runs
   - Consolidation runs
   - Rebuild runs

3. **Sleep-time consolidation**
   - Reconstruct durative memory from temporal fact histories
   - Deduplicate matrix pointers conservatively

4. **Index rebuild**
   - Recreate source-grounded matrix pointers from surviving semantic facts
   - Refresh dashboard material after consolidation or deletion

5. **Operator surfaces**
   - Consolidate memory
   - Rebuild memory indexes
   - Delete memory scope

## Intentional Minimums

- Deletion is scope-driven and tombstone-based, not physical hard purge of every stored artifact.
- Consolidation is rule-based, not a learned sleep model.
- Rebuild is pointer regeneration, not a full graph retraining process.
