"""Action layer — one of the three extension points.

An action does something with extracted data: post to Telegram, write a Firefly
III transaction, append a Sheet row, POST a webhook, append to a file. To add a
new one (Notion, Obsidian, Home Assistant), implement :class:`BaseAction` and
register it with ``@action("your_type")``.
"""

# Importing the modules registers their action types as a side effect.
from server.actions import file as _file  # noqa: F401
from server.actions import firefly as _firefly  # noqa: F401
from server.actions import notion as _notion  # noqa: F401
from server.actions import sheet as _sheet  # noqa: F401
from server.actions import telegram as _telegram  # noqa: F401
from server.actions import webhook as _webhook  # noqa: F401
from server.actions.base import ActionContext, ActionError, BaseAction, build_action, register

__all__ = [
    "BaseAction",
    "ActionContext",
    "ActionError",
    "build_action",
    "register",
]
