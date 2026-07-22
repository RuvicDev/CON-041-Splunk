"""Conector Ruvic para Splunk (búsquedas SPL, solo lectura por defecto)."""

from .client import SplunkClient
from .config import ENV_PREFIX, SplunkConfig
from .exceptions import (
    SplunkAuthError,
    SplunkConfigError,
    SplunkConnectorError,
    SplunkDataError,
    SplunkNetworkError,
    SplunkSecurityError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "SplunkAuthError",
    "SplunkClient",
    "SplunkConfig",
    "SplunkConfigError",
    "SplunkConnectorError",
    "SplunkDataError",
    "SplunkNetworkError",
    "SplunkSecurityError",
    "setup_logging",
]

__version__ = "1.0.0"
