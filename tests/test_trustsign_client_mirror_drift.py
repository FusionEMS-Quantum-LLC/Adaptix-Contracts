"""Mirror-drift detection for the canonical TrustSign HTTP client.

There are intentionally TWO copies of the TrustSign HTTP client in the
Adaptix codebase:

1. ``adaptix_contracts/trustsign_client.py`` (this package) — the canonical
   import path for every consumer service (Core, Transport, Integrations,
   Founder).
2. ``Adaptix-Billing-Service:backend/billing_app/trustsign/http_client.py``
   — the Billing-internal copy so Billing doesn't take a self-dependency
   on adaptix-contracts at runtime.

Per the founder directive 2026-05-25 the two MUST stay byte-equivalent so
the contract that Billing's engine exposes and the contract consumers
import never drift. This test asserts the shape of the public surface
(class names + method names + signatures) is identical between the two
copies.

We cannot directly import the Billing copy from this package — there is
no cross-repo Python dependency — so the drift check compares the public
attribute set of the local module against a frozen manifest. Any time
the canonical client gains or loses a public attribute, BOTH this
manifest and the Billing copy must be updated in lockstep.
"""

from __future__ import annotations

import inspect

import adaptix_contracts.trustsign_client as canonical

# ── Frozen public-surface manifest ────────────────────────────────────────
#
# This list IS the contract that consumer repositories rely on. Changing
# it requires a coordinated PR across:
#   - adaptix-contracts (this package)
#   - Adaptix-Billing-Service:backend/billing_app/trustsign/http_client.py
#   - Adaptix-Billing-Service:backend/billing_app/trustsign/__init__.py
#     (re-export list)
# Every consumer repo PR (Core/Transport/Integrations/Founder) then needs
# its adaptix-contracts pin bumped to the new minor version.

EXPECTED_PUBLIC_NAMES = {
    "ChartSignatureCompleteInput",
    "ChartSignatureCompleteResponse",
    "ChartSignatureConsent",
    "ChartSignatureStartInput",
    "ChartSignatureStartResponse",
    "CreateRequestInput",
    "CreateRequestResponse",
    "RequestStatusResponse",
    "SignerResponse",
    "SignerSpec",
    "TrustSignClient",
    "TrustSignClientConfig",
    "TrustSignClientError",
    "TrustSignConfigurationError",
    "TrustSignServerError",
    "TrustSignTransportError",
    "TrustSignUnauthorizedError",
    "TrustSignValidationError",
}


EXPECTED_CLIENT_METHODS = {
    "__init__",
    "__aenter__",
    "__aexit__",
    "aclose",
    "complete_chart_signature",
    "create_request",
    "get_request_status",
    "download_archive",
    "void_request",
    "start_chart_signature",
    "verify_webhook_signature",
}


def test_public_attribute_set_matches_manifest() -> None:
    """If this fails, sync the Billing-Service mirror + bump the contracts version."""
    actual_local = {
        name
        for name in dir(canonical)
        if not name.startswith("_")
        and getattr(getattr(canonical, name, None), "__module__", "")
        == canonical.__name__
    }
    missing = EXPECTED_PUBLIC_NAMES - actual_local
    extra = actual_local - EXPECTED_PUBLIC_NAMES
    assert not missing, (
        f"Manifest expects {missing} but they are missing from the module."
    )
    assert not extra, (
        f"Module exposes {extra} which is NOT in the manifest. Either add to "
        f"manifest (and mirror Billing) or remove from module."
    )


def test_client_public_method_set_matches_manifest() -> None:
    """Check PUBLIC methods only; private helpers are implementation detail."""
    actual = {
        name
        for name, _ in inspect.getmembers(
            canonical.TrustSignClient, predicate=inspect.isfunction
        )
        if not name.startswith("_") or name in {"__init__", "__aenter__", "__aexit__"}
    }
    missing = EXPECTED_CLIENT_METHODS - actual
    assert not missing, f"TrustSignClient missing methods: {missing}"
    # extras are allowed — private helpers — as long as nothing public goes missing.


def test_create_request_signature_matches_manifest() -> None:
    sig = inspect.signature(canonical.TrustSignClient.create_request)
    assert list(sig.parameters.keys()) == ["self", "payload"]
    payload_param = sig.parameters["payload"]
    # __future__ annotations defers evaluation — compare by string form.
    assert (
        payload_param.annotation == canonical.CreateRequestInput
        or str(payload_param.annotation) == "CreateRequestInput"
    )


def test_verify_webhook_signature_is_staticmethod() -> None:
    # The signature verifier must remain callable without a client instance
    # so receivers can validate webhooks before any DI setup.
    bound = inspect.getattr_static(
        canonical.TrustSignClient, "verify_webhook_signature"
    )
    assert isinstance(bound, staticmethod), (
        "verify_webhook_signature MUST stay a staticmethod so webhook "
        "handlers can call it without constructing a client."
    )
