"""Cliente para ejecutar búsquedas SPL y consultar datos en Splunk.

Capacidades:
- execute_spl_search():  crear un job de búsqueda, esperar a que termine
                          y traer sus resultados (todo en una llamada).
- list_indexes():        listar los índices disponibles.
- get_job_results():     consultar los resultados de un job ya existente
                          (por su `sid`), útil si se creó por otro medio o
                          si `execute_spl_search` no alcanzó a terminar
                          dentro del tiempo de espera configurado.

Protección de seguridad incorporada: por defecto, este conector bloquea
comandos SPL que escriben o ejecutan algo fuera de la propia búsqueda
(`delete`, `outputlookup`, `outputcsv`, `collect`, `summaryindex`,
`script`, `run`, `sendemail`, `mcollect`) — es un conector de consulta,
no de modificación. Se puede habilitar con `allow_write_commands` si
hace falta.

Autenticación: token Bearer (recomendado) o usuario/contraseña, contra
el puerto de administración de Splunk (8089 por defecto). Las
credenciales SIEMPRE provienen de variables de entorno RUVIC_SPLUNK_*
(ver config.SplunkConfig.from_env). Prohibido hardcodearlas.
"""

from __future__ import annotations

import re
import time
from typing import Any

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException, Timeout

from .config import SplunkConfig
from .exceptions import (
    SplunkAuthError,
    SplunkDataError,
    SplunkNetworkError,
    SplunkSecurityError,
)
from .logging_utils import get_logger

_WRITE_COMMANDS = (
    "delete", "outputlookup", "outputcsv", "collect", "summaryindex",
    "script", "run", "sendemail", "mcollect",
)
_WRITE_COMMAND_RE = re.compile(
    r"\|\s*(" + "|".join(_WRITE_COMMANDS) + r")\b", re.IGNORECASE
)


class SplunkClient:
    """Cliente de Splunk autenticado por token o usuario/contraseña.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_SPLUNK_* (comportamiento estándar
            en el runtime de la plataforma).

    Ejemplo:
        >>> client = SplunkClient()  # lee RUVIC_SPLUNK_* del entorno
        >>> client.execute_spl_search("search index=main error", max_results=10)
        {'sid': '...', 'rows': [...], 'is_done': True}
    """

    def __init__(self, config: SplunkConfig | None = None) -> None:
        self.config = config or SplunkConfig.from_env()
        self._logger = get_logger()

    # ------------------------------------------------------------------ #
    # Autenticación / peticiones HTTP
    # ------------------------------------------------------------------ #

    def _request_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "verify": self.config.verify_ssl,
            "timeout": self.config.timeout,
        }
        if self.config.auth_mode == "token":
            kwargs["headers"] = {"Authorization": f"Bearer {self.config.token}"}
        else:
            kwargs["auth"] = (self.config.username, self.config.password)
        return kwargs

    def _request(self, method: str, path: str, **extra: Any) -> requests.Response:
        url = f"{self.config.base_url}{path}"
        kwargs = self._request_kwargs()
        kwargs.update(extra)
        try:
            return requests.request(method, url, **kwargs)
        except Timeout as exc:
            raise SplunkNetworkError(
                f"Tiempo de espera agotado ({self.config.timeout}s) llamando a {path}."
            ) from exc
        except RequestsConnectionError as exc:
            raise SplunkNetworkError(f"No se pudo conectar a {url}: {exc}") from exc
        except RequestException as exc:
            raise SplunkNetworkError(f"Error de red: {exc}") from exc

    def _raise_for_error(self, resp: requests.Response, context: str) -> None:
        message = resp.text[:300] or "Error desconocido"
        if resp.status_code in (401, 403):
            raise SplunkAuthError(
                f"Autenticación/permisos insuficientes en {context} (HTTP {resp.status_code}): {message}"
            )
        if resp.status_code == 404:
            raise SplunkDataError(f"No encontrado en {context}: {message}")
        if resp.status_code == 400:
            raise SplunkDataError(f"Solicitud inválida en {context} (SPL inválido?): {message}")
        raise SplunkDataError(f"Error de Splunk en {context} (HTTP {resp.status_code}): {message}")

    # ------------------------------------------------------------------ #
    # Protección de seguridad: bloqueo de comandos SPL de escritura
    # ------------------------------------------------------------------ #

    def _validate_spl_safety(self, spl: str) -> None:
        if self.config.allow_write_commands:
            return
        match = _WRITE_COMMAND_RE.search(spl)
        if match:
            raise SplunkSecurityError(
                f"Búsqueda bloqueada: contiene el comando SPL de escritura/ejecución "
                f"{match.group(1)!r}. Este conector solo permite búsquedas de consulta "
                "por defecto. Si necesitas usar este comando, activa "
                "'allow_write_commands' explícitamente en la configuración del conector."
            )

    @staticmethod
    def _normalize_spl(spl: str) -> str:
        """Splunk exige que la búsqueda empiece con 'search' o un comando
        generador (que arranca con '|'); si no, se lo agregamos."""
        stripped = spl.strip()
        if stripped.startswith("|") or stripped.lower().startswith("search "):
            return stripped
        return f"search {stripped}"

    # ------------------------------------------------------------------ #
    # Ping / prueba de conexión
    # ------------------------------------------------------------------ #

    def ping(self) -> bool:
        """Verifica las credenciales listando índices (barato, no ejecuta ninguna búsqueda)."""
        resp = self._request("GET", "/services/data/indexes", params={"output_mode": "json", "count": 1})
        if resp.status_code != 200:
            self._raise_for_error(resp, "ping")
        self._logger.info("Ping exitoso a Splunk (%s)", self.config.base_url)
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: ejecutar una búsqueda SPL (crear job + esperar + traer resultados)
    # ------------------------------------------------------------------ #

    def execute_spl_search(
        self,
        spl: str,
        earliest_time: str | None = None,
        latest_time: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Crea un job de búsqueda, espera a que termine, y trae sus resultados.

        Args:
            spl: consulta en lenguaje SPL (se le antepone "search " automáticamente
                si no empieza con "search" o un comando generador "|").
            earliest_time: límite inferior de tiempo (ej. "-24h", "-7d@d").
                Si se omite, usa el valor por defecto configurado (default "-24h").
            latest_time: límite superior de tiempo (ej. "now"). Opcional.
            max_results: máximo de filas a traer si el job termina a tiempo (default 100).

        Returns:
            Dict con "sid" (Id del job, útil para consultarlo después con
            `get_job_results` si no terminó a tiempo), "rows" (lista de
            dicts, vacía si no terminó), y "is_done" (bool).

        Raises:
            SplunkSecurityError: si el SPL contiene un comando de escritura
                no permitido.

        Ejemplo:
            >>> client.execute_spl_search("index=main error", earliest_time="-1h")
            {'sid': '1234.56', 'rows': [...], 'is_done': True}
        """
        if not spl or not spl.strip():
            raise SplunkDataError("La búsqueda SPL no puede estar vacía.")
        self._validate_spl_safety(spl)

        normalized = self._normalize_spl(spl)
        data = {
            "search": normalized,
            "earliest_time": earliest_time or self.config.default_earliest_time,
            "output_mode": "json",
        }
        if latest_time:
            data["latest_time"] = latest_time

        resp = self._request("POST", "/services/search/jobs", data=data)
        if resp.status_code not in (200, 201):
            self._raise_for_error(resp, "execute_spl_search (crear job)")

        sid = resp.json().get("sid")
        if not sid:
            raise SplunkDataError(f"Splunk no devolvió un sid de job: {resp.text[:300]}")

        is_done = self._wait_for_job(sid)
        rows: list[dict[str, Any]] = []
        if is_done:
            rows = self._fetch_job_results(sid, max_results)

        self._logger.info(
            "execute_spl_search sid=%s is_done=%s filas=%d", sid, is_done, len(rows)
        )
        return {"sid": sid, "rows": rows, "is_done": is_done}

    def _wait_for_job(self, sid: str) -> bool:
        deadline = time.time() + self.config.max_wait_seconds
        while time.time() < deadline:
            resp = self._request(
                "GET", f"/services/search/jobs/{sid}", params={"output_mode": "json"}
            )
            if resp.status_code != 200:
                self._raise_for_error(resp, f"consultar estado del job {sid}")
            content = resp.json()["entry"][0]["content"]
            if content.get("isDone") or content.get("dispatchState") == "DONE":
                return True
            time.sleep(self.config.poll_interval_seconds)
        return False

    def _fetch_job_results(self, sid: str, max_results: int) -> list[dict[str, Any]]:
        resp = self._request(
            "GET", f"/services/search/jobs/{sid}/results",
            params={"output_mode": "json", "count": max_results},
        )
        if resp.status_code != 200:
            self._raise_for_error(resp, f"traer resultados del job {sid}")
        return resp.json().get("results", [])

    # ------------------------------------------------------------------ #
    # Capacidad 2: listar índices
    # ------------------------------------------------------------------ #

    def list_indexes(self) -> list[dict[str, Any]]:
        """Lista los índices disponibles.

        Returns:
            Lista de dicts con "name" y "total_event_count" (si el servidor lo reporta).

        Ejemplo:
            >>> client.list_indexes()
            [{'name': 'main', 'total_event_count': 15234}, {'name': 'security', ...}]
        """
        resp = self._request(
            "GET", "/services/data/indexes", params={"output_mode": "json", "count": 0}
        )
        if resp.status_code != 200:
            self._raise_for_error(resp, "list_indexes")

        entries = resp.json().get("entry", [])
        indexes = [
            {
                "name": e.get("name"),
                "total_event_count": e.get("content", {}).get("totalEventCount"),
            }
            for e in entries
        ]
        self._logger.info("list_indexes: %d índice(s)", len(indexes))
        return indexes

    # ------------------------------------------------------------------ #
    # Capacidad 3: obtener resultados de un job existente
    # ------------------------------------------------------------------ #

    def get_job_results(self, sid: str, max_results: int = 100) -> dict[str, Any]:
        """Consulta el estado y los resultados de un job de búsqueda existente.

        Args:
            sid: Id del job (obtenido de `execute_spl_search`, o de otro medio).
            max_results: máximo de filas a traer si el job ya terminó (default 100).

        Returns:
            Dict con "sid", "rows" (vacía si el job no ha terminado), e "is_done".

        Ejemplo:
            >>> client.get_job_results("1234.56")
            {'sid': '1234.56', 'rows': [...], 'is_done': True}
        """
        if not sid or not sid.strip():
            raise SplunkDataError("sid no puede estar vacío.")

        resp = self._request(
            "GET", f"/services/search/jobs/{sid}", params={"output_mode": "json"}
        )
        if resp.status_code != 200:
            self._raise_for_error(resp, f"get_job_results {sid}")

        content = resp.json()["entry"][0]["content"]
        is_done = bool(content.get("isDone")) or content.get("dispatchState") == "DONE"

        rows: list[dict[str, Any]] = []
        if is_done:
            rows = self._fetch_job_results(sid, max_results)

        return {"sid": sid, "rows": rows, "is_done": is_done}
