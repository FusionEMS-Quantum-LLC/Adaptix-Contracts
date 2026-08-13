"""Tests for the centralized CI binary digest registry.

These tests verify the integrity of the ``VERIFIED_DIGESTS`` registry
in ``adaptix_contracts.security.ci_digests`` — the single source of
truth for all SHA-256 checksums pinned in CodeBuild buildspecs across
the AdaptixCore polyrepo.
"""

from __future__ import annotations

import re

from adaptix_contracts.security.ci_digests import (
    VERIFIED_DIGESTS,
    _RETIRED_DIGESTS,
    is_retired,
    is_verified,
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TestDigestRegistryIntegrity:
    """Structural invariants for the digest sets."""

    def test_all_active_digests_are_hex_sha256(self) -> None:
        for digest in VERIFIED_DIGESTS:
            assert SHA256_PATTERN.match(
                digest
            ), f"Active digest is not a valid SHA-256 hex string: {digest!r}"

    def test_all_retired_digests_are_hex_sha256(self) -> None:
        for digest in _RETIRED_DIGESTS:
            assert SHA256_PATTERN.match(
                digest
            ), f"Retired digest is not a valid SHA-256 hex string: {digest!r}"

    def test_no_overlap_between_active_and_retired(self) -> None:
        overlap = VERIFIED_DIGESTS & _RETIRED_DIGESTS
        assert (
            not overlap
        ), f"Digests must not appear in both active and retired sets: {overlap}"

    def test_active_set_is_not_empty(self) -> None:
        assert len(VERIFIED_DIGESTS) > 0, "Active digest set must not be empty"

    def test_known_uv_digest_is_present(self) -> None:
        """The uv 0.12.3 digest that caused the fleet-wide CI failure."""
        uv_sha = (
            "600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101"
        )
        assert is_verified(uv_sha), f"uv 0.12.3 digest missing from registry"

    def test_known_gitleaks_digest_is_present(self) -> None:
        gl_sha = (
            "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
        )
        assert is_verified(gl_sha), "gitleaks 8.30.1 digest missing"


class TestHelpers:
    """Test the convenience helper functions."""

    def test_is_verified_true_for_known(self) -> None:
        any_digest = next(iter(VERIFIED_DIGESTS))
        assert is_verified(any_digest) is True

    def test_is_verified_false_for_unknown(self) -> None:
        assert is_verified("0" * 64) is False

    def test_is_retired_false_when_empty(self) -> None:
        assert is_retired("0" * 64) is False
