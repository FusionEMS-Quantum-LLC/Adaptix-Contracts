#!/usr/bin/env python3
"""Fail CI when a repository uses an unapproved dependency or unlocked toolchain.

The policy file and every manifest this script reads arrive through
``json.loads`` and ``tomllib.loads``, which hand the type checker nothing it can
reason about. They are narrowed by the two readers below (``string_keyed_mapping``
and ``string_list``) before any check touches them, so every value a check
compares against the policy has a known type.

The script fails closed on every input it cannot read. The policy file declares
``"defaultPolicy": "deny"``: a policy it cannot read stops the run with exit 2
(``PolicyError``, or a missing or mis-shaped policy file), and a manifest shaped
in a way the readers cannot narrow is reported as a violation (exit 1) rather
than skipped, because a dependency list this script cannot read is one it
cannot approve.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeGuard

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "approved-tools.json"

SKIP_PARTS = {
    ".git",
    ".next",
    ".terraform",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)

POLICY_SECTIONS = ("npm", "python")


class PolicyError(ValueError):
    """The approved-tools policy file itself is malformed.

    Raised for a ``forbidden`` entry that is present but not a list (null, a
    string, an object). Read as "nothing is forbidden" it would let a forbidden
    package through, which is the one direction a dependency gate must never
    fail in; the policy file is the defect, not the repository under check.
    """

    def __init__(self, section: str, found: str) -> None:
        super().__init__(
            f"{POLICY_PATH}: '{section}.forbidden' must be a list, found {found}"
        )


def fail(message: str) -> None:
    print(f"TOOLCHAIN ERROR: {message}", file=sys.stderr)


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def iter_files(name: str) -> Iterable[Path]:
    for path in ROOT.rglob(name):
        if not should_skip(path):
            yield path


def is_object_dict(value: object) -> TypeGuard[dict[object, object]]:
    """True for every ``dict``: each key and value of any dict is an object.

    ``isinstance(value, dict)`` alone narrows to ``dict[Unknown, Unknown]``, which
    the strict checker refuses to iterate. The guard states the one fact that is
    true of any dict without claiming anything about its contents.
    """
    return isinstance(value, dict)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    """True for every ``list``; see ``is_object_dict``."""
    return isinstance(value, list)


def string_keyed_mapping(value: object) -> dict[str, object] | None:
    """The entries of ``value`` under its string keys, or None when it is no mapping.

    A JSON object and a TOML table both arrive as ``dict`` with unknown key and
    value types. Only string keys can name a dependency or a policy section, so
    any other key is dropped here and every value stays ``object`` until a check
    narrows it further.
    """
    if is_object_dict(value):
        return {key: item for key, item in value.items() if isinstance(key, str)}

    return None


def string_list(value: object) -> list[str] | None:
    """The entries of ``value``, or None when it is not a list of strings.

    A list holding any entry that is not a string is no list this script can
    read, so it answers None exactly as for a value that is no list at all, and
    each caller reports that shape (the policy's ``forbidden`` list raises
    ``PolicyError``). Converting such an entry with ``str()`` would turn a
    malformed manifest into a dependency name nobody declared.
    """
    if not is_object_list(value):
        return None

    strings = [item for item in value if isinstance(item, str)]
    if len(strings) != len(value):
        return None

    return strings


def normalized_python_name(requirement: str) -> str:
    value = requirement.strip()

    if " @ " in value:
        value = value.split(" @ ", 1)[0]

    value = value.split(";", 1)[0]
    value = value.split("[", 1)[0]
    value = re.split(r"[<>=!~\s]", value, maxsplit=1)[0]

    return value.strip().lower().replace("_", "-")


def collect_allowed(section: Mapping[str, object]) -> set[str]:
    """Every name listed under any key of ``section`` other than ``forbidden``.

    A key whose value is not a list (``schemaVersion``, ``defaultPolicy`` and the
    like sit beside the lists in the policy file) contributes nothing.
    """
    allowed: set[str] = set()

    for key, value in section.items():
        if key == "forbidden":
            continue

        names = string_list(value)
        if names is not None:
            allowed.update(name.lower() for name in names)

    return allowed


def forbidden_names(section: Mapping[str, object], name: str) -> list[str]:
    """The ``forbidden`` list of policy section ``name`` (absent: nothing forbidden).

    Present under any shape other than a list it is a ``PolicyError``: see that
    class for why this cannot read as an empty list.
    """
    if "forbidden" not in section:
        return []

    value = section["forbidden"]
    names = string_list(value)
    if names is None:
        raise PolicyError(name, type(value).__name__)

    return names


def exact_npm_spec(spec: str) -> bool:
    value = spec.strip()

    allowed_nonregistry_prefixes = (
        "file:",
        "git+",
        "github:",
        "link:",
        "workspace:",
    )

    if value.startswith(allowed_nonregistry_prefixes):
        return True

    if value in {"*", "latest", "next"}:
        return False

    if value.startswith(("^", "~", ">", "<", "=")):
        return False

    if "||" in value or " - " in value:
        return False

    return bool(re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", value))


def check_npm(policy: Mapping[str, object], violations: list[str]) -> None:
    allowed = collect_allowed(policy)
    forbidden = {name.lower() for name in forbidden_names(policy, "npm")}

    for package_path in iter_files("package.json"):
        manifest = string_keyed_mapping(
            json.loads(package_path.read_text(encoding="utf-8"))
        )

        if manifest is None:
            violations.append(f"{package_path}: package.json is not a JSON object")
            continue

        lock_path = package_path.with_name("package-lock.json")
        if not lock_path.exists():
            violations.append(f"{package_path}: package-lock.json is missing")

        for section_name in DEPENDENCY_SECTIONS:
            if section_name not in manifest:
                continue

            dependencies = string_keyed_mapping(manifest[section_name])

            if dependencies is None:
                message = (
                    f"{package_path}: {section_name} must be a JSON object "
                    "mapping package names to version specs"
                )
                violations.append(message)
                continue

            for package_name, spec in dependencies.items():
                normalized = package_name.lower()

                if normalized in forbidden:
                    violations.append(
                        f"{package_path}: forbidden npm dependency {package_name}"
                    )
                    continue

                if normalized not in allowed:
                    violations.append(
                        f"{package_path}: unapproved npm dependency {package_name}"
                    )

                if isinstance(spec, str):
                    if exact_npm_spec(spec):
                        continue
                    found = repr(spec)
                else:
                    # Not a string, so no version spec at all: name it as the
                    # JSON the manifest holds (18, true, null, [...]).
                    found = json.dumps(spec)
                message = (
                    f"{package_path}: direct dependency {package_name} "
                    f"must use an exact approved version, found {found}"
                )
                violations.append(message)


def nearest_uv_lock(pyproject_path: Path) -> Path | None:
    current = pyproject_path.parent

    while current == ROOT or ROOT in current.parents:
        candidate = current / "uv.lock"
        if candidate.exists():
            return candidate

        if current == ROOT:
            break

        current = current.parent

    return None


def project_requirements(
    pyproject_path: Path, project: Mapping[str, object], violations: list[str]
) -> list[str]:
    """Every requirement string the ``[project]`` table declares.

    ``dependencies`` is an array of requirement strings and
    ``optional-dependencies`` a table of such arrays (PEP 621). Either key may be
    absent; present under any other shape it is a violation, because a
    dependency list that cannot be read cannot be approved.
    """
    requirements: list[str] = []

    if "dependencies" in project:
        runtime = string_list(project["dependencies"])
        if runtime is None:
            message = (
                f"{pyproject_path}: project.dependencies must be an array "
                "of requirement strings"
            )
            violations.append(message)
        else:
            requirements.extend(runtime)

    if "optional-dependencies" in project:
        groups = string_keyed_mapping(project["optional-dependencies"])
        if groups is None:
            message = (
                f"{pyproject_path}: project.optional-dependencies must be a "
                "table of requirement arrays"
            )
            violations.append(message)
        else:
            for group_name, values in groups.items():
                group = string_list(values)
                if group is None:
                    message = (
                        f"{pyproject_path}: project.optional-dependencies."
                        f"{group_name} must be an array of requirement strings"
                    )
                    violations.append(message)
                else:
                    requirements.extend(group)

    return requirements


def check_python(policy: Mapping[str, object], violations: list[str]) -> None:
    allowed = collect_allowed(policy)
    forbidden = {
        normalized_python_name(name) for name in forbidden_names(policy, "python")
    }

    for pyproject_path in iter_files("pyproject.toml"):
        data = string_keyed_mapping(
            tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        )

        # tomllib.loads always returns a table; the reader cannot say otherwise.
        if data is None or "project" not in data:
            continue

        project = string_keyed_mapping(data["project"])

        if project is None:
            violations.append(f"{pyproject_path}: project must be a TOML table")
            continue

        all_requirements = project_requirements(pyproject_path, project, violations)

        for requirement in all_requirements:
            package_name = normalized_python_name(requirement)

            if package_name in forbidden:
                violations.append(
                    f"{pyproject_path}: forbidden Python dependency {package_name}"
                )
                continue

            if package_name not in allowed:
                violations.append(
                    f"{pyproject_path}: unapproved Python dependency {package_name}"
                )

        if all_requirements and nearest_uv_lock(pyproject_path) is None:
            violations.append(
                f"{pyproject_path}: uv.lock is missing from the project hierarchy"
            )


def check_terraform(violations: list[str]) -> None:
    terraform_files = list(iter_files("*.tf"))

    if not terraform_files:
        return

    lockfiles = list(iter_files(".terraform.lock.hcl"))

    if not lockfiles:
        violations.append("Terraform files exist but no .terraform.lock.hcl was found")


def check_gradle(violations: list[str]) -> None:
    gradle_files = [
        *iter_files("build.gradle"),
        *iter_files("build.gradle.kts"),
    ]

    if not gradle_files:
        return

    wrappers = list(iter_files("gradle-wrapper.properties"))

    if not wrappers:
        violations.append(
            "Gradle project exists but gradle-wrapper.properties is missing"
        )


def load_policy() -> dict[str, dict[str, object]] | None:
    """The policy file's ``npm`` and ``python`` sections, or None (reason printed).

    A policy file that is missing, is not a JSON object, or lacks either section
    as an object cannot be applied, and a policy that cannot be applied approves
    nothing: the caller exits 2.
    """
    if not POLICY_PATH.exists():
        fail(f"policy file not found: {POLICY_PATH}")
        return None

    policy = string_keyed_mapping(json.loads(POLICY_PATH.read_text(encoding="utf-8")))

    sections: dict[str, dict[str, object]] = {}

    for name in POLICY_SECTIONS:
        section = None if policy is None else string_keyed_mapping(policy.get(name))
        if section is None:
            fail(
                f"{POLICY_PATH} must define both an 'npm' object and a 'python' object"
            )
            return None
        sections[name] = section

    return sections


def main() -> int:
    policy = load_policy()

    if policy is None:
        return 2

    violations: list[str] = []

    try:
        check_npm(policy["npm"], violations)
        check_python(policy["python"], violations)
    except PolicyError as error:
        fail(str(error))
        return 2

    check_terraform(violations)
    check_gradle(violations)

    if violations:
        print("\n".join(f"- {item}" for item in sorted(set(violations))))
        print(f"\n{len(set(violations))} toolchain violation(s) found.")
        return 1

    print("Toolchain policy passed with zero violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
