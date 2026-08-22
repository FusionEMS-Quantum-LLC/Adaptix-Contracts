"""Adaptix-native TrustSign HTTP client — canonical replacement for Dropbox Sign / HelloSign.

This client lets every Adaptix service that needs digital signatures call
the TrustSign engine at ``/api/v1/trustsign/*``. It is the **only**
authorized signature integration path going forward. There is no fallback
to Dropbox Sign / HelloSign.

ROUTING REALITY (verified 2026-08-05): as of the 2026-07-15 cutover, the
gateway (``Adaptix-Gateway/backend/app/config/routes.py``, the
``/api/v1/trustsign`` and ``/api/v1/trustsign/sign`` ``RouteEntry`` rows)
forwards ALL ``/api/v1/trustsign/*`` traffic to the standalone
``Adaptix-TrustSign-Service`` engine — NOT to ``Adaptix-Billing-Service``.
``Adaptix-Billing-Service`` still ships its own in-process mirror
(``billing_app.trustsign.request_service`` / legacy
``billing_app/api/trustsign_routes.py``) with an independently-migrated
database of the same table names; that copy is no longer reachable via the
gateway prefix this client calls. A caller anywhere in the fleet that mints
a signing request through Billing's *internal* (non-HTTP) engine — as
``Adaptix-Billing-Service``'s onboarding legal-packet dispatch
(``billing_app.services.trustsign_legal_packet_service``) still does — will
produce a magic-link token that this client (and the gateway-routed
``/sign/{token}`` Web-App page) cannot resolve, because the standalone
engine's database has never seen that token. See the confirmed BAA
capture-and-persist journey gap logged 2026-08-05. This client itself only
ever talks to the gateway/standalone engine, so it is not the broken hop —
but do not assume every "TrustSign" caller in the fleet already goes
through this client.

Design rules (per founder directive 2026-05-25):

* The client speaks only HTTP to the Billing-Service TrustSign engine
  through the canonical gateway (``api.adaptixcore.com``) or the internal
  service mesh. It never imports billing_app internals, so consumer
  repositories don't need a transitive dependency on Billing-Service.
* No call ever goes to ``api.hellosign.com`` / ``api.dropbox.com`` /
  ``dropboxsign.com``. The client refuses to be configured with one of
  those hostnames (defence-in-depth ``ValueError`` at construction).
* Webhook signature verification is HMAC-SHA256 over the raw body using
  the ``ADAPTIX_TRUSTSIGN_WEBHOOK_SECRET`` shared with Billing-Service.
* Tenant scoping is preserved by forwarding the caller's Bearer token
  unchanged — the gateway + Billing's ``get_auth_context`` are the
  authority for tenant/agency/user identity. The client does not invent
  tenant IDs.
* Errors raise structured exceptions (``TrustSignClientError`` subclasses)
  so callers can map them to user-facing language without stringy parsing.

Canonical import path for all consumer Adaptix services:

    from adaptix_contracts.trustsign_client import (
        TrustSignClient, TrustSignClientConfig, CreateRequestInput, SignerSpec,
    )

A mirror copy lives at ``billing_app.trustsign.http_client`` inside
``Adaptix-Billing-Service`` (the canonical Phase 1 PR) so Billing-internal
callers don't take a self-dependency on adaptix-contracts. Both files
MUST stay byte-equivalent. The Billing copy is the source of truth for
the engine contract; this copy is the source of truth for consumer
imports. A drift test in this package asserts the two stay in sync.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, EmailStr, Field

logger = logging.getLogger(__name__)

# ── Disallowed hostnames — defence-in-depth against accidental fallback ────
_FORBIDDEN_HOSTS = frozenset(
    {
        "api.hellosign.com",
        "hellosign.com",
        "app.hellosign.com",
        "api.dropboxsign.com",
        "dropboxsign.com",
        "app.dropboxsign.com",
    }
)

_TRUSTSIGN_PURPOSES = frozenset(
    {
        "msa_signing",
        "baa_signing",
        "aup_signing",
        "dpa_signing",
        "tos_signing",
        "privacy_signing",
        "subprocessor_acknowledgement",
        "compliance_attestation",
        "signature_authority_attestation",
        "agency_contract_bundle",
        "transportlink_partner_agreement",
        "agency_onboarding_packet",
    }
)


# ── Client request/response models ────────────────────────────────────────


class SignerSpec(BaseModel):
    """One signer on a TrustSign request."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=64)
    signing_order: int = Field(default=1, ge=1, le=20)


class CreateRequestInput(BaseModel):
    """Inbound parameters for ``TrustSignClient.create_request``."""

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(..., min_length=1, max_length=64)
    template_id: str = Field(..., min_length=1, max_length=64)
    template_version: str | None = Field(default=None, max_length=32)
    signers: list[SignerSpec] = Field(..., min_length=1, max_length=20)
    merge_fields: dict[str, Any] = Field(default_factory=dict)
    expiration_days: int | None = Field(default=None, ge=1, le=365)
    custom_body_text: str | None = Field(default=None, min_length=1)


class SignerResponse(BaseModel):
    """One signer slot, as returned by Billing TrustSign."""

    signer_id: str
    email: str
    full_name: str
    role: str
    signing_url: str
    expires_at: str


class CreateRequestResponse(BaseModel):
    """``POST /api/v1/trustsign/requests`` happy-path response."""

    request_id: str
    verification_id: str
    template_id: str
    template_version: str
    purpose: str
    status: str
    expires_at: str
    signers: list[SignerResponse]


class RequestStatusResponse(BaseModel):
    """``GET /api/v1/trustsign/requests/{id}`` response."""

    request_id: str
    verification_id: str
    purpose: str
    status: str
    template_id: str
    template_version: str
    created_at: str
    expires_at: str
    archived_at: str | None = None
    signers: list[dict[str, Any]] = Field(default_factory=list)


# ── Exceptions ────────────────────────────────────────────────────────────


class TrustSignClientError(RuntimeError):
    """Base class for all TrustSignClient failures."""


class TrustSignConfigurationError(TrustSignClientError):
    """Raised when the client is constructed with an invalid config."""


class TrustSignTransportError(TrustSignClientError):
    """Raised when the HTTP transport itself fails (DNS, connect, timeout)."""


class TrustSignServerError(TrustSignClientError):
    """Raised when Billing-Service returns a 5xx response."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"TrustSign server returned {status_code}: {body!r}")
        self.status_code = status_code
        self.body = body


class TrustSignValidationError(TrustSignClientError):
    """Raised when Billing-Service returns a 4xx validation response."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"TrustSign rejected request ({status_code}): {body!r}")
        self.status_code = status_code
        self.body = body


class TrustSignUnauthorizedError(TrustSignClientError):
    """Raised when Billing-Service returns 401/403."""


# ── The client ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrustSignClientConfig:
    """Construction parameters for ``TrustSignClient``."""

    base_url: str
    """Absolute base URL for the TrustSign API. In production this is
    ``https://api.adaptixcore.com`` (the gateway), routing
    ``/api/v1/trustsign/*`` to the standalone Adaptix-TrustSign-Service
    (cutover 2026-07-15 — this no longer forwards to Adaptix-Billing-Service).
    In service-mesh deployments this may point directly at the standalone
    engine's internal service DNS name instead."""

    bearer_token: str
    """The caller's Adaptix JWT (Cognito or Core RS256). Tenant scoping
    flows from this token via ``get_auth_context``."""

    webhook_secret: str | None = None
    """Shared HMAC secret for webhook signature verification. Required only
    on the receiving service; emitters do not need it."""

    timeout_seconds: float = 15.0
    """Per-request timeout."""

    user_agent: str = "adaptix-trustsign-client/1.0"


class TrustSignClient:
    """HTTP client for the Adaptix-native TrustSign engine.

    Usage (Billing-internal, Core-Service, Transport-Service, etc.):

        cfg = TrustSignClientConfig(
            base_url="https://api.adaptixcore.com",
            bearer_token=request.headers["authorization"].removeprefix("Bearer "),
            webhook_secret=os.environ["ADAPTIX_TRUSTSIGN_WEBHOOK_SECRET"],
        )
        async with TrustSignClient(cfg) as client:
            resp = await client.create_request(
                CreateRequestInput(
                    purpose="msa_signing",
                    template_id="msa_v2",
                    signers=[SignerSpec(email="...", full_name="...", role="signer")],
                ),
            )
    """

    def __init__(
        self,
        config: TrustSignClientConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._validate_base_url(config.base_url)
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=config.timeout_seconds)
            self._owns_client = True

    # ── lifecycle ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "TrustSignClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ── config validation ───────────────────────────────────────────────

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"}:
            raise TrustSignConfigurationError(
                f"base_url scheme must be http or https; got {parts.scheme!r}"
            )
        host = (parts.hostname or "").lower()
        if not host:
            raise TrustSignConfigurationError(
                f"base_url must include a hostname; got {base_url!r}"
            )
        if host in _FORBIDDEN_HOSTS:
            raise TrustSignConfigurationError(
                f"base_url {base_url!r} points at the legacy Dropbox Sign / "
                f"HelloSign host. TrustSign is the only authorized signature "
                f"system; reconfigure to point at the Adaptix gateway "
                f"(https://api.adaptixcore.com) or the internal service mesh."
            )

    # ── auth header ─────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.bearer_token}",
            "User-Agent": self._config.user_agent,
            "Accept": "application/json",
        }

    # ── primitives ──────────────────────────────────────────────────────

    async def _request(
        self,
        method: Literal["GET", "POST", "DELETE"],
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = self._config.base_url.rstrip("/") + path
        headers = self._auth_headers()
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = await self._client.request(
                method,
                url,
                json=json_body,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise TrustSignTransportError(
                f"TrustSign {method} {path} transport failure: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise TrustSignUnauthorizedError(
                f"TrustSign {method} {path} returned {response.status_code}"
            )
        if 400 <= response.status_code < 500:
            raise TrustSignValidationError(response.status_code, _safe_json(response))
        if response.status_code >= 500:
            raise TrustSignServerError(response.status_code, _safe_json(response))
        return response

    # ── public methods ──────────────────────────────────────────────────

    async def create_request(
        self, payload: CreateRequestInput
    ) -> CreateRequestResponse:
        """Create a new signing request.

        Per-signer magic-link URLs come back in ``response.signers[*].signing_url``
        — these are short-lived bearer tokens, NOT Adaptix session URLs.
        """
        if payload.purpose not in _TRUSTSIGN_PURPOSES:
            logger.warning(
                "trustsign.client.create_request unknown_purpose purpose=%s",
                payload.purpose,
            )
        body = payload.model_dump(exclude_none=True, mode="json")
        response = await self._request(
            "POST", "/api/v1/trustsign/requests", json_body=body
        )
        return CreateRequestResponse.model_validate(response.json())

    async def get_request_status(self, request_id: str) -> RequestStatusResponse:
        """Read current status + signer progress for a request."""
        response = await self._request(
            "GET", f"/api/v1/trustsign/requests/{request_id}"
        )
        return RequestStatusResponse.model_validate(response.json())

    async def download_archive(self, request_id: str) -> bytes:
        """Stream the archived signed PDF. Caller must persist or display it.

        Calls ``GET /api/v1/trustsign/archives/by-request/{request_id}/download``
        on Adaptix-TrustSign-Service with gateway identity headers. A missing
        or not-yet-archived request returns 404 (``archive_not_found``). A
        stored file that no longer matches the recorded hash is refused by
        the service (409). Public verification remains
        ``GET /api/v1/verifications/signature/{verification_id}``.
        """
        url = self._config.base_url.rstrip("/") + (
            f"/api/v1/trustsign/archives/by-request/{request_id}/download"
        )
        try:
            response = await self._client.get(url, headers=self._auth_headers())
        except httpx.RequestError as exc:
            raise TrustSignTransportError(
                f"TrustSign archive download transport failure: {exc}"
            ) from exc
        if response.status_code in (401, 403):
            raise TrustSignUnauthorizedError(
                f"TrustSign archive download returned {response.status_code}"
            )
        if response.status_code == 404:
            raise TrustSignValidationError(404, {"code": "archive_not_found"})
        if 400 <= response.status_code < 500:
            raise TrustSignValidationError(response.status_code, _safe_json(response))
        if response.status_code >= 500:
            raise TrustSignServerError(response.status_code, _safe_json(response))
        return response.content

    async def void_request(self, request_id: str, *, reason: str | None = None) -> None:
        """Cancel a pending signing request.

        Calls ``POST /api/v1/trustsign/requests/{request_id}/void`` on
        Adaptix-TrustSign-Service. Unused signing links are revoked. An
        already-finished archived request is refused (409). Cross-tenant
        callers receive 404.
        """
        body = {"reason": reason} if reason else {}
        await self._request(
            "POST",
            f"/api/v1/trustsign/requests/{request_id}/void",
            json_body=body,
        )

    async def resend_request(
        self, request_id: str, *, expiration_days: int | None = None
    ) -> None:
        """Re-issue the per-signer magic links (resets expiration).

        NOT YET IMPLEMENTED on the standalone Adaptix-TrustSign-Service
        (verified 2026-08-05: no matching route in
        ``Adaptix-TrustSign-Service/backend/app/routes/trustsign.py``). This
        path exists only on Adaptix-Billing-Service's deprecated legacy
        router (``billing_app/api/trustsign_routes.py``), which the gateway
        no longer forwards ``/api/v1/trustsign/*`` traffic to. Calling this
        against the real gateway-routed ``base_url`` today raises
        ``TrustSignValidationError(404, ...)`` — a clean typed failure, not
        a silent one, but the capability itself does not exist server-side
        yet.
        """
        body = (
            {"expiration_days": expiration_days} if expiration_days is not None else {}
        )
        await self._request(
            "POST",
            f"/api/v1/trustsign/requests/{request_id}/resend",
            json_body=body,
        )

    # ── webhook signature verification ──────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        *,
        body: bytes,
        signature_header: str | None,
        secret: str,
    ) -> bool:
        """Verify a TrustSign webhook signature.

        Compares ``signature_header`` (expected format
        ``sha256=<hex>``) against ``HMAC-SHA256(secret, body)`` using
        constant-time comparison.
        """
        if not signature_header or not secret:
            return False
        if not signature_header.startswith("sha256="):
            return False
        provided = signature_header.removeprefix("sha256=").strip()
        if len(provided) != 64:
            return False
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided, expected)


def _safe_json(response: httpx.Response) -> Any:
    """Best-effort JSON decode; never raises."""
    try:
        return response.json()
    except ValueError:
        return response.text[:1024]
