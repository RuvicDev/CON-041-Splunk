"""Excepciones propias del conector Splunk.

Separan los tipos de fallo que el usuario debe distinguir: configuración
inválida, autenticación, red, seguridad (comando SPL de escritura
bloqueado), y datos (SPL inválido, job/índice inexistente).
"""


class SplunkConnectorError(Exception):
    """Error base del conector."""


class SplunkConfigError(SplunkConnectorError):
    """Configuración inválida: falta un campo requerido."""


class SplunkAuthError(SplunkConnectorError):
    """Token o usuario/contraseña inválidos, o sin permisos suficientes."""


class SplunkNetworkError(SplunkConnectorError):
    """No se pudo alcanzar el servidor Splunk (DNS, timeout, red, TLS)."""


class SplunkSecurityError(SplunkConnectorError):
    """La búsqueda fue bloqueada por una protección de seguridad: contiene
    un comando SPL de escritura/ejecución no permitido."""


class SplunkDataError(SplunkConnectorError):
    """La operación es válida pero el SPL es inválido, el job no existe,
    o el servidor rechazó la operación por una razón propia."""
