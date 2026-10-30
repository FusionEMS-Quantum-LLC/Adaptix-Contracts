# Migrating off the unbound gateway verifier (Contracts #397)

`adaptix_contracts.gateway_signature.verify_gateway_signature` and its alias
`adaptix_contracts.gateway_identity.verify` are deprecated since 5.45.0 and are
removed in the next major release (`DEPRECATION_POLICY.md`, rule 5). Behaviour
is unchanged for the whole overlap.

## Why

The verifier checks the gateway's signed `method`/`path` claims only when its
caller passes `request_method` and `request_path`. Called without them, a
context the gateway signed for `GET /a` verifies identically on `DELETE /b` of
the same audience, and the short name does not say so. AssetOps #163 showed
the cost: a context signed for `/work-orders/` resolved an identity on
`/vendors/`. The in-process replay cache does not cover that gap on a service
with more than one task.

## What to call instead

| Where the call runs | Replacement |
| --- | --- |
| An HTTP route or dependency (the served `Request` is available) | `verify_gateway_signature_for_request(request, context_b64=..., signature_hex=..., shared_secret=..., auth_path=..., key_id=...)`. It binds the real method and path and verifies once per request. |
| A FastAPI dependency built on the canonical identity dependency | Resolve `adaptix_contracts.auth_contracts.get_auth_context` through `Depends(...)`, or call it with `request=request`. A call without `request=` runs the unbound path (Governance #347); so does a positional call, because the dependency's `request` parameter is last. |
| Code no route can reach: a worker, a CLI, an in-process caller | `verify_gateway_signature_without_request_binding(context_b64=..., signature_hex=..., ...)`, with a comment at the call site saying why no route reaches it. Under `ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH` a bound context fails closed there, because that caller can never check it. |

Both replacements take the same keyword arguments as the deprecated name
minus `request_method`/`request_path` (`for_request` reads them from the
request; `without_request_binding` has none).

Before binding an HTTP path, confirm the path the gateway signs is the path
the service sees: no prefix rewrite and no `root_path` between them. The
services already on `for_request` are the evidence that it holds for the
fleet's standard mount; a service that rewrites paths in middleware (EPCR
rewrites `/api/epcr/...` to `/api/v1/epcr/...`) binds the pre-rewrite path it
captured in `scope`. A binding that refuses real traffic is an outage, not a
fix. Each migration PR carries a test that a context signed for `GET /a` is
refused on `GET /b` and served on `GET /a`, failing on the PR's own base.

## How the deprecation is enforced (5.48.0)

1. **Type level (PEP 702).** Both deprecated names carry `@deprecated(...)`.
   mypy reports every import, alias and attribute reference once the
   `deprecated` error code is on; pyright reports them under
   `reportDeprecated`; editors strike the names through. Enable it in the
   consumer:

   ```toml
   [tool.mypy]
   enable_error_code = ["deprecated"]
   ```

   ```json
   { "reportDeprecated": "error" }
   ```

   The message names both replacements and this issue.

2. **Runtime, opt-in only.** There is no `DeprecationWarning` by default:
   consumers run their suites under `-W error` and would fail the moment they
   repin, which the overlap exists to avoid. To list a service's own call
   sites by file and line, run its suite once with
   `ADAPTIX_GATEWAY_WARN_UNBOUND_VERIFIER=1` (also `true`/`yes`/`on`); each
   deprecated call then warns with `stacklevel` pointing at the caller.

3. **CI.** `scripts/check_unbound_gateway_verifier.py` parses Python with
   `ast` and refuses any use of the deprecated names, or a
   `get_auth_context(...)` call that passes neither `request=` nor the
   request as its first positional argument (`*args`/`**kwargs` calls are
   not provable and not reported), unless the site is on an allowlist with a
   reason. It runs from
   `scripts/ci/verify-toolchain.sh` here, and any service can run it against
   its own tree: `python scripts/check_unbound_gateway_verifier.py <root>`.

## Per-lane checklist

- [ ] Run the checker (3) and, if useful, the opt-in warning (2) against the
      service tree; list every site.
- [ ] HTTP sites: switch to `verify_gateway_signature_for_request(request, ...)`
      or pass `request=` to `get_auth_context`; add the cross-route refusal test.
- [ ] Non-HTTP sites: switch to `verify_gateway_signature_without_request_binding`
      and write the reason at the call site.
- [ ] Dead imports: delete.
- [ ] Enable the `deprecated` error code in the service's mypy or pyright
      config so the name cannot come back unnoticed.
- [ ] Repin `adaptix-contracts` to a release at or above 5.48.0.

The fleet state as of 2026-10-28 is in
`docs/FLEET_CENSUS_2026-10-28_VALIDATION_ERRORS_AND_GATEWAY_VERIFIER.md`.
