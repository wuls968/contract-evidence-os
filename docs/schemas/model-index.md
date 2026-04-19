# Model Index

This index tracks the major public model families used by the runtime OS, AMOS memory OS, and software control fabric.

## Runtime and Core Execution

- Contracts: `TaskContract`, `ContractDelta`, `ContractLattice`
- Planning: `PlanNode`, `PlanEdge`, `PlanGraph`, `PlanRevision`, `ExecutionBranch`
- Evidence: `SourceRecord`, `EvidenceNode`, `EvidenceEdge`, `ClaimRecord`, `ValidationReport`
- Audit and execution: `AuditEvent`, `ExecutionReceipt`
- Queueing and coordination: `QueueItem`, `QueueLease`, `DispatchRecord`, `WorkerLifecycleRecord`, `LeaseOwnershipRecord`

## AMOS Memory Kernel

- Base memory: `MemoryRecord`, `MemoryPromotionRecord`, `RawEpisodeRecord`, `WorkingMemorySnapshot`
- Write and evidence surfaces: `MemoryWriteCandidate`, `MemoryWriteReceipt`, `MemoryEvidencePack`
- Governance: `MemoryAdmissionPolicy`, `MemoryAdmissionDecision`, `MemoryGovernanceDecision`, `MemoryDeletionReceipt`
- Semantic and temporal state: `TemporalSemanticFact`, `DurativeMemoryRecord`, `MemoryTimelineSegment`, `MemoryTimelineView`
- Project state: `MemoryProjectStateSnapshot`, `MemoryProjectStateView`
- Matrix and procedural lanes: `MatrixAssociationPointer`, `ProceduralPattern`, `MemorySoftwareProcedureRecord`
- Consolidation and repair: `MemoryConsolidationRun`, `MemoryConsolidationPolicy`, `MemoryRepairPolicy`, `MemoryContradictionRepairRecord`
- Purge and rebuild: `MemoryDeletionRun`, `MemorySelectivePurgeRun`, `MemoryHardPurgeRun`, `MemoryRebuildRun`, `MemorySelectiveRebuildRun`, `MemoryPurgeManifest`
- Maintenance and operations: `MemoryMaintenanceWorkerRecord`, `MemoryMaintenanceSchedule`, `MemoryMaintenanceRun`, `MemoryMaintenanceIncidentRecord`, `MemoryOperationsLoopRun`, `MaintenanceDaemonRun`, `MaintenanceWorkerLeaseState`, `MaintenanceIncidentRecommendation`, `MaintenanceResolutionAnalytics`

## Software Control Fabric

- Harness and bridge: `SoftwareHarnessRecord`, `SoftwareHarnessValidation`, `SoftwareControlBridgeConfig`, `SoftwareBuildRequest`
- Public capability and manifests: `AppCapabilityRecord`, `HarnessManifest`, `SoftwareRiskClass`
- Execution and replay: `SoftwareActionReceipt`, `SoftwareReplayRecord`, `SoftwareReplayDiagnostic`, `SoftwareFailurePattern`, `SoftwareFailureCluster`, `SoftwareRecoveryHint`
- Automation: `SoftwareAutomationMacro`
- Policy and commands: `SoftwareControlPolicy`, `SoftwareCommandDescriptor`

## Observability

- Telemetry and authoritative snapshots: `TelemetryEvent`, `ObservabilityMetricSnapshot`, `SoftwareControlTelemetryRecord`
- Trend and alert surfaces: `ObservabilityTrendReport`, `ObservabilityAlertRecord`

## Reliability, Security, and Shared State

- Reliability: `ReliabilityIncident`, `BackendOutageRecord`, `ReconciliationRun`, `LeasePredictionRecord`
- Provider governance: `ProviderDemandForecast`, `ProviderCapacityForecast`, `ProviderQuotaPolicy`, `QuotaGovernanceDecision`
- Auth and trust: `AuthCredential`, `AuthPrincipal`, `ServiceCredential`, `ServicePrincipal`, `ServiceTrustPolicy`, `TrustBoundaryDescriptor`
- Shared state and backends: `SharedStateBackendDescriptor`, `BackendHealthRecord`, `BackendPressureSnapshot`

## Evolution and Analytics

- Evolution core: `EvolutionCandidate`, `EvaluationRun`, `CanaryRun`
- Memory policy evolution: `MemoryLifecycleTrace`, `MemoryPolicyMiningRun`, `MemoryPolicyAnalyticsRecord`

## Stability Notes

- `operator api v1` and the `ceos` operator CLI should prefer the models listed above instead of milestone-specific ad hoc payloads.
- Internal milestone-era record types still exist, but the models in this file are the preferred public/stable vocabulary for `0.9.0`.
