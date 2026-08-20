"""Cortex Live demo side-effect classification contracts.

Shared vocabulary for how a Cortex Live public demo session may interact with
the world. Domain services remain responsible for CLASSIFYING their own
operations — this module only defines the canonical classes and the default
platform policy so every service enforces the same boundary instead of each
inventing its own.

The demo status itself comes exclusively from a VERIFIED signed gateway
context (``AuthContext.is_demo`` in ``adaptix_contracts.auth_contracts``);
no raw header can grant it.

Policy (platform default):

* ``auth.is_demo`` is ``False`` — this gate imposes nothing; the service's
  normal production policy governs.
* ``auth.is_demo`` is ``True``:
    - ``READ``                -> allow
    - ``LOCAL_DEMO_WRITE``    -> allow (real product logic on synthetic
      records inside the leased demo tenant)
    - ``SANDBOX_EXTERNAL``    -> allow ONLY when the service has an official
      provider sandbox/test path explicitly configured for the operation
    - ``PRODUCTION_EXTERNAL`` -> deny, always (real payer submissions,
      payments, patient SMS/calls, faxes, physical mail, external e-sign
      recipients, production webhooks, PHI export, external email)
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "DemoSideEffectClass",
    "demo_side_effect_allowed",
]


class DemoSideEffectClass(str, Enum):
    """Canonical classification of an operation's external consequence."""

    READ = "read"
    LOCAL_DEMO_WRITE = "local_demo_write"
    SANDBOX_EXTERNAL = "sandbox_external"
    PRODUCTION_EXTERNAL = "production_external"


def demo_side_effect_allowed(
    *,
    is_demo: bool,
    side_effect: DemoSideEffectClass,
    sandbox_configured: bool = False,
) -> bool:
    """Apply the platform-default demo side-effect policy.

    Args:
        is_demo: ``AuthContext.is_demo`` — demo status from the VERIFIED
            signed gateway context only.
        side_effect: The service's own classification of the operation.
        sandbox_configured: ``True`` only when the service has an official
            provider sandbox/test path explicitly configured for this exact
            operation. Defaults to ``False`` so an unclassified integration
            fails closed for demo principals.

    Returns:
        ``True`` when this gate permits the operation. For non-demo requests
        this is always ``True`` — the gate imposes nothing and the service's
        normal production policy governs. For demo requests it implements the
        default policy above; a ``False`` means the service must refuse the
        operation (and should surface a structured denial, not fake success).
    """
    if not is_demo:
        return True
    if side_effect is DemoSideEffectClass.READ:
        return True
    if side_effect is DemoSideEffectClass.LOCAL_DEMO_WRITE:
        return True
    if side_effect is DemoSideEffectClass.SANDBOX_EXTERNAL:
        return sandbox_configured
    return False
