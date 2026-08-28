"""Import smoke coverage for modules no other test reaches.

WHY THIS EXISTS
---------------
`epcr/clinical_contracts.py`, `epcr/caregraph_contracts.py` and
`cad/nemsis_handoff.py` are shipped, importable modules that, before this file,
NO test imported and NO package `__init__` re-exported. Between them they hold
26 of the package's model definitions.

That combination is dangerous rather than merely untidy: class-level pydantic
configuration is evaluated at CLASS CREATION time, so a defect in it fails at
IMPORT, not at first use. With no test importing these modules, the suite could
report 1915 passing while a downstream service that imports any of them dies on
`import`. That is exactly what happened with the class-based `Config` blocks
these modules carried - the full suite surfaced only 2 of the package's 28
`PydanticDeprecatedSince20` warnings, because it never imported the three files
holding the other 26.

These tests are deliberately shallow. They assert the property that was
actually unprotected - that each module imports, that its models are
constructible, and that neither the module nor its models still rely on a
pydantic API scheduled for removal. They are not a substitute for behavioural
coverage of these contracts.
"""

from __future__ import annotations

import importlib
import inspect
import warnings

import pytest
from pydantic import BaseModel

# The modules that had no test importing them. Add to this list, never remove
# from it: an entry leaving means a shipped module lost its only import check.
UNREFERENCED_MODULES = (
    "adaptix_contracts.epcr.clinical_contracts",
    "adaptix_contracts.epcr.caregraph_contracts",
    "adaptix_contracts.cad.nemsis_handoff",
    "adaptix_contracts.auth.cognito",
)


def _models(module):
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj is not BaseModel
    ]


@pytest.mark.parametrize("dotted", UNREFERENCED_MODULES)
def test_module_imports_without_deprecation_warning(dotted: str) -> None:
    """Importing must not emit a pydantic removal warning.

    Class-based `Config` is consumed at class creation, so this fires on import
    and would become an ImportError under pydantic 3.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(importlib.import_module(dotted))

    offenders = [
        f"{w.category.__name__}: {w.message}"
        for w in caught
        if "PydanticDeprecatedSince" in w.category.__name__
    ]
    assert not offenders, (
        f"{dotted} still uses a pydantic API scheduled for removal: {offenders}. "
        "Replace `class Config:` with `model_config = ConfigDict(...)`."
    )


@pytest.mark.parametrize("dotted", UNREFERENCED_MODULES)
def test_module_defines_models_and_they_are_constructible(dotted: str) -> None:
    """Every model must build from its own defaults, or declare required fields.

    A model whose configuration is broken raises here rather than in a consumer.
    """
    module = importlib.import_module(dotted)
    models = _models(module)
    assert models, f"{dotted} defines no pydantic models - has it been emptied?"

    for model in models:
        # Models with required fields legitimately refuse to build with no
        # arguments; that ValidationError proves the schema is live. Anything
        # else - a config error, a bad default, an unresolved annotation - is a
        # real defect and propagates.
        try:
            model()
        except Exception as exc:  # noqa: BLE001 - narrowed immediately below
            if exc.__class__.__name__ != "ValidationError":
                raise AssertionError(
                    f"{dotted}.{model.__name__} failed to construct with "
                    f"{exc.__class__.__name__}: {exc}"
                ) from exc


@pytest.mark.parametrize("dotted", UNREFERENCED_MODULES)
def test_module_uses_no_class_based_config(dotted: str) -> None:
    """Belt-and-braces: no model may carry the pre-v2 `Config` inner class."""
    module = importlib.import_module(dotted)
    offenders = [
        m.__name__
        for m in _models(module)
        if isinstance(getattr(m, "Config", None), type)
    ]
    assert not offenders, (
        f"{dotted} models still declare a class-based Config: {offenders}"
    )
