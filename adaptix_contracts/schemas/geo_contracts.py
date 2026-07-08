"""Geospatial contracts shared across Adaptix services.

Canonical coordinate, geocoding, distance, routing, and service-area shapes
for the AdaptixCore Geo shared service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Coordinates
# ---------------------------------------------------------------------------


class GeoCoordinate(BaseModel):
    """A WGS84 latitude/longitude pair."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


class GeocodeRequest(BaseModel):
    """Request to resolve an address to coordinates."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    address: str = Field(..., min_length=1, max_length=500)
    city: Optional[str] = Field(None, max_length=120)
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(None, max_length=16)
    country: str = Field("US", min_length=2, max_length=2)


class GeocodeResult(BaseModel):
    """Result of resolving an address to coordinates."""

    coordinate: GeoCoordinate
    formatted_address: str
    matched: bool
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    place_id: Optional[str] = None
    provider: Optional[str] = None


# ---------------------------------------------------------------------------
# Distance & Routing
# ---------------------------------------------------------------------------


class DistanceResult(BaseModel):
    """Straight-line or road distance between two coordinates."""

    origin: GeoCoordinate
    destination: GeoCoordinate
    distance_meters: float = Field(..., ge=0.0)
    distance_miles: float = Field(..., ge=0.0)
    provider: Optional[str] = None


class RouteEstimate(BaseModel):
    """Estimated driving route between two coordinates."""

    origin: GeoCoordinate
    destination: GeoCoordinate
    distance_meters: float = Field(..., ge=0.0)
    distance_miles: float = Field(..., ge=0.0)
    duration_seconds: float = Field(..., ge=0.0)
    duration_minutes: float = Field(..., ge=0.0)
    polyline: Optional[str] = Field(
        None, description="Encoded route geometry, if provided."
    )
    provider: Optional[str] = None
    estimated_at: datetime


# ---------------------------------------------------------------------------
# Service Area
# ---------------------------------------------------------------------------


class ServiceArea(BaseModel):
    """A tenant's operational service area (polygon and/or radius)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    polygon: list[GeoCoordinate] = Field(default_factory=list)
    center: Optional[GeoCoordinate] = None
    radius_miles: Optional[float] = Field(None, ge=0.0)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
