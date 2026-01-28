from __future__ import annotations

import importlib
import os
import pkgutil
import sys

from .registry import registry, register_agent, register_tool

# Export config helpers that `chatgpt` expects early to avoid circular imports.
from .config import *  # noqa: F403,E402


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _minimal_mode() -> bool:
    if _truthy(os.environ.get("OCEANS_MINIMAL_PLUGINS")):
        return True
    if getattr(sys, "frozen", False):
        return True
    return False


excluded_modules = ["config", "registry", "__init__"]
current_dir = os.path.dirname(__file__)

if not _minimal_mode():
    for _, module_name, _ in pkgutil.iter_modules([current_dir]):
        if module_name not in excluded_modules:
            importlib.import_module(f".{module_name}", package=__name__)
else:
    module_list = os.environ.get("OCEANS_PLUGIN_MODULES", "").strip()
    if module_list:
        wanted = [m.strip() for m in module_list.split(",") if m.strip()]
    else:
        wanted = [
            "get_time",
            "read_image",
            "list_directory",
            "excute_command",
            "websearch",
            "arXiv",
            "readonly",
        ]
    for module_name in wanted:
        try:
            importlib.import_module(f".{module_name}", package=__name__)
        except Exception:
            pass

for tool_name, tool_func in registry.tools.items():
    globals()[tool_name] = tool_func

__all__ = [
    "PLUGINS",
    "function_call_list",
    "get_tools_result_async",
    "registry",
    "register_tool",
    "register_agent",
    "update_tools_config",
    "get_function_call_list",
] + list(registry.tools.keys())
