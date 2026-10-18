"""``gateway_hmac_enforced()``: the public read of gateway-HMAC enforcement (Contracts #403).

Services need to know whether an ABSENT gateway signature is rejected, for
example to report their trust posture on a health route. Before 5.44.0 the only
way was the private ``auth_contracts._gateway_hmac_enforce()``, which Finance
and TrustSign call directly, while HL7, AssetOps and Device copy its logic. A
copy can drift from the library's real behaviour and then misreport the
posture, so the library now publishes the one resolution:

* ``ADAPTIX_GATEWAY_HMAC_ENFORCE`` explicitly true-y (``true``/``1``/``yes``,
  any case, surrounding whitespace ignored) -> ``True`` in every environment;
* explicitly false-y (``false``/``0``/``no``) -> ``False`` in every environment;
* unset, blank or any other value -> ``True`` in production
  (``ENVIRONMENT`` ``production``/``prod``), ``False`` elsewhere.

The private name stays as a deprecated alias (the same function object) until
the next major, and must agree with the public one on every case.
"""

from __future__ import annotations

import pytest

from adaptix_contracts import auth_contracts
from adaptix_contracts.auth_contracts import gateway_hmac_enforced

_ENFORCE_ENV = "ADAPTIX_GATEWAY_HMAC_ENFORCE"
_ENVIRONMENT_ENV = "ENVIRONMENT"

#: ``ENVIRONMENT`` values that mean production (``None`` leaves it unset).
_PRODUCTION: tuple[str, ...] = ("production", "prod", " Production ")
#: ``ENVIRONMENT`` values that do not (``None`` leaves it unset).
_NON_PRODUCTION: tuple[str | None, ...] = (None, "", "staging", "development")

_TRUTHY: tuple[str, ...] = ("true", "1", "yes", "TRUE", " Yes ")
_FALSY: tuple[str, ...] = ("false", "0", "no", "FALSE", " No ")
#: Unset (``None``), blank, and values outside both lists: the environment decides.
#: ``on``/``off``/``enabled`` are NOT recognised, so they fall back too.
_UNRESOLVED: tuple[str | None, ...] = (None, "", "   ", "on", "off", "enabled")

_ENVIRONMENTS: tuple[str | None, ...] = (*_PRODUCTION, *_NON_PRODUCTION)
_ALL_RAW: tuple[str | None, ...] = (*_TRUTHY, *_FALSY, *_UNRESOLVED)

#: Deprecated names consumers still resolve on the module, each with the
#: public function it must agree with. Read as attributes of the module, the
#: way a consumer's ``auth_contracts._gateway_hmac_enforce()`` resolves them.
_DEPRECATED_ALIASES: tuple[tuple[str, str], ...] = (
    ("_gateway_hmac_enforce", "gateway_hmac_enforced"),
)


def _set_env(monkeypatch: pytest.MonkeyPatch, name: str, value: str | None) -> None:
    """Set ``name`` to ``value``, or remove it when ``value`` is ``None``."""
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


def _apply(
    monkeypatch: pytest.MonkeyPatch, environment: str | None, raw: str | None
) -> None:
    _set_env(monkeypatch, _ENVIRONMENT_ENV, environment)
    _set_env(monkeypatch, _ENFORCE_ENV, raw)


@pytest.mark.parametrize("environment", _ENVIRONMENTS)
@pytest.mark.parametrize("raw", _TRUTHY)
def test_explicit_truthy_value_enforces_in_every_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str | None, raw: str
) -> None:
    _apply(monkeypatch, environment, raw)

    assert gateway_hmac_enforced() is True


@pytest.mark.parametrize("environment", _ENVIRONMENTS)
@pytest.mark.parametrize("raw", _FALSY)
def test_explicit_falsy_value_opts_out_in_every_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str | None, raw: str
) -> None:
    _apply(monkeypatch, environment, raw)

    assert gateway_hmac_enforced() is False


@pytest.mark.parametrize("environment", _PRODUCTION)
@pytest.mark.parametrize("raw", _UNRESOLVED)
def test_unset_blank_or_unrecognised_value_fails_closed_in_production(
    monkeypatch: pytest.MonkeyPatch, environment: str, raw: str | None
) -> None:
    _apply(monkeypatch, environment, raw)

    assert gateway_hmac_enforced() is True


@pytest.mark.parametrize("environment", _NON_PRODUCTION)
@pytest.mark.parametrize("raw", _UNRESOLVED)
def test_unset_blank_or_unrecognised_value_is_off_outside_production(
    monkeypatch: pytest.MonkeyPatch, environment: str | None, raw: str | None
) -> None:
    _apply(monkeypatch, environment, raw)

    assert gateway_hmac_enforced() is False


def test_the_value_is_read_on_every_call_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply(monkeypatch, "production", None)
    assert gateway_hmac_enforced() is True

    _apply(monkeypatch, "production", "false")
    assert gateway_hmac_enforced() is False

    _apply(monkeypatch, None, "true")
    assert gateway_hmac_enforced() is True


def test_only_the_public_name_is_exported() -> None:
    assert "gateway_hmac_enforced" in auth_contracts.__all__
    assert "_gateway_hmac_enforce" not in auth_contracts.__all__


@pytest.mark.parametrize(("alias", "replacement"), _DEPRECATED_ALIASES)
def test_deprecated_private_name_is_the_public_function(
    alias: str, replacement: str
) -> None:
    assert getattr(auth_contracts, alias) is getattr(auth_contracts, replacement)


@pytest.mark.parametrize(("alias", "replacement"), _DEPRECATED_ALIASES)
@pytest.mark.parametrize("environment", _ENVIRONMENTS)
@pytest.mark.parametrize("raw", _ALL_RAW)
def test_deprecated_private_name_agrees_with_the_public_one(
    monkeypatch: pytest.MonkeyPatch,
    alias: str,
    replacement: str,
    environment: str | None,
    raw: str | None,
) -> None:
    _apply(monkeypatch, environment, raw)
    deprecated = getattr(auth_contracts, alias)
    public = getattr(auth_contracts, replacement)
    assert callable(deprecated)
    assert callable(public)

    deprecated_result = deprecated()
    public_result = public()

    assert isinstance(deprecated_result, bool)
    assert deprecated_result is public_result
