"""Centralized CI binary digest registry.

Every CodeBuild buildspec in the AdaptixCore polyrepo pins external tool
downloads by SHA-256 so that supply-chain-compromised artefacts are
detected at install time.  The ``test_ci_download_checksums.py`` test in
each repo verifies that the SHAs used in buildspecs belong to the
``VERIFIED_DIGESTS`` set.

**This module is the single source of truth for that set.**

When a tool version is bumped:

1. Verify the digest against the publisher's signed release manifest.
2. Add the new digest here.
3. Run ``uv sync && pytest tests/`` in Adaptix-Contracts.
4. Merge to main.  Every downstream repo's ``test_ci_download_checksums.py``
   already imports from this module (or should be migrated to do so).
5. No per-repo test edits are needed.

When a tool is retired, move its digest to ``_RETIRED_DIGESTS`` so it
can be audited but will no longer pass the active gate.
"""

from __future__ import annotations

from typing import Final

# ── Active verified digests ──────────────────────────────────────────
#
# Each entry carries a comment identifying the tool, version, platform,
# and artefact filename so reviewers can trace the provenance.

VERIFIED_DIGESTS: Final[frozenset[str]] = frozenset(
    {
        # ── uv ──────────────────────────────────────────────────────
        # uv 0.12.3 uv-x86_64-unknown-linux-gnu.tar.gz
        "600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101",
        # ── gitleaks ────────────────────────────────────────────────
        # gitleaks 8.30.1 linux_x64.tar.gz
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        # gitleaks 8.21.2 linux_x64.tar.gz
        "5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba",
        # gitleaks 8.18.4 linux_x64.tar.gz
        "ba6dbb656933921c775ee5a2d1c13a91046e7952e9d919f9bac4cec61d628e7d",
        # ── terraform ───────────────────────────────────────────────
        # terraform 1.14.8 linux_amd64.zip
        "56a5d12f47cbc1c6bedb8f5426ae7d5df984d1929572c24b56f4c82e9f9bf709",
        # ── trivy ───────────────────────────────────────────────────
        # trivy 0.71.0 Linux-64bit.tar.gz
        "30a3d22b23f88c233f1658f562fb477cae3b3e8b4761109d515b7698daf85814",
        # ── cosign ──────────────────────────────────────────────────
        # cosign 2.4.1 cosign-linux-amd64
        "8b24b946dd5809c6bd93de08033bcf6bc0ed7d336b7785787c080f574b89249b",
        # ── syft ────────────────────────────────────────────────────
        # syft 1.18.0 linux_amd64.tar.gz
        "0b6fd1e0dd5b00b19585e5cde8e1c1f4ef60dc8fba8b41fab55f00852a2fbb8d",
        # ── shellcheck ──────────────────────────────────────────────
        # shellcheck 0.10.0 linux.x86_64.tar.xz
        "6c881ab0698e4e6ea235245f22832860544f17ba386442fe7e9d629f8cbedf87",
        # ── detekt ──────────────────────────────────────────────────
        # detekt-cli 1.23.8 -all.jar
        "2ce2ff952e150baf28a29cda70a363b0340b3e81a55f43e51ec5edffc3d066c1",
    }
)

# ── Retired digests ──────────────────────────────────────────────────
#
# Digests that were once valid but have been superseded.  Kept for audit
# trails and rollback verification.  These MUST NOT appear in active
# buildspecs.

_RETIRED_DIGESTS: Final[frozenset[str]] = frozenset(
    {
        # (none yet — add retired SHAs here with version and retirement date)
    }
)


def is_verified(digest: str) -> bool:
    """Return True when *digest* is in the active verified set."""
    return digest in VERIFIED_DIGESTS


def is_retired(digest: str) -> bool:
    """Return True when *digest* was once active but has been retired."""
    return digest in _RETIRED_DIGESTS
