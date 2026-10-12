"""``tools/bedrock_ops.py`` checks what Bedrock, STS and the workflow files hand it.

A Converse reply without message text is an error that says so, for both the
invoke test and the repair call. The caller identity is three named strings. A
workflow-file check reports parse and read failures and lets any other error
surface.

The module lives outside the installed package, so it is loaded by path.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

import pytest

_MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bedrock_ops.py"
_MODEL_ID = "us.anthropic.test-model"


def _load_bedrock_ops() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "adaptix_bedrock_ops_typed_replies", _MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # @dataclass resolves sys.modules[cls.__module__] while it builds the class.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bedrock_ops = _load_bedrock_ops()


class _ConverseRuntime:
    """A bedrock-runtime client that answers every Converse call with one reply."""

    def __init__(self, reply: dict[str, object]) -> None:
        super().__init__()
        self.reply = reply
        self.requests: list[dict[str, object]] = []

    def converse(self, **request: object) -> dict[str, object]:
        self.requests.append(request)
        return self.reply


class _CallerIdentity:
    """An STS client that answers GetCallerIdentity and counts the calls."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def get_caller_identity(self) -> dict[str, object]:
        self.calls += 1
        return {
            "UserId": "AROAEXAMPLEROLEID:session",
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/adaptix-ops/session",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }


def _use_runtime(
    monkeypatch: pytest.MonkeyPatch, reply: dict[str, object]
) -> _ConverseRuntime:
    runtime = _ConverseRuntime(reply)

    def client(service_name: str, **_options: object) -> _ConverseRuntime:
        assert service_name == "bedrock-runtime"
        return runtime

    monkeypatch.setattr("boto3.client", client)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_REPAIR_MODEL_ID", _MODEL_ID)
    return runtime


def test_converse_returns_the_first_blocks_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _use_runtime(
        monkeypatch,
        {"output": {"message": {"role": "assistant", "content": [{"text": "patch"}]}}},
    )

    assert (
        bedrock_ops.converse_text("us-east-1", _MODEL_ID, "fix it", max_tokens=64)
        == "patch"
    )
    assert runtime.requests == [
        {
            "modelId": _MODEL_ID,
            "messages": [{"role": "user", "content": [{"text": "fix it"}]}],
            "inferenceConfig": {"maxTokens": 64, "temperature": 0},
        }
    ]


_REPLIES_WITHOUT_TEXT: list[tuple[dict[str, object], str]] = [
    ({"output": {}}, "no message content"),
    (
        {"output": {"message": {"role": "assistant", "content": []}}},
        "no message content",
    ),
    (
        {"output": {"message": {"role": "assistant", "content": [{"toolUse": {}}]}}},
        "without text",
    ),
]


@pytest.mark.parametrize(
    ("reply", "message"),
    _REPLIES_WITHOUT_TEXT,
    ids=["no-message", "no-content-block", "block-without-text"],
)
def test_a_converse_reply_without_text_is_an_error(
    monkeypatch: pytest.MonkeyPatch, reply: dict[str, object], message: str
) -> None:
    _ = _use_runtime(monkeypatch, reply)

    with pytest.raises(RuntimeError, match=message):
        _ = bedrock_ops.call_bedrock("fix it")


def test_the_caller_identity_is_three_named_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    sts = _CallerIdentity()

    def client(service_name: str, **_options: object) -> _CallerIdentity:
        assert service_name == "sts"
        return sts

    written = tmp_path / "identity.txt"
    monkeypatch.setattr("boto3.client", client)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setattr(bedrock_ops, "CALLER_IDENTITY", written)

    assert bedrock_ops.get_identity() == {
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/adaptix-ops/session",
        "UserId": "AROAEXAMPLEROLEID:session",
    }
    assert written.read_text(encoding="utf-8").splitlines() == [
        "Account: 123456789012",
        "Arn: arn:aws:sts::123456789012:assumed-role/adaptix-ops/session",
        "UserId: AROAEXAMPLEROLEID:session",
    ]
    assert sts.calls == 1


def _workflow_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    return workflows


def test_a_workflow_that_does_not_parse_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _ = (_workflow_dir(tmp_path) / "ci.yml").write_text(
        "jobs: [unclosed\n", encoding="utf-8"
    )
    monkeypatch.setattr(bedrock_ops, "ROOT", tmp_path)

    assert bedrock_ops.yaml_lint() == 1


def test_an_unexpected_error_in_the_workflow_check_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def broken_loader(_text: str) -> object:
        message = "loader defect"
        raise RuntimeError(message)

    _ = (_workflow_dir(tmp_path) / "ci.yml").write_text("on: push\n", encoding="utf-8")
    monkeypatch.setattr(bedrock_ops, "ROOT", tmp_path)
    monkeypatch.setattr("yaml.safe_load", broken_loader)

    with pytest.raises(RuntimeError, match="loader defect"):
        _ = bedrock_ops.yaml_lint()


def test_the_invoke_test_passes_on_the_exact_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _use_runtime(
        monkeypatch,
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": " ADAPTIX_BEDROCK_OK\n"}],
                }
            }
        },
    )

    assert bedrock_ops.invoke_test() == 0
    assert len(runtime.requests) == 1


def test_an_invoke_test_reply_without_text_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _use_runtime(
        monkeypatch,
        {"output": {"message": {"role": "assistant", "content": [{"toolUse": {}}]}}},
    )

    with pytest.raises(RuntimeError, match="without text"):
        _ = bedrock_ops.invoke_test()
