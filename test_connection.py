"""Prueba de conexión estándar del conector splunk.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_SPLUNK_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Verifica las credenciales listando índices."""
    try:
        from ruvic_splunk_connector import (
            SplunkAuthError,
            SplunkClient,
            SplunkDataError,
            SplunkNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-splunk-connector no está instalada. "
            "Instala con: pip install git+https://github.com/tu-org/"
            "conector-splunk.git#subdirectory=lib",
        )

    try:
        client = SplunkClient()  # valida config y credenciales del modo detectado
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except SplunkAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except SplunkNetworkError as exc:
        return False, f"Error de red: {exc}"
    except SplunkDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return True, f"Conexión exitosa a {client.config.base_url} (modo: {client.config.auth_mode})"


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
