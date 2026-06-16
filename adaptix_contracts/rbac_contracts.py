"""
Adaptix RBAC Contracts
======================
Role-based access control definitions for Inventory, Medications, and Narcotics modules.

Canonical role hierarchy and permission matrix for production use.
Every service must use these definitions to enforce consistent RBAC.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InventoryRole(str, Enum):
    """Roles specific to Inventory module."""

    FOUNDER = "founder"
    AGENCY_ADMIN = "agency_admin"
    OPERATIONS_CHIEF = "operations_chief"
    SUPPLY_OFFICER = "supply_officer"
    FLEET_EQUIPMENT_MANAGER = "fleet_equipment_manager"
    SUPERVISOR = "supervisor"
    PARAMEDIC = "paramedic"
    EMT = "emt"
    AUDITOR = "auditor"
    INSPECTOR = "inspector"


class MedicationsRole(str, Enum):
    """Roles specific to Medications module."""

    FOUNDER = "founder"
    AGENCY_ADMIN = "agency_admin"
    OPERATIONS_CHIEF = "operations_chief"
    SUPPLY_OFFICER = "supply_officer"
    PHARMACY_MEDICATION_MANAGER = "pharmacy_medication_manager"
    MEDICAL_DIRECTOR = "medical_director"
    SUPERVISOR = "supervisor"
    PARAMEDIC = "paramedic"
    EMT = "emt"
    BILLING_OPERATOR = "billing_operator"
    AUDITOR = "auditor"
    INSPECTOR = "inspector"


class NarcoticsRole(str, Enum):
    """Roles specific to Narcotics module."""

    FOUNDER = "founder"
    AGENCY_ADMIN = "agency_admin"
    OPERATIONS_CHIEF = "operations_chief"
    NARCOTICS_OFFICER = "narcotics_officer"
    MEDICAL_DIRECTOR = "medical_director"
    SUPERVISOR = "supervisor"
    PARAMEDIC = "paramedic"
    BILLING_OPERATOR = "billing_operator"
    AUDITOR = "auditor"
    INSPECTOR = "inspector"


# ============================================================================
# INVENTORY PERMISSIONS
# ============================================================================

INVENTORY_PERMISSIONS = {
    # Full read/write access
    "inventory:full_access": {
        "roles": [InventoryRole.FOUNDER, InventoryRole.AGENCY_ADMIN]
    },
    # Supply Officer — inventory full access
    "inventory:create_items": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
        ]
    },
    "inventory:read_items": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.OPERATIONS_CHIEF,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
            InventoryRole.SUPERVISOR,
            InventoryRole.PARAMEDIC,
            InventoryRole.EMT,
            InventoryRole.AUDITOR,
            InventoryRole.INSPECTOR,
        ]
    },
    "inventory:update_items": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
        ]
    },
    "inventory:delete_items": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
        ]
    },
    # Restock (inventory and narcotics)
    "inventory:record_restock": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
        ]
    },
    "inventory:read_restocks": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.OPERATIONS_CHIEF,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
            InventoryRole.SUPERVISOR,
            InventoryRole.AUDITOR,
            InventoryRole.INSPECTOR,
        ]
    },
    # Stock management
    "inventory:receive_stock": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
        ]
    },
    "inventory:use_stock": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.PARAMEDIC,
            InventoryRole.EMT,
        ]
    },
    "inventory:transfer_stock": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
        ]
    },
    "inventory:read_stock": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.OPERATIONS_CHIEF,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.FLEET_EQUIPMENT_MANAGER,
            InventoryRole.SUPERVISOR,
            InventoryRole.PARAMEDIC,
            InventoryRole.EMT,
            InventoryRole.AUDITOR,
            InventoryRole.INSPECTOR,
        ]
    },
    # Audit
    "inventory:submit_audit": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.SUPERVISOR,
        ]
    },
    "inventory:read_audit": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.OPERATIONS_CHIEF,
            InventoryRole.SUPPLY_OFFICER,
            InventoryRole.SUPERVISOR,
            InventoryRole.AUDITOR,
            InventoryRole.INSPECTOR,
        ]
    },
    # Approval workflows (Supervisor only)
    "inventory:approve_discrepancy": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
            InventoryRole.SUPERVISOR,
        ]
    },
    # Cost reports (Billing only)
    "inventory:read_cost_reports": {
        "roles": [
            InventoryRole.FOUNDER,
            InventoryRole.AGENCY_ADMIN,
        ]
    },
}

# ============================================================================
# MEDICATIONS PERMISSIONS
# ============================================================================

MEDICATIONS_PERMISSIONS = {
    # Full read/write access
    "medications:full_access": {
        "roles": [MedicationsRole.FOUNDER, MedicationsRole.AGENCY_ADMIN]
    },
    # Pharmacy/Medication Manager — medications full access
    "medications:create": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.PHARMACY_MEDICATION_MANAGER,
        ]
    },
    "medications:read": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.OPERATIONS_CHIEF,
            MedicationsRole.PHARMACY_MEDICATION_MANAGER,
            MedicationsRole.MEDICAL_DIRECTOR,
            MedicationsRole.SUPERVISOR,
            MedicationsRole.PARAMEDIC,
            MedicationsRole.EMT,
            MedicationsRole.AUDITOR,
            MedicationsRole.INSPECTOR,
        ]
    },
    "medications:update": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.PHARMACY_MEDICATION_MANAGER,
        ]
    },
    "medications:delete": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
        ]
    },
    # Administration
    "medications:administer": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.PARAMEDIC,
        ]
    },
    "medications:read_administrations": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.MEDICAL_DIRECTOR,
            MedicationsRole.SUPERVISOR,
            MedicationsRole.AUDITOR,
            MedicationsRole.INSPECTOR,
        ]
    },
    # Cost reports
    "medications:read_cost_reports": {
        "roles": [
            MedicationsRole.FOUNDER,
            MedicationsRole.AGENCY_ADMIN,
            MedicationsRole.BILLING_OPERATOR,
        ]
    },
}

# ============================================================================
# NARCOTICS PERMISSIONS
# ============================================================================

NARCOTICS_PERMISSIONS = {
    # Full read/write access
    "narcotics:full_access": {
        "roles": [NarcoticsRole.FOUNDER, NarcoticsRole.AGENCY_ADMIN]
    },
    # Narcotics Officer — narcotics full access
    "narcotics:create": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.NARCOTICS_OFFICER,
        ]
    },
    "narcotics:read": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.OPERATIONS_CHIEF,
            NarcoticsRole.NARCOTICS_OFFICER,
            NarcoticsRole.MEDICAL_DIRECTOR,
            NarcoticsRole.SUPERVISOR,
            NarcoticsRole.PARAMEDIC,
            NarcoticsRole.AUDITOR,
            NarcoticsRole.INSPECTOR,
        ]
    },
    "narcotics:update": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.NARCOTICS_OFFICER,
        ]
    },
    "narcotics:delete": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
        ]
    },
    # DEA compliance and tracking
    "narcotics:track_usage": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.PARAMEDIC,
        ]
    },
    "narcotics:read_usage": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.OPERATIONS_CHIEF,
            NarcoticsRole.NARCOTICS_OFFICER,
            NarcoticsRole.MEDICAL_DIRECTOR,
            NarcoticsRole.SUPERVISOR,
            NarcoticsRole.AUDITOR,
            NarcoticsRole.INSPECTOR,
        ]
    },
    # Discrepancy management (Supervisor approval)
    "narcotics:submit_discrepancy": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.SUPERVISOR,
        ]
    },
    "narcotics:approve_discrepancy": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.MEDICAL_DIRECTOR,
        ]
    },
    # DEA packet access
    "narcotics:read_dea_packet": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.NARCOTICS_OFFICER,
            NarcoticsRole.INSPECTOR,
        ]
    },
    # Cost attribution
    "narcotics:read_cost_attribution": {
        "roles": [
            NarcoticsRole.FOUNDER,
            NarcoticsRole.AGENCY_ADMIN,
            NarcoticsRole.BILLING_OPERATOR,
        ]
    },
}

# ============================================================================
# MODULE ENTITLEMENTS
# ============================================================================

MODULE_ENTITLEMENTS = {
    "inventory": "Inventory Module - Supply chain management",
    "medications": "Medications Module - Medication administration",
    "narcotics": "Narcotics Module - Controlled substance tracking",
}


class RBACPermissionCheck(BaseModel):
    """Result of RBAC permission check."""

    has_permission: bool
    permission: str
    reason: str | None = None
    roles_with_permission: list[str] = Field(default_factory=list)


class ModuleEntitlementCheck(BaseModel):
    """Result of module entitlement check."""

    has_entitlement: bool
    module: str
    reason: str | None = None


class RBACContext(BaseModel):
    """Complete RBAC context for a request."""

    user_id: str
    tenant_id: str
    roles: list[str]
    permissions: set[str] = Field(default_factory=set)
    modules_enabled: list[str] = Field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        """Check if user has any of the specified permissions."""
        return any(p in self.permissions for p in permissions)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_module(self, module: str) -> bool:
        """Check if tenant has purchased the module."""
        return module in self.modules_enabled

    def is_founder(self) -> bool:
        """Check if user is founder."""
        return "founder" in self.roles

    def is_admin(self) -> bool:
        """Check if user is agency admin."""
        return "agency_admin" in self.roles or self.is_founder()


def compute_inventory_permissions(roles: list[str]) -> set[str]:
    """Compute all inventory permissions for a user based on roles."""
    permissions = set()
    for permission, config in INVENTORY_PERMISSIONS.items():
        permission_roles = [r.value for r in config["roles"]]
        if any(role in permission_roles for role in roles):
            permissions.add(permission)
    return permissions


def compute_medications_permissions(roles: list[str]) -> set[str]:
    """Compute all medications permissions for a user based on roles."""
    permissions = set()
    for permission, config in MEDICATIONS_PERMISSIONS.items():
        permission_roles = [r.value for r in config["roles"]]
        if any(role in permission_roles for role in roles):
            permissions.add(permission)
    return permissions


def compute_narcotics_permissions(roles: list[str]) -> set[str]:
    """Compute all narcotics permissions for a user based on roles."""
    permissions = set()
    for permission, config in NARCOTICS_PERMISSIONS.items():
        permission_roles = [r.value for r in config["roles"]]
        if any(role in permission_roles for role in roles):
            permissions.add(permission)
    return permissions
