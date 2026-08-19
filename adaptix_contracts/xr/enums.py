"""Adaptix AR/XR Remote Physician Overwatch + Training — Enumerations.

Play P04 (XR service). Enums are shared across ``models.py`` and
``events.py`` so device, session, annotation, and recording lifecycle
strings never drift between the models a service publishes and the
events consumers read.
"""

from __future__ import annotations

from enum import StrEnum


class XrDevice(StrEnum):
    """Hardware the field-side participant is wearing/holding for the session.

    ``phone`` covers a standard smartphone camera stream (the fallback path
    with no headset required). The remaining values are the AR/XR headsets
    and smart glasses Josh named explicitly for Play P04.
    """

    PHONE = "phone"
    XREAL = "xreal"
    RAYBAN = "rayban"
    VISION_PRO = "vision_pro"
    QUEST3 = "quest3"
    HOLOLENS = "hololens"


class SessionType(StrEnum):
    """What kind of XR session this is.

    ``overwatch`` is a live remote-physician session where a physician
    observes and guides a field provider in real time. ``training`` is a
    simulation session used for skills practice and does not represent a
    real patient encounter.
    """

    OVERWATCH = "overwatch"
    TRAINING = "training"


class SessionStatus(StrEnum):
    """Lifecycle of an :class:`~adaptix_contracts.xr.models.XrSession`."""

    PENDING = "pending"
    CONNECTING = "connecting"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    FAILED = "failed"
    ABANDONED = "abandoned"


class AnnotationType(StrEnum):
    """The kind of overlay a remote physician places into the field-of-view."""

    TEXT_NOTE = "text_note"
    VOICE_NOTE = "voice_note"
    SPATIAL_MARKER = "spatial_marker"
    HIGHLIGHT_REGION = "highlight_region"
    DRAWING = "drawing"
    PROCEDURE_STEP_FLAG = "procedure_step_flag"


class RecordingStatus(StrEnum):
    """Lifecycle of a session recording's storage manifest."""

    PENDING = "pending"
    RECORDING = "recording"
    PROCESSING = "processing"
    AVAILABLE = "available"
    FAILED = "failed"
    PURGED = "purged"


class TrainingDifficulty(StrEnum):
    """Difficulty tier of a :class:`~adaptix_contracts.xr.models.TrainingScenario`."""

    INTRODUCTORY = "introductory"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


__all__ = [
    "AnnotationType",
    "RecordingStatus",
    "SessionStatus",
    "SessionType",
    "TrainingDifficulty",
    "XrDevice",
]
