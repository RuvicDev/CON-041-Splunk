---
name: splunk
description: "Usa la librería ruvic_splunk_connector para consultar eventos en Splunk - ejecutar una búsqueda SPL y traer sus resultados (execute_spl_search), listar los índices disponibles (list_indexes), y consultar los resultados de un job de búsqueda existente (get_job_results). Úsala cuando el usuario pida buscar eventos/logs en Splunk, explorar qué índices existen, o revisar el resultado de una búsqueda anterior. Por defecto, este conector NO permite comandos SPL de escritura (delete, outputlookup, collect, script, etc.) — solo consulta."
triggers:
- splunk
- spl
- buscar eventos
- indices splunk
- logs de seguridad
---

# Conector Splunk (ruvic_splunk_connector)

Librería Python para ejecutar búsquedas SPL y consultar índices en Splunk, autenticada por token o usuario/contraseña. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/tu-org/conector-splunk.git#subdirectory=lib`).

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `splunk` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_SPLUNK_BASE_URL` | Siempre requerida |
| `RUVIC_SPLUNK_TOKEN` | Si el modo es token (recomendado) |
| `RUVIC_SPLUNK_USERNAME` / `..._PASSWORD` | Si el modo es usuario/contraseña |
| `RUVIC_SPLUNK_VERIFY_SSL` | (opcional) `true`/`false`, default `true` |
| `RUVIC_SPLUNK_ALLOW_WRITE_COMMANDS` | (opcional) `true`/`false`, default `false` |
| `RUVIC_SPLUNK_DEFAULT_EARLIEST_TIME` | (opcional) default `"-24h"` |
| `RUVIC_SPLUNK_MAX_WAIT_SECONDS` | (opcional) default `60` |
| `RUVIC_SPLUNK_REQUEST_TIMEOUT` | (opcional) segundos, default `30` |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

El código generado **NUNCA** usa nombres de variable con segmento de alias (`_DEFAULT_`, `_TEST_`, `_PRODUCCION_`, etc.) — siempre `{ENV_PREFIX}{CAMPO}` tal cual, sin importar cuántas instancias de este conector haya configuradas. Esto aplica salvo que dichos nombres aparezcan explícitamente en una sección autogenerada al final de este skill.

## Conexión (siempre igual)

```python
from ruvic_splunk_connector import SplunkClient

client = SplunkClient()  # lee RUVIC_SPLUNK_* del entorno automáticamente
```

## Capacidad 1 — Ejecutar una búsqueda SPL

Crea el job, espera a que termine (hasta el tiempo configurado), y trae los resultados en una sola llamada:

```python
resultado = client.execute_spl_search("index=security sourcetype=firewall action=blocked", earliest_time="-4h")
if resultado["is_done"]:
    for fila in resultado["rows"]:
        print(fila)
else:
    print(f"El job {resultado['sid']} no terminó a tiempo — consúltalo después con get_job_results")
```

No es necesario escribir "search" al inicio — se agrega automáticamente si hace falta. Siempre incluye `earliest_time` (o confía en el valor por defecto configurado) para evitar búsquedas accidentales sobre "todo el tiempo", que son lentas y costosas en un Splunk real.

## Capacidad 2 — Listar índices

```python
indices = client.list_indexes()
for i in indices:
    print(f"{i['name']}: {i['total_event_count']} eventos")
```

## Capacidad 3 — Consultar los resultados de un job existente

Útil si `execute_spl_search` no terminó a tiempo, o si el `sid` viene de otro lugar:

```python
resultado = client.get_job_results("1234567890.56")
if resultado["is_done"]:
    print(resultado["rows"])
else:
    print("Todavía no termina, intenta de nuevo en unos segundos")
```

## Este conector es de solo consulta por defecto

`execute_spl_search` **rechaza automáticamente** cualquier búsqueda que contenga comandos SPL de escritura/ejecución (`delete`, `outputlookup`, `outputcsv`, `collect`, `summaryindex`, `script`, `run`, `sendemail`, `mcollect`) salvo que el admin haya activado `allow_write_commands` explícitamente. Si la operación falla con `SplunkSecurityError`, informa que el conector está en modo de solo consulta — no intentes rodear esta protección.

## Manejo de errores

```python
from ruvic_splunk_connector import (
    SplunkAuthError, SplunkNetworkError, SplunkSecurityError, SplunkDataError,
)

try:
    client.execute_spl_search("index=main error")
except SplunkAuthError:
    print("Credenciales inválidas o permisos insuficientes — revisa la configuración del conector")
except SplunkNetworkError:
    print("No se pudo conectar a Splunk — revisa la red/VPN")
except SplunkSecurityError as e:
    print(f"Búsqueda bloqueada por seguridad: {e}")
except SplunkDataError as e:
    print(f"Error de datos: {e}")  # ej. SPL inválido, job no encontrado
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_SPLUNK_*` (el constructor de `SplunkClient` ya lo hace).
2. Nunca imprimas `RUVIC_SPLUNK_TOKEN` ni `RUVIC_SPLUNK_PASSWORD` en logs ni en la salida.
3. Siempre especifica (o confía en el default de) `earliest_time` — evita búsquedas sobre todo el histórico, que son lentas en Splunk real.
4. No intentes construir búsquedas con comandos de escritura salvo que sepas que `allow_write_commands` está activo.
5. Si `is_done` es `False`, no asumas que la búsqueda falló — informa al usuario que puede tardar más y ofrece consultar de nuevo con `get_job_results` usando el `sid` retornado.
