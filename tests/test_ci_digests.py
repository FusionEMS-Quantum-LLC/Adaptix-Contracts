"""Tests for the centralized CI binary digest registry."""

from __future__ import annotations

import re
from pathlib import Path

from adaptix_contracts.security.ci_digests import (
    VERIFIED_DIGESTS,
    _RETIRED_DIGESTS,
    is_retired,
    is_verified,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VAR_PATTERN = {
    "UV_SHA256": re.compile(r'UV_SHA256:\s*"(?P<sha>[0-9a-f]{64})"'),
    "GITLEAKS_SHA256": re.compile(r'GITLEAKS_SHA256:\s*"(?P<sha>[0-9a-f]{64})"'),
}


class TestDigestRegistryIntegrity:
    """Structural invariants for the digest sets."""

    def test_all_active_digests_are_hex_sha256(self) -> None:
        for digest in VERIFIED_DIGESTS:
            assert SHA256_PATTERN.match(digest), (
                f"Active digest is not a valid SHA-256 hex string: {digest!r}"
            )

    def test_all_retired_digests_are_hex_sha256(self) -> None:
        for digest in _RETIRED_DIGESTS:
            assert SHA256_PATTERN.match(digest), (
                f"Retired digest is not a valid SHA-256 hex string: {digest!r}"
            )

    def test_no_overlap_between_active_and_retired(self) -> None:
        overlap = VERIFIED_DIGESTS & _RETIRED_DIGESTS
        assert not overlap, f"Digests in both active and retired: {overlap}"

    def test_active_set_is_not_empty(self) -> None:
        assert len(VERIFIED_DIGESTS) > 0

    def test_known_uv_digest_is_present(self) -> None:
        uv_sha = "600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101"
        assert is_verified(uv_sha), "uv 0.12.3 digest missing"

    def test_known_gitleaks_digest_is_present(self) -> None:
        gl_sha = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
        assert is_verified(gl_sha), "gitleaks 8.30.1 digest missing"


class TestHelpers:
    def test_is_verified_true_for_known(self) -> None:
        assert is_verified(next(iter(VERIFIED_DIGESTS))) is True

    def test_is_verified_false_for_unknown(self) -> None:
        assert is_verified("0" * 64) is False

    def test_is_retired_false_when_empty(self) -> None:
        assert is_retired("0" * 64) is False
