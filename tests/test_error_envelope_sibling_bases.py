"""Domain error envelopes are SIBLINGS of the platform envelope, not subclasses.

Edge and QA need an envelope whose ``error_code`` accepts their own enum as well
as the platform one. Expressing that by subclassing ``AdaptixErrorEnvelope`` and
re-declaring the field is a Liskov violation, and the type checker rejected it —
two identical errors sat on ``main``.

The fix shares everything except ``error_code`` through
``AdaptixErrorEnvelopeBase``. These tests pin the property that makes the fix
safe: **the platform envelope's validation was not weakened**. Widening
``AdaptixErrorEnvelope.error_code`` would have silenced the type checker too,
and would have made every service in the fleet accept Edge and QA codes. The
first test below is the one that tells those two outcomes apart.

These envelopes had no test coverage at all before this file.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from adaptix_contracts.edge.errors import EdgeErrorCode, EdgeErrorEnvelope
from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixErrorEnvelopeBase,
)
from adaptix_contracts.qa.errors import QaErrorCode, QaErrorEnvelope

FIXED_TS = "2026-01-01T00:00:00+00:00"


class TestPlatformValidationNotWeakened:
    """The platform envelope must still refuse domain-specific codes."""

    @pytest.mark.parametrize(
        "foreign_code",
        [next(iter(EdgeErrorCode)), next(iter(QaErrorCode))],
        ids=["edge_code", "qa_code"],
    )
    def test_platform_envelope_rejects_domain_codes(self, foreign_code):
        with pytest.raises(ValidationError):
            AdaptixErrorEnvelope(error_code=foreign_code, message="m")

    def test_platform_envelope_accepts_platform_codes(self):
        env = AdaptixErrorEnvelope(error_code=AdaptixErrorCode.NOT_FOUND, message="m")

        assert env.error_code is AdaptixErrorCode.NOT_FOUND


class TestDomainEnvelopesStayScopedToTheirOwnCodes:
    """Each domain envelope takes its own codes plus the platform ones — no more."""

    def test_edge_accepts_edge_and_platform(self):
        assert EdgeErrorEnvelope(error_code=next(iter(EdgeErrorCode)), message="m")
        assert EdgeErrorEnvelope(error_code=AdaptixErrorCode.NOT_FOUND, message="m")

    def test_edge_rejects_qa_codes(self):
        with pytest.raises(ValidationError):
            EdgeErrorEnvelope(error_code=next(iter(QaErrorCode)), message="m")

    def test_qa_accepts_qa_and_platform(self):
        assert QaErrorEnvelope(error_code=next(iter(QaErrorCode)), message="m")
        assert QaErrorEnvelope(error_code=AdaptixErrorCode.NOT_FOUND, message="m")

    def test_qa_rejects_edge_codes(self):
        with pytest.raises(ValidationError):
            QaErrorEnvelope(error_code=next(iter(EdgeErrorCode)), message="m")


class TestSharedBehaviourSurvivesReParenting:
    """Fields, factories and to_http_response are inherited exactly as before."""

    @pytest.mark.parametrize(
        "cls",
        [AdaptixErrorEnvelope, EdgeErrorEnvelope, QaErrorEnvelope],
        ids=["platform", "edge", "qa"],
    )
    def test_every_envelope_shares_the_common_base(self, cls):
        assert issubclass(cls, AdaptixErrorEnvelopeBase)

    @pytest.mark.parametrize(
        "cls",
        [AdaptixErrorEnvelope, EdgeErrorEnvelope, QaErrorEnvelope],
        ids=["platform", "edge", "qa"],
    )
    @pytest.mark.parametrize(
        "factory", ["unauthorized", "forbidden", "not_found", "internal_error"]
    )
    def test_factories_survive_and_return_their_own_class(self, cls, factory):
        """A domain envelope keeps every platform factory helper it had."""
        fn = getattr(cls, factory)
        produced = fn("Widget") if factory == "not_found" else fn()

        assert isinstance(produced, cls)
        assert produced.success is False

    @pytest.mark.parametrize(
        "cls",
        [AdaptixErrorEnvelope, EdgeErrorEnvelope, QaErrorEnvelope],
        ids=["platform", "edge", "qa"],
    )
    def test_serialized_content_is_unchanged(self, cls):
        """Same keys, same values. Key ORDER moved; content did not."""
        env = cls(
            error_code=AdaptixErrorCode.NOT_FOUND, message="m", timestamp=FIXED_TS
        )
        payload = json.loads(env.model_dump_json())

        assert payload["success"] is False
        assert payload["error_code"] == "not_found"
        assert payload["message"] == "m"
        assert payload["timestamp"] == FIXED_TS
        assert payload["detail"] is None
        assert payload["validation_errors"] is None
        assert payload["provider_error"] is None
        assert payload["trace"] is None

    @pytest.mark.parametrize(
        "cls",
        [AdaptixErrorEnvelope, EdgeErrorEnvelope, QaErrorEnvelope],
        ids=["platform", "edge", "qa"],
    )
    def test_to_http_response_drops_none_fields(self, cls):
        env = cls(
            error_code=AdaptixErrorCode.NOT_FOUND, message="m", timestamp=FIXED_TS
        )
        body = env.to_http_response()

        assert "detail" not in body
        assert body["error_code"] is AdaptixErrorCode.NOT_FOUND
        assert body["message"] == "m"
