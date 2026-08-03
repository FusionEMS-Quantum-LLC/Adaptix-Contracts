"""Command-execution safety guards for ``tools/bedrock_ops.py``.

These tests lock in the controls that close the CommandInjection finding on
``tools/bedrock_ops.py``:

1. ``run`` executes only argv lists whose executable is on a fixed allowlist,
   never a shell string — so the generic executor cannot be turned into an
   arbitrary-command sink by a caller that builds a command from repository
   content, Bedrock model output, or environment input.
2. ``run`` additionally pins the WHOLE argv to a fixed catalogue of command
   lines. An executable-name allowlist alone is not enough: ``python``,
   ``git`` and ``npm`` all accept arguments that are arbitrary-execution
   primitives (``python -c``, ``git -c core.pager=...``, ``npm run <script>``),
   so no argument position may be caller-controlled either.
3. Every ``subprocess.run`` call site passes a *literal* argv, so nothing
   assembled at runtime reaches the process-spawn sink.
4. ``command_exists`` resolves names with ``shutil.which`` and never spawns a
   shell, so no value is interpolated into a shell command string.
5. Every spawn pins argv[0] to the absolute path of its executable. A bare
   name is re-resolved through ``PATH`` by the child at exec time, so any
   writable directory preceding the real tool would be executed instead --
   and this module runs holding AWS credentials assumed through OIDC.

The module lives outside the installed package (``tools/`` is excluded from
``[tool.setuptools.packages.find]``), so it is loaded by path.
"""

from __future__ import annotations

import ast
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

    assert captured["argv"] == [bedrock_ops._exe("git"), "status", "--short"]
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


def test_exe_pins_argv0_to_the_absolute_resolved_path(monkeypatch) -> None:
    """argv[0] is resolved to an absolute path before it reaches the spawn."""
    monkeypatch.setattr(bedrock_ops.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert bedrock_ops._exe("git") == "/usr/bin/git"


def test_exe_falls_back_to_the_bare_name_when_unresolvable(monkeypatch) -> None:
    """An unresolvable tool keeps today's ``FileNotFoundError`` failure mode.

    ``git`` and ``python`` are spawned without a :func:`command_exists` gate, so
    the resolver must not convert "tool missing" into a different error.
    """
    monkeypatch.setattr(bedrock_ops.shutil, "which", lambda name: None)
    assert bedrock_ops._exe("ruff") == "ruff"


def test_every_runner_spawns_the_resolved_executable(monkeypatch) -> None:
    """No spawn in the catalogue leaves argv[0] as a bare PATH-resolved name."""
    resolved: list[str] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(argv, **kwargs):
        resolved.append(argv[0])
        return _Proc()

    monkeypatch.setattr(bedrock_ops.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fake_run)

    for key, runner in bedrock_ops._COMMAND_RUNNERS.items():
        resolved.clear()
        runner(300)
        assert resolved == [f"/usr/bin/{key[0]}"], key


# Every one of these uses an executable that IS on the allowlist, but with
# arguments this module never issues. Each is a real arbitrary-execution or
# arbitrary-file primitive, so an executable-name check alone would let them
# through. Pinning the whole argv is what actually stops them.
_ALLOWLISTED_EXECUTABLE_WITH_INJECTED_ARGUMENTS = [
    ["python", "-c", "import os; os.system('id')"],
    ["python", "-m", "http.server"],
    ["git", "-c", "core.pager=sh -c id", "log"],
    ["git", "apply", "/tmp/attacker-supplied.patch"],
    ["npm", "run", "postinstall"],
    ["npm", "exec", "--", "some-package"],
    ["ruff", "check", "--config", "/tmp/attacker.toml", "."],
    ["pytest", "-p", "attacker_plugin"],
]


@pytest.mark.parametrize("command", _ALLOWLISTED_EXECUTABLE_WITH_INJECTED_ARGUMENTS)
def test_validated_argv_rejects_injected_arguments_on_allowlisted_executables(
    command: list[str],
) -> None:
    with pytest.raises(RuntimeError, match="Refusing to execute"):
        bedrock_ops.validated_argv(command)


@pytest.mark.parametrize("command", _ALLOWLISTED_EXECUTABLE_WITH_INJECTED_ARGUMENTS)
def test_run_rejects_injected_arguments_before_spawning(monkeypatch, command) -> None:
    """An argument-injected command must never reach ``subprocess.run``."""

    def _fail(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("subprocess.run was called for a disallowed command")

    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fail)
    with pytest.raises(RuntimeError, match="Refusing to execute"):
        bedrock_ops.run(command)


def test_allowed_commands_is_the_command_set_this_module_issues() -> None:
    """The catalogue covers every real command and nothing else."""
    issued = {tuple(command) for command in _COMMANDS_THIS_MODULE_ISSUES}
    catalogue = set(bedrock_ops.ALLOWED_COMMANDS)

    assert issued <= catalogue

    # The only members beyond the bare-filename forms above are the same two
    # ``git apply`` lines carrying the absolute artifact path, which is what
    # ``apply_patch`` actually issues.
    patch = str(bedrock_ops.PATCH_ARTIFACT)
    assert catalogue - issued == {
        ("git", "apply", "--check", patch),
        ("git", "apply", patch),
    }


def test_allowed_executables_is_derived_from_the_catalogue() -> None:
    """The two allowlists cannot drift apart."""
    assert bedrock_ops.ALLOWED_EXECUTABLES == {
        command[0] for command in bedrock_ops.ALLOWED_COMMANDS
    }


def test_detect_validation_commands_only_returns_catalogued_commands() -> None:
    """Nothing the module plans to run can be rejected at spawn time."""
    for command in bedrock_ops.detect_validation_commands():
        assert tuple(command) in bedrock_ops.ALLOWED_COMMANDS


def test_run_spawns_git_apply_against_the_module_patch_artifact(
    monkeypatch, tmp_path
) -> None:
    """``git apply`` resolves to this module's own artifact, never a caller path."""
    captured: dict[str, object] = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _Proc()

    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fake_run)
    monkeypatch.setattr(bedrock_ops, "VALIDATION_LOG", tmp_path / "validation.log")

    patch = str(bedrock_ops.PATCH_ARTIFACT)
    bedrock_ops.run(["git", "apply", "--check", patch])

    assert captured["argv"] == [bedrock_ops._exe("git"), "apply", "--check", patch]


def test_every_subprocess_run_call_passes_a_literal_argv() -> None:
    """No runtime-assembled value reaches the process-spawn sink.

    This is the structural property the CommandInjection rule checks: the argv
    handed to ``subprocess.run`` must be a list literal whose executable is
    named by a string literal, never a name bound to a value built at runtime.

    argv[0] is written as ``_exe("<name>")``. The executable is still named by
    a literal; ``_exe`` only resolves that literal to an absolute path, so no
    runtime-assembled value can reach the executable position either.
    """
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]

    assert calls, "expected at least one subprocess.run call site"

    for call in calls:
        argv = call.args[0]
        assert isinstance(argv, ast.List), ast.dump(argv)
        assert argv.elts, "argv literal must not be empty"

        head = argv.elts[0]
        assert isinstance(head, ast.Call), (
            f"executable must be pinned with _exe(...), got {ast.dump(head)}"
        )
        assert isinstance(head.func, ast.Name) and head.func.id == "_exe", (
            f"executable must be pinned with _exe(...), got {ast.dump(head)}"
        )
        assert len(head.args) == 1 and not head.keywords, ast.dump(head)
        exe_name = head.args[0]
        assert isinstance(exe_name, ast.Constant) and isinstance(exe_name.value, str), (
            f"_exe must take a string literal, got {ast.dump(exe_name)}"
        )
        assert exe_name.value in bedrock_ops.ALLOWED_EXECUTABLES, exe_name.value

        for element in argv.elts[1:]:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                continue
            # The single permitted non-literal element is the patch-artifact
            # path bound by the two ``git apply`` runner builders. It can only
            # ever be fed from ``_PATCH_ARTIFACT_ARGS`` — a module constant no
            # caller can influence — which
            # ``test_git_apply_runners_only_carry_the_module_patch_artifact``
            # asserts at runtime.
            assert isinstance(element, ast.Name), ast.dump(element)
            assert element.id == "patch", ast.dump(element)


def test_every_subprocess_run_call_states_check_and_inherits_no_shell() -> None:
    """Each spawn states its own failure mode and inherits the no-shell pin.

    ``check`` is asserted at every call site because leaving it implicit makes
    the spawn's failure mode unreadable there. ``shell`` is asserted once on
    ``_SPAWN_IO`` plus the requirement that every call site unpacks it, which
    covers every spawn without restating the flag fifteen times.
    """
    assert bedrock_ops._SPAWN_IO["shell"] is False

    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ):
            continue

        check = {kw.arg: kw.value for kw in node.keywords}.get("check")
        assert check is not None, f"line {node.lineno}: check not set explicitly"
        assert isinstance(check, ast.Constant) and check.value is False, (
            f"line {node.lineno}: check must be the literal False"
        )

        unpacked = [
            kw.value.id
            for kw in node.keywords
            if kw.arg is None and isinstance(kw.value, ast.Name)
        ]
        assert "_SPAWN_IO" in unpacked, (
            f"line {node.lineno}: spawn does not inherit _SPAWN_IO (no-shell pin)"
        )


def test_each_runner_spawns_exactly_the_argv_it_is_keyed_by(monkeypatch) -> None:
    """The catalogue key and the literal argv at the sink cannot drift apart.

    Every entry states its argv twice — as the dict key and as the literal
    handed to ``subprocess.run``. This drives every runner and proves the two
    agree, so a typo in either copy fails the suite instead of silently
    executing a different command than the one that was validated.

    argv[0] is compared against its resolved form, since every spawn pins the
    executable to an absolute path.
    """
    captured: list[object] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(argv, **kwargs):
        captured.append(argv)
        return _Proc()

    monkeypatch.setattr(bedrock_ops.subprocess, "run", _fake_run)

    for key, runner in bedrock_ops._COMMAND_RUNNERS.items():
        captured.clear()
        runner(300)
        expected = [bedrock_ops._exe(key[0]), *key[1:]]
        assert captured == [expected], f"{key} spawned {captured}"


def test_git_apply_runners_only_carry_the_module_patch_artifact() -> None:
    """No ``git apply`` entry can name a file other than this module's patch."""
    permitted = set(bedrock_ops._PATCH_ARTIFACT_ARGS)
    assert permitted == {
        str(bedrock_ops.PATCH_ARTIFACT),
        bedrock_ops.PATCH_ARTIFACT.name,
    }

    apply_keys = [
        key for key in bedrock_ops.ALLOWED_COMMANDS if key[:2] == ("git", "apply")
    ]
    assert len(apply_keys) == 4
    for key in apply_keys:
        assert key[-1] in permitted, key


def test_allowlists_are_derived_from_the_runner_table() -> None:
    """A command can be validated if and only if a runner exists for it."""
    assert bedrock_ops.ALLOWED_COMMANDS == frozenset(bedrock_ops._COMMAND_RUNNERS)
