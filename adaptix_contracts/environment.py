"""Canonical ``ENVIRONMENT`` detection for the Adaptix platform.

Every service that needs to know "am I running in production" MUST use
:func:`is_production` (or the pure :func:`is_production_environment` when the
value is already in hand, e.g. in a test). Before this module existed, the
identical ``{"production", "prod"}``-membership predicate was independently
implemented four times inside this package alone --
``gateway_signature.is_production``, ``auth_contracts._is_production``,
``auth.module_entitlement_gate._is_production`` (whose own comment already
noted "Matches auth_contracts._is_production"), and
``security.temporal_payload_codec.is_production_environment`` -- with no
shared source. A future correction to the predicate (a new alias, a stricter
comparison) would have needed four separate, easy-to-miss follow-up patches.
All four now delegate here; their public names and import paths are
preserved for backward compatibility.

Fail-open trap this module exists to close: every one of those four
call sites reads ``ENVIRONMENT`` with ``.get(..., "")`` and treats an EMPTY
value as "not production," which is the correct behavior for a deliberately
non-production deployment (local dev, CI, a test run) but is exactly wrong
for a production task definition that simply forgot to set the variable --
the silent result is every production-only guard these functions gate
(cross-service replay-protection audience enforcement in
``gateway_signature._expected_audience``, the D-053 symmetric-mode warning,
production founder-privilege floors in ``auth_contracts``) quietly disables
itself instead of failing loudly. :func:`assert_environment_configured` closes
that gap WITHOUT changing :func:`is_production`'s runtime semantics (an
unset value still means "not production" for every existing call site, so
legitimate non-production deployments that never set the variable are
unaffected): it is an opt-in check a service calls once at startup, and it
raises immediately if ``ENVIRONMENT`` was never set at all. It intentionally
does not validate the value against an enumerated allow-list of "known good"
non-production names (staging/dev/test/qa/sandbox/... vary by service and
are not this package's policy to define) -- it only catches "nobody set it,"
which is the specific forgotten-task-definition-variable failure class this
module's docstring and D-034 describe.
"""

from __future__ import annotations

import os

ENVIRONMENT_ENV = "ENVIRONMENT"

#: Values of ENVIRONMENT that mean "real customer data lives here." Matched
#: case-insensitively. Anything in this set forbids unencrypted payloads,
#: requires the gateway audience pin, and gates other production-only floors.
PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})


def is_production_environment(value: str | None) -> bool:
    """Return True when ``value`` names a production environment.

    Pure and case/whitespace tolerant so the same rule applies to a value
    read live from the environment and to a value supplied directly (e.g.
    in a test, or by a caller that already resolved its own environment
    string through some other configuration path).
    """
    return (value or "").strip().lower() in PRODUCTION_ENVIRONMENTS


def is_production() -> bool:
    """Return whether this process is running in the production environment.

    Reads ``ENVIRONMENT`` from the live process environment. An unset or
    empty value returns ``False`` -- the correct behavior for a deliberately
    non-production process, but see :func:`assert_environment_configured`
    for why a production deployment must never rely on that default.
    """
    return is_production_environment(os.environ.get(ENVIRONMENT_ENV))


def assert_environment_configured() -> None:
    """Raise immediately if ``ENVIRONMENT`` was never set at all.

    Call once at service startup (before serving any request), not on a
    request-handling hot path and not automatically at import time -- many
    legitimate processes (local development, this package's own test suite,
    one-off scripts) never set ``ENVIRONMENT`` and must not be forced to.
    This function exists for services to opt into at their own bootstrap
    entrypoint specifically so a REAL deployment's forgotten task-definition
    variable is caught loudly at boot, instead of silently running with
    every ``is_production()``-gated protection disabled indefinitely.

    Deliberately does not validate the value against an enumerated set of
    "known good" non-production names -- only that some value was
    configured at all. Raises ``RuntimeError`` because callers of this
    function are service bootstrap code, not this package's own
    configuration-error taxonomy (``GatewayVerifierConfigurationError`` and
    friends are specific to the gateway-signature verifier and would be a
    misleading exception type for a general-purpose startup check).

    Raises:
        RuntimeError: ``ENVIRONMENT`` is unset or blank.
    """
    if not os.environ.get(ENVIRONMENT_ENV, "").strip():
        raise RuntimeError(
            f"{ENVIRONMENT_ENV} is not set. Every Adaptix service must set "
            f"{ENVIRONMENT_ENV} explicitly (e.g. 'production', 'staging', "
            "'development') in its task definition or local environment -- "
            "a forgotten production task-definition variable must not "
            "silently disable every is_production()-gated protection "
            "(cross-service gateway-audience replay protection, encrypted-"
            "payload enforcement, production founder-privilege floors, and "
            "any other production-only guard in this package or its "
            "consumers)."
        )


__all__ = [
    "ENVIRONMENT_ENV",
    "PRODUCTION_ENVIRONMENTS",
    "assert_environment_configured",
    "is_production",
    "is_production_environment",
]
