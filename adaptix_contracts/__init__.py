"""Adaptix contracts package containing shared cross-domain schema definitions.

This package provides typed contract definitions for cross-domain communication
across the Adaptix polyrepo platform.

Import patterns:
    # Import all schemas
    from adaptix_contracts.schemas import *

    # Import specific schemas
    from adaptix_contracts.schemas import (
        ClaimContract,
        EpcrChartCreatedEvent,
        TransportRequestCreate,
    )
"""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from adaptix_contracts import schemas as _schemas

# Static re-export surface for type checkers (runtime uses globals().update below).
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adaptix_contracts.schemas import *  # noqa: F401,F403

# Redundant aliases mark these as intentional re-exports (suppresses F401
# without requiring entries in __all__, which preserves the package surface
# invariant checked by test_contract_surface.py).
from adaptix_contracts.schemas.legal_execution_contracts import (
    ContractAccessCheckRequest as ContractAccessCheckRequest,
    ContractAccessCheckResponse as ContractAccessCheckResponse,
    ContractSignatureEvent as ContractSignatureEvent,
    ContractStatus as ContractStatus,
    ContractType as ContractType,
    TenantContractStatusMap as TenantContractStatusMap,
)
from adaptix_contracts.event_contracts import (
    EventMetadata as EventMetadata,
    EventSchema as EventSchema,
    EventValidator as EventValidator,
    LocalEventConsumerRegistry as LocalEventConsumerRegistry,
)


def _resolve_version() -> str:
    """Resolve the package version from installed metadata or ``pyproject.toml``."""

    try:
        return version("adaptix-contracts")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        project_config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(project_config["project"]["version"])


__version__ = _resolve_version()

# Re-export all schema symbols at package level for convenience.
__all__ = list(_schemas.__all__)
_missing_exports = [name for name in __all__ if not hasattr(_schemas, name)]
if _missing_exports:
    raise ImportError(
        "adaptix_contracts.schemas.__all__ includes missing exports: "
        + ", ".join(sorted(_missing_exports))
    )

globals().update({name: getattr(_schemas, name) for name in _schemas.__all__})

del _schemas
