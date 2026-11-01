"""Contracts #375 step 4: the static check that refuses an app without the installer."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from _asgi_client import ASGIClient

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _ROOT / "scripts" / "check_input_free_validation_errors.py"
_ALLOWLIST = _ROOT / "scripts" / "input_free_validation_errors_allowlist.txt"

# Stands in for a patient name; it must never come back once installed.
_LAST_NAME = "Zyxwvutsrq"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "adaptix_check_input_free_validation_errors", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load_module()


def _findings(source: str) -> list[tuple[int, str]]:
    return [(f.line, f.kind) for f in check.scan_source(source, "main.py")]


def test_app_without_the_installer_is_reported() -> None:
    src = "from fastapi import FastAPI\napp = FastAPI()\n"
    assert _findings(src) == [(2, check.MISSING_INSTALLER)]


def test_app_with_the_installer_is_not_reported() -> None:
    src = (
        "from fastapi import FastAPI\n"
        "from adaptix_contracts.validation_errors import (\n"
        "    install_input_free_validation_errors,\n"
        ")\n"
        "app = FastAPI()\n"
        "install_input_free_validation_errors(app)\n"
    )
    assert _findings(src) == []


@pytest.mark.parametrize(
    "src",
    [
        (
            "from adaptix_contracts.validation_errors import (\n"
            "    install_input_free_validation_errors as install,\n"
            ")\n"
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "install(app)\n"
        ),
        (
            "from adaptix_contracts import validation_errors\n"
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "validation_errors.install_input_free_validation_errors(\n"
            "    app, server_side_errors=False\n"
            ")\n"
        ),
        (
            "from fastapi import FastAPI\n"
            "from adaptix_contracts.validation_errors import (\n"
            "    install_input_free_validation_errors,\n"
            ")\n"
            "def create_app() -> FastAPI:\n"
            "    app = FastAPI(title='svc')\n"
            "    install_input_free_validation_errors(app)\n"
            "    return app\n"
        ),
    ],
)
def test_installer_through_an_alias_module_or_factory_counts(src: str) -> None:
    assert _findings(src) == []


@pytest.mark.parametrize(
    "src",
    [
        "from fastapi import FastAPI as App\napp = App()\n",
        "import fastapi\napp = fastapi.FastAPI()\n",
        "import fastapi as fa\napp = fa.FastAPI()\n",
    ],
)
def test_app_built_through_an_alias_is_reported(src: str) -> None:
    assert _findings(src) == [(2, check.MISSING_INSTALLER)]


def test_a_second_app_needs_its_own_call() -> None:
    # A mounted sub-app does not use its parent's exception handlers.
    src = (
        "from fastapi import FastAPI\n"
        "from adaptix_contracts.validation_errors import (\n"
        "    install_input_free_validation_errors,\n"
        ")\n"
        "app = FastAPI()\n"
        "admin = FastAPI()\n"
        "install_input_free_validation_errors(app)\n"
        "app.mount('/admin', admin)\n"
    )
    findings = check.scan_source(src, "main.py")
    assert [(f.line, f.kind) for f in findings] == [
        (5, check.MISSING_INSTALLER),
        (6, check.MISSING_INSTALLER),
    ]
    assert findings[0].detail == "2 app(s), 1 installer call(s) in this file"


def test_names_in_strings_and_docstrings_are_ignored() -> None:
    src = '"""Call after ``FastAPI(...)``."""\nx = "FastAPI()"\n'
    assert _findings(src) == []


def test_unrelated_fastapi_name_from_another_module_is_still_reported() -> None:
    # A bare ``FastAPI(`` is the census's own criterion; a star import or a
    # re-export cannot be told apart from the real class at the call site.
    assert _findings("app = FastAPI()\n") == [(1, check.MISSING_INSTALLER)]


@pytest.mark.parametrize(
    "src",
    [
        (
            "from fastapi import FastAPI\n"
            "from fastapi.exceptions import RequestValidationError\n"
            "app = FastAPI()\n"
            "@app.exception_handler(RequestValidationError)\n"
            "async def h(request, exc): ...\n"
        ),
        (
            "from fastapi import FastAPI\n"
            "from fastapi import exceptions\n"
            "app = FastAPI()\n"
            "app.add_exception_handler(exceptions.RequestValidationError, h)\n"
        ),
        (
            "from fastapi import FastAPI\n"
            "from fastapi.exceptions import RequestValidationError\n"
            "app = FastAPI(exception_handlers={RequestValidationError: h})\n"
        ),
    ],
)
def test_own_handler_is_still_reported_and_named_in_the_detail(src: str) -> None:
    findings = check.scan_source(src, "main.py")
    assert [f.kind for f in findings] == [check.MISSING_INSTALLER]
    assert findings[0].detail.endswith(
        "registers its own RequestValidationError handler"
    )


def test_allowlist_requires_a_reason() -> None:
    with pytest.raises(check.AllowlistError):
        check.parse_allowlist("main.py:missing-installer\n")
    with pytest.raises(check.AllowlistError):
        check.parse_allowlist("main.py:not-a-kind  # reason\n")
    assert check.parse_allowlist(
        "# comment\n\nmain.py:missing-installer  # own handler drops input\n"
    ) == {("main.py", check.MISSING_INSTALLER): "own handler drops input"}


_SERVICE = """\
from fastapi import FastAPI
from pydantic import BaseModel
{import_line}

class Lookup(BaseModel):
    last_name: str
    dob: str


def create_app() -> FastAPI:
    app = FastAPI()

    @app.post("/lookup")
    async def lookup(body: Lookup) -> dict[str, str]:
        return {{"dob": body.dob}}

{install_line}
    return app
"""


def _write_service(tmp_path: Path, *, installed: bool) -> Path:
    import_line = (
        "from adaptix_contracts.validation_errors import "
        "install_input_free_validation_errors"
        if installed
        else ""
    )
    install_line = "    install_input_free_validation_errors(app)" if installed else ""
    service = tmp_path / "svc"
    service.mkdir()
    (service / "main.py").write_text(
        _SERVICE.format(import_line=import_line, install_line=install_line),
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    return service / "main.py"


@pytest.fixture
def import_service() -> Iterator[object]:
    loaded: list[str] = []

    def load(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        loaded.append(name)
        spec.loader.exec_module(module)
        return module

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def _refused_lookup_text(module) -> tuple[int, str]:
    # A missing field: FastAPI's default answer repeats the whole body.
    response = ASGIClient(module.create_app()).post(
        "/lookup", json={"last_name": _LAST_NAME}
    )
    return response.status_code, response.text


def test_the_app_it_refuses_repeats_the_patient_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], import_service
) -> None:
    main_py = _write_service(tmp_path, installed=False)
    assert check.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "svc/main.py:11: missing-installer" in out
    assert "tests/" not in out
    assert "1 finding(s), 0 allowlisted" in out

    status, text = _refused_lookup_text(
        import_service(main_py, "adaptix_input_free_fixture_bare")
    )
    assert status == 422
    assert _LAST_NAME in text


def test_the_app_it_passes_does_not_repeat_the_patient_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], import_service
) -> None:
    main_py = _write_service(tmp_path, installed=True)
    assert check.main([str(tmp_path)]) == 0
    assert "0 finding(s)" in capsys.readouterr().out

    status, text = _refused_lookup_text(
        import_service(main_py, "adaptix_input_free_fixture_installed")
    )
    assert status == 422
    assert _LAST_NAME not in text
    assert '"loc":["body","dob"]' in text


def test_allowlisted_finding_passes_and_stale_entries_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_service(tmp_path, installed=False)
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text(
        "svc/main.py:missing-installer  # own handler drops input\n"
        "svc/gone.py:missing-installer  # adopted the installer\n",
        encoding="utf-8",
    )
    assert check.main([str(tmp_path), "--allowlist", str(allowlist)]) == 0
    out = capsys.readouterr().out
    assert "stale allowlist entry: svc/gone.py:missing-installer" in out
    assert "1 allowlisted across 2 entries, 0 refused, 1 stale" in out


def test_malformed_allowlist_exits_2(tmp_path: Path) -> None:
    allowlist = tmp_path / "allow.txt"
    allowlist.write_text("svc/main.py:missing-installer\n", encoding="utf-8")
    assert check.main([str(tmp_path), "--allowlist", str(allowlist)]) == 2


def test_this_repository_passes_with_its_allowlist() -> None:
    assert check.main([str(_ROOT), "--allowlist", str(_ALLOWLIST)]) == 0
