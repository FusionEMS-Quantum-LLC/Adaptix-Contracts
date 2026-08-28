"""Identity references used by canonical interoperability resources.

Patient matching remains owned by Adaptix-Patient-Identity-Service. These are
references only; they deliberately do not implement matching logic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class PatientIdentityReference(BaseModel):  # pylint: disable=too-few-public-methods
    """A reference to a resolved patient identity, never a match decision.

    ``patient_identity_ref`` is Adaptix's identity reference and
    ``external_patient_identity_ref`` the peer's, so both sides of an
    exchange can be correlated without either system having to adopt the
    other's identifier. ``match_confidence`` and ``match_status`` report what
    Adaptix-Patient-Identity-Service decided; carrying that decision is the
    whole of this contract's job, per this module's ownership note above.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    patient_identity_ref: str = Field(..., min_length=1)
    external_patient_identity_ref: str | None = None
    match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    match_status: str | None = None


__all__ = ["PatientIdentityReference"]
