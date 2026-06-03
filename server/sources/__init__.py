"""Source layer — one of the three extension points.

A source turns a raw, source-specific payload (already decrypted from the
transport envelope) into the normalized :class:`~server.models.SignalEvent`.
The pipeline engine never sees source-specific shapes; it only sees
``SignalEvent``. To add a new signal origin (browser extension, desktop app),
implement :class:`BaseSource` and register it.
"""

from server.sources.base import BaseSource, SourceError, get_source, register_source
from server.sources.email import EmailSource
from server.sources.notification import NotificationSource
from server.sources.sms import SmsSource

__all__ = [
    "BaseSource",
    "SourceError",
    "get_source",
    "register_source",
    "SmsSource",
    "EmailSource",
    "NotificationSource",
]
