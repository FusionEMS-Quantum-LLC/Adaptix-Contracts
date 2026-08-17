"""AI & Agent Connection contracts for the AdaptixCore Claude + External MCP
control plane.

These are the SHARED, versioned enums and value objects that every consumer
repository (Core policy authority, AI-Service Claude Direct runtime, the MCP
Tool Broker, and the Web-App configuration surfaces) must agree on. Defining
them once here — rather than letting each service invent its own string
constants — is what keeps the provider-neutral MCP capability plane and the
policy authority in lockstep.

Design rules encoded here (do not weaken downstream):

* Provider identity is a small closed set of *provider keys* (``cortex``,
  ``anthropic_claude``). Raw Bedrock model IDs are NEVER provider identities —
  a model id is resolved server-side from an approved alias, never accepted
  from a client. See :class:`AIProviderKey` and :mod:`adaptix_contracts.ai.mcp_tools`.
* ``SECRET`` data classification must NEVER be exposed through MCP. The
  :func:`data_classification_allows_mcp` helper is the single source of truth.
* Policy decisions are a closed set: ``ALLOW`` / ``DENY`` / ``APPROVAL_REQUIRED``.
  There is no implicit fourth state; "unknown" resolves to ``DENY`` at the
  resolver (fail-closed), never here.

This module is import-only value objects — no I/O, no network, no secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Bump in lockstep with additive changes so consumers can pin behaviour.
AI_CONNECTION_CONTRACT_VERSION = "1.0.0"


class AIProviderKey(str, Enum):
    """Canonical provider identities.

    A provider key is the stable identity the policy plane governs. It is NOT a
    cloud runtime (``bedrock``) and NOT a model id (``anthropic.claude-sonnet-5``).
    Exposing arbitrary model ids as provider identities is forbidden.
    """

    CORTEX = "cortex"
    ANTHROPIC_CLAUDE = "anthropic_claude"


class AIExecutionMode(str, Enum):
    """How an AI request is executed.

    * ``CORTEX`` — native Adaptix Cortex orchestration (Nova primary).
    * ``CORTEX_ROUTED`` — Cortex selected Claude through the model router,
      subject to ``cortex_routing_enabled`` policy.
    * ``DIRECT`` — the user intentionally chose Claude Direct; bypasses Cortex
      orchestration but NOT auth/tenancy/policy/PHI/audit/budget.
    * ``EXTERNAL_MCP`` — an external MCP client (Claude/ChatGPT/etc.) invoking an
      Adaptix tool through the AgentCore Gateway.
    """

    CORTEX = "cortex"
    CORTEX_ROUTED = "cortex_routed"
    DIRECT = "direct"
    EXTERNAL_MCP = "external_mcp"


class ExternalClientType(str, Enum):
    """External MCP client families. The protocol layer is provider-neutral;
    this only classifies *which client family* a connection belongs to so a
    tenant/workspace can enable Claude clients while leaving ChatGPT off (or
    vice-versa)."""

    CLAUDE = "claude"
    CLAUDE_DESKTOP = "claude_desktop"
    CLAUDE_CODE = "claude_code"
    CHATGPT = "chatgpt"
    OTHER_MCP = "other_mcp"


class PolicyDecision(str, Enum):
    """The closed set of effective policy outcomes."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class ToolRiskClass(str, Enum):
    """Risk classification for an exposed MCP tool.

    Ordering matters for policy comparisons: a workspace that permits up to
    ``SIDE_EFFECT`` must still deny ``HIGH_RISK_SIDE_EFFECT``. Use
    :func:`tool_risk_rank` for comparisons rather than comparing enum members.
    ``FORBIDDEN`` tools are never exposable under any policy.
    """

    READ_ONLY = "READ_ONLY"
    LOCAL_DRAFT = "LOCAL_DRAFT"
    SIDE_EFFECT = "SIDE_EFFECT"
    HIGH_RISK_SIDE_EFFECT = "HIGH_RISK_SIDE_EFFECT"
    FORBIDDEN = "FORBIDDEN"


# Monotonic rank for risk comparison. FORBIDDEN is deliberately the ceiling so
# no "max risk permitted" policy can ever admit it.
_TOOL_RISK_ORDER: dict[str, int] = {
    ToolRiskClass.READ_ONLY.value: 0,
    ToolRiskClass.LOCAL_DRAFT.value: 1,
    ToolRiskClass.SIDE_EFFECT.value: 2,
    ToolRiskClass.HIGH_RISK_SIDE_EFFECT.value: 3,
    ToolRiskClass.FORBIDDEN.value: 99,
}


def tool_risk_rank(risk: ToolRiskClass | str) -> int:
    """Return the monotonic rank for a risk class (higher == riskier)."""

    value = risk.value if isinstance(risk, ToolRiskClass) else str(risk)
    if value not in _TOOL_RISK_ORDER:
        # Unknown risk class is treated as maximally risky — fail closed.
        return _TOOL_RISK_ORDER[ToolRiskClass.FORBIDDEN.value]
    return _TOOL_RISK_ORDER[value]


def tool_is_write(risk: ToolRiskClass | str) -> bool:
    """True when a tool has any side effect (needs write policy + approval)."""

    value = risk.value if isinstance(risk, ToolRiskClass) else str(risk)
    return value in (
        ToolRiskClass.SIDE_EFFECT.value,
        ToolRiskClass.HIGH_RISK_SIDE_EFFECT.value,
    )


class DataClassification(str, Enum):
    """Data sensitivity classes. ``SECRET`` must never cross the MCP boundary."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PII = "PII"
    PHI = "PHI"
    FINANCIAL = "FINANCIAL"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"
    SECRET = "SECRET"


def data_classification_allows_mcp(classification: DataClassification | str) -> bool:
    """Single source of truth: may this classification EVER cross MCP?

    ``SECRET`` is categorically forbidden through MCP regardless of any toggle.
    An unknown classification fails closed (returns False).
    """

    value = (
        classification.value
        if isinstance(classification, DataClassification)
        else str(classification)
    )
    if value == DataClassification.SECRET.value:
        return False
    return value in {c.value for c in DataClassification} and value != (
        DataClassification.SECRET.value
    )


def data_classification_is_phi(classification: DataClassification | str) -> bool:
    """True when a classification carries PHI handling obligations."""

    value = (
        classification.value
        if isinstance(classification, DataClassification)
        else str(classification)
    )
    return value == DataClassification.PHI.value


# ---------------------------------------------------------------------------
# Effective policy decision value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectivePolicyDecision:
    """The resolver's answer — an *effective decision*, never raw DB rows.

    Consumers must treat this as the authoritative verdict. ``reason_code`` is a
    stable machine string (e.g. ``WORKSPACE_PROVIDER_DISABLED``) safe to surface
    to operators; it never contains host names, secrets, or internal policy
    detail. When ``decision`` is ``APPROVAL_REQUIRED`` the caller must create an
    approval record before any side effect.
    """

    allowed: bool
    decision: PolicyDecision
    reason_code: str
    policy_version: int
    approval_required: bool = False
    effective_scopes: tuple[str, ...] = field(default_factory=tuple)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        # Keep the three derived booleans internally consistent so a consumer
        # can trust any one of them.
        object.__setattr__(self, "allowed", self.decision == PolicyDecision.ALLOW)
        object.__setattr__(
            self,
            "approval_required",
            self.decision == PolicyDecision.APPROVAL_REQUIRED,
        )


# Stable reason codes shared across the policy plane. Consumers should prefer
# these constants over string literals so audit/metrics stay consistent.
class PolicyReasonCode(str, Enum):
    ALLOWED = "ALLOWED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    # Provider / Claude Direct
    BEDROCK_INFRA_DISABLED = "BEDROCK_INFRA_DISABLED"
    PROVIDER_DISABLED = "PROVIDER_DISABLED"
    WORKSPACE_PROVIDER_DISABLED = "WORKSPACE_PROVIDER_DISABLED"
    DIRECT_DISABLED = "DIRECT_DISABLED"
    CORTEX_ROUTING_DISABLED = "CORTEX_ROUTING_DISABLED"
    EXECUTION_MODE_DISABLED = "EXECUTION_MODE_DISABLED"
    USER_NOT_PERMITTED = "USER_NOT_PERMITTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    PHI_NOT_PERMITTED = "PHI_NOT_PERMITTED"
    MODEL_NOT_APPROVED = "MODEL_NOT_APPROVED"
    # External / MCP
    EXTERNAL_GLOBAL_STOP = "EXTERNAL_GLOBAL_STOP"
    EXTERNAL_TENANT_DISABLED = "EXTERNAL_TENANT_DISABLED"
    EXTERNAL_WORKSPACE_DISABLED = "EXTERNAL_WORKSPACE_DISABLED"
    CLIENT_FAMILY_DISABLED = "CLIENT_FAMILY_DISABLED"
    CONNECTION_NOT_ACTIVE = "CONNECTION_NOT_ACTIVE"
    CONNECTION_REVOKED = "CONNECTION_REVOKED"
    CONNECTION_EXPIRED = "CONNECTION_EXPIRED"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    RBAC_DENIED = "RBAC_DENIED"
    DATA_CLASSIFICATION_DENIED = "DATA_CLASSIFICATION_DENIED"
    RISK_CLASS_DENIED = "RISK_CLASS_DENIED"
    # Fail-closed
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    UNKNOWN_MODE = "UNKNOWN_MODE"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    UNKNOWN_USER = "UNKNOWN_USER"


def deny(
    reason_code: PolicyReasonCode | str,
    *,
    policy_version: int = 0,
    correlation_id: str | None = None,
) -> EffectivePolicyDecision:
    """Construct a canonical DENY decision (the fail-closed default)."""

    code = (
        reason_code.value
        if isinstance(reason_code, PolicyReasonCode)
        else str(reason_code)
    )
    return EffectivePolicyDecision(
        allowed=False,
        decision=PolicyDecision.DENY,
        reason_code=code,
        policy_version=policy_version,
        correlation_id=correlation_id,
    )


def allow(
    *,
    policy_version: int,
    effective_scopes: tuple[str, ...] = (),
    correlation_id: str | None = None,
) -> EffectivePolicyDecision:
    """Construct a canonical ALLOW decision."""

    return EffectivePolicyDecision(
        allowed=True,
        decision=PolicyDecision.ALLOW,
        reason_code=PolicyReasonCode.ALLOWED.value,
        policy_version=policy_version,
        effective_scopes=effective_scopes,
        correlation_id=correlation_id,
    )


def approval_required(
    *,
    policy_version: int,
    effective_scopes: tuple[str, ...] = (),
    correlation_id: str | None = None,
) -> EffectivePolicyDecision:
    """Construct a canonical APPROVAL_REQUIRED decision."""

    return EffectivePolicyDecision(
        allowed=False,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        reason_code=PolicyReasonCode.APPROVAL_REQUIRED.value,
        policy_version=policy_version,
        effective_scopes=effective_scopes,
        correlation_id=correlation_id,
    )
