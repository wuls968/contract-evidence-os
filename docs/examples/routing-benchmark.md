# Routing Benchmark

Milestone 2 adds a benchmarkable strategy comparison path.

## Strategies

- `economy`
  Uses lighter extraction and may capture fewer grounded facts.
- `quality`
  Uses a fuller extraction profile and aims for stronger evidence coverage.

## Flow

1. Load a golden task dataset.
2. Run the same task set through two runtime factories.
3. Grade each strategy on:
   - expected fact coverage,
   - evidence coverage,
   - policy violations,
   - trace integrity,
   - shadow verification.
4. Return a `StrategyEvaluationReport` per strategy.

## Verified By

- [tests/evaluation/test_routing_benchmark.py](/Users/a0000/contract-evidence-os/tests/evaluation/test_routing_benchmark.py:9)
