"""Contracts #397: the verifier names say whether the route is bound.

``verify_gateway_signature`` checks the signed ``method``/``path`` claims only
when its caller passes the inbound request's method and path, and its name
does not say so (AssetOps #163). It is deprecated with no runtime warning;
``verify_gateway_signature_without_request_binding`` is the explicit name for
callers that no route can reach. These tests pin that the new name behaves as
the documented no-request arm, and that the deprecated name is unchanged
during the overlap.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path
from uuid import uuid4

import pytest

from adaptix_contracts import gateway_identity, gateway_signature
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    GatewayVerifierConfigurationError,
    verify_gateway_signature,
    verify_gateway_signature_without_request_binding,
)

_SECRET = "unit-test-hmac-material-not-a-real-value"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sign(**overrides: object) -> tuple[str, str]:
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": "adaptix-gateway",
        "aud": "adaptix-core",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    payload.update(overrides)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        _SECRET.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


@pytest.fixture(autouse=True)
def _hmac_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raising=False)
    gateway_signature.reset_gateway_replay_cache_for_tests()


def test_accepts_a_valid_context() -> None:
    ctx, sig = _sign()
    payload = verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["user_id"] == "11111111-1111-1111-1111-111111111111"


def test_rejects_a_bad_signature() -> None:
    ctx, _ = _sign()
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex="0" * 64, shared_secret=_SECRET
        )


def test_still_records_replay() -> None:
    ctx, sig = _sign()
    verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_bound_context_is_accepted_when_flag_is_off() -> None:
    """Flag off: nothing to compare against, same as the documented arm."""
    ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
    payload = verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["path"] == "/api/v1/patients/123"


def test_bound_context_fails_closed_under_require_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service that requires the binding cannot verify a bound context here."""
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")
    ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
    with pytest.raises(GatewayVerifierConfigurationError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_has_no_request_method_or_path_parameters() -> None:
    """The name promises no binding; it must not accept request fields."""
    ctx, sig = _sign()
    with pytest.raises(TypeError):
        verify_gateway_signature_without_request_binding(  # type: ignore[call-arg]
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
        )


def test_deprecated_name_still_binds_when_given_the_request() -> None:
    ctx, sig = _sign(method="GET", path="/api/v1/work-orders/")
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/vendors/",
        )


def test_deprecated_name_emits_no_runtime_warning() -> None:
    """Consumers run with ``-W error``; the deprecation is docs plus the check."""
    ctx, sig = _sign()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_new_names_are_exported() -> None:
    for module in (gateway_signature, gateway_identity):
        assert "verify_gateway_signature_without_request_binding" in module.__all__
        assert "verify_gateway_signature_for_request" in module.__all__
    assert (
        gateway_identity.verify_gateway_signature_without_request_binding
        is verify_gateway_signature_without_request_binding
    )


# --- 5.48.0: PEP 702 marker, opt-in runtime warning, deprecated alias --------


def test_deprecated_names_carry_the_pep_702_marker() -> None:
    assert verify_gateway_signature.__deprecated__ == (
        gateway_signature.UNBOUND_VERIFIER_DEPRECATION
    )
    assert gateway_identity.verify.__deprecated__ == (
        gateway_signature.UNBOUND_VERIFIER_DEPRECATION
    )
    for replacement in (
        verify_gateway_signature_without_request_binding,
        gateway_signature.verify_gateway_signature_for_request,
    ):
        assert not hasattr(replacement, "__deprecated__")


def test_deprecation_text_names_both_replacements() -> None:
    text = gateway_signature.UNBOUND_VERIFIER_DEPRECATION
    assert "verify_gateway_signature_for_request" in text
    assert "verify_gateway_signature_without_request_binding" in text
    assert "#397" in text


def test_alias_emits_no_runtime_warning_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        gateway_signature.GATEWAY_WARN_UNBOUND_VERIFIER_ENV, raising=False
    )
    ctx, sig = _sign()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        payload = gateway_identity.verify(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
    assert payload["tenant_id"] == "22222222-2222-2222-2222-222222222222"


@pytest.mark.parametrize("value", ["1", "true", "YES", " on "])
def test_opt_in_runtime_warning_names_the_call_site(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(gateway_signature.GATEWAY_WARN_UNBOUND_VERIFIER_ENV, value)
    ctx, sig = _sign()
    with pytest.warns(DeprecationWarning, match="#397") as caught:
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
    (warning,) = caught
    # stacklevel points at this test, the deprecated function's caller.
    assert warning.filename == __file__

    ctx, sig = _sign()
    with pytest.warns(DeprecationWarning, match="#397") as caught:
        gateway_identity.verify(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
    (warning,) = caught
    assert warning.filename == __file__


@pytest.mark.parametrize("value", ["", "0", "false", "off"])
def test_opt_in_runtime_warning_stays_off_for_falsy_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(gateway_signature.GATEWAY_WARN_UNBOUND_VERIFIER_ENV, value)
    ctx, sig = _sign()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_alias_still_binds_when_given_the_request() -> None:
    ctx, sig = _sign(method="GET", path="/api/v1/work-orders/")
    with pytest.raises(GatewaySignatureError):
        gateway_identity.verify(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/vendors/",
        )


def test_env_var_name_is_exported() -> None:
    assert (
        gateway_signature.GATEWAY_WARN_UNBOUND_VERIFIER_ENV
        == "ADAPTIX_GATEWAY_WARN_UNBOUND_VERIFIER"
    )
    assert "GATEWAY_WARN_UNBOUND_VERIFIER_ENV" in gateway_signature.__all__
    assert "UNBOUND_VERIFIER_DEPRECATION" in gateway_signature.__all__


_CONSUMER_SNIPPET = """\
from adaptix_contracts import gateway_identity
from adaptix_contracts.gateway_signature import (
    verify_gateway_signature,
    verify_gateway_signature_for_request,
    verify_gateway_signature_without_request_binding,
)

def unbound(ctx: str, sig: str) -> None:
    verify_gateway_signature(context_b64=ctx, signature_hex=sig)
    gateway_identity.verify(context_b64=ctx, signature_hex=sig)

def explicit(ctx: str, sig: str) -> None:
    verify_gateway_signature_without_request_binding(context_b64=ctx, signature_hex=sig)
"""


def test_type_checker_reports_every_reference_to_the_unbound_verifier(
    tmp_path: Path,
) -> None:
    """The type-level deterrent: mypy names the import and both calls.

    Runs mypy the way a consumer does once it enables the ``deprecated`` error
    code (docs/GATEWAY_VERIFIER_MIGRATION.md). The replacement names are not
    reported.
    """
    consumer = tmp_path / "consumer.py"
    consumer.write_text(_CONSUMER_SNIPPET, encoding="utf-8")
    config = tmp_path / "mypy.ini"
    config.write_text(
        "[mypy]\nenable_error_code = deprecated\ncache_dir = "
        + str(tmp_path / ".mypy_cache")
        + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(config),
            "--no-error-summary",
            str(consumer),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    reported = [
        line for line in completed.stdout.splitlines() if "[deprecated]" in line
    ]
    assert completed.returncode == 1, completed.stdout + completed.stderr
    # mypy names each deprecated symbol where it is bound: the import statement
    # (line 2) and the attribute reference ``gateway_identity.verify`` (line 10).
    # Line 13, the explicit no-binding replacement, is not reported.
    assert [line.split(":")[1] for line in reported] == ["2", "10"], reported
    assert all("#397" in line for line in reported)
    assert all("without_request_binding is deprecated" not in line for line in reported)
