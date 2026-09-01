# MIH identity contract

Canonical entitlement id: `mih_community_paramedicine`

Canonical service audience: `adaptix-mih`

`adaptix-mih` is registered in `service_audiences.py`, and
`mih_community_paramedicine` is registered in `module_registry.py`
(alias `mih`, audience `adaptix-mih`, purchasable) so Core's module catalog
can grant it and per-state restriction keeps matching the same string. Core, Gateway, and Adaptix-MIH-Service must consume these identifiers from the shared Contracts package or pin equivalent values in tests until the module registry entry is fully consolidated.

## Service surface covered by `adaptix_contracts.mih`

| Adaptix-MIH-Service route family | Shared contract |
| --- | --- |
| `/api/v1/mih/patients` | `MihEnrollment` (enrollment lifecycle; the service's `patient_identity_id` is the opaque platform patient identity) |
| `/api/v1/mih/patients/{id}/care-plans` | `MihServicePlan` |
| `/api/v1/mih/patients/{id}/visits` | `MihVisit` |
| `/api/v1/mih/patients/{id}/readings` | `MihRemoteReading`, `MihRemoteReadingBreach` |
| `/api/v1/mih/thresholds` | `MihMonitoringThreshold` |
| `/api/v1/mih/escalations` | `MihEscalation` |
| `/api/v1/mih/utilization/policies` | `MihUtilizationPolicy` |
| `/api/v1/mih/utilization/observations` | `MihUtilizationObservation` |
| `/api/v1/mih/utilization/evaluations` | `HighUtilizerSignal` |
| `/api/v1/mih/utilization/recommendations` | `MihEnrollmentRecommendation` |

Events: `mih.utilization.observation_recorded`, `mih.high_utilizer.evaluated`,
`mih.enrollment_recommendation.changed` (see `adaptix_contracts/mih/events.py`).
The MIH service does not yet publish these events; the shapes are the agreed
contract for the producer wave. A high-utilizer recommendation never enrolls a
patient: `status=enrolled` only ever records a supervisor resolving the row
against an enrollment that already exists with recorded consent.
