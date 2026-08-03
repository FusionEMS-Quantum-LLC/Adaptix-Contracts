from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import boto3
import yaml


ROOT = pathlib.Path.cwd()
REPORT = ROOT / "bedrock-repair-report.md"
PATCH_ARTIFACT = ROOT / "bedrock-repair.patch"
VALIDATION_LOG = ROOT / "bedrock-validation.log"
CALLER_IDENTITY = ROOT / "bedrock-caller-identity.txt"
CHANGED_FILES = ROOT / "bedrock-changed-files.txt"

FORBIDDEN_FILE_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
}

SECRET_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"aws_secret_access_key\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"AWS_ACCESS_KEY_ID\s*[:=]\s*['\"]?[A-Z0-9]{16,}", re.IGNORECASE),
    re.compile(
        r"AWS_SECRET_ACCESS_KEY\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{20,}", re.IGNORECASE
    ),
]

ALLOWED_MODEL_PREFIXES = (
    "us.anthropic.",
    "anthropic.",
    "us.amazon.",
    "amazon.",
)

# The complete catalogue of command lines this module is permitted to execute.
#
# Allowlisting only ``argv[0]`` is not sufficient. Every executable this module
# needs also accepts arguments that are themselves arbitrary-execution
# primitives — ``python -c '<code>'``, ``git -c core.pager='sh -c <code>' log``,
# ``npm run <arbitrary-script>`` — so a caller that assembled a command from
# repository content, Bedrock model output, or environment input could still
# reach a process-spawn sink while passing an executable-name check. Pinning the
# WHOLE argv removes that flow: no argument position is caller-controlled, so
# there is nothing left to inject into.
#
# ``git apply`` is listed with both the absolute artifact path (the form this
# module issues) and the bare filename. Every spawn runs with ``cwd=ROOT``, so
# the two name the same file.
_PATCH_ARTIFACT_ARGS = (str(PATCH_ARTIFACT), PATCH_ARTIFACT.name)

# I/O options shared by every ``subprocess.run`` call site below. ``shell`` is
# pinned here rather than restated 15 times, so no spawn in this module can hand
# an argument to a shell to reparse. ``check`` is deliberately NOT in here: it is
# passed explicitly at every call site so the spawn's failure mode is readable
# where it happens.
_SPAWN_IO: dict[str, Any] = {
    "cwd": ROOT,
    "text": True,
    "capture_output": True,
    "shell": False,
}

_Runner = Callable[[int], "subprocess.CompletedProcess[str]"]


def _git_apply(patch: str) -> _Runner:
    """Build the runner for ``git apply <patch>``."""
    return lambda t: subprocess.run(
        ["git", "apply", patch], **_SPAWN_IO, timeout=t, check=False
    )


def _git_apply_check(patch: str) -> _Runner:
    """Build the runner for ``git apply --check <patch>``."""
    return lambda t: subprocess.run(
        ["git", "apply", "--check", patch], **_SPAWN_IO, timeout=t, check=False
    )


# The complete catalogue: every command line this module may execute, mapped to
# the runner that executes it.
#
# The argv appears twice per entry - once as the key and once as the literal
# passed to ``subprocess.run``. That duplication is deliberate and load-bearing:
# the key is what ``validated_argv`` matches against, and the literal is what
# reaches the spawn, so no runtime-assembled value is ever handed to
# ``subprocess.run``. A test drives every runner and asserts the two agree.
_COMMAND_RUNNERS: dict[tuple[str, ...], _Runner] = {
    ("git", "ls-files"): lambda t: subprocess.run(
        ["git", "ls-files"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("git", "status", "--short"): lambda t: subprocess.run(
        ["git", "status", "--short"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("git", "diff", "--name-only"): lambda t: subprocess.run(
        ["git", "diff", "--name-only"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("python", "-m", "compileall", "."): lambda t: subprocess.run(
        ["python", "-m", "compileall", "."], **_SPAWN_IO, timeout=t, check=False
    ),
    ("ruff", "check", "."): lambda t: subprocess.run(
        ["ruff", "check", "."], **_SPAWN_IO, timeout=t, check=False
    ),
    ("ruff", "check", ".", "--fix"): lambda t: subprocess.run(
        ["ruff", "check", ".", "--fix"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("ruff", "format", "--check", "."): lambda t: subprocess.run(
        ["ruff", "format", "--check", "."], **_SPAWN_IO, timeout=t, check=False
    ),
    ("ruff", "format", "."): lambda t: subprocess.run(
        ["ruff", "format", "."], **_SPAWN_IO, timeout=t, check=False
    ),
    ("pytest", "-q"): lambda t: subprocess.run(
        ["pytest", "-q"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("npm", "run", "lint", "--if-present"): lambda t: subprocess.run(
        ["npm", "run", "lint", "--if-present"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("npm", "run", "typecheck", "--if-present"): lambda t: subprocess.run(
        ["npm", "run", "typecheck", "--if-present"], **_SPAWN_IO, timeout=t, check=False
    ),
    ("npm", "test", "--if-present", "--", "--runInBand"): lambda t: subprocess.run(
        ["npm", "test", "--if-present", "--", "--runInBand"],
        **_SPAWN_IO,
        timeout=t,
        check=False,
    ),
    ("npm", "run", "build", "--if-present"): lambda t: subprocess.run(
        ["npm", "run", "build", "--if-present"], **_SPAWN_IO, timeout=t, check=False
    ),
    # ``git apply`` accepts either the absolute artifact path (the form this
    # module issues) or the bare filename; every spawn runs with ``cwd=ROOT``,
    # so the two name the same file.
    **{("git", "apply", p): _git_apply(p) for p in _PATCH_ARTIFACT_ARGS},
    **{
        ("git", "apply", "--check", p): _git_apply_check(p)
        for p in _PATCH_ARTIFACT_ARGS
    },
}

# Both allowlists are derived from the runner table, so the set of commands that
# validate and the set that can actually be spawned can never drift apart.
ALLOWED_COMMANDS: frozenset[tuple[str, ...]] = frozenset(_COMMAND_RUNNERS)
ALLOWED_EXECUTABLES = frozenset(command[0] for command in ALLOWED_COMMANDS)


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def validated_argv(command: list[str]) -> list[str]:
    """Return ``command`` as an argv list, or raise if it is not permitted.

    Enforces three properties at the single point where this module decides what
    may be executed:

    * the command is a real argv sequence (never a shell string),
    * ``command[0]`` is on :data:`ALLOWED_EXECUTABLES`, and
    * the WHOLE argv is one of :data:`ALLOWED_COMMANDS`, so no argument position
      is caller-controlled.

    Raises ``RuntimeError`` on violation so a rejected command fails loudly in
    the workflow log instead of silently doing something unexpected.
    """
    if not isinstance(command, (list, tuple)) or not command:
        raise RuntimeError(f"Refusing to execute non-argv command: {command!r}")
    argv = [str(part) for part in command]
    executable = argv[0]
    if executable not in ALLOWED_EXECUTABLES:
        allowed = ", ".join(sorted(ALLOWED_EXECUTABLES))
        raise RuntimeError(
            f"Refusing to execute {executable!r}; allowed executables: {allowed}"
        )
    if tuple(argv) not in ALLOWED_COMMANDS:
        raise RuntimeError(
            f"Refusing to execute {argv!r}; it is not one of the "
            f"{len(ALLOWED_COMMANDS)} command lines this module may run."
        )
    return argv


def _spawn(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Dispatch a validated argv to its runner, which spawns a *literal* argv.

    :func:`run` has already proven ``argv`` is in :data:`ALLOWED_COMMANDS`; the
    table lookup below re-checks rather than trusting its caller. Because the
    argv handed to ``subprocess.run`` is a literal inside the selected runner,
    nothing assembled at runtime reaches the spawn sink — there is no value an
    attacker could influence even if a future caller were compromised.
    """
    runner = _COMMAND_RUNNERS.get(tuple(argv))
    if runner is None:  # defensive: ``run`` validates first
        raise RuntimeError(f"Refusing to execute unvalidated command: {argv!r}")
    return runner(timeout)


def run(command: list[str], timeout: int = 300) -> CommandResult:
    argv = validated_argv(command)
    proc = _spawn(argv, timeout)
    result = CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)
    with VALIDATION_LOG.open("a", encoding="utf-8") as log:
        log.write(f"$ {' '.join(argv)}\n")
        log.write(f"exit={result.returncode}\n")
        if result.stdout:
            log.write("STDOUT:\n")
            log.write(result.stdout[-20000:])
            log.write("\n")
        if result.stderr:
            log.write("STDERR:\n")
            log.write(result.stderr[-20000:])
            log.write("\n")
        log.write("\n")
    return result


def command_exists(name: str) -> bool:
    """True when ``name`` resolves to an executable on PATH.

    Uses ``shutil.which`` instead of ``bash -lc "command -v <name>"``: no shell
    is spawned, so no value is ever interpolated into a shell command string.
    It also resolves against the SAME PATH that ``subprocess.run(argv)`` uses in
    :func:`run`, so a command reported present here is actually launchable there
    (a login shell can see binaries this process cannot).
    """
    return shutil.which(name) is not None


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_model_id(model_id: str) -> None:
    if not model_id.startswith(ALLOWED_MODEL_PREFIXES):
        allowed = ", ".join(ALLOWED_MODEL_PREFIXES)
        raise RuntimeError(
            f"Blocked Bedrock model id {model_id!r}; allowed prefixes: {allowed}"
        )


def get_identity() -> dict[str, str]:
    aws_region = require_env("AWS_REGION")
    sts = boto3.client("sts", region_name=aws_region)
    identity = sts.get_caller_identity()
    CALLER_IDENTITY.write_text(
        "\n".join(
            [
                f"Account: {identity.get('Account')}",
                f"Arn: {identity.get('Arn')}",
                f"UserId: {identity.get('UserId')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return identity


def preflight() -> int:
    aws_region = require_env("AWS_REGION")
    model_id = require_env("BEDROCK_REPAIR_MODEL_ID")
    validate_model_id(model_id)

    identity = get_identity()
    arn = identity.get("Arn", "")

    print("AWS caller identity:")
    print(f"Account: {identity.get('Account')}")
    print(f"Arn: {arn}")
    print(f"Bedrock region: {aws_region}")
    print(f"Bedrock model: {model_id}")

    if ":root" in arn:
        raise RuntimeError("Blocked: workflow is running as AWS root.")
    if "assumed-role" not in arn:
        raise RuntimeError("Blocked: workflow did not assume an AWS role through OIDC.")

    return 0


def invoke_test() -> int:
    aws_region = require_env("AWS_REGION")
    model_id = require_env("BEDROCK_REPAIR_MODEL_ID")
    validate_model_id(model_id)

    client = boto3.client("bedrock-runtime", region_name=aws_region)
    response = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": "Return exactly this text and nothing else: ADAPTIX_BEDROCK_OK"
                    }
                ],
            }
        ],
        inferenceConfig={"maxTokens": 64, "temperature": 0},
    )

    text = response["output"]["message"]["content"][0]["text"].strip()
    print(f"Bedrock response: {text}")
    if text != "ADAPTIX_BEDROCK_OK":
        raise RuntimeError(
            "Bedrock invoke test failed: expected exact ADAPTIX_BEDROCK_OK response."
        )

    return 0


def is_ignored_path(path: pathlib.Path) -> bool:
    return bool(set(path.parts).intersection(FORBIDDEN_FILE_PARTS))


def security_audit() -> int:
    tracked = run(["git", "ls-files"], timeout=120)
    if tracked.returncode != 0:
        print(tracked.stderr)
        return tracked.returncode

    violations: list[str] = []
    for raw in tracked.stdout.splitlines():
        path = ROOT / raw
        if not path.exists() or not path.is_file() or is_ignored_path(path):
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            violations.append(raw)

    if violations:
        print("Static AWS credential material detected in tracked files:")
        for item in violations:
            print(f"- {item}")
        return 1

    print("Security audit passed: no tracked static AWS credential material found.")
    return 0


def yaml_lint() -> int:
    workflow_dir = ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        print("No .github/workflows directory found.")
        return 0

    failures: list[str] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - CLI reports parser details.
            failures.append(f"{path}: {exc}")

    if failures:
        print("Workflow YAML parse failures:")
        for failure in failures:
            print(failure)
        return 1

    print("Workflow YAML parse passed.")
    return 0


def detect_validation_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    if (ROOT / "pyproject.toml").exists() or (ROOT / "requirements.txt").exists():
        commands.append(["python", "-m", "compileall", "."])
        if command_exists("ruff"):
            commands.append(["ruff", "check", "."])
            commands.append(["ruff", "format", "--check", "."])
        if command_exists("pytest"):
            commands.append(["pytest", "-q"])
    if (ROOT / "package.json").exists() and command_exists("npm"):
        commands.append(["npm", "run", "lint", "--if-present"])
        commands.append(["npm", "run", "typecheck", "--if-present"])
        commands.append(["npm", "test", "--if-present", "--", "--runInBand"])
        commands.append(["npm", "run", "build", "--if-present"])
    if not commands:
        commands.append(["git", "status", "--short"])
    return commands


def run_validation() -> list[CommandResult]:
    VALIDATION_LOG.write_text("", encoding="utf-8")
    return [run(command) for command in detect_validation_commands()]


def failed_results(results: list[CommandResult]) -> list[CommandResult]:
    return [result for result in results if result.returncode != 0]


def trim(text: str, limit: int = 18000) -> str:
    return text if len(text) <= limit else text[-limit:]


def extract_candidate_paths(output: str) -> list[pathlib.Path]:
    paths: set[pathlib.Path] = set()
    for match in re.findall(
        r"([A-Za-z0-9_./-]+\.(py|ts|tsx|js|jsx|json|yml|yaml|md))", output
    ):
        candidate = ROOT / match[0]
        if (
            candidate.exists()
            and candidate.is_file()
            and not is_ignored_path(candidate)
        ):
            paths.add(candidate)

    for raw in os.getenv("FOCUS_PATHS", "").split(","):
        value = raw.strip()
        if not value:
            continue
        candidate = ROOT / value
        if (
            candidate.exists()
            and candidate.is_file()
            and not is_ignored_path(candidate)
        ):
            paths.add(candidate)

    return sorted(paths)


def read_context(paths: list[pathlib.Path], max_chars: int = 70000) -> str:
    chunks: list[str] = []
    used = 0
    for path in paths:
        rel = path.relative_to(ROOT)
        chunk = f"\n--- FILE: {rel} ---\n{path.read_text(errors='replace')}\n"
        if used + len(chunk) > max_chars:
            break
        chunks.append(chunk)
        used += len(chunk)
    return "\n".join(chunks)


def build_repair_prompt(failed: list[CommandResult], context: str) -> str:
    failure_text = "\n\n".join(
        [
            f"$ {' '.join(result.command)}\n"
            f"exit={result.returncode}\n"
            f"STDOUT:\n{trim(result.stdout)}\n"
            f"STDERR:\n{trim(result.stderr)}"
            for result in failed
        ]
    )
    return f"""
You are repairing a live Adaptix production repository.

Return ONLY a valid unified diff patch.
Do not include Markdown fences.
Do not include explanation text.

Rules:
- Fix the lint/test failures shown.
- Preserve Adaptix tenant safety.
- Preserve RBAC/auth behavior.
- Preserve audit logging.
- Preserve billing logic.
- Preserve PHI/PII safety.
- Preserve queue and worker behavior.
- Do not remove production logic to make tests pass.
- Do not skip tests.
- Do not weaken assertions.
- Do not edit secrets, credentials, .env files, AWS root, IAM users, or deployment credentials.
- Make the smallest correct production-safe patch.

FAILURES:
{failure_text}

RELEVANT FILES:
{context}
""".strip()


def clean_patch_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def call_bedrock(prompt: str) -> str:
    aws_region = require_env("AWS_REGION")
    model_id = require_env("BEDROCK_REPAIR_MODEL_ID")
    validate_model_id(model_id)
    client = boto3.client("bedrock-runtime", region_name=aws_region)
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 12000, "temperature": 0},
    )
    return clean_patch_text(response["output"]["message"]["content"][0]["text"])


def apply_patch(patch_text: str) -> bool:
    PATCH_ARTIFACT.write_text(patch_text, encoding="utf-8")
    check = run(["git", "apply", "--check", str(PATCH_ARTIFACT)], timeout=120)
    if check.returncode != 0:
        print("Patch failed git apply --check")
        print(check.stdout)
        print(check.stderr)
        return False
    applied = run(["git", "apply", str(PATCH_ARTIFACT)], timeout=120)
    if applied.returncode != 0:
        print("Patch failed git apply")
        print(applied.stdout)
        print(applied.stderr)
        return False
    return True


def write_repair_report(history: list[str], final_results: list[CommandResult]) -> None:
    changed = run(["git", "diff", "--name-only"]).stdout.strip()
    CHANGED_FILES.write_text(
        (changed if changed else "No files changed.") + "\n", encoding="utf-8"
    )
    lines = [
        "# Bedrock Repo Repair Report",
        "",
        "## Model",
        require_env("BEDROCK_REPAIR_MODEL_ID"),
        "",
        "## AWS caller identity",
        CALLER_IDENTITY.read_text(encoding="utf-8")
        if CALLER_IDENTITY.exists()
        else "Not captured.",
        "",
        "## Files changed",
        changed if changed else "No files changed.",
        "",
        "## Repair history",
        *history,
        "",
        "## Final validation",
    ]
    for result in final_results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        lines.append(f"- `{' '.join(result.command)}`: {status}")
    lines.extend(
        [
            "",
            "## Adaptix platform propagation",
            "- Auth/RBAC: preserved unless explicitly listed in files changed.",
            "- Tenant isolation: preserved unless explicitly listed in files changed.",
            "- Billing behavior: preserved unless explicitly listed in files changed.",
            "- PHI/PII safety: preserved unless explicitly listed in files changed.",
            "- Queues/workers: preserved unless explicitly listed in files changed.",
            "- Audit/monitoring: preserved unless explicitly listed in files changed.",
            "",
            "## Rollback",
            "Revert this PR or reset the repair branch.",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def repair() -> int:
    preflight()
    max_iterations = int(os.getenv("MAX_ITERATIONS", "3"))
    history: list[str] = []
    for iteration in range(1, max_iterations + 1):
        results = run_validation()
        failed = failed_results(results)
        if not failed:
            history.append(f"- Iteration {iteration}: validation passed.")
            write_repair_report(history, results)
            return 0
        combined_output = "\n".join(
            [result.stdout + "\n" + result.stderr for result in failed]
        )
        candidate_paths = extract_candidate_paths(combined_output)
        context = read_context(candidate_paths)
        history.append(
            f"- Iteration {iteration}: {len(failed)} failing command(s), {len(candidate_paths)} candidate file(s)."
        )
        if not candidate_paths:
            history.append(f"- Iteration {iteration}: no candidate files found.")
            write_repair_report(history, results)
            return 1
        patch_text = call_bedrock(build_repair_prompt(failed, context))
        if not apply_patch(patch_text):
            history.append(
                f"- Iteration {iteration}: Bedrock patch could not be applied."
            )
            write_repair_report(history, results)
            return 1
        if command_exists("ruff"):
            run(["ruff", "check", ".", "--fix"], timeout=300)
            run(["ruff", "format", "."], timeout=300)

    final_results = run_validation()
    write_repair_report(history, final_results)
    return 0 if not failed_results(final_results) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "preflight",
            "invoke-test",
            "smoke",
            "security-audit",
            "yaml-lint",
            "repair",
        ],
    )
    args = parser.parse_args()
    if args.command == "preflight":
        return preflight()
    if args.command in {"invoke-test", "smoke"}:
        return invoke_test()
    if args.command == "security-audit":
        return security_audit()
    if args.command == "yaml-lint":
        return yaml_lint()
    if args.command == "repair":
        return repair()
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
