"""Internal helpers for building ``PricingBand`` seed data from string literals.

Private to the ``commercial`` package's seed catalog files — not part of the
public surface (no leading-underscore-free re-export anywhere). Split out of
``wisconsin_launch_catalog.py`` purely for reuse across that file's own
domain-grouped entry modules; it has no logic of its own beyond literal-to-
``Decimal`` conversion.
"""

from __future__ import annotations

from decimal import Decimal

from adaptix_contracts.commercial.pricing_catalog import PricingBand

__all__ = ["custom_quote_band", "flat_band", "per_unit_band"]


def flat_band(
    min_units: int, max_units: int | None, monthly: str, annual: str
) -> PricingBand:
    """One flat-priced (non-custom-quote) band from string literals.

    String literals, not floats, so every figure is an exact ``Decimal`` —
    floating point has no place in a price list.
    """

    return PricingBand(
        min_units=min_units,
        max_units=max_units,
        monthly_price=Decimal(monthly),
        annual_price=Decimal(annual),
    )


def per_unit_band(
    min_units: int, max_units: int | None, monthly: str, annual: str
) -> PricingBand:
    """One per-unit-priced (non-custom-quote) band from string literals."""

    return PricingBand(
        min_units=min_units,
        max_units=max_units,
        monthly_price_per_unit=Decimal(monthly),
        annual_price_per_unit=Decimal(annual),
    )


def custom_quote_band(min_units: int) -> PricingBand:
    return PricingBand(min_units=min_units, max_units=None, custom_quote=True)
