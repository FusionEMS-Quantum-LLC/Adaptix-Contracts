"""Tests for the MEDICAL_DIRECTOR canonical role.

The medical director is the clinical authority who owns and signs an agency's protocol
library. It gates the Medical Director module (protocol authoring / medication add / sign-off).
Before this it existed only as free-text strings in epcr/quality_contracts.py — not as a
canonical AdaptixRole — so services could not enforce it uniformly. These tests lock it in.
"""

from __future__ import annotations

from adaptix_contracts.auth.context import AdaptixRole, AdaptixRoleSet


def test_medical_director_is_canonical_role() -> None:
    assert AdaptixRole.MEDICAL_DIRECTOR.value == "medical_director"
    # Round-trips from the wire value used across services.
    assert AdaptixRole("medical_director") is AdaptixRole.MEDICAL_DIRECTOR


def test_is_medical_director_helper() -> None:
    md = AdaptixRoleSet(roles=[AdaptixRole.MEDICAL_DIRECTOR])
    assert md.is_medical_director() is True
    assert md.has_role(AdaptixRole.MEDICAL_DIRECTOR) is True

    other = AdaptixRoleSet(roles=[AdaptixRole.PARAMEDIC])
    assert other.is_medical_director() is False


def test_medical_director_distinct_from_admin_and_founder() -> None:
    # The MD is a distinct clinical authority — never conflated with agency admin or founder.
    md = AdaptixRoleSet(roles=[AdaptixRole.MEDICAL_DIRECTOR])
    assert md.is_agency_admin() is False
    assert md.is_founder() is False
    assert md.is_service_account() is False
