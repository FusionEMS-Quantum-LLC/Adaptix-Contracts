# ECS Container-Metadata Fallback Pattern for `/version`

**Status:** stable — adopted in `Adaptix-CAD-Service` (PR #287, `828034a`) and `Adaptix-Payments-Service` (PR #33, `6835cca`).
**Owner:** any service that exposes a `/version` endpoint and runs on ECS.
**Origin:** Josh directive 2026-08-14 — zero-fabrication + operational-application. General-chat cross-lane recommendation 2026-08-15.

---

## 1. Problem the pattern solves

Services expose `/version` so operators can prove code-in-prod against a git ref without reading a task definition or an ECR tag list. Historically the endpoint has read only from task-definition environment variables (e.g. `GIT_COMMIT_SHA`, `PAYMENTS_GIT_SHA`, `BUILD_TIMESTAMP`, `IMAGE_TAG`).

When those env vars have not been wired yet — for example while a fleet-wide canonical env-var rollout is still in progress in Infra — every service's `/version` returns:

```json
{"service": "...", "git_sha": "unknown", "build_time": "unknown", "image_tag": "unknown"}
```

That is truthful, but it leaves the operator without a runtime source of build identity, and forces them out-of-band to `aws ecs describe-task-definition` to correlate a deploy with a merge SHA.

The running container already **knows** its own image tag. AWS injects `ECS_CONTAINER_METADATA_URI_V4` into every task container, and the response contains the running image reference including its tag. If the pipeline embeds `{commit_sha}` in the tag, that tag is proof of the deployed code.

## 2. Precedence (zero-fabrication)

The endpoint composes its payload in this fixed order:

1. **Explicit env vars** (e.g. `PAYMENTS_GIT_SHA`, `PAYMENTS_BUILD_TIME`, `PAYMENTS_IMAGE_TAG`). Wins when Infra wiring lands. Canonical.
2. **ECS container-metadata fallback**. Parses the running container's own image tag using a strict regex. If any part fails, returns empty triple.
3. **Truthful `"unknown"` string**. Final honest fallback.

**No SHA is ever fabricated.** Every value is env, from the running container's own image tag, or the literal `"unknown"` string.

## 3. Reference implementations

- Adaptix-CAD-Service PR #287 (`backend/cad_app/main.py`) — the canonical fleet pattern.
- Adaptix-Payments-Service PR #33 (`backend/payments_app/api/health.py`) — second adopter, extends to 3-field payload (`git_sha`, `build_time`, `image_tag`) and adds targeted Bandit B310 suppression (see §5).

## 4. Portable Python sketch

```python
import json
import os
import re
import urllib.error
import urllib.request

_IMAGE_TAG_PATTERN = re.compile(
    r"^(?P<commit>[0-9a-f]{7,40})-(?P<environment>[A-Za-z0-9_-]+)-(?P<timestamp>\d{8}T\d{6}Z)$"
)


def _version_from_container_metadata() -> tuple[str, str, str]:
    """(commit, timestamp, full_tag) or empty triple on any failure."""
    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4", "").strip()
    if not metadata_uri:
        return "", "", ""
    try:
        # Bandit B310 justification below (see §5).
        with urllib.request.urlopen(metadata_uri, timeout=1.0) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, urllib.error.URLError):
        return "", "", ""
    image = str(payload.get("Image") or "").strip()
    if ":" not in image:
        return "", "", ""
    tag = image.rsplit(":", 1)[-1]
    match = _IMAGE_TAG_PATTERN.fullmatch(tag)
    if match is None:
        return "", "", ""
    return match.group("commit"), match.group("timestamp"), tag
```

## 5. Bandit B310 note for services with `-ll` security-scan config

Services running `bandit -r <app> -ll` (Payments, and any other lane whose `.codebuild/security-scan.yml` reports Medium+ severity) will fail the security-scan gate on the `urllib.request.urlopen` call — Bandit rule **B310** is Medium severity.

**Adoption rule for those services:**

- Add a **targeted** `# nosec B310` comment on the `urlopen` line only. Do **not** broadly suppress B310 project-wide.
- Include a **truthful in-code justification** documenting why the URL is not attacker-controlled.

Payments' justification (verbatim, portable to any adopter):

```python
# Bandit B310: the URL is not attacker-controlled. It comes from the
# ECS agent via ``ECS_CONTAINER_METADATA_URI_V4`` — an AWS-managed env
# variable injected into every task container. Only the running
# container's own image metadata is read. There is no tenant, gateway,
# or webhook path that can influence this value. 1s timeout bounds the
# call and every exception falls through to the truthful ``unknown``
# fallback rather than fabricate a SHA.
with urllib.request.urlopen(metadata_uri, timeout=1.0) as response:  # nosec B310
    payload = json.loads(response.read().decode("utf-8"))
```

**Services whose security-scan config already runs `bandit -l` (Low+) or has different exclusions may not need this.** Adaptix-CAD-Service (PR #287) did not need a `nosec` under its own config.

The `nosec` is safe because:

- The URL comes from an AWS-controlled env variable, not user input.
- Only the running container's own image metadata is read.
- 1-second timeout bounds the network call.
- Any exception falls through to `"unknown"` — no fabricated value is ever produced.

## 6. Adoption checklist

- [ ] Copy the sketch in §4 into your service's health/version module.
- [ ] Adjust the returned payload shape to match your existing `/version` schema (2 fields, 3 fields, etc.).
- [ ] Make explicit env vars take precedence over the metadata fallback.
- [ ] If your build pipeline uses a different tag format, adjust `_IMAGE_TAG_PATTERN` accordingly. It MUST still be strict — a permissive regex re-introduces fabrication surface.
- [ ] Add tests: env-vars-win, env-missing-metadata-wins, URLError → `"unknown"`, malformed tag → `"unknown"`, missing metadata env → `"unknown"`.
- [ ] If your security-scan runs `bandit -ll` or stricter, add the targeted `# nosec B310` with in-code justification from §5.
- [ ] Confirm the pattern still returns `"unknown"` under every failure path — no exception may fabricate a partial value.

## 7. What the pattern is NOT

- **Not a replacement for Infra env-var wiring.** Env vars remain canonical and win when present. The fallback exists so `/version` is useful *while* the wiring is being rolled out fleet-wide.
- **Not a security boundary.** The endpoint is anonymous and reports only build identity that is already provable from ECR and CloudTrail.
- **Not a caching layer.** The metadata endpoint is fast and local; caching adds staleness risk and is unnecessary at `/version` traffic levels.

## 8. Change control

Loosening the image-tag regex, removing the timeout, or broadening the `nosec` scope requires an explicit PR justification. Removing the pattern once adopted requires operator sign-off.
