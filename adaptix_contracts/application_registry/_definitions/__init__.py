"""Application and shared-capability definitions, one module per domain.

EVERY route in these modules is a real ``page.tsx`` on Web-App main 35b4a12e.
EVERY service audience was read from the gateway route table for the prefix
the surface actually calls. Do not add an application because a service or a
repository exists; add one because a person performs that job.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.command import (
    COMMAND_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.operations import (
    OPERATIONS_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.clinical import (
    CLINICAL_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.fire import FIRE_APPLICATIONS
from adaptix_contracts.application_registry._definitions.revenue import (
    REVENUE_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.workforce import (
    WORKFORCE_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.logistics import (
    LOGISTICS_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.business import (
    BUSINESS_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.intelligence import (
    INTELLIGENCE_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.governance import (
    GOVERNANCE_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.administration import (
    ADMINISTRATION_APPLICATIONS,
)
from adaptix_contracts.application_registry._definitions.capabilities import (
    SHARED_CAPABILITIES,
)
from adaptix_contracts.application_registry._model import ApplicationDefinition

__all__ = ["APPLICATIONS", "SHARED_CAPABILITIES"]

# Presentation order = the directive's domain order (``ApplicationDomain``).
APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    *COMMAND_APPLICATIONS,
    *OPERATIONS_APPLICATIONS,
    *CLINICAL_APPLICATIONS,
    *FIRE_APPLICATIONS,
    *REVENUE_APPLICATIONS,
    *WORKFORCE_APPLICATIONS,
    *LOGISTICS_APPLICATIONS,
    *BUSINESS_APPLICATIONS,
    *INTELLIGENCE_APPLICATIONS,
    *GOVERNANCE_APPLICATIONS,
    *ADMINISTRATION_APPLICATIONS,
)
