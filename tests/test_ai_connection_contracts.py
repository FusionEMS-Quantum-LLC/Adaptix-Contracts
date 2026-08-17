"""Contract tests for the AI & Agent Connection control plane (v1).

Covers Step 1 requirements from the AdaptixCore Claude + External MCP directive:
policy enum compatibility, invalid-enum rejection, tool-contract serialization
and self-consistency, SECRET-never-through-MCP, and the fail-closed helpers.
"""

from __future__ import annotations

import dataclasses

import pytest

from adaptix_contracts.ai import (
    AI_CONNECTION_CONTRACT_VERSION,
    MCP_TOOL_CONTRACT_VERSION,
    AIExecutionMode,
    AIProviderKey,
    DataClassification,
    EffectivePolicyDecision,
    ExternalClientType,
    FORBIDDEN_TOOL_NAMES,
    MCPToolContract,
    MCPToolContractError,
    PolicyDecision,
    PolicyReasonCode,
    ReadOrWrite,
    ToolRiskClass,
    allow,
    approval_required,
    data_classification_allows_mcp,
    data_classification_is_phi,
    deny,
    tool_is_write,
    tool_risk_rank,
)


# ---------------------------------------------------------------------------
# Enum shape / compatibility
# ---------------------------------------------------------------------------


def test_provider_keys_are_the_closed_set() -> None:
    assert {p.value for p in AIProviderKey} == {"cortex", "anthropic_claude"}


def test_execution_modes_are_the_closed_set() -> None:
    assert {m.value for m in AIExecutionMode} == {
        "cortex",
        "cortex_routed",
        "direct",
        "external_mcp",
    }


def test_external_client_types_are_the_closed_set() -> None:
    assert {c.value for c in ExternalClientType} == {
        "claude",
        "claude_desktop",
        "claude_code",
        "chatgpt",
        "other_mcp",
    }


def test_policy_decisions_are_the_closed_set() -> None:
    assert {d.value for d in PolicyDecision} == {"ALLOW", "DENY", "APPROVAL_REQUIRED"}


def test_tool_risk_classes_are_the_closed_set() -> None:
    assert {r.value for r in ToolRiskClass} == {
        "READ_ONLY",
        "LOCAL_DRAFT",
        "SIDE_EFFECT",
        "HIGH_RISK_SIDE_EFFECT",
        "FORBIDDEN",
    }


def test_data_classifications_are_the_closed_set() -> None:
    assert {c.value for c in DataClassification} == {
        "PUBLIC",
        "INTERNAL",
        "PII",
        "PHI",
        "FINANCIAL",
        "SECURITY_SENSITIVE",
        "SECRET",
    }


def test_invalid_enum_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        AIProviderKey("openai_gpt")
    with pytest.raises(ValueError):
        AIExecutionMode("freestyle")
    with pytest.raises(ValueError):
        DataClassification("TOP_SECRET")


def test_contract_versions_present() -> None:
    assert AI_CONNECTION_CONTRACT_VERSION == "1.0.0"
    assert MCP_TOOL_CONTRACT_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# Risk ranking + write classification
# ---------------------------------------------------------------------------


def test_risk_rank_is_monotonic_and_forbidden_is_ceiling() -> None:
    assert tool_risk_rank(ToolRiskClass.READ_ONLY) < tool_risk_rank(
        ToolRiskClass.LOCAL_DRAFT
    )
    assert tool_risk_rank(ToolRiskClass.LOCAL_DRAFT) < tool_risk_rank(
        ToolRiskClass.SIDE_EFFECT
    )
    assert tool_risk_rank(ToolRiskClass.SIDE_EFFECT) < tool_risk_rank(
        ToolRiskClass.HIGH_RISK_SIDE_EFFECT
    )
    # FORBIDDEN must be strictly above every real-risk tool.
    assert tool_risk_rank(ToolRiskClass.HIGH_RISK_SIDE_EFFECT) < tool_risk_rank(
        ToolRiskClass.FORBIDDEN
    )


def test_unknown_risk_fails_closed_as_max() -> None:
    assert tool_risk_rank("garbage") == tool_risk_rank(ToolRiskClass.FORBIDDEN)


def test_write_classification() -> None:
    assert not tool_is_write(ToolRiskClass.READ_ONLY)
    assert not tool_is_write(ToolRiskClass.LOCAL_DRAFT)
    assert tool_is_write(ToolRiskClass.SIDE_EFFECT)
    assert tool_is_write(ToolRiskClass.HIGH_RISK_SIDE_EFFECT)


# ---------------------------------------------------------------------------
# Data classification / MCP boundary
# ---------------------------------------------------------------------------


def test_secret_never_crosses_mcp() -> None:
    assert data_classification_allows_mcp(DataClassification.SECRET) is False
    # As a raw string too — defense in depth.
    assert data_classification_allows_mcp("SECRET") is False


def test_non_secret_classifications_allowed_through_mcp() -> None:
    for c in DataClassification:
        if c == DataClassification.SECRET:
            continue
        assert data_classification_allows_mcp(c) is True


def test_unknown_classification_fails_closed() -> None:
    assert data_classification_allows_mcp("MADE_UP") is False


def test_phi_detection() -> None:
    assert data_classification_is_phi(DataClassification.PHI) is True
    assert data_classification_is_phi(DataClassification.PII) is False


# ---------------------------------------------------------------------------
# EffectivePolicyDecision + helpers
# ---------------------------------------------------------------------------


def test_deny_helper_is_fail_closed() -> None:
    d = deny(PolicyReasonCode.POLICY_UNAVAILABLE, policy_version=7)
    assert d.allowed is False
    assert d.decision == PolicyDecision.DENY
    assert d.approval_required is False
    assert d.reason_code == "POLICY_UNAVAILABLE"
    assert d.policy_version == 7


def test_allow_helper() -> None:
    d = allow(policy_version=42, effective_scopes=("adaptix-mcp/read",))
    assert d.allowed is True
    assert d.decision == PolicyDecision.ALLOW
    assert d.approval_required is False
    assert d.effective_scopes == ("adaptix-mcp/read",)


def test_approval_required_helper() -> None:
    d = approval_required(policy_version=42)
    assert d.allowed is False
    assert d.decision == PolicyDecision.APPROVAL_REQUIRED
    assert d.approval_required is True


def test_decision_derived_booleans_cannot_be_forged() -> None:
    # Even if a caller tries to set allowed=True with a DENY decision, the
    # frozen dataclass reconciles them from `decision` (fail closed).
    d = EffectivePolicyDecision(
        allowed=True,
        decision=PolicyDecision.DENY,
        reason_code="X",
        policy_version=1,
    )
    assert d.allowed is False
    assert d.approval_required is False


def test_decision_is_frozen() -> None:
    d = allow(policy_version=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.allowed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MCP tool contract
# ---------------------------------------------------------------------------


def _valid_read_tool() -> MCPToolContract:
    return MCPToolContract(
        tool_name="claims.search",
        contract_version="1.0.0",
        domain="billing",
        description="Search claims for the authorized tenant/workspace.",
        read_or_write=ReadOrWrite.READ,
        risk_class=ToolRiskClass.READ_ONLY,
        data_classification=DataClassification.FINANCIAL,
        possible_phi=False,
        required_adaptix_permission="billing.claims.read",
        required_service_scope="adaptix-mcp/read",
        target_service="adaptix-billing",
        approval_required=False,
        idempotency_required=False,
    )


def _valid_write_tool() -> MCPToolContract:
    return MCPToolContract(
        tool_name="claims.submit_correction",
        contract_version="1.0.0",
        domain="billing",
        description="Submit an approved claim correction.",
        read_or_write=ReadOrWrite.WRITE,
        risk_class=ToolRiskClass.HIGH_RISK_SIDE_EFFECT,
        data_classification=DataClassification.FINANCIAL,
        possible_phi=False,
        required_adaptix_permission="billing.claims.write",
        required_service_scope="adaptix-mcp/request-write",
        target_service="adaptix-billing",
        approval_required=True,
        idempotency_required=True,
    )


def test_valid_read_tool_passes() -> None:
    _valid_read_tool().validate()
    assert _valid_read_tool().is_valid() is True


def test_valid_write_tool_passes() -> None:
    _valid_write_tool().validate()
    assert _valid_write_tool().is_valid() is True


def test_forbidden_tool_names_rejected() -> None:
    for name in FORBIDDEN_TOOL_NAMES:
        bad = dataclasses.replace(_valid_read_tool(), tool_name=name)
        with pytest.raises(MCPToolContractError):
            bad.validate()


def test_generic_admin_primitives_are_all_forbidden() -> None:
    # The directive's explicit prohibition list must all be present.
    required = {
        "database.execute",
        "database.query",
        "sql.run",
        "shell.run",
        "command.execute",
        "aws.execute",
        "aws.cli",
        "filesystem.read_arbitrary",
        "filesystem.write_arbitrary",
        "secrets.read",
        "secrets.list",
        "environment.read",
        "http.request_arbitrary",
    }
    assert required.issubset(FORBIDDEN_TOOL_NAMES)


def test_secret_data_tool_rejected() -> None:
    bad = dataclasses.replace(
        _valid_read_tool(), data_classification=DataClassification.SECRET
    )
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_forbidden_risk_class_rejected() -> None:
    bad = dataclasses.replace(_valid_read_tool(), risk_class=ToolRiskClass.FORBIDDEN)
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_write_without_approval_rejected() -> None:
    bad = dataclasses.replace(_valid_write_tool(), approval_required=False)
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_write_without_idempotency_rejected() -> None:
    bad = dataclasses.replace(_valid_write_tool(), idempotency_required=False)
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_side_effect_declared_as_read_rejected() -> None:
    bad = dataclasses.replace(_valid_write_tool(), read_or_write=ReadOrWrite.READ)
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_read_declared_as_write_rejected() -> None:
    bad = dataclasses.replace(_valid_read_tool(), read_or_write=ReadOrWrite.WRITE)
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_possible_phi_requires_phi_classification() -> None:
    bad = dataclasses.replace(
        _valid_read_tool(),
        possible_phi=True,
        data_classification=DataClassification.PUBLIC,
    )
    with pytest.raises(MCPToolContractError):
        bad.validate()


def test_possible_phi_with_phi_classification_ok() -> None:
    ok = dataclasses.replace(
        _valid_read_tool(),
        possible_phi=True,
        data_classification=DataClassification.PHI,
    )
    ok.validate()


def test_missing_required_field_rejected() -> None:
    for empty_field in (
        "tool_name",
        "domain",
        "description",
        "required_adaptix_permission",
        "required_service_scope",
        "target_service",
    ):
        bad = dataclasses.replace(_valid_read_tool(), **{empty_field: "  "})
        with pytest.raises(MCPToolContractError):
            bad.validate()
