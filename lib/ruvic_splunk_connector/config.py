"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_SPLUNK_.

Soporta dos modos, detectados automáticamente por las variables presentes:
- "token": autenticación por token Bearer (recomendado). Requiere TOKEN.
- "basic": usuario y contraseña. Requiere USERNAME y PASSWORD.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_SPLUNK_"


@dataclass(frozen=True)
class SplunkConfig:
    """Parámetros de conexión a un servidor Splunk (puerto de administración)."""

    base_url: str
    auth_mode: str  # "token" | "basic"
    token: str = ""
    username: str = ""
    password: str = ""
    verify_ssl: bool = True
    allow_write_commands: bool = False
    default_earliest_time: str = "-24h"
    poll_interval_seconds: float = 1.0
    max_wait_seconds: int = 60
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "SplunkConfig":
        """Construye la configuración desde las variables RUVIC_SPLUNK_*.

        Detecta el modo automáticamente: TOKEN presente -> token; si no,
        exige USERNAME y PASSWORD -> basic.

        Raises:
            ValueError: si falta BASE_URL o las credenciales del modo detectado.
        """
        base_url = os.environ.get(f"{ENV_PREFIX}BASE_URL", "").strip()
        if not base_url:
            raise ValueError(
                f"Falta la variable de entorno del conector splunk: "
                f"{ENV_PREFIX}BASE_URL. Configura el conector en Settings → Conectores."
            )
        if not (base_url.startswith("https://") or base_url.startswith("http://")):
            raise ValueError(
                f"{ENV_PREFIX}BASE_URL debe incluir el esquema y el puerto de administración "
                f"(ej. https://splunk.miempresa.com:8089): {base_url!r}"
            )

        verify_ssl_raw = os.environ.get(f"{ENV_PREFIX}VERIFY_SSL", "true").strip().lower()
        verify_ssl = verify_ssl_raw not in ("false", "0", "no")
        allow_write_raw = os.environ.get(f"{ENV_PREFIX}ALLOW_WRITE_COMMANDS", "false").strip().lower()
        allow_write = allow_write_raw in ("true", "1", "yes")

        common_kwargs = dict(
            base_url=base_url.rstrip("/"),
            verify_ssl=verify_ssl,
            allow_write_commands=allow_write,
            default_earliest_time=os.environ.get(f"{ENV_PREFIX}DEFAULT_EARLIEST_TIME", "-24h").strip() or "-24h",
            poll_interval_seconds=float(os.environ.get(f"{ENV_PREFIX}POLL_INTERVAL_SECONDS", "1")),
            max_wait_seconds=int(os.environ.get(f"{ENV_PREFIX}MAX_WAIT_SECONDS", "60")),
            timeout=int(os.environ.get(f"{ENV_PREFIX}REQUEST_TIMEOUT", "30")),
        )

        token = os.environ.get(f"{ENV_PREFIX}TOKEN", "").strip()
        if token:
            return cls(auth_mode="token", token=token, **common_kwargs)

        username = os.environ.get(f"{ENV_PREFIX}USERNAME", "").strip()
        password = os.environ.get(f"{ENV_PREFIX}PASSWORD", "")
        if username and password:
            return cls(auth_mode="basic", username=username, password=password, **common_kwargs)

        raise ValueError(
            f"Falta una credencial válida del conector splunk: define "
            f"{ENV_PREFIX}TOKEN (recomendado), o {ENV_PREFIX}USERNAME + "
            f"{ENV_PREFIX}PASSWORD (usuario y contraseña)."
        )
