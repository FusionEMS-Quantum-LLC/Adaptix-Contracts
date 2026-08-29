"""Geospatial contracts shared across Adaptix services.

Canonical coordinate, geocoding, distance, routing, and service-area shapes
for the AdaptixCore Geo shared service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
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
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(default=None, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)


class GeocodeResult(BaseModel):
    """Result of resolving an address to coordinates."""

    coordinate: GeoCoordinate
    formatted_address: str
    matched: bool
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
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
        default=None, description="Encoded route geometry, if provided."
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
    description: Optional[str] = Field(default=None, max_length=1000)
    polygon: list[GeoCoordinate] = Field(default_factory=list)
    center: Optional[GeoCoordinate] = None
    radius_miles: Optional[float] = Field(default=None, ge=0.0)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Reverse Geocoding & Autocomplete
# ---------------------------------------------------------------------------


class ReverseGeocodeRequest(BaseModel):
    """Request to resolve coordinates back to a formatted address."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    coordinate: GeoCoordinate


class AutocompleteRequest(BaseModel):
    """Request for address autocomplete suggestions."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    query: str = Field(..., min_length=1, max_length=500)
    country: str = Field(default="US", min_length=2, max_length=2)
    limit: int = Field(default=5, ge=1, le=25)


class AddressSuggestion(BaseModel):
    """A single address autocomplete suggestion."""

    formatted_address: str
    coordinate: Optional[GeoCoordinate] = None
    place_id: Optional[str] = None
    provider: Optional[str] = None


class AutocompleteResult(BaseModel):
    """Ordered set of address autocomplete suggestions."""

    suggestions: list[AddressSuggestion] = Field(default_factory=list)
    provider: Optional[str] = None


# ---------------------------------------------------------------------------
# Route & Distance Requests
# ---------------------------------------------------------------------------


class RouteRequest(BaseModel):
    """Request for a driving route/ETA between two coordinates."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    origin: GeoCoordinate
    destination: GeoCoordinate
    include_polyline: bool = True


class DistanceRequest(BaseModel):
    """Request for the distance between two coordinates."""

    tenant_id: UUID
    correlation_id: Optional[str] = None
    origin: GeoCoordinate
    destination: GeoCoordinate


# ---------------------------------------------------------------------------
# Consumer Client Helper
# ---------------------------------------------------------------------------


class GeoClient:
    """Thin async HTTP client for the AdaptixCore Geo service.

    Wraps the ``/api/v1/geo`` endpoints and returns the canonical Geo DTOs so
    consumers (CAD, EPCR, Hospital, Transport) call one typed client instead
    of duplicating a Stadia Maps / haversine integration. The caller owns the
    ``httpx.AsyncClient`` lifecycle when one is supplied; otherwise a client is
    created per call.

    Example::

        client = GeoClient("http://adaptix-geo:8000", token=service_jwt)
        result = await client.geocode(
            GeocodeRequest(tenant_id=tid, address="123 Main St")
        )
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: Optional[str] = None,
        timeout: float = 8.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._headers: dict[str, str] = {}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    async def _post(self, path: str, payload: BaseModel) -> httpx.Response:
        url = f"{self._base_url}/api/v1/geo{path}"
        body = payload.model_dump(mode="json")
        if self._client is not None:
            return await self._client.post(url, json=body, headers=self._headers)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(url, json=body, headers=self._headers)

    async def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        """Resolve an address to coordinates."""
        response = await self._post("/geocode", request)
        response.raise_for_status()
        return GeocodeResult.model_validate(response.json())

    async def reverse_geocode(self, request: ReverseGeocodeRequest) -> GeocodeResult:
        """Resolve coordinates back to a formatted address."""
        response = await self._post("/reverse-geocode", request)
        response.raise_for_status()
        return GeocodeResult.model_validate(response.json())

    async def autocomplete(self, request: AutocompleteRequest) -> AutocompleteResult:
        """Return address autocomplete suggestions."""
        response = await self._post("/autocomplete", request)
        response.raise_for_status()
        return AutocompleteResult.model_validate(response.json())

    async def route(self, request: RouteRequest) -> RouteEstimate:
        """Return a driving route/ETA between two coordinates."""
        response = await self._post("/route", request)
        response.raise_for_status()
        return RouteEstimate.model_validate(response.json())

    async def distance(self, request: DistanceRequest) -> DistanceResult:
        """Return the distance between two coordinates."""
        response = await self._post("/distance", request)
        response.raise_for_status()
        return DistanceResult.model_validate(response.json())
