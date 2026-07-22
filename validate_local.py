"""Validación local del conector splunk: ejercita las 3 capacidades.

Requiere las env vars RUVIC_SPLUNK_* exportadas contra un servidor Splunk
de prueba. Splunk ofrece una imagen de Docker oficial para pruebas
locales (ver README.md), lo cual permite probar esto sin depender de un
tenant real de un cliente.
"""

from ruvic_splunk_connector import SplunkClient, setup_logging

setup_logging("INFO")
client = SplunkClient()

print("== 1. Listar indices ==")
indices = client.list_indexes()
print(f"  {len(indices)} indice(s) encontrado(s)")
for i in indices[:5]:
    print(f"    {i}")

print("== 2. Ejecutar una busqueda SPL simple (metadata interna, siempre disponible) ==")
resultado = client.execute_spl_search("| metadata type=sourcetypes index=_internal", max_results=5)
print(f"  sid={resultado['sid']} is_done={resultado['is_done']} filas={len(resultado['rows'])}")
for fila in resultado["rows"][:3]:
    print(f"    {fila}")

if resultado["sid"]:
    print(f"== 3. Consultar los resultados de ese mismo job via get_job_results ==")
    resultado2 = client.get_job_results(resultado["sid"], max_results=5)
    print(f"  is_done={resultado2['is_done']} filas={len(resultado2['rows'])}")

print("== 4. Confirmar que un comando SPL de escritura se bloquea por defecto ==")
try:
    client.execute_spl_search("index=main | delete")
    print("  ERROR: debio bloquearse")
except Exception as exc:
    print(f"  OK, bloqueado correctamente: {exc}")

print("\nValidación completa.")
