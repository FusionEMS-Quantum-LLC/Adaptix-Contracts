"""Dynamic forms contracts shared across Adaptix services.

Canonical form template, versioned schema, field definitions, and validation
rules for the AdaptixCore Forms shared service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FormFieldType(str, Enum):
    """Supported input types for a form field."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    MULTISELECT = "multiselect"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    EMAIL = "email"
    PHONE = "phone"
    SIGNATURE = "signature"
    FILE = "file"


class FormStatus(str, Enum):
    """Lifecycle state of a form template."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Field & Validation
# ---------------------------------------------------------------------------


class FormValidationRule(BaseModel):
    """A single validation constraint applied to a form field."""

    rule_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="e.g. required, min_length, max_length, regex, min, max.",
    )
    value: Optional[str] = Field(
        None, description="Rule parameter serialized as a string, when applicable."
    )
    message: Optional[str] = Field(None, max_length=500)


class FormFieldDefinition(BaseModel):
    """Definition of a single field within a form schema."""

    key: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=255)
    field_type: FormFieldType
    required: bool = False
    placeholder: Optional[str] = Field(None, max_length=255)
    help_text: Optional[str] = Field(None, max_length=1000)
    options: list[str] = Field(
        default_factory=list, description="Choices for select/radio/multiselect."
    )
    default_value: Optional[str] = None
    validation_rules: list[FormValidationRule] = Field(default_factory=list)
    order: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Schema, Version & Template
# ---------------------------------------------------------------------------


class FormSchema(BaseModel):
    """An ordered set of field definitions describing a form."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    fields: list[FormFieldDefinition] = Field(default_factory=list)


class FormVersion(BaseModel):
    """An immutable, numbered version of a form's schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    version: int = Field(..., ge=1)
    form_schema: FormSchema
    is_published: bool = False
    created_by: Optional[UUID] = None
    created_at: datetime
    published_at: Optional[datetime] = None


class FormTemplate(BaseModel):
    """A named, versioned form owned by a tenant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    key: str = Field(..., min_length=1, max_length=160)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: FormStatus = FormStatus.DRAFT
    current_version: int = Field(1, ge=1)
    latest_version: Optional[FormVersion] = None
    created_at: datetime
    updated_at: datetime
