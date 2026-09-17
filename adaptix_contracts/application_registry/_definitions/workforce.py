"""WORKFORCE domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import (
    _GW,
    _WEB,
    _WF_SHELL,
)
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    _app,
    _ws,
)

WORKFORCE_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "workforce",
        "Workforce",
        "Staff the organization: scheduling, people, labor, HR, training, credentials and availability.",
        domain=ApplicationDomain.WORKFORCE,
        canonical_route="/workspace/workforce",
        modules=("workforce", "scheduling", "labor", "hr", "training"),
        primary_services=("adaptix-workforce", "adaptix-labor"),
        supporting_services=("adaptix-hr", "adaptix-training"),
        clients=("Adaptix-Android-Workforce",),
        workspaces=(
            _ws(
                "schedule",
                "Schedule",
                "/workspace/workforce/schedule",
                modules=("scheduling",),
            ),
            _ws(
                "ems_schedule",
                "EMS Schedule",
                "/workspace/workforce?section=ems-schedule",
                modules=("scheduling",),
            ),
            _ws(
                "shifts",
                "Shifts",
                "/workspace/workforce/shifts",
                modules=("scheduling",),
            ),
            _ws(
                "open_shifts",
                "Open Shifts",
                "/workspace/workforce/open-shifts",
                modules=("scheduling",),
            ),
            _ws(
                "shift_swaps",
                "Shift Swaps",
                "/workspace/workforce/shift-swaps",
                modules=("scheduling",),
            ),
            _ws(
                "time_off",
                "Time Off",
                "/workspace/workforce/time-off",
                modules=("scheduling",),
            ),
            _ws(
                "labor",
                "Labor",
                "/workspace/workforce?section=labor-overview",
                modules=("labor",),
            ),
            _ws(
                "overtime",
                "Overtime",
                "/workspace/workforce/overtime",
                modules=("labor",),
            ),
            _ws(
                "timecards",
                "Timecards",
                "/workspace/workforce/timecards",
                modules=("labor",),
            ),
            _ws(
                "time_clock",
                "Time Clock",
                "/workspace/workforce/time-clock",
                modules=("labor",),
            ),
            _ws(
                "payroll", "Payroll", "/workspace/workforce/payroll", modules=("labor",)
            ),
            # These live under app/workspace/workforce/layout.tsx, whose own gate
            # is ANY-OF workforce/scheduling/labor. They carry that gate
            # explicitly rather than inheriting the umbrella's (which also
            # admits hr and training for the two workspaces that live outside
            # the shell) — an HR-only tenant must not be offered the shell's
            # personnel, fatigue or command surfaces.
            _ws(
                "people", "People", "/workspace/workforce/directory", modules=_WF_SHELL
            ),
            _ws(
                "credentials",
                "Credentials",
                "/workspace/workforce/credentials",
                modules=_WF_SHELL,
            ),
            _ws(
                "certifications",
                "Certifications",
                "/workspace/workforce/certifications",
                modules=_WF_SHELL,
            ),
            _ws(
                "availability",
                "Availability",
                "/workspace/workforce/availability",
                modules=_WF_SHELL,
            ),
            _ws(
                "fatigue", "Fatigue", "/workspace/workforce/fatigue", modules=_WF_SHELL
            ),
            _ws(
                "readiness",
                "Readiness",
                "/workspace/workforce/readiness",
                modules=_WF_SHELL,
            ),
            _ws(
                "mission_command",
                "Mission Command",
                "/workspace/workforce/mission-command",
                modules=_WF_SHELL,
            ),
            _ws("hr", "HR", "/workspace/hr", modules=("hr",)),
            _ws("training", "Training", "/workspace/training", modules=("training",)),
        ),
        source=(
            f"{_WEB} (app/workspace/workforce/layout.tsx gates ANY-OF "
            "workforce/scheduling/labor; /workspace/training gates 'training'); "
            f"{_GW} /api/v1/workforce -> adaptix-workforce + adaptix-labor, "
            "/api/v1/scheduling AND /api/v1/labor -> adaptix-labor, /api/v1/hr -> "
            "adaptix-hr, /api/v1/training -> adaptix-training. The application "
            "is offered when ANY of its products is held (an HR-only tenant has "
            "/workspace/hr today and must still find it); entitlements stay "
            "separate per workspace: a scheduling-only tenant sees the Schedule "
            "workspaces, never Labor, HR or Training (module_registry: "
            "scheduling implies none of them)."
        ),
    ),
)
