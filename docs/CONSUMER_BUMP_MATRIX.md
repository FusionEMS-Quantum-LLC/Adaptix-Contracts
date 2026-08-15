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

Authoritative producer evidence came from Adaptix-Gateway:

- `backend/app/middleware/cognito_auth.py:1430-1435`
- `backend/app/services/auth_context.py:27-29`
- `backend/app/services/auth_context.py:188-201`
- `backend/app/services/auth_context.py:284`

## Migration guidance

| Repo | Representative caller | Usage class | Required action |
| --- | --- | --- | --- |
| Adaptix-AssetOps-Service | `backend/assetops_app/gateway_context.py` | Production | Verify requests validated here carry the route audience string and update synthetic/test payloads to include `aud`. |
| Adaptix-Core-Service | `core/backend/core_app/dependencies.py` | Production | Verify all direct calls and tests include `aud`; Core owns several auth/support surfaces. |
| Adaptix-EPCR-Service | `backend/epcr_app/demo/context.py` | Demo/runtime | Ensure demo-context signed payloads include `aud`. |
| Adaptix-OfficeAlly-Service | `backend/officeally_app/api/deps.py` | Production | Verify signed payloads include `aud`. |
| Adaptix-Device-Service | `backend/device_app/auth/__init__.py` | Production | Verify signed payloads include `aud`. |
| Adaptix-Graph-Service | `backend/graph_app/dependencies.py` | Production | Verify signed payloads include `aud`; update helper tests under `backend/tests/_gateway_sign.py`. |
| Adaptix-Fire-Service | `backend/fire_app/cortex_ai_client.py` | Production | Verify signed payloads include `aud`; update `test_cortex_ai_signing.py`. |
| Adaptix-CRM-Service | `backend/crm_app/lead_scoring.py` | Production | Verify signed payloads include `aud`; update `test_lead_scoring.py`. |
| Adaptix-AI-Service | `backend/ai_app/governance_gate.py` | Production | Verify signed payloads include `aud`; update `test_ai_signed_identity_context.py`. |
| Adaptix-Marketing-Service | `backend/marketing_app/copy_assist.py` | Production | Verify signed payloads include `aud`; update `test_copy_assist_ai_signing.py`. |
| Adaptix-Analytics-Service | `backend/analytics_app/persistence_routes.py` | Production | Verify signed payloads include `aud`; update `test_ai_signing.py`. |
| Adaptix-Communications-Service | `backend/communications_app/services/ai_service_client.py` | Production | Verify signed payloads include `aud`; update `test_ai_service_client_signing.py`. |
| Adaptix-Workforce-Service | `backend/workforce_app/wellness_sentinel/sentinel.py` | Production | Verify signed payloads include `aud`; update `test_wellness_sentinel_ai_signing.py`. |
| Adaptix-Operations-Service | `backend/tests/test_cortex_gateway_signing.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-Billing-Service | `backend/tests/test_cortex_ai_hop_is_signed.py` | Test-only | Update synthetic signed payloads to include `aud` whenever this Contracts bump is consumed. |
| Adaptix-CAD-Service | `backend/tests/test_ai_client_gateway_signing.py` | Test-only | Already discovered in CAD PR #285; keep `aud` in synthetic signed payloads. |
| Adaptix-Hospital-Service | `backend/tests/test_hl7_client_signing.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-Partner-Service | `backend/tests/conftest.py` | Test-only | Update helper payloads to include `aud`. |
| Adaptix-Imports-Service | `backend/tests/test_dispatch.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-RTC-Service | `backend/tests/test_gateway_auth.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-Labor-Service | `backend/tests/_gateway_signing_helpers.py` | Test/helper | Update shared helper payloads to include `aud`. |
| Adaptix-Payments-Service | `backend/tests/test_gateway_audience_pinning.py` | Test-only | Keep synthetic signed payloads aligned with the canonical audience rule. |
| Adaptix-Training-Service | `backend/tests/test_auth_gateway_hmac.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-Inventory-Service | `backend/tests/test_phase1_c9_inventory_auth.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-HL7-Service | `backend/tests/test_appsec_p0_p1_p2_hardening.py` | Test-only | Update synthetic signed payloads to include `aud`. |
| Adaptix-Crew-Service | `backend/tests/test_workforce_roster_sync.py` | Test-only | Update synthetic signed payloads to include `aud`. |

## Notes

- CAD is **not** a required consumer of the EPCR trio
  (`epcr.chart.amended`, `epcr.chart.finalized`,
  `epcr.nemsis_submit.succeeded`). Its queue-ack fix is separate.
- Billing's `EpcrChartAmendedEvent` failure was diagnosed as stale
  packaged/runtime state in the failing environment, not missing source in
  current `Adaptix-Contracts`.
- Consumers in this fleet currently pin `adaptix-contracts` by git revision,
  so the publish point for `2.7.0` is merged `main` plus tag `v2.7.0`.
