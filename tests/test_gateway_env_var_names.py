"""Single-source-of-truth guards for the gateway environment-variable NAMES.

``ADAPTIX_GATEWAY_SHARED_SECRET`` is the name of an environment variable, never
a secret value — the secret itself is read from the process environment at call
time. The name was previously declared as a literal in two modules
(``gateway_signature`` and ``auth_contracts``); two independent literals can
drift apart and silently point signature verification at a different variable
than the one operations configures. It now has exactly one definition.

These tests prove the consolidation did not change any observable value or
behavior, and that the duplication cannot come back.
"""

from __future__ import annotations

from adaptix_contracts import auth_contracts, gateway_signature


def test_shared_secret_env_name_is_unchanged() -> None:
    assert (
        gateway_signature.GATEWAY_SHARED_SECRET_ENV == "ADAPTIX_GATEWAY_SHARED_SECRET"
    )


def test_expected_audience_env_name_is_unchanged() -> None:
    assert (
        gateway_signature.GATEWAY_EXPECTED_AUDIENCE_ENV
        == "ADAPTIX_GATEWAY_EXPECTED_AUDIENCE"
    )


def test_auth_contracts_reexports_the_one_canonical_object() -> None:
    """Not merely equal — the same object, so the two cannot diverge."""
    assert (
        auth_contracts.GATEWAY_SHARED_SECRET_ENV
        is gateway_signature.GATEWAY_SHARED_SECRET_ENV
    )


def test_shared_secret_env_name_stays_a_public_export() -> None:
    assert "GATEWAY_SHARED_SECRET_ENV" in auth_contracts.__all__
    assert "GATEWAY_SHARED_SECRET_ENV" in gateway_signature.__all__


def test_secret_is_read_from_the_environment_not_from_source(monkeypatch) -> None:
    """End-to-end: the configured env var still drives the returned secret."""
    monkeypatch.setenv(gateway_signature.GATEWAY_SHARED_SECRET_ENV, "  s3cr3t-value  ")
    assert gateway_signature.gateway_shared_secret() == "s3cr3t-value"

    monkeypatch.setenv(gateway_signature.GATEWAY_SHARED_SECRET_ENV, "   ")
    assert gateway_signature.gateway_shared_secret() is None

    monkeypatch.delenv(gateway_signature.GATEWAY_SHARED_SECRET_ENV, raising=False)
    assert gateway_signature.gateway_shared_secret() is None
