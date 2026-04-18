# Capability Mapping

This document maps the required core capabilities to concrete code in the repository.

## 1. Task planning and decomposition

- `src/contract_evidence_os/contracts/compiler.py`
- `src/contract_evidence_os/planning/engine.py`
- `src/contract_evidence_os/planning/models.py`

## 2. Tool use and environment action

- `src/contract_evidence_os/tools/files/tool.py`
- `src/contract_evidence_os/tools/shell/tool.py`
- `src/contract_evidence_os/tools/sandbox/tool.py`
- `src/contract_evidence_os/tools/web/tool.py`
- `src/contract_evidence_os/tools/gui/harness.py`

## 3. State retention and multi-layer memory

- `src/contract_evidence_os/memory/models.py`
- `src/contract_evidence_os/memory/matrix.py`

## 4. Result verification and evaluation

- `src/contract_evidence_os/verification/shadow.py`
- `src/contract_evidence_os/tools/verification/toolchain.py`
- `src/contract_evidence_os/evals/harness.py`

## 5. Error recovery, rollback, and replanning

- `src/contract_evidence_os/recovery/engine.py`
- `src/contract_evidence_os/planning/engine.py`

## 6. Multi-agent collaboration and role switching

- `src/contract_evidence_os/agents/models.py`
- `src/contract_evidence_os/agents/registry.py`
- `src/contract_evidence_os/runtime/service.py`

## 7. Human approval, permission boundaries, and policy control

- `src/contract_evidence_os/policy/models.py`
- `src/contract_evidence_os/policy/lattice.py`

## 8. Observability, auditability, and explainable execution trails

- `src/contract_evidence_os/audit/models.py`
- `src/contract_evidence_os/audit/ledger.py`
- `src/contract_evidence_os/evidence/models.py`
- `src/contract_evidence_os/evidence/graph.py`

## 9. Long-horizon continuity and cross-session persistence

- `src/contract_evidence_os/runtime/service.py`
- persisted artifacts in `storage_root/results`, `storage_root/checkpoints`, and `storage_root/audit`

## 10. Safety, robustness, and transparency

- `src/contract_evidence_os/policy/lattice.py`
- `src/contract_evidence_os/verification/shadow.py`
- `src/contract_evidence_os/tools/gui/harness.py`

## 11. Controlled self-learning and self-evolution

- `src/contract_evidence_os/evolution/models.py`
- `src/contract_evidence_os/evolution/engine.py`
- `src/contract_evidence_os/evals/harness.py`
