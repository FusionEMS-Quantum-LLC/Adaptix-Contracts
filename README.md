# Adaptix Contracts

**Version:** 2.2.0

Canonical shared cross-domain schema definitions for the Adaptix polyrepo platform.

## Overview

This package provides typed Pydantic contract definitions for cross-domain
communication across all Adaptix services. It is the single source of truth for:

- **Event contracts** - Domain events published across services
- **Request/Response contracts** - API request and response schemas
- **Read-only contracts** - Cross-domain data transfer objects
- **Shared enums** - Canonical status and type enumerations

## Package Structure

```text
adaptix_contracts/
├── __init__.py          # Package root with convenience exports
└── schemas/             # All contract schema definitions
    ├── __init__.py      # Consolidated schema exports
    ├── air_contracts.py
    ├── air_pilot_contracts.py
    ├── audit_contracts.py
    ├── billing_*.py     # Billing domain contracts
    ├── cad_*.py         # CAD domain contracts
    ├── core_contracts.py
    ├── crewlink_contracts.py
    ├── communications_contracts.py
    ├── contract_onboarding_contracts.py
    ├── epcr_contracts.py
    ├── feature_flag_contracts.py
    ├── field_contracts.py
    ├── fire_contracts.py
    ├── legal_execution_contracts.py
    ├── metrics_contracts.py
    ├── nemsis_exports.py
    ├── ocr_contracts.py
    ├── patient_portal_contracts.py
    ├── search_contracts.py
    ├── signature_compliance_contracts.py
    ├── transport_contracts.py
    ├── voice_contracts.py
    └── workflow_contracts.py
```

## Domain Coverage

This package provides schema coverage across the core platform foundation plus
operational, legal, signature, and onboarding domains. The authoritative
inventory is the validator output from `python validate_contracts.py --json`.

### Core Infrastructure

- **core** - Base event contracts and auth context
- **audit** - Audit logging, PHI access, security events
- **metrics** - Service health, observability
- **search** - Cross-domain search and indexing
- **communications** - Notifications and messaging
- **feature_flag** - Feature flag resolution
- **workflow** - Long-running workflows and orchestration

### Billing Domain (8 modules)

- **billing** - Core claim lifecycle, payments, denials
- **billing_auth** - Billing portal authentication
- **billing_clearinghouse** - Clearinghouse integrations
- **billing_eligibility** - Insurance verification
- **billing_portal** - Portal UI contracts
- **billing_transport** - Billing-transport readiness

### Clinical & Operations

- **epcr** - Electronic patient care reports
- **clinical_visual** - AR-assisted clinical overlays and structured findings
- **nemsis** - NEMSIS export lifecycle
- **ocr** - Document OCR processing
- **patient_portal** - Patient-facing portal

### Dispatch & Field

- **cad** - Computer-aided dispatch
- **cad_transport** - CAD-transport integration
- **fire** - Fire incident management
- **field** - Field unit status and telemetry
- **inventory** - Inventory, replenishment, readiness, and cycle count contracts

### Air Operations

- **air** - Air mission contracts
- **air_pilot** - Pilot readiness and go/no-go

### Transport

- **transport** - Transport request lifecycle
- **crewlink** - Crew paging and rostering

### Voice

- **voice** - Voice room management

## Installation

```bash
# From source (development)
pip install -e .

# From package repository
pip install adaptix-contracts
```

## Requirements

- Python >= 3.11
- Pydantic >= 2.6.0

## Usage

### Import All Schemas

```python
from adaptix_contracts.schemas import *

# Use any schema
claim = ClaimContract(
    claim_id="claim-123",
    tenant_id="tenant-123",
    patient_id="patient-123",
    status=ClaimStatus.DRAFT,
    total_charge_cents=10000,
    balance_cents=10000,
    created_at=datetime.now(),
    updated_at=datetime.now(),
)
```

### Import Specific Schemas

```python
from adaptix_contracts.schemas import (
    ClaimContract,
    ClaimStatus,
    ClaimCreatedEvent,
    EpcrChartFinalizedEvent,
    TransportRequestCreate,
)
```

### Working with Events

```python
from adaptix_contracts.schemas import (
    ClaimCreatedEvent,
    EpcrChartFinalizedEvent,
    TransportRequestCreatedEvent,
)
from datetime import datetime

# Create an event
event = ClaimCreatedEvent(
    claim_id="claim-123",
    tenant_id="tenant-123",
    patient_id="patient-123",
    created_at=datetime.now(),
)

# Serialize to dict
event_dict = event.model_dump()

# Deserialize from dict
event_restored = ClaimCreatedEvent(**event_dict)
```

### Using Enums

```python
from adaptix_contracts.schemas import (
    ClaimStatus,
    WorkflowStatus,
    AuditSeverity,
)

# Access enum values
status = ClaimStatus.SUBMITTED
print(status.value)  # "submitted"

# Validate enum values
try:
    status = ClaimStatus("invalid")
except ValueError:
    print("Invalid status value")
```

## Canonical auth surfaces

There is exactly ONE canonical surface per auth layer. Anything else in this
package that looks auth-shaped is deprecated — do not adopt it.

| Layer | Canonical surface | Notes |
| --- | --- | --- |
| Service-edge identity (every inbound request) | `adaptix_contracts.auth_contracts.get_auth_context` → `AuthContext` | Gateway header contract (`X-User-Id`/`X-Tenant-Id`/…) + HMAC-signed context verification (`X-Adaptix-Auth-Context`/`-Signature`). Production default is fail-closed for unsigned requests (`ADAPTIX_GATEWAY_HMAC_ENFORCE`). |
| Signed-context crypto | `adaptix_contracts.gateway_signature` | Byte-compatible with the gateway producer in Adaptix-Core-Service. Do not reimplement. |
| Module entitlement (402 gate) | `adaptix_contracts.auth.module_entitlement_gate.require_module_entitlement` / `require_any_module_entitlement` | Verifies the gateway-signed context first; production fails closed when a present signature cannot be verified. |
| Rich JWT-payload model (service auth dependencies) | `adaptix_contracts.auth.context.AdaptixAuthContext` (+ `AdaptixRole`, `AdaptixRoleSet`, `AdaptixTenantContext`) | Built FROM an already-verified token payload via `from_token_payload`. It performs no verification itself. |

Deprecated (import paths preserved until 2.0.0, emit `DeprecationWarning`):

- `adaptix_contracts.security.auth_context`
  (`TenantAuthContext`, `RolePermissionDecision`) — third parallel context
  model, zero consumers.
- `adaptix_contracts.auth.rbac_dependencies` — never adopt: its
  `Depends()`-on-a-pydantic-model pattern sources identity from request data,
  its `require_module_entitlement` conflicts with the real gate, and
  `rbac_decorator` enforces nothing.

## Contract Principles

This package adheres to strict contract-only boundaries:

### ✅ What This Package Contains

- **Pydantic models** for events, requests, responses
- **Enums** for canonical statuses and types
- **Type annotations** for all fields
- **Field validation** at the schema level
- **Shared contract definitions** used across domains

### ❌ What This Package Does NOT Contain

- **Business logic** - No service implementation
- **Database models** - No ORM models or persistence
- **API routes** - No HTTP handlers
- **Service orchestration** - No workflow engines
- **Infrastructure code** - No Terraform, Docker, etc.

## Validation

Run the validation script to ensure all contracts are properly defined:

```bash
python validate_contracts.py
```

For release automation and machine-readable proof, emit the JSON report:

```bash
python validate_contracts.py --json
```

This validates:

- All exported schemas are importable
- All models are Pydantic v2 compatible
- All enums are properly defined
- All expected domains are covered, with any additional domains reported
- Sample models can be instantiated

The current validator report on this branch emits 813 public exports, 633
models, and 169 enums.

Run the automated regression suite for export integrity, schema serialization,
and representative validation failures:

```bash
pip install -e .[dev]
python -m pytest
```

Build and verify the publishable package artifacts before any release:

```bash
python -m build --sdist --wheel
python -m twine check dist/*
```

GitHub Actions in this repo (`CodeQL`, `Codacy Coverage`) are analysis-only.
Authoritative release and publishability validation is owned by CodeBuild
buildspecs, not GitHub Actions.

Audit a polyrepo workspace for shadow `adaptix_contracts` packages that can
silently override the canonical repo during production builds:

```bash
python scripts/audit_workspace_contracts.py --workspace-root C:\Users\fusio\Desktop\workspace
```

## Versioning

This package follows semantic versioning:

- **Major version** - Breaking changes to contracts
- **Minor version** - New contracts or backward-compatible additions
- **Patch version** - Bug fixes, documentation updates

Release governance artifacts:

- [`CHANGELOG.md`](CHANGELOG.md) — authoritative release history
- [`DEPRECATION_POLICY.md`](DEPRECATION_POLICY.md) — backward-compatibility and
  retirement rules
- [`MARKET_READY_LEDGER.md`](MARKET_READY_LEDGER.md) — current proof ledger and
  market-readiness verdict

Contract changes are not considered releasable until the changelog is updated,
deprecation impact is documented for public surface changes, and the validation
script, pytest suite, build verification, and shadow-package audit all pass.

## Contributing

When adding new contracts:

1. Add the contract file to `adaptix_contracts/schemas/`
2. Export symbols in `adaptix_contracts/schemas/__init__.py`
3. Add to `__all__` list in alphabetical/domain order
4. Run `python validate_contracts.py` to verify
5. Ensure Pydantic v2 compatibility
6. Follow existing naming conventions

## License

Internal Adaptix package - not for public distribution.

## Support

For questions or issues, contact the Adaptix platform team.
