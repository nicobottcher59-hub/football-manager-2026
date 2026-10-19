# TS-14 — Persistence Architecture (SQLite opt-in)

## Objetivo y alcance

Crear una frontera de persistencia local versionada para soportar, en una etapa
posterior, carreras completas con clubes, futbolistas, fichajes, empleados,
economia, instalaciones y predio. **TS-14 no activa el guardado del entrenador
ni modifica la interfaz**. El `DevelopmentSession` y el servidor siguen en
memoria; los `WorldCareer.save_json/load_json` actuales continúan funcionando.

Se incorpora **solo una infraestructura reutilizable y un adaptador explícito
para archivos de resultados**; esto permite probar de verdad la base de datos
sin presentar un guardado incompleto como si fuera una carrera jugable.

## Capas

```text
Dominio Python ──> Adaptador de snapshot por módulo (futuro: manager, squad...)
                      │
           SaveDocument, SaveSection, EntityKey, EntityLink
                      │
                SQLiteSaveRepository
                      │
             archivo .sqlite3 local (stdlib)
```

- Los objetos de negocio no importan `sqlite3` ni dependen de rutas físicas.
- La capa de interfaz NO escribe directamente SQL.
- Cada módulo futuro define explícitamente su versión de payload y valida su
  reconstrucción antes de publicar cualquier estado en una sesión activa.
- `WorldCareer` se puede adaptar con `world_career_document`, `save_world_results`
  y `load_world_results`, **solo para resultados y temporadas**. Este adaptador
  invoca las validaciones del dominio tanto al guardar como al cargar.

## Esquema SQLite v1

Se usa exclusivamente la biblioteca estándar de Python; no hay Node ni servicio
externo. `PRAGMA user_version=1` es la versión de la **base**. La creación desde
una base vacía se hace en una transacción. Una base de versión desconocida o una
base ajena no versionada se rechaza sin modificarla; las migraciones futuras
requieren una versión nueva y transformaciones explícitas.

| Tabla | Responsabilidad |
| --- | --- |
| `save_slots` | ID estable, nombre visible, tipo, revisión para concurrencia optimista, UTC de creación/actualización |
| `save_sections` | Componentes JSON con versión individual y hash SHA-256, dependientes del slot |
| `save_entities` | Índice de identidades `(slot, kind, scope, entity_id)` sin depender de nombres ni posiciones |
| `save_links` | Relaciones dirigidas entre identidades del mismo slot con claves foráneas compuestas |

`PRAGMA foreign_keys=ON` se aplica en todas las conexiones. Un jugador con el
mismo identificador local en dos clubes puede distinguirse por el `scope`; esto
preserva las reglas de identidad del motor existente. El adaptador de resultados
indexa clubes y temporadas, con la relación `participates_in`. No crea jugadores
ni edificios ficticios y no supone que esas entidades estén ya modeladas.

## Contrato de consistencia

1. **Revision obligatoria:** `expected_revision=0` crea un slot; para reemplazarlo
   se debe usar exactamente la revisión recibida. Si otro proceso guardó antes,
   se lanza `SaveConflictError` y el slot anterior permanece intacto.
2. **Commit único:** metadatos, secciones e índice relacional se guardan en una
   sola transacción `BEGIN IMMEDIATE`; una excepción revierte la operación.
3. **Validación estricta:** JSON UTF-8, claves de objeto tipo `str`, sin `NaN` ni
   `Infinity`; las secciones se comprueban con SHA-256 al cargar. No se utiliza
   `pickle` ni se silencian los formatos desconocidos.
4. **Claves foráneas:** las relaciones inválidas se rechazan antes de guardar y
   son imposibles de insertar con FK habilitadas.
5. **Dominio canónico:** el archivo `world_results` pasa por
   `WorldCareer.validate_integrity()`; al cargar se comprueba también que el
   índice relacional corresponda a las entidades del mundo reconstruido.
6. **Sin cambios de formato existentes:** los JSON anteriores siguen válidos.
   No hay migración automática ni cambio de ruta de los guardados actuales.

El SHA-256 detecta modificaciones accidentales de payload, no proporciona
cifrado, autenticación ni protección contra ataques deliberados. La base es
local y de un solo jugador. Para respaldos futuros de una DB abierta, usar la
API `sqlite3.Connection.backup()` en vez de copiar un archivo mientras se escribe.

## Uso explícito por código (no se llama desde la UX)

```python
from football_manager.persistence import (
    SQLiteSaveRepository, save_world_results, load_world_results,
)

repo = SQLiteSaveRepository("./mis-partidas.sqlite3")
metadata = save_world_results(
    repo, slot_id="carrera-001", display_name="Temporada de prueba",
    career=world_career, expected_revision=0,
)
metadata_loaded, recovered = load_world_results(repo, "carrera-001")
# recovered contiene resultados/temporadas, NO una sesión del entrenador.
```

## Lo que se deja para TS-15

- Contratos de serialización y reconstrucción completos de
  `DevelopmentSession`, alineaciones, futbolistas, lesiones, tácticas,
  familiaridades, RNG, fecha actual y estado de simulación pendiente.
- Autosave, carga desde la UI, selector de partidas, respaldos, cierre inesperado
  de la aplicación y recuperación sin inconsistencias.
- Migraciones evolutivas y pruebas de ida/vuelta entre versiones de carrera.
- Partición del estado entre componentes para evitar reescribir el universo
  completo ante cada pequeña acción; medir antes de normalizar tablas específicas.

**Criterio para TS-15:** no se expondrá el botón Guardar/Cargar hasta demostrar
que el snapshot reproduce todas las decisiones y que retomar la simulación con
la misma semilla conserva la evolución del juego.

## Validación

Ejecutar desde la raíz del repositorio en PowerShell (sin Node):

```powershell
python -m pytest -ra tests/test_ts_14_persistence_architecture.py
python -m pytest -ra
```

La primera suite cubre: migración inicial y versiones futuras, transacciones,
revisiones concurrentes, referencialidad, Unicode, corrupción de payload,
validaciones de archivos JSON existentes y roundtrip de un WorldCareer de
resultados. La segunda suite protege todo el juego actual.

No hay comprobaciones de UI específicas porque **no se modificó la interfaz**.
