"""
Publisher registry.

Adapters self-register with @register("platform_name").  The registry
lazy-imports the adapter module on first lookup so importing
services.publishers doesn't pull every HTTP client into memory.

To add a new platform:
    1. Create services/publishers/<name>.py
    2. Decorate the class with @register("<name>")
    3. Nothing else — get_publisher("<name>") will find it
"""
from __future__ import annotations

import importlib
from typing import Type

from .base import Publisher

# The package these adapters live in.  NOTE: this is NOT `__name__` — that
# would resolve to `...publishers.registry`, which is a module, not a package.
_PACKAGE = "smauto.services.publishers"

_REGISTRY: dict[str, Type[Publisher]] = {}
_LOADED: set[str] = set()

# Everything that ships in this package.
_KNOWN = {"linkedin", "x", "instagram", "facebook", "youtube", "tiktok"}


def register(name: str):
    """Class decorator — adds a publisher class to the registry."""
    def deco(cls: Type[Publisher]) -> Type[Publisher]:
        _REGISTRY[name] = cls
        _LOADED.add(name)
        return cls
    return deco


def _ensure_loaded(name: str) -> None:
    """Lazy-import the adapter module if it hasn't been imported yet."""
    if name in _LOADED:
        return
    if name not in _KNOWN:
        raise KeyError(
            f"Unknown publisher '{name}'. Known: {sorted(_KNOWN)}. "
            f"If you wrote a custom one, make sure it's imported somewhere."
        )
    # Import the *module* `<package>.<name>`, e.g. smauto.services.publishers.linkedin
    importlib.import_module(f"{_PACKAGE}.{name}")


def get_publisher(name: str) -> Publisher:
    """Instantiate the publisher registered under `name`."""
    name = name.strip().lower()
    _ensure_loaded(name)
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Publisher '{name}' is known but not registered — "
                       f"did you forget @register('{name}')?")
    return cls()


def list_registered() -> list[str]:
    """Return the names of everything currently registered."""
    for n in _KNOWN:
        try:
            _ensure_loaded(n)
        except Exception:  # noqa: BLE001
            continue
    return sorted(_REGISTRY.keys())