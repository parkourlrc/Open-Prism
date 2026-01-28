from __future__ import annotations

# Keep top-level `beswarm` import lightweight for packaged app.
# The desktop app imports tool modules directly (e.g. `beswarm.tools.worker`).

from .core import register_system_prompt_provider, clear_system_prompt_providers

# Re-export architext blocks (used by some upstream internals / dev scripts).
from .aient.aient.architext.architext import (  # noqa: F401
    Messages,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolCalls,
    ToolResults,
    Texts,
    RoleMessage,
    Images,
    Files,
)

