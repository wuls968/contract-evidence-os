# Evolution Canary Example

Repeated successful traces of "file retrieval -> evidence extraction -> shadow validation"
may be distilled into a `SkillCapsule`.

That capsule becomes an `EvolutionCandidate` and must:

1. pass offline evaluation,
2. run in a limited canary scope,
3. emit canary metrics, and
4. either promote or roll back based on regression signals.
