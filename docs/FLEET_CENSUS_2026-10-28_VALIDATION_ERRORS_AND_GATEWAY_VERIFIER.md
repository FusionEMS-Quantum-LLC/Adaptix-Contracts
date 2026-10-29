# Fleet census, 2026-10-28: input-free 422 answers (#375) and the unbound gateway verifier (#397, Governance #347)

Read-only evidence. Every row was measured on the `origin/main` of the named
repository as fetched into the workspace on 2026-10-28 (short SHA in the
second column), by exporting that ref with `git archive` and scanning the
export; no checkout's working tree was read. Test files, `tests/` trees,
virtual environments and vendored code were excluded. Android, docs,
governance and other repositories without a `FastAPI(` app or a verifier
finding are not listed. 108 repositories were exported; 85 appear below.

## 1. Services and their `RequestValidationError` handler (Contracts #375)

Method: a repository counts as having a FastAPI app when a non-test Python
file calls `FastAPI(`. Its handler status is:

- **installer**: calls `adaptix_contracts.validation_errors.install_input_free_validation_errors`;
- **own handler**: registers a `RequestValidationError` handler itself
  (`@app.exception_handler(RequestValidationError)`,
  `add_exception_handler(RequestValidationError, ...)` or the
  `exception_handlers=` keyword). Whether that handler drops `input` was not
  read here; Gateway #379, Integrations #335 and Transport #350 are known to,
  and Billing, CAD and EPCR (`error_handlers.py`) and Core and
  Patient-Identity (`phi_safe_errors`) were listed as such in the issue;
- **none**: FastAPI's default answer, which repeats the caller's input.

A service that only installs `phi_safe_logging` (Communications, Cortex,
Hospital, OfficeAlly, Payments, Workforce) is **none**: that guards the log
line, not the 422 body.

**Counts: 85 repositories with a FastAPI app; installer 0, own handler 13,
none 72.** Of the 72, three are not services (adaptix-ops, Adaptix-Web-App,
Adaptix-Field-App) and need reading before they count, leaving **69 services
on the framework default**. Adoption of the installer by a service: **0** (an
org code search on 2026-10-28 agreed). Adaptix-Contracts itself is not a row:
the scan matched `adaptix_contracts/validation_errors.py`, but its only
`FastAPI(` is the docstring text "after ``FastAPI(...)``" and its installer
match is the definition of `install_input_free_validation_errors`, not an app
that calls it (the package's test apps are excluded with every other test
file).

| Repository | origin/main | `FastAPI(` files | Handler | Where |
| --- | --- | --- | --- | --- |
| Adaptix-AI-Service | `be2d18e` | 1 | none |   |
| Adaptix-Air-Service | `06f5b13` | 1 | none |   |
| Adaptix-Air-Service-Pilot | `09d9167` | 1 | none |   |
| Adaptix-Analytics-Service | `96f245e` | 1 | none |   |
| Adaptix-App-Management-Service | `516e1d7` | 1 | none |   |
| Adaptix-AssetOps-Service | `d750a2f` | 1 | none |   |
| Adaptix-Audit-Service | `ff15a0a` | 1 | none |   |
| Adaptix-Bedrock-Service | `94f4466` | 1 | none |   |
| Adaptix-Billing-Service | `eb9fab7` | 1 | own handler | `backend/billing_app/error_handlers.py`  |
| Adaptix-CAD-Service | `2198dba` | 1 | own handler | `backend/cad_app/error_handlers.py`  |
| Adaptix-CCT-Service | `0225a71` | 1 | own handler | `backend/cct_app/main.py`  |
| Adaptix-CRM-Service | `1cc2fae` | 1 | none |   |
| Adaptix-CRR-Service | `225a6cb` | 1 | none |   |
| Adaptix-Calendar-Service | `b95092d` | 1 | none |   |
| Adaptix-Communications-Service | `1088e59` | 2 | none |   |
| Adaptix-Compliance-Service | `7c2786d` | 1 | none |   |
| Adaptix-Core-Service | `b067e21` | 3 | own handler | `core/backend/core_app/error_handlers.py`  |
| Adaptix-Cortex-Service | `324e37d` | 1 | none |   |
| Adaptix-Crew-Service | `50a1b7d` | 1 | none |   |
| Adaptix-Customer-Success-Service | `bf59510` | 1 | none |   |
| Adaptix-Device-Service | `2fcee28` | 1 | none |   |
| Adaptix-Documents-Service | `2230660` | 1 | none |   |
| Adaptix-EPCR-Service | `870dfe8` | 1 | own handler | `backend/epcr_app/error_handlers.py`  |
| Adaptix-Edge-Service | `82e48a2` | 1 | none |   |
| Adaptix-Exports-Service | `7e38906` | 1 | none |   |
| Adaptix-Facility-Registry-Service | `bcc73dd` | 1 | none |   |
| Adaptix-Field-App | `02f08d7` | 1 | none |  non-service / needs reading before it counts |
| Adaptix-Finance-Service | `34dbb2e` | 1 | none |   |
| Adaptix-Fire-Service | `30c3e11` | 1 | none |   |
| Adaptix-Fleet-Service | `17744d6` | 1 | none |   |
| Adaptix-Forms-Service | `2e9fe21` | 1 | none |   |
| Adaptix-Founder-Service | `96beca5` | 1 | none |   |
| Adaptix-Gateway | `a480353` | 1 | own handler | `backend/app/main.py`  |
| Adaptix-Geo-Service | `196019e` | 1 | none |   |
| Adaptix-Governance-Service | `2e38dc1` | 1 | none |   |
| Adaptix-Graph-Service | `7e57117` | 1 | none |   |
| Adaptix-HL7-Service | `a9536c4` | 1 | none |   |
| Adaptix-HR-Service | `47923d9` | 1 | none |   |
| Adaptix-Hospital-Service | `fc7cef5` | 1 | none |   |
| Adaptix-Hydrant-Service | `511fd35` | 1 | none |   |
| Adaptix-Imports-Service | `19c930c` | 1 | none |   |
| Adaptix-Integrations-Service | `b0e2474` | 3 | own handler | `backend/integrations_app/main.py`  |
| Adaptix-Inventory-Service | `0545b4f` | 1 | none |   |
| Adaptix-Investor-Service | `9f65fe6` | 1 | none |   |
| Adaptix-Labor-Service | `2f282eb` | 1 | own handler | `backend/labor_app/error_handlers.py`  |
| Adaptix-Legal-Service | `db7e21b` | 1 | none |   |
| Adaptix-MCP-Service | `12c95bb` | 1 | none |   |
| Adaptix-MIH-Service | `fd870e5` | 1 | none |   |
| Adaptix-Mailroom-Service | `3f59688` | 1 | none |   |
| Adaptix-Marketing-Service | `7af69e4` | 1 | none |   |
| Adaptix-Media-Service | `b0870d9` | 1 | none |   |
| Adaptix-Medications-Service | `97c15ad` | 1 | none |   |
| Adaptix-NEMSIS-Service | `a6b8e67` | 1 | own handler | `backend/nemsis_app/error_handlers.py`  |
| Adaptix-NERIS-Service | `d149d2d` | 1 | none |   |
| Adaptix-Narcotics-Service | `15032c8` | 1 | none |   |
| Adaptix-Notifications-Service | `4edafb3` | 1 | none |   |
| Adaptix-Office-Service | `084a9ae` | 1 | none |   |
| Adaptix-OfficeAlly-Service | `1244163` | 2 | none |   |
| Adaptix-Operations-Service | `fce55bd` | 1 | none |   |
| Adaptix-Partner-Service | `48fa6a4` | 1 | none |   |
| Adaptix-Patient-Identity-Service | `3f9588e` | 1 | own handler | `backend/patient_identity_app/main.py`  |
| Adaptix-Payments-Service | `424abc9` | 1 | none |   |
| Adaptix-Policy-Service | `277e488` | 1 | none |   |
| Adaptix-Preplan-Service | `c850450` | 1 | none |   |
| Adaptix-Pricing-Service | `c029288` | 1 | none |   |
| Adaptix-QA-Service | `b87f95c` | 1 | none |   |
| Adaptix-QHIN-Service | `c68b357` | 1 | none |   |
| Adaptix-RTC-Service | `529c775` | 1 | none |   |
| Adaptix-Reference-Data-Service | `9da51fd` | 1 | none |   |
| Adaptix-SageMaker-Service | `08745de` | 1 | none |   |
| Adaptix-Search-Service | `4c416ca` | 1 | none |   |
| Adaptix-SignalCore-Service | `0c49dc6` | 1 | none |   |
| Adaptix-Social-Service | `7eeeb1e` | 1 | none |   |
| Adaptix-Telephony-Service | `f5ced7c` | 1 | own handler | `backend/telnyx_app/main.py`  |
| Adaptix-Terminology-Service | `fac2e47` | 1 | none |   |
| Adaptix-Training-Service | `16cc0a0` | 1 | own handler | `backend/training_app/main.py`  |
| Adaptix-Transport-Service | `47da21d` | 1 | own handler | `backend/transportlink_app/main.py`  |
| Adaptix-TrustSign-Service | `42ea617` | 1 | none |   |
| Adaptix-Vision-Service | `a52beed` | 1 | none |   |
| Adaptix-Voice-Service | `1bc19c2` | 1 | none |   |
| Adaptix-Web-App | `630162c` | 1 | none |  non-service / needs reading before it counts |
| Adaptix-Wildland-Service | `7f9c8f7` | 1 | none |   |
| Adaptix-Workforce-Service | `6d0bcdf` | 1 | none |   |
| Adaptix-XR-Service | `097e917` | 1 | none |   |
| adaptix-ops | `f26d55c` | 4 | none |  non-service / needs reading before it counts |

Next action per service lane, unchanged from the issue: in the PR that repins
`adaptix-contracts` to a release at or above 5.47.0 (5.48.0 adds the
server-side handlers), add `install_input_free_validation_errors(app)` in the
app factory and a test that a refused request with a PHI-shaped body answers
without `input`.

## 2. Unbound gateway verifier and `get_auth_context` without the request (Contracts #397, Governance #347)

Method: `scripts/check_unbound_gateway_verifier.py` from this change, run
with no allowlist against each export. It reports any import or use of
`verify_gateway_signature` or `gateway_identity.verify`, and any call of
`get_auth_context` (or an import alias of it) that passes neither `request=`
nor the request as its first positional argument (`request` or
`<x>.request`); `*args` and `**kwargs` calls are not provable and not
reported. The request-first exemption is new in this change: the checker on
`main` reported Billing's `get_auth_context(request, authorization=..., ...)`
as unbound although the request is its first positional argument. Any other
positional call is still reported, because the contracts dependency's header
parameters are positional-or-keyword and its `request` parameter is last.

**Findings on 2026-10-28: 4 repositories, 8 sites** under the rule from this
change (Audit, Contracts, Core, Voice). The table also keeps the two Billing
rows that only the rule on `main` reports, marked as such: **5 repositories,
10 rows under that rule.**

| Repository | origin/main | Finding |
| --- | --- | --- |
| Adaptix-Audit-Service | `ff15a0a` | `backend/audit_app/api/gateway_auth.py:51: unbound-verifier (import from adaptix_contracts.gateway_signature)` |
| Adaptix-Audit-Service | `ff15a0a` | `backend/audit_app/api/gateway_auth.py:274: unbound-verifier (use)` |
| Adaptix-Billing-Service | `eb9fab7` | `backend/billing_app/api/cortex_tools.py:157: get-auth-context-without-request (plain call)` — rule on `main` only; request is the first positional argument, not a finding under this change |
| Adaptix-Billing-Service | `eb9fab7` | `backend/billing_app/api/dependencies.py:956: get-auth-context-without-request (plain call)` — rule on `main` only; request is the first positional argument, not a finding under this change |
| Adaptix-Contracts | `3c13f3a` | `adaptix_contracts/gateway_identity/__init__.py:32: unbound-verifier (import from adaptix_contracts.gateway_signature)` |
| Adaptix-Contracts | `3c13f3a` | `adaptix_contracts/gateway_identity/__init__.py:243: unbound-verifier (use)` |
| Adaptix-Core-Service | `b067e21` | `core/backend/core_app/auth/gateway_context.py:80: unbound-verifier (import from adaptix_contracts.gateway_signature)` |
| Adaptix-Core-Service | `b067e21` | `core/backend/core_app/auth/gateway_context.py:262: unbound-verifier (use)` |
| Adaptix-Voice-Service | `1bc19c2` | `backend/voice_app/api/auth.py:133: get-auth-context-without-request (plain call)` |
| Adaptix-Voice-Service | `1bc19c2` | `backend/voice_app/api/auth.py:178: get-auth-context-without-request (plain call)` |

Reading of each:

- **Adaptix-Audit-Service** `backend/audit_app/api/gateway_auth.py:274`: an
  HTTP request-authentication path still on the deprecated name. Audit #155
  (2026-10-18 comment on #397) carries the fix; it is not on `main` yet.
- **Adaptix-Core-Service** `core/backend/core_app/auth/gateway_context.py:262`:
  the documented no-request arm; every HTTP caller passes the request
  (`:255-261`). It renames to
  `verify_gateway_signature_without_request_binding` once Core repins (its
  pin predates 5.45.0).
- **Adaptix-Voice-Service** `backend/voice_app/api/auth.py:133` and `:178`:
  the contracts `get_auth_context`, imported as `_get_auth_context`, called
  without `request=` from the HTTP dependency and from the WebSocket resolver
  (`api/calls.py:759` calls the latter). These are the two Voice rows of
  Governance #347 and are still open.
- **Adaptix-Contracts** `adaptix_contracts/gateway_identity/__init__.py`: the
  overlap-period re-export, on the repository's own allowlist.

The remaining Governance #347 rows were also re-read with the issue's own
method (a call passing `x_adaptix_auth_signature=` and no `request=`):
Analytics (`auth.py:218`), Calendar (`auth.py:208`), Device
(`routes_app_releases.py:339`), Finance (`auth.py:375`), HL7
(`api/dependencies.py:241`), Labor (`dependencies.py:373`), NEMSIS
(`auth.py:230`), Partner (`auth.py:377`) and Training (`auth.py:191`) all
build a header block and then call the canonical dependency **with**
`request=request` whenever a request exists (`if request is None:` ...
`else: ...(**headers, request=request)`); HR (`auth.py:257`), Imports
(`auth.py:278`) and Media (`auth.py:278`) pass `request=request` directly.
Those twelve are closed on `main`. Billing's two sites pass the request
positionally to its own wrapper. **Open from #347: Voice only.**

## 3. What this census does not say

It does not say whether a service's own `RequestValidationError` handler is
input-free, whether an unbound verifier site is reachable from a route in
production, or what any service runs in production; it reads source on
`origin/main` only. Deployed-state evidence for the verifier class is in the
2026-10-15 comment on #397.
