"""Contracts #397: the static check that refuses new unbound verifier uses."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _ROOT / "scripts" / "check_unbound_gateway_verifier.py"
_ALLOWLIST = _ROOT / "scripts" / "unbound_gateway_verifier_allowlist.txt"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "adaptix_check_unbound_gateway_verifier", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load_module()


def _kinds(source: str) -> list[str]:
    return [f.kind for f in check.scan_source(source, "app.py")]


def test_import_of_the_unbound_name_is_reported() -> None:
    src = "from adaptix_contracts.gateway_signature import verify_gateway_signature\n"
    assert _kinds(src) == [check.UNBOUND_VERIFIER]


def test_attribute_use_is_reported() -> None:
    src = (
        "from adaptix_contracts import gateway_signature\n"
        "gateway_signature.verify_gateway_signature(context_b64='', signature_hex='')\n"
    )
    assert _kinds(src) == [check.UNBOUND_VERIFIER]


def test_gateway_identity_verify_alias_is_reported() -> None:
    assert _kinds("from adaptix_contracts.gateway_identity import verify\n") == [
        check.UNBOUND_VERIFIER
    ]
    src = "from adaptix_contracts import gateway_identity as gi\ngi.verify()\n"
    assert _kinds(src) == [check.UNBOUND_VERIFIER]


def test_bound_and_explicit_names_are_not_reported() -> None:
    src = (
        "from adaptix_contracts.gateway_signature import (\n"
        "    verify_gateway_signature_for_request,\n"
        "    verify_gateway_signature_without_request_binding,\n"
        ")\n"
        "verify_gateway_signature_for_request(None)\n"
        "verify_gateway_signature_without_request_binding()\n"
    )
    assert _kinds(src) == []


def test_names_in_strings_and_docstrings_are_ignored() -> None:
    src = '"""verify_gateway_signature is deprecated."""\nx = "verify_gateway_signature"\n'
    assert _kinds(src) == []


def test_get_auth_context_without_request_is_reported() -> None:
    assert _kinds("get_auth_context(x_user_id='u')\n") == [
        check.GET_AUTH_CONTEXT_WITHOUT_REQUEST
    ]


def test_get_auth_context_called_through_an_import_alias_is_reported() -> None:
    # Calendar's shape: the canonical dependency imported under another name
    # and awaited by hand without request=.
    src = (
        "from adaptix_contracts.auth_contracts import (\n"
        "    get_auth_context as _contracts_get_auth_context,\n"
        ")\n"
        "async def f():\n"
        "    await _contracts_get_auth_context(x_user_id='u')\n"
    )
    assert _kinds(src) == [check.GET_AUTH_CONTEXT_WITHOUT_REQUEST]


def test_aliased_get_auth_context_with_request_is_not_reported() -> None:
    src = (
        "from adaptix_contracts.auth_contracts import get_auth_context as gac\n"
        "gac(request=req)\n"
        "Depends(gac)\n"
    )
    assert _kinds(src) == []


def test_an_unrelated_name_is_not_treated_as_an_alias() -> None:
    src = "from x import other as gac\ngac(x_user_id='u')\n"
    assert _kinds(src) == []


def test_get_auth_context_as_dependency_or_with_request_is_not_reported() -> None:
    src = (
        "Depends(get_auth_context)\n"
        "get_auth_context(request=req)\n"
        "get_auth_context(**kwargs)\n"
    )
    assert _kinds(src) == []


def test_allowlist_requires_a_reason() -> None:
    with pytest.raises(check.AllowlistError):
        check.parse_allowlist("app.py:unbound-verifier\n")
    with pytest.raises(check.AllowlistError):
        check.parse_allowlist("app.py:not-a-kind  # reason\n")
    assert check.parse_allowlist(
        "# comment\n\napp.py:unbound-verifier  # worker\n"
    ) == {("app.py", check.UNBOUND_VERIFIER): "worker"}


def _write(tmp_path: Path, source: str) -> Path:
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "auth.py").write_text(source, encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "from x import verify_gateway_signature\n", encoding="utf-8"
    )
    return tmp_path


def test_unlisted_finding_fails_and_tests_are_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _write(tmp_path, "from x import verify_gateway_signature\n")
    assert check.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert "svc/auth.py:1: unbound-verifier" in out
    assert "tests/" not in out
    assert "1 finding(s), 0 allowlisted" in out


def test_allowlisted_finding_passes_and_stale_entries_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _write(tmp_path, "from x import verify_gateway_signature\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text(
        "svc/auth.py:unbound-verifier  # worker, no route\n"
        "svc/gone.py:unbound-verifier  # migrated\n",
        encoding="utf-8",
    )
    assert check.main([str(root), "--allowlist", str(allowlist)]) == 0
    out = capsys.readouterr().out
    assert "stale allowlist entry: svc/gone.py:unbound-verifier" in out
    assert "1 allowlisted across 2 entries, 0 refused, 1 stale" in out


def test_malformed_allowlist_exits_2(tmp_path: Path) -> None:
    root = _write(tmp_path, "x = 1\n")
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("svc/auth.py:unbound-verifier\n", encoding="utf-8")
    assert check.main([str(root), "--allowlist", str(allowlist)]) == 2


def test_this_repository_passes_with_its_allowlist() -> None:
    assert check.main([str(_ROOT), "--allowlist", str(_ALLOWLIST)]) == 0
