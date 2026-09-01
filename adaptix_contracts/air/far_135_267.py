"""Single numeric authority for the 14 CFR 135.267 duty/rest floors shared by
Adaptix-Air-Service and Adaptix-Air-Service-Pilot.

Why this exists
----------------

Both HEMS duty engines independently declared the same two federal numbers:

* ``Adaptix-Air-Service/backend/air_app/far_135_267.py`` —
  ``DUTY_EXCEPTION_MAX_DUTY_HOURS = 14`` and ``REST_BEFORE_COMPLETION_HOURS = 10``
* ``Adaptix-Air-Service-Pilot/backend/air_pilot_app/far_135_267.py`` —
  ``MAX_DUTY_MINUTES_CEILING = 14 * 60`` and ``MIN_REST_MINUTES_FLOOR = 10 * 60``

Both cited 14 CFR 135.267 and, as of 2026-09-01, both agreed. Agreement was not
guaranteed: nothing prevented one file from being corrected (a citation fix, a
CFR amendment, a typo repair) without the other being touched, and the two
duty engines on this platform must never disagree about federal law. This
module is the one place either number is declared; both services import it
and derive whatever unit (hours or minutes) their own domain needs locally.

This is a deduplication fix, not a policy change. The values are transcribed,
not reinterpreted: 14 CFR 135.267(c) duty exception ("a regularly assigned
duty period of no more than 14 hours") and 135.267(d) rest-before-completion
("at least 10 consecutive hours of rest during the 24-hour period that
precedes the planned completion time of the assignment"). Do not change
either value without confirming the corresponding CFR text has actually
changed — this is not a tunable.

Authority
---------

Transcribed from the GPO print of the CFR, CFR-2016-title14-vol3-sec135-267,
verified 2026-08-15 (see the companion citation/history in each consuming
service's own ``far_135_267`` module).
"""

from __future__ import annotations

__all__ = [
    "DUTY_EXCEPTION_MAX_DUTY_HOURS",
    "REST_BEFORE_COMPLETION_HOURS",
]

#: 14 CFR 135.267(c) — the 14-hour duty-period exception: "a regularly
#: assigned duty period of no more than 14 hours".
DUTY_EXCEPTION_MAX_DUTY_HOURS: int = 14

#: 14 CFR 135.267(d) — the rest-before-completion floor: "at least 10
#: consecutive hours of rest during the 24-hour period that precedes the
#: planned completion time of the assignment". A floor, not a tier: a policy
#: or engine may require more rest, never less.
REST_BEFORE_COMPLETION_HOURS: int = 10
