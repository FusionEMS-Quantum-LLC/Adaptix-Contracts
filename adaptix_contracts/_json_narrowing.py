"""Truthful narrowing for decoded JSON values (package-internal).

A verified token or a signed gateway context arrives as decoded JSON: its
values are ``object`` until the reader checks them. ``isinstance(value, list)``
proves a list, but a type checker then knows nothing about the items, so every
item read from it is unknown. These guards say exactly what the check proved,
and nothing more:

* a JSON array is a ``list`` whose items are read as ``object``;
* a JSON object is a ``dict`` whose keys are ``str`` (JSON keys are always
  strings) and whose values are read as ``object``;
* any non-string sequence is read item by item as ``object``.

Each reader then narrows the items it uses. Nothing here coerces or converts.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeGuard


def is_json_list(value: object) -> TypeGuard[list[object]]:
    """True for a list; its items are then read as ``object``."""
    return isinstance(value, list)


def is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """True for a dict decoded from JSON, whose keys are therefore ``str``."""
    return isinstance(value, dict)


def is_object_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """True for any ``Sequence``; its items are then read as ``object``.

    A ``str`` is a sequence of its characters, and ``bytes`` of its byte
    values, so a caller that means "a sequence of entries" refuses those first.
    """
    return isinstance(value, Sequence)
