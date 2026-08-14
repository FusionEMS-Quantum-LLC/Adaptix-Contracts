"""AdaptixCore Fire CAD Connect — canonical enums.

CAD Connect ingests dispatch/CAD information an agency can legitimately provide
(uploaded run sheets, exports, pasted text, or — later — direct feeds) and
normalizes it to ONE AdaptixCore Standard CAD Incident. These enums are the
fixed vocabularies shared across the ingest (Imports-Service), the interpreter
(Cortex CAD Mapper in the AI-Service), the owner (Fire-Service), and the UI
(Web-App) so the same string values are used everywhere and never re-invented
per service.
"""

from __future__ import annotations

from enum import Enum


class FieldStatus(str, Enum):
    """Per-field review state on a normalized CAD value.

    Cortex never silently guesses an important value. Every extracted field
    carries exactly one of these states so the firefighter always sees where
    human judgement is required.
    """

    CONFIRMED = "confirmed"  # high confidence / deterministic source
    REVIEW = "review"  # found, but wants human confirmation
    MISSING = "missing"  # source did not contain a usable value (never invented)
    CONFLICT = "conflict"  # two or more different values were found


class IngestionMethod(str, Enum):
    """How a CAD payload entered the Universal CAD Gateway.

    All methods normalize to the same AdaptixCore Standard CAD Incident. The
    customer can begin with manual/upload intake and later move to a direct
    connection without rebuilding downstream Fire/NERIS configuration.
    """

    MANUAL_UPLOAD = "manual_upload"  # firefighter uploads a file
    PASTE = "paste"  # firefighter pastes dispatch text
    SECURE_FILE_FEED = "secure_file_feed"  # SFTP / scheduled drop
    AUTOMATIC_INBOX = "automatic_inbox"  # agency-specific dispatch inbox (email)
    VENDOR_API = "vendor_api"  # authorized vendor API connector
    STANDARD_EIDO = "standard_eido"  # NENA EIDO / EIDD standards feed


class ConnectorSupportStatus(str, Enum):
    """Lifecycle of a Universal CAD Gateway connector in the registry.

    A connector is only ``PRODUCTION_VERIFIED`` after a real sanctioned test
    exchange with an authorized endpoint. A vendor logo or a registered
    connector key is NOT support — never label a connector connected/supported
    without exchanged real test data.
    """

    PLANNED = "planned"
    AUTHORIZATION_REQUIRED = (
        "authorization_required"  # awaiting vendor/PSAP authorization
    )
    IMPLEMENTATION_AVAILABLE = "implementation_available"  # code exists, unproven live
    TEST_ENVIRONMENT_VERIFIED = (
        "test_environment_verified"  # sanctioned test exchange succeeded
    )
    PRODUCTION_VERIFIED = (
        "production_verified"  # proven against a live authorized source
    )
    DEPRECATED = "deprecated"


class ExtractionMethod(str, Enum):
    """How a single normalized field value was derived (attribution)."""

    DETERMINISTIC = "deterministic"  # parsed from structured input (csv/xml/json/nfirs)
    PROFILE = "profile"  # applied a confirmed agency mapping profile
    CORTEX = "cortex"  # interpreted by the Cortex CAD Mapper


class MappingProfileStatus(str, Enum):
    """Lifecycle of an agency CAD import mapping profile."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"  # activated after a successful sample test
    SUPERSEDED = (
        "superseded"  # replaced by a newer version; immutable, retained for audit
    )


__all__ = [
    "FieldStatus",
    "IngestionMethod",
    "ConnectorSupportStatus",
    "ExtractionMethod",
    "MappingProfileStatus",
]
