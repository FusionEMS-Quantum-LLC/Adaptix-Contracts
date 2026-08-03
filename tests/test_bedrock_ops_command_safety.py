"""Command-execution safety guards for ``tools/bedrock_ops.py``.

These tests lock in the two controls that close the CommandInjection finding on
``tools/bedrock_ops.py``:

1. ``run`` executes only argv lists whose executable is on a fixed allowlist,
   never a shell string — so the generic executor cannot be turned into an
   arbitrary-command sink by a caller that builds a command from repository
   content, Bedrock model output, or environment input.
2. ``command_exists`` resolves names with ``shutil.which`` and never spawns a
   shell, so no value is interpolated into a shell command string.

The module lives outside the installed package (``tools/`` is excluded from
``[tool.setuptools.packages.find]``), so it is loaded by path.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bedrock_ops.py"


def _load_bedrock_ops():
    spec = importlib.util.spec_from_file_location("adaptix_bedrock_ops", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bedrock_ops = _load_bedrock_ops()


# Every argv this module actually issues, gathered from ``security_audit``,
# ``detect_validation_commands``, ``apply_patch``, ``write_repair_report`` and
# ``repair``. The allowlist must not reject any of them.
_COMMANDS_THIS_MODULE_ISSUES = [
    ["git", "ls-files"],
    ["git", "status", "--short"],
    ["git", "apply", "--check", "bedrock-repair.patch"],
    ["git", "apply", "bedrock-repair.patch"],
    ["git", "diff", "--name-only"],
    ["python", "-m", "compileall", "."],
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["ruff", "check", ".", "--fix"],
    ["ruff", "format", "."],
    ["pytest", "-q"],
    ["npm", "run", "lint", "--if-present"],
    ["npm", "run", "typecheck", "--if-present"],
    ["npm", "test", "--if-present", "--", "--runInBand"],
    ["npm", "run", "build", "--if-present"],
]


@pytest.mark.parametrize("command", _COMMANDS_THIS_MODULE_ISSUES)
def test_validated_argv_allows_every_command_this_module_issues(
    command: list[str],
) -> None:
    """The allowlist does not change behavior for the real command set."""
    assert bedrock_ops.validated_argv(command) == command


def test_validated_argv_rejects_executable_outside_the_allowlist() -> None:
    with pytest.raises(RuntimeError, match="Refusing to execute"):
        bedrock_ops.validated_argv(["curl", "https://example.invalid/x"])


def test_validated_argv_rejects_a_shell_string() -> None:
    """A shell string must never be accepted where an argv list is expected."""
    with pytest.raises(RuntimeError, match="non-argv command"):
        bedrock_ops.validated_argv("git ls-files; curl https://example.invalid")


def test_validated_argv_rejects_empty_command() -> None:
    with pytest.raises(RuntimeError, match="non-argv command"):
        bedrock_ops.validated_argv([])


def test_run_rejects_disallowed_executable_before_spawning(monkeypatch) -> None:
    """A rejected command must never reach ``subprocess.run``."""

    def _fail(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("subprocess.run was called for a disallowed command")

    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fail)
    with pytest.raises(RuntimeError, match="Refusing to execute"):
        bedrock_ops.run(["curl", "https://example.invalid/x"])


def test_run_passes_an_argv_list_and_never_a_shell(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fake_run)
    monkeypatch.setattr(bedrock_ops, "VALIDATION_LOG", tmp_path / "validation.log")

    result = bedrock_ops.run(["git", "status", "--short"])

    assert captured["argv"] == ["git", "status", "--short"]
    assert isinstance(captured["argv"], list)
    assert captured["kwargs"]["shell"] is False
    assert result.command == ["git", "status", "--short"]
    assert result.returncode == 0


def test_command_exists_spawns_no_process(monkeypatch) -> None:
    """``command_exists`` must resolve PATH without executing anything."""

    def _fail(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("command_exists spawned a subprocess")

    monkeypatch.setattr(subprocess, "run", _fail)
    monkeypatch.setattr(subprocess, "Popen", _fail)
    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fail)

    # Both branches exercised: a name that resolves and one that cannot.
    assert bedrock_ops.command_exists("adaptix-no-such-binary-9f3a1c") is False
    assert isinstance(bedrock_ops.command_exists("python"), bool)


def test_command_exists_uses_the_same_path_resolution_as_run(monkeypatch) -> None:
    """A name reported present must be resolvable by ``shutil.which``."""
    monkeypatch.setattr(bedrock_ops.shutil, "which", lambda name: "/usr/bin/ruff")
    assert bedrock_ops.command_exists("ruff") is True

    monkeypatch.setattr(bedrock_ops.shutil, "which", lambda name: None)
    assert bedrock_ops.command_exists("ruff") is False
