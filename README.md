# conector-splunk

Conector Ruvic para Splunk: ejecutar búsquedas SPL, listar índices, y obtener resultados de un job de búsqueda.

## Capacidades

`execute_spl_search`, `list_indexes`, `get_job_results`.

## Protección de seguridad incorporada

Por defecto, `execute_spl_search` **bloquea comandos SPL de escritura/ejecución** (`delete`, `outputlookup`, `outputcsv`, `collect`, `summaryindex`, `script`, `run`, `sendemail`, `mcollect`) — es un conector de consulta, no de modificación. Se puede habilitar con `allow_write_commands` si hace falta.

## Instalación

Requiere **Python ≥ 3.10**.

```bash
pip install git+https://github.com/tu-org/conector-splunk.git#subdirectory=lib
```

Para desarrollo local (editable, en un venv limpio):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib
```

## Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_SPLUNK_BASE_URL` | Sí | URL del puerto de administración (ej. `https://splunk.miempresa.com:8089`) |
| `RUVIC_SPLUNK_TOKEN` | Si modo token | Token de autenticación (recomendado) |
| `RUVIC_SPLUNK_USERNAME` / `..._PASSWORD` | Si modo usuario/contraseña | — |
| `RUVIC_SPLUNK_VERIFY_SSL` | No | `true`/`false`, default `true` |
| `RUVIC_SPLUNK_ALLOW_WRITE_COMMANDS` | No | `true`/`false`, default `false` |
| `RUVIC_SPLUNK_DEFAULT_EARLIEST_TIME` | No | Default `"-24h"` |
| `RUVIC_SPLUNK_MAX_WAIT_SECONDS` | No | Default `60` |
| `RUVIC_SPLUNK_REQUEST_TIMEOUT` | No | Segundos, default `30` |

El modo se detecta automáticamente: `TOKEN` presente → modo token; si no, `USERNAME`+`PASSWORD` → modo básico.

## Permisos / prerrequisitos en Splunk

1. Pide al administrador un **usuario o token dedicado** a esta integración.
2. Rol mínimo: **`user`** con capacidad **`search`** sobre los índices que el agente necesita consultar — nunca uses una cuenta `admin`.
3. Si vas a usar token: **Settings → Tokens** en Splunk Web, genera uno para el usuario de servicio.

## Cómo correr las pruebas locales

Splunk ofrece una **imagen oficial de Docker** para pruebas, lo que permite validar este conector sin depender de un tenant real:

```bash
docker run -d --name splunk-test -p 8089:8089 -p 8000:8000 \
  -e SPLUNK_START_ARGS='--accept-license' \
  -e SPLUNK_PASSWORD='ContraseñaSegura123!' \
  splunk/splunk:latest

# Espera 1-2 minutos a que Splunk termine de iniciar, luego:
export RUVIC_SPLUNK_BASE_URL=https://localhost:8089
export RUVIC_SPLUNK_USERNAME=admin
export RUVIC_SPLUNK_PASSWORD='ContraseñaSegura123!'
export RUVIC_SPLUNK_VERIFY_SSL=false  # el contenedor usa un certificado autofirmado

python test_connection.py
python validate_local.py
```

Prueba también el caso de error:

```bash
RUVIC_SPLUNK_PASSWORD=incorrecta python test_connection.py
# FALLO: Autenticación fallida: ...
```

## Limitaciones conocidas

- `execute_spl_search` espera de forma síncrona hasta `max_wait_seconds` — si la búsqueda tarda más, hay que consultar el resultado después con `get_job_results` usando el `sid` retornado.
- No implementa exportación de resultados en streaming para búsquedas con millones de eventos — usa `max_results` para acotar.
- No gestiona búsquedas guardadas (saved searches) ni alertas — solo búsquedas ad-hoc.

## Notas de integración

- El paquete pip es `ruvic-splunk-connector`; el import name es `ruvic_splunk_connector`.
- Única dependencia externa: `requests`.
- Ver `SKILL.md` para los ejemplos de uso que consume el agente.
