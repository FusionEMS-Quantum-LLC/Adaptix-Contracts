"""DEPRECATED — do not adopt. Scheduled for removal in adaptix-contracts 2.0.0.

Audit 2026-07-03: no service in the Adaptix polyrepo imports
``TenantAuthContext`` or ``RolePermissionDecision``. This module is a third,
parallel auth-context model that duplicates (and drifts from) the two live
surfaces documented in README "Canonical auth surfaces":

* ``adaptix_contracts.auth_contracts.AuthContext`` — gateway header contract
  resolved by ``get_auth_context`` (the service-edge identity).
* ``adaptix_contracts.auth.context.AdaptixAuthContext`` — the rich JWT-payload
  model used by service auth dependencies.

Per DEPRECATION_POLICY.md the import path is preserved (with a
DeprecationWarning) until the next major version.
"""

import warnings
from typing import Optional

from pydantic import BaseModel

warnings.warn(
    "adaptix_contracts.security.auth_context is deprecated and will be removed "
    "in adaptix-contracts 2.0.0. Use auth_contracts.AuthContext (gateway edge) "
    "or auth.context.AdaptixAuthContext (JWT payload model) instead.",
    DeprecationWarning,
    stacklevel=2,
)


class TenantAuthContext(BaseModel):
    tenant_id: str
    user_id: str
    roles: list[str]
    permissions: list[str]
    session_id: str
    issued_at: str
    expires_at: str
    source_service: Optional[str] = None


class RolePermissionDecision(BaseModel):
    allowed: bool
    role: str
    permission: str
    reason: Optional[str] = None
    tenant_id: str
    user_id: str
