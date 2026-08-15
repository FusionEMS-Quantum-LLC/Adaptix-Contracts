# Consumer bump matrix

This checklist tracks repos that currently call
`adaptix_contracts.gateway_signature.verify_gateway_signature` and therefore
must keep their signed test payloads and any direct producer code aligned with
the canonical `aud` claim requirement.

## Canonical `aud` rule

- The live Gateway signer already emits `aud`.
- The canonical value is the matched `RouteEntry.audience` string for the
  downstream service.
- The fleet pattern is `adaptix-<service>` (for example `adaptix-cad`).
- This is **not** the same as Cognito/JWT app-client audiences such as
  Billing's legacy `ADAPTIX_JWT_AUDIENCE=billing`. Gateway-signed `aud` is a
  downstream service-routing claim; Cognito `aud` is a token-client audience.
  Do not substitute one for the other.

Authoritative producer evidence came from Adaptix-Gateway:

- `backend/app/middleware/cognito_auth.py:1430-1435`
- `backend/app/services/auth_context.py:27-29`
- `backend/app/services/auth_context.py:188-201`
- `backend/app/services/auth_context.py:284`

## Migration guidance

| Repo | Representative caller(s) | Usage class | Required action |
| --- | --- | --- | --- |
| Adaptix-AssetOps-Service | `backend/assetops_app/gateway_context.py:113` | Production | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Core-Service | `core/backend/core_app/dependencies.py:36`, `core/backend/core_app/auth/dependencies.py:1140` | Production | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-EPCR-Service | `backend/epcr_app/demo/context.py:114` | Demo/runtime | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-OfficeAlly-Service | `backend/officeally_app/api/deps.py:65` | Production | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Device-Service | `backend/device_app/auth/__init__.py:203` | Production | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Graph-Service | `backend/graph_app/dependencies.py:44`, `backend/tests/_gateway_sign.py:7` | Production + helper test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Fire-Service | `backend/fire_app/cortex_ai_client.py:57`, `backend/tests/test_cortex_ai_signing.py:112` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-CRM-Service | `backend/crm_app/lead_scoring.py:80`, `backend/tests/test_lead_scoring.py:483` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-AI-Service | `backend/ai_app/governance_gate.py:120`, `backend/tests/test_ai_signed_identity_context.py:16` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Marketing-Service | `backend/marketing_app/copy_assist.py:97`, `backend/tests/test_copy_assist_ai_signing.py:185` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Analytics-Service | `backend/analytics_app/persistence_routes.py:109`, `backend/tests/test_ai_signing.py:99` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Communications-Service | `backend/communications_app/services/ai_service_client.py:21`, `backend/tests/test_ai_service_client_signing.py:102` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Workforce-Service | `backend/workforce_app/wellness_sentinel/sentinel.py:112`, `backend/tests/test_wellness_sentinel_ai_signing.py:147` | Production + test | **PR needed — verify prod signer emits matching `aud` before pin bump (safety-override).** |
| Adaptix-Billing-Service | `backend/tests/test_cortex_ai_hop_is_signed.py:76` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** Note: Billing's legacy `ADAPTIX_JWT_AUDIENCE=billing` is a separate Cognito/JWT layer and is not the Gateway-signed `aud` value. |
| Adaptix-CAD-Service | `backend/tests/test_ai_client_gateway_signing.py:86`, `backend/tests/test_cad_workforce_signed_headers.py:50`, `backend/cad_app/demo/context.py:185` | Test/demo | **PR needed — add `aud` to test payloads before pin bump.** CAD already discovered this in PR #285. |
| Adaptix-Hospital-Service | `backend/tests/test_hl7_client_signing.py:98` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Partner-Service | `backend/tests/conftest.py:85` | Test/helper | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Imports-Service | `backend/tests/test_dispatch.py:411` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-RTC-Service | `backend/tests/test_gateway_auth.py:64` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Labor-Service | `backend/tests/_gateway_signing_helpers.py:7`, `backend/tests/test_employee_identity_gate.py:952` | Test/helper | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Payments-Service | `backend/tests/test_gateway_audience_pinning.py:1` | Test-only | **No action — test-only coverage already centers the `aud` contract, but keep fixtures aligned when bumping pins.** |
| Adaptix-Training-Service | `backend/tests/test_auth_gateway_hmac.py:67` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Inventory-Service | `backend/tests/test_phase1_c9_inventory_auth.py:111` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-HL7-Service | `backend/tests/test_appsec_p0_p1_p2_hardening.py:79` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Crew-Service | `backend/tests/test_workforce_roster_sync.py:331` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |
| Adaptix-Operations-Service | `backend/tests/test_cortex_gateway_signing.py:95` | Test-only | **PR needed — add `aud` to test payloads before pin bump.** |

## Notes

- CAD is **not** a required consumer of the EPCR trio
  (`epcr.chart.amended`, `epcr.chart.finalized`,
  `epcr.nemsis_submit.succeeded`). Its queue-ack fix is separate.
- Billing's `EpcrChartAmendedEvent` failure was diagnosed as stale
  packaged/runtime state in the failing environment, not missing source in
  current `Adaptix-Contracts`.
- This matrix is a migration checklist, not blanket approval to bump every
  consumer immediately. Production callers must first verify that the live
  Gateway signer emits the matching route audience for their service.
- Consumers in this fleet currently pin `adaptix-contracts` by git revision,
  so the publish point for `2.7.0` is merged `main` plus tag `v2.7.0`.
