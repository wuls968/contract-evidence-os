# Evolution Candidate Evaluation and Rollback

Evolution candidates are now gated by evaluation reports rather than raw hand-fed gains.

## Example

1. Create a routing-rule candidate.
2. Evaluate it against a benchmark report.
3. If evidence coverage is too weak, the evaluation run fails.
4. A poor canary or failed evaluation leads to rollback.
5. Only candidates with a passing evaluation report and a healthy canary promote.

## Verified By

- [tests/evaluation/test_routing_benchmark.py](/Users/a0000/contract-evidence-os/tests/evaluation/test_routing_benchmark.py:50)
- [tests/regression/test_permission_and_candidate_regressions.py](/Users/a0000/contract-evidence-os/tests/regression/test_permission_and_candidate_regressions.py:21)
