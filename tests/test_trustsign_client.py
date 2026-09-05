"""Tests for the canonical TrustSign HTTP client.

Coverage:

* Construction-time validation rejects legacy Dropbox/HelloSign hostnames.
* ``create_request`` POSTs the JSON shape the server endpoint expects.
* ``get_request_status`` parses the server response into typed model.
* ``download_archive`` returns raw bytes and surfaces 404 as
  ``TrustSignValidationError``.
* ``void_request`` round-trip with optional bodies.
* ``start_chart_signature`` / ``complete_chart_signature`` post the exact
  server shapes, carry no body tenant, and surface every refusal the
  service can raise (403 signer mismatch, 409 hash mismatch/replay,
  410 expiry, 422 consent) as a typed error rather than a silent success.
* Webhook signature verification accepts a correct HMAC and rejects
  every malformed shape (no header, wrong prefix, tampered hex, wrong
  length, wrong secret).
* 401/403 → ``TrustSignUnauthorizedError``.
* 5xx → ``TrustSignServerError`` with structured body capture.
* Network failures → ``TrustSignTransportError``.

All HTTP traffic is stubbed via ``httpx.MockTransport`` — no live calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from pydantic import ValidationError

from adaptix_contracts.trustsign_client import (
    ChartSignatureCompleteInput,
    ChartSignatureConsent,
    ChartSignatureStartInput,
    CreateRequestInput,
    SignerSpec,
    TrustSignClient,
    TrustSignClientConfig,
    TrustSignConfigurationError,
    TrustSignServerError,
    TrustSignTransportError,
    TrustSignUnauthorizedError,
    TrustSignValidationError,
)


def _cfg(
    base_url: str = "https://api.adaptixcore.com", *, secret: str | None = None
) -> TrustSignClientConfig:
    return TrustSignClientConfig(
        base_url=base_url,
        bearer_token="test-bearer-token",
        webhook_secret=secret,
    )


# ── construction-time guards ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://api.hellosign.com",
        "https://hellosign.com",
        "https://api.dropboxsign.com",
        "https://dropboxsign.com",
        "http://app.hellosign.com",
    ],
)
def test_construction_refuses_legacy_signature_hosts(bad_url: str) -> None:
    with pytest.raises(TrustSignConfigurationError) as exc:
        TrustSignClient(_cfg(bad_url))
    assert "TrustSign is the only authorized signature system" in str(exc.value)


def test_construction_refuses_unknown_scheme() -> None:
    with pytest.raises(TrustSignConfigurationError):
        TrustSignClient(_cfg("ftp://example.com"))


def test_construction_refuses_missing_hostname() -> None:
    with pytest.raises(TrustSignConfigurationError):
        TrustSignClient(_cfg("https://"))


def test_construction_accepts_canonical_gateway() -> None:
    client = TrustSignClient(_cfg("https://api.adaptixcore.com"))
    assert client is not None


def test_construction_accepts_internal_service_mesh() -> None:
    client = TrustSignClient(_cfg("http://adaptix-billing:8000"))
    assert client is not None


# ── create_request ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_request_posts_expected_body_and_returns_parsed_response() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/trustsign/requests"
        assert request.headers["Authorization"] == "Bearer test-bearer-token"
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "request_id": "req_123",
                "verification_id": "ver_abc",
                "template_id": "msa_v2",
                "template_version": "1.0",
                "purpose": "msa_signing",
                "status": "pending",
                "expires_at": "2026-06-01T00:00:00+00:00",
                "signers": [
                    {
                        "signer_id": "sig_1",
                        "email": "signer@example.com",
                        "full_name": "Alex Signer",
                        "role": "signer",
                        "signing_url": "https://api.adaptixcore.com/api/v1/trustsign/sign/tok_xyz",
                        "expires_at": "2026-06-01T00:00:00+00:00",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            resp = await client.create_request(
                CreateRequestInput(
                    purpose="msa_signing",
                    template_id="msa_v2",
                    template_version="1.0",
                    signers=[
                        SignerSpec(
                            email="signer@example.com",
                            full_name="Alex Signer",
                            role="signer",
                        )
                    ],
                    merge_fields={"agency_name": "Acme EMS"},
                    expiration_days=14,
                )
            )

    assert resp.request_id == "req_123"
    assert resp.signers[0].signing_url.endswith("/sign/tok_xyz")
    assert captured["body"]["purpose"] == "msa_signing"
    assert captured["body"]["signers"][0]["email"] == "signer@example.com"
    assert captured["body"]["merge_fields"] == {"agency_name": "Acme EMS"}
    assert captured["body"]["expiration_days"] == 14


@pytest.mark.asyncio
async def test_create_request_4xx_raises_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": {"code": "trustsign_invalid_purpose", "message": "bad"}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(TrustSignValidationError) as exc:
                await client.create_request(
                    CreateRequestInput(
                        purpose="msa_signing",
                        template_id="msa_v2",
                        signers=[
                            SignerSpec(
                                email="x@example.com",
                                full_name="x",
                                role="signer",
                            )
                        ],
                    )
                )
            assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_create_request_5xx_raises_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream_unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(TrustSignServerError) as exc:
                await client.create_request(
                    CreateRequestInput(
                        purpose="msa_signing",
                        template_id="msa_v2",
                        signers=[
                            SignerSpec(
                                email="x@example.com",
                                full_name="x",
                                role="signer",
                            )
                        ],
                    )
                )
            assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_create_request_401_raises_unauthorized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "no token"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(TrustSignUnauthorizedError):
                await client.create_request(
                    CreateRequestInput(
                        purpose="msa_signing",
                        template_id="msa_v2",
                        signers=[
                            SignerSpec(
                                email="x@example.com",
                                full_name="x",
                                role="signer",
                            )
                        ],
                    )
                )


@pytest.mark.asyncio
async def test_create_request_transport_error_raises_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(TrustSignTransportError):
                await client.create_request(
                    CreateRequestInput(
                        purpose="msa_signing",
                        template_id="msa_v2",
                        signers=[
                            SignerSpec(
                                email="x@example.com",
                                full_name="x",
                                role="signer",
                            )
                        ],
                    )
                )


# ── get_request_status ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_request_status_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/trustsign/requests/req_abc"
        return httpx.Response(
            200,
            json={
                "request_id": "req_abc",
                "verification_id": "ver_abc",
                "purpose": "baa_signing",
                "status": "signed",
                "template_id": "baa_v3",
                "template_version": "3.1",
                "created_at": "2026-05-20T00:00:00+00:00",
                "expires_at": "2026-06-03T00:00:00+00:00",
                "archived_at": "2026-05-25T00:00:00+00:00",
                "signers": [{"signer_id": "sig_a", "status": "signed"}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            status = await client.get_request_status("req_abc")
    assert status.status == "signed"
    assert status.archived_at == "2026-05-25T00:00:00+00:00"


# ── download_archive ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_archive_returns_pdf_bytes() -> None:
    pdf = b"%PDF-1.7\nfake-archive-bytes\n%%EOF"

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.path == "/api/v1/trustsign/archives/by-request/req_xyz/download"
        )
        return httpx.Response(
            200, content=pdf, headers={"content-type": "application/pdf"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            content = await client.download_archive("req_xyz")
    assert content == pdf


@pytest.mark.asyncio
async def test_download_archive_404_raises_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "archive_not_found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(TrustSignValidationError) as exc:
                await client.download_archive("req_missing")
            assert exc.value.status_code == 404


# ── void ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_void_request_posts_reason() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/trustsign/requests/req_void/void"
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "cancelled"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            await client.void_request("req_void", reason="caller cancelled")
    assert captured["body"] == {"reason": "caller cancelled"}


# ── chart signature lifecycle ─────────────────────────────────────────────


_HASH = "a" * 64


def _complete_payload(document_hash: str = _HASH) -> ChartSignatureCompleteInput:
    return ChartSignatureCompleteInput(
        document_hash=document_hash,
        signature_type="drawn",
        signature_value="data:image/png;base64,iVBORw0KGgo=",
        consent=ChartSignatureConsent(
            consent_accepted=True, consent_text_sha256="b" * 64
        ),
    )


@pytest.mark.asyncio
async def test_start_chart_signature_posts_server_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/trustsign/chart-signatures"
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "request_id": "req_chart_1",
                "verification_id": "ver_1",
                "chart_id": "chart_1",
                "document_hash": _HASH,
                "intent": "Author attestation",
                "status": "pending",
                "expires_at": "2026-09-01T00:00:00Z",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            out = await client.start_chart_signature(
                ChartSignatureStartInput(
                    chart_id="chart_1",
                    document_hash=_HASH,
                    intent="Author attestation",
                    signer_full_name="Dana Medic",
                )
            )

    assert captured["body"] == {
        "chart_id": "chart_1",
        "document_hash": _HASH,
        "intent": "Author attestation",
        "signer_full_name": "Dana Medic",
    }
    assert out.request_id == "req_chart_1"
    assert out.document_hash == _HASH


def test_chart_signature_start_rejects_body_tenant() -> None:
    """Tenant comes from the authenticated session, never the request body."""
    with pytest.raises(ValidationError):
        ChartSignatureStartInput(
            chart_id="chart_1",
            document_hash=_HASH,
            intent="Author attestation",
            signer_full_name="Dana Medic",
            tenant_id="some-other-tenant",
        )


def test_chart_signature_complete_rejects_body_tenant() -> None:
    with pytest.raises(ValidationError):
        ChartSignatureCompleteInput(
            document_hash=_HASH,
            signature_type="drawn",
            consent=ChartSignatureConsent(
                consent_accepted=True, consent_text_sha256="b" * 64
            ),
            tenant_id="some-other-tenant",
        )


@pytest.mark.parametrize("bad_hash", ["", "zz", "g" * 64, "a" * 63, "a" * 65])
def test_chart_signature_requires_a_sha256_document_hash(bad_hash: str) -> None:
    with pytest.raises(ValidationError):
        ChartSignatureStartInput(
            chart_id="chart_1",
            document_hash=bad_hash,
            intent="Author attestation",
            signer_full_name="Dana Medic",
        )


@pytest.mark.asyncio
async def test_complete_chart_signature_returns_signed_artifact() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/api/v1/trustsign/chart-signatures/req_chart_1/complete"
        )
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "request_id": "req_chart_1",
                "verification_id": "ver_1",
                "status": "completed",
                "signer_signed_at": "2026-08-24T12:00:00Z",
                "all_signers_complete": True,
                "archive_s3_key": "tenant/chart_1/req_chart_1.pdf",
                "final_pdf_sha256": "c" * 64,
                "kms_key_id": "arn:aws:kms:us-east-1:1:key/abc",
                "kms_signature": "AAAA",
                "kms_signing_algorithm": "RSASSA_PSS_SHA_256",
                "kms_signed_at": "2026-08-24T12:00:01Z",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            out = await client.complete_chart_signature(
                "req_chart_1", _complete_payload()
            )

    assert captured["body"]["document_hash"] == _HASH
    assert "tenant_id" not in captured["body"]
    assert out.all_signers_complete is True
    assert out.final_pdf_sha256 == "c" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (403, TrustSignUnauthorizedError),
        (404, TrustSignValidationError),
        (409, TrustSignValidationError),
        (410, TrustSignValidationError),
        (422, TrustSignValidationError),
        (502, TrustSignServerError),
        (503, TrustSignServerError),
    ],
)
async def test_complete_chart_signature_refusals_are_typed(
    status_code: int, expected: type[Exception]
) -> None:
    """Every service refusal must raise — never return a "signed" result."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "refused"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw:
        async with TrustSignClient(_cfg(), http_client=raw) as client:
            with pytest.raises(expected):
                await client.complete_chart_signature(
                    "req_chart_1", _complete_payload()
                )


# ── webhook signature verification ────────────────────────────────────────


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_accepts_correct_hmac() -> None:
    secret = "shared-trustsign-secret"
    body = b'{"event":"request.signed","request_id":"req_1"}'
    assert TrustSignClient.verify_webhook_signature(
        body=body, signature_header=_sign(secret, body), secret=secret
    )


def test_webhook_signature_rejects_tampered_body() -> None:
    secret = "shared-trustsign-secret"
    sig = _sign(secret, b"original")
    assert not TrustSignClient.verify_webhook_signature(
        body=b"tampered", signature_header=sig, secret=secret
    )


def test_webhook_signature_rejects_wrong_secret() -> None:
    body = b"payload"
    sig = _sign("right-secret", body)
    assert not TrustSignClient.verify_webhook_signature(
        body=body, signature_header=sig, secret="wrong-secret"
    )


def test_webhook_signature_rejects_missing_header() -> None:
    assert not TrustSignClient.verify_webhook_signature(
        body=b"payload", signature_header=None, secret="anything"
    )


def test_webhook_signature_rejects_missing_secret() -> None:
    assert not TrustSignClient.verify_webhook_signature(
        body=b"payload", signature_header="sha256=" + "a" * 64, secret=""
    )


def test_webhook_signature_rejects_wrong_prefix() -> None:
    body = b"payload"
    expected_hex = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert not TrustSignClient.verify_webhook_signature(
        body=body, signature_header="md5=" + expected_hex, secret="secret"
    )


def test_webhook_signature_rejects_short_hex() -> None:
    assert not TrustSignClient.verify_webhook_signature(
        body=b"payload", signature_header="sha256=abc", secret="secret"
    )


def test_webhook_signature_rejects_non_ascii_digest_without_raising() -> None:
    """A 64-char digest containing a non-hex, non-ASCII byte must reject cleanly.

    Regression for a real crash: ``hmac.compare_digest`` raises ``TypeError``
    on a ``str`` operand containing any non-ASCII character. The prior
    implementation only checked ``len(provided) != 64``, and
    ``len("é" * 64) == 64``, so a single crafted webhook request turned a
    should-be-401 verification into an unhandled 500 -- no secret and no
    timing side channel required. This must return False, not raise.
    """
    body = b"payload"
    poisoned = "sha256=" + ("é" * 64)
    assert (
        TrustSignClient.verify_webhook_signature(
            body=body, signature_header=poisoned, secret="secret"
        )
        is False
    )


def test_webhook_signature_rejects_non_hex_ascii_digest() -> None:
    """64 ASCII characters that are not hex digits must also reject cleanly."""
    body = b"payload"
    non_hex = "sha256=" + ("g" * 64)
    assert not TrustSignClient.verify_webhook_signature(
        body=body, signature_header=non_hex, secret="secret"
    )
