# ADR-070 Learned Maintenance Recommendation Canary

## Status

Accepted

## Decision

We add a lightweight learned maintenance controller, maintenance canary runs, and maintenance promotion recommendations.

The learned controller does not directly mutate memory state. It only changes recommendation scoring and must first pass through canary and promotion surfaces.

## Why

Milestone 19 added learned repair safety, but maintenance recommendation logic was still fully static. This milestone extends learning to the maintenance layer without making it opaque.

