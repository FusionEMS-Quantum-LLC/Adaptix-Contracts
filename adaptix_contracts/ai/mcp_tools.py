"""MCP tool contract for the AdaptixCore external capability plane.

Every tool exposed through the AgentCore Gateway / MCP Tool Broker MUST declare
a complete :class:`MCPToolContract`. The broker refuses to expose any tool whose
contract is incomplete or self-inconsistent — this is what guarantees that
"appears in tools/list" can never mean "unauthorized capability leaked".

Hard invariants enforced by :meth:`MCPToolContract.validate`:

* ``SECRET`` data classification is never exposable (delegates to
  :func:`adaptix_contracts.ai.connection.data_classification_allows_mcp`).
* ``read_or_write`` must agree with ``risk_class``: a READ_ONLY tool cannot be a
  write, and any side-effecting tool must be marked write AND require approval
  AND require idempotency.
* A ``possible_phi`` tool must carry PHI (or stricter) data classification —
  you cannot claim a tool might return PHI while labelling its data PUBLIC.
* Generic administrative primitives (``database.execute``, ``shell.run``,
  ``secrets.read`` …) are permanently forbidden tool names, regardless of any
  other field. See :data:`FORBIDDEN_TOOL_NAMES`.

This module is import-only value objects — no I/O, no secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .connection import (
    DataClassification,
    ToolRiskClass,
    data_classification_allows_mcp,
    data_classification_is_phi,
    tool_is_write,
)

MCP_TOOL_CONTRACT_VERSION = "1.0.0"


class ReadOrWrite(str, Enum):
    READ = "read"
    WRITE = "write"


# Permanently prohibited MCP tool names — generic administrative primitives that
# must NEVER be exposed, with no exception hidden behind founder status. Domain
# *intents* (claims.search, epcr.get_chart_status …) are the only shape allowed.
FORBIDDEN_TOOL_NAMES: frozenset[str] = frozenset(
    {
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
)


class MCPToolContractError(ValueError):
    """Raised when a tool contract is incomplete or self-inconsistent.

    A tool that raises this is not eligible for MCP exposure.
    """


@dataclass(frozen=True)
class MCPToolContract:
    """The complete, declared contract for one MCP-exposed Adaptix tool.

    All fields are required. If any field is unknown, the tool is not eligible
    for MCP exposure — construct-time and :meth:`validate` both enforce this.
    """

    tool_name: str
    contract_version: str
    domain: str
    description: str
    read_or_write: ReadOrWrite
    risk_class: ToolRiskClass
    data_classification: DataClassification
    possible_phi: bool
    required_adaptix_permission: str
    required_service_scope: str
    target_service: str
    approval_required: bool
    idempotency_required: bool

    def validate(self) -> None:
        """Enforce every hard invariant. Raises :class:`MCPToolContractError`.

        The broker calls this before ever admitting a tool to the registry.
        """

        # 1. Required non-empty string fields.
        for name in (
            "tool_name",
            "contract_version",
            "domain",
            "description",
            "required_adaptix_permission",
            "required_service_scope",
            "target_service",
        ):
            value = getattr(self, name)
            if not value or not str(value).strip():
                raise MCPToolContractError(
                    f"tool contract field {name!r} is required and non-empty"
                )

        # 2. Forbidden generic-primitive names — no exceptions.
        if self.tool_name in FORBIDDEN_TOOL_NAMES:
            raise MCPToolContractError(
                f"tool name {self.tool_name!r} is permanently forbidden from MCP exposure"
            )

        # 3. SECRET never crosses MCP.
        if not data_classification_allows_mcp(self.data_classification):
            raise MCPToolContractError(
                f"data_classification {self.data_classification!r} is not exposable through MCP"
            )

        # 4. FORBIDDEN risk class is never exposable.
        if self.risk_class == ToolRiskClass.FORBIDDEN:
            raise MCPToolContractError("FORBIDDEN risk_class tools cannot be exposed")

        # 5. read_or_write must agree with risk_class.
        is_write = tool_is_write(self.risk_class)
        if is_write and self.read_or_write != ReadOrWrite.WRITE:
            raise MCPToolContractError(
                "side-effecting risk_class must be declared read_or_write=WRITE"
            )
        if not is_write and self.read_or_write == ReadOrWrite.WRITE:
            raise MCPToolContractError(
                "read_or_write=WRITE requires a side-effecting risk_class"
            )

        # 6. Any write requires approval AND idempotency (Step 22 / Step 24).
        if is_write:
            if not self.approval_required:
                raise MCPToolContractError(
                    "write tools must set approval_required=True"
                )
            if not self.idempotency_required:
                raise MCPToolContractError(
                    "write tools must set idempotency_required=True"
                )

        # 7. possible_phi must be consistent with data_classification.
        if self.possible_phi and not data_classification_is_phi(
            self.data_classification
        ):
            raise MCPToolContractError(
                "possible_phi=True requires data_classification=PHI"
            )

    def is_valid(self) -> bool:
        """Non-raising convenience wrapper around :meth:`validate`."""

        try:
            self.validate()
        except MCPToolContractError:
            return False
        return True
