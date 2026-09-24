"""Tenant classification vocabulary (FND-001, Adaptix Certification Fabric).

``tenant_type`` is owned by Adaptix-Core-Service; its CERT-CORE change adds
the ``core_tenants.tenant_type`` column and the ``tenant_type`` access-token
claim with exactly these two values. No contract carried the vocabulary
before this one, so every other service would have had to restate the two
strings.
"""

from __future__ import annotations

import adaptix_contracts
from adaptix_contracts import schemas
from adaptix_contracts.schemas.tenant_contracts import TenantType


def test_tenant_type_is_exactly_customer_and_production_certification() -> None:
    assert [(member.name, member.value) for member in TenantType] == [
        ("CUSTOMER", "customer"),
        ("PRODUCTION_CERTIFICATION", "production_certification"),
    ]


def test_tenant_type_parses_the_wire_values() -> None:
    assert TenantType("customer") is TenantType.CUSTOMER
    assert TenantType("production_certification") is TenantType.PRODUCTION_CERTIFICATION
    assert TenantType.PRODUCTION_CERTIFICATION == "production_certification"


def test_tenant_type_is_on_the_published_schema_surface() -> None:
    assert "TenantType" in schemas.__all__
    assert schemas.TenantType is TenantType
    assert adaptix_contracts.TenantType is TenantType
