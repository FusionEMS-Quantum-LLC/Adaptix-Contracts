"""Shared module entitlement gate for module-services.

Module-services (CAD, ePCR, Fire, Air, Narcotics, Billing) apply this
FastAPI dependency at the router-include level to enforce that the
calling tenant has paid for / been provisioned the corresponding
module slug. The gate is a hard server-side 402 — frontend hiding is
not enough.

The gate reads the verified JWT (the upstream auth dep already
validated signature and expiry) plus a ``request.state`` fallback that
Core's auth dependency populates for Cognito-issued tokens (which
cannot carry the multi-module entitlement list inside the JWT itself
due to Cognito custom-attribute size limits).

Failure response (402 Payment Required)::

    {
        "code": "module_not_entitled",
        "message": "Your agency's current subscription does not include the 'epcr' module.",
        "required_module": "epcr",
        "current_entitlements": ["cad", "scheduler"],
        "upgrade_url": "/pricing",
        "contact_url": "/schedule",
    }

Founder accounts (``is_founder=True`` claim or ``founder`` role) bypass
the gate so founders can operate any agency for support / migration /
verification without being blocked by per-tenant subscription state.

This is a copy of the in-repo gate that lives in
``Adaptix-Core-Service/.../module_entitlement_gate.py`` — the contract
is shared across every module-service via the ``adaptix-contracts``
package.
"""

from __future__ import annotations

import json as _json
import logging
import os
from typing import Annotated, Optional
from collections.abc import Callable

import jwt as pyjwt
from fastapi import Header, HTTPException, Request, status

logger = logging.getLogger(__name__)

AUDIT_ACTION = "billing.module_not_entitled"


def _normalize_slug(value: str) -> str:
    return (value or "").strip().lower()


def _claims_carry_founder(claims: dict) -> bool:
    raw = claims.get("is_founder")
    if isinstance(raw, bool) and raw:
        return True
    if isinstance(raw, str) and raw.strip().lower() in {"1", "true", "yes", "founder"}:
        return True
    roles_claim = (
        claims.get("roles")
        or claims.get("custom:adaptix_roles")
        or claims.get("cognito:groups")
    )
    role_values: list[str] = []
    if isinstance(roles_claim, list):
        role_values = [str(r).strip().lower() for r in roles_claim if str(r).strip()]
    elif isinstance(roles_claim, str):
        s = roles_claim.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = _json.loads(s)
                if isinstance(parsed, list):
                    role_values = [
                        str(r).strip().lower() for r in parsed if str(r).strip()
                    ]
            except _json.JSONDecodeError:
                role_values = [p.strip().lower() for p in s.split(",") if p.strip()]
        else:
            role_values = [p.strip().lower() for p in s.split(",") if p.strip()]
    return "founder" in set(role_values)


def _claims_module_entitlements(claims: dict) -> list[str]:
    raw = claims.get("module_entitlements") or claims.get(
        "custom:adaptix_module_entitlements"
    )
    if not raw:
        return []
    if isinstance(raw, list):
        return [_normalize_slug(str(m)) for m in raw if str(m).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = _json.loads(s)
                if isinstance(parsed, list):
                    return [_normalize_slug(str(m)) for m in parsed if str(m).strip()]
            except _json.JSONDecodeError:
                pass
        return [_normalize_slug(p) for p in s.split(",") if p.strip()]
    return []


def _decode_claims_for_gate(token: str) -> dict:
    try:
        return pyjwt.decode(token, options={"verify_signature": False})
    except Exception:  # pragma: no cover
        return {}


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def require_module_entitlement(module_slug: str) -> Callable:
    """Return a FastAPI dependency that gates a route on ``module_slug``.

    Usage::

        from adaptix_contracts.auth.module_entitlement_gate import (
            require_module_entitlement,
        )

        app.include_router(
            cad_router,
            prefix="/api/v1/cad",
            dependencies=[Depends(require_module_entitlement("cad"))],
        )

    Returns:
        A callable suitable for ``Depends()``.
    """
    required = _normalize_slug(module_slug)
    if not required:
        raise ValueError(
            "require_module_entitlement(): module_slug must be a non-empty string."
        )

    async def _gate(
        request: Request,
        authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
    ) -> None:
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "missing_bearer_token",
                    "message": "Authorization bearer token is required.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        claims = _decode_claims_for_gate(token)
        if _claims_carry_founder(claims):
            return

        entitlements = _claims_module_entitlements(claims)
        # Fallback for Cognito tokens: the upstream auth dep populates
        # ``request.state.module_entitlements`` from the tenant row.
        if not entitlements:
            state_entitlements = getattr(request.state, "module_entitlements", None)
            if isinstance(state_entitlements, list):
                entitlements = [
                    _normalize_slug(str(m))
                    for m in state_entitlements
                    if str(m).strip()
                ]

        if required in set(entitlements):
            return

        logger.info(
            "module_entitlement_gate: denied module=%s current=%s tenant=%s",
            required,
            entitlements,
            claims.get("tid")
            or claims.get("tenant_id")
            or claims.get("custom:adaptix_tenant_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "module_not_entitled",
                "message": (
                    f"Your agency's current subscription does not include the "
                    f"'{required}' module. Upgrade or contact us to enable it."
                ),
                "required_module": required,
                "current_entitlements": entitlements,
                "upgrade_url": os.environ.get("ADAPTIX_UPGRADE_URL", "/pricing"),
                "contact_url": os.environ.get("ADAPTIX_CONTACT_URL", "/schedule"),
            },
        )

    _gate.__name__ = f"require_module_entitlement_{required}"
    return _gate


def require_any_module_entitlement(*module_slugs: str) -> Callable:
    """Return a FastAPI dependency that gates a route on ANY of the slugs.

    Use when a single route legitimately serves multiple modules — e.g.
    the CAD write-back surface that is consumed by BOTH Field-App (MDT)
    and CrewLink. The route should be reachable when the tenant has any
    one of the named entitlements.

    Usage::

        app.include_router(
            writeback_router,
            dependencies=[
                Depends(require_any_module_entitlement("mdt", "crewlink"))
            ],
        )
    """
    required = [_normalize_slug(s) for s in module_slugs if s and s.strip()]
    if not required:
        raise ValueError(
            "require_any_module_entitlement(): at least one slug required."
        )
    required_set = set(required)
    label = "|".join(required)

    async def _gate(
        request: Request,
        authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
    ) -> None:
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "missing_bearer_token",
                    "message": "Authorization bearer token is required.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        claims = _decode_claims_for_gate(token)
        if _claims_carry_founder(claims):
            return
        entitlements = _claims_module_entitlements(claims)
        if not entitlements:
            state_entitlements = getattr(request.state, "module_entitlements", None)
            if isinstance(state_entitlements, list):
                entitlements = [
                    _normalize_slug(str(m))
                    for m in state_entitlements
                    if str(m).strip()
                ]
        if required_set & set(entitlements):
            return
        logger.info(
            "module_entitlement_gate: denied any-of=%s current=%s tenant=%s",
            label,
            entitlements,
            claims.get("tid")
            or claims.get("tenant_id")
            or claims.get("custom:adaptix_tenant_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "module_not_entitled",
                "message": (
                    f"Your agency's current subscription does not include any "
                    f"of the required modules ({label}). Upgrade or contact us "
                    f"to enable them."
                ),
                "required_modules": required,
                "current_entitlements": entitlements,
                "upgrade_url": os.environ.get("ADAPTIX_UPGRADE_URL", "/pricing"),
                "contact_url": os.environ.get("ADAPTIX_CONTACT_URL", "/schedule"),
            },
        )

    _gate.__name__ = f"require_any_module_entitlement_{'_'.join(required)}"
    return _gate


__all__ = [
    "require_module_entitlement",
    "require_any_module_entitlement",
    "AUDIT_ACTION",
]
