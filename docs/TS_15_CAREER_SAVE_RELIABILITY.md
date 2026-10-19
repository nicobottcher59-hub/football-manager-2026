# TS-15 — Career Save Reliability (SQLite)

## Alcance

Esta etapa parte de **TS-14**. Agrega guardado y restauración de la
`DevelopmentSession` jugable, de forma **opcional**, con la interfaz existente
sin cambios. No activa autosave ni añade botones. El guardado funciona desde
los servicios Python o la API HTTP local; la integración visual se evaluará más
adelante si se autoriza un cambio de UX.

La sesión incluye:

- fecha actual, semillas del simulador, mundo y resultados, historial de carrera;
- equipos, plantillas, identidades de jugadores, atributos, lesiones, fatiga,
  confianza, moral, familiaridad táctica y posicional;
- formación, alineaciones, suplentes, roles, instrucciones tácticas;
- competiciones, fixtures, eliminatorias, selecciones de participantes y
  estados temporales necesarios para continuar una temporada;
- metadatos de la interfaz actuales: dorsales, flags de transferibilidad y
  resumen del último encuentro.

**No** se guardan las ediciones temporales de una previa que todavía no fueron
confirmadas en un partido, ni un trabajo de simulación asíncrona en curso.
No hay sistemas financieros, empleados, instalaciones o mercado de fichajes
persistentes porque esas mecánicas aún no existen.

## Contrato técnico

`manager_career_document` construye un documento SQLite `manager_career`
con dos secciones de versión 1: `manager_state` y `ui_metadata`.

El codec `session_codec` serializa el grafo de objetos con referencias
explícitas: una instancia de `Player` compartida por el club y la alineación
sigue siendo la **misma** después de recuperar una partida. Solo deserializa
clases de módulos previamente permitidos del juego. No utiliza `pickle` ni
importa nombres arbitrarios suministrados por un archivo.

Los límites de integridad son:

1. Validar las referencias del mundo, el historial, la plantilla y las tácticas
   **antes de escribir** y **después de reconstruir** la partida.
2. Validar el catálogo relacional de jugadores, clubes y temporadas contra las
   entidades reconstruidas.
3. Comprobar checksums SHA-256 de las secciones y rechazar versiones futuras
   desconocidas, sin reinterpretarlas o intentar migrarlas silenciosamente.
4. Conservar `expected_revision` para impedir sobrescrituras por estados
   obsoletos. SQLite confirma los datos del slot y su índice en una transacción.
5. En la API, construir la nueva sesión fuera del estado público; **solo
   reemplazar la sesión activa cuando toda la carga haya terminado bien**.
6. Bloquear guardado y carga mientras haya una simulación asíncrona activa.

La base SQLite sigue en la versión de esquema 1 de TS-14. El guardado de
manager (`manager_state` v1) está versionado por separado y no sustituye los
archivos `world_results`/JSON antiguos. No hay una migración desde JSON de
**resultados** a una **carrera**: faltan jugadores y tácticas en ese origen.

### Backup / recuperación

`SQLiteSaveRepository.backup_to(destino)` usa la API de backup de SQLite y
reemplaza atómicamente el destino *solo al finalizar*. No se debe copiar la
base abierta a mano con el Explorador de Windows. Es una copia de seguridad
**manual**, no un autosave ni un sistema de backups rotativos automáticos.

El directorio por defecto de guardados es:

- Windows: `%LOCALAPPDATA%\FootballManagerGame\saves.sqlite3`
- Linux: `~/.local/share/football-manager-game/saves.sqlite3`

La variable de entorno `FM_SAVE_DATABASE` permite configurar la ubicación
antes de abrir el servidor. Por defecto no se almacena en el repositorio Git
ni en OneDrive.

## Uso para desarrollo (sin botones nuevos)

Primero abrir el juego con `INICIAR_INTERFAZ_WINDOWS.bat` o el comando que ya
utilizabas, y luego abrir **otro PowerShell**:

```powershell
$base = 'http://127.0.0.1:8765'

# Primer guardado en el slot: revision 0 = crearlo.
Invoke-RestMethod -Uri "$base/api/career/save" -Method Post -ContentType 'application/json' -Body '{"slot_id":"mi-carrera","display_name":"Carrera principal","expected_revision":0}'

# Comprobar los slots existentes y la revision de cada uno.
Invoke-RestMethod -Uri "$base/api/career/saves"

# Cargar el estado completo del slot en la sesion en ejecucion.
Invoke-RestMethod -Uri "$base/api/career/load" -Method Post -ContentType 'application/json' -Body '{"slot_id":"mi-carrera"}'
```

Para **actualizar** el mismo slot, pasar `expected_revision=1` después del
primer guardado, luego 2 y así sucesivamente. Una revisión obsoleta devuelve
HTTP 409 y no sobrescribe nada. Si cargás otro slot, el navegador puede
necesitar refrescar las vistas abiertas, porque el estado del juego cambió.

### Respaldar la base con Python

Con la aplicación cerrada o abierta, ejecutar:

```powershell
@'
from football_manager.persistence import SQLiteSaveRepository
from football_manager.ui_shell.server import default_save_path
path = default_save_path()
backup = path.with_name('saves-backup.sqlite3')
SQLiteSaveRepository(path).backup_to(backup)
print('Backup creado:', backup)
'@ | python -
```

Para recuperar una copia, **cerrar la aplicación** y resguardar antes el archivo
principal existente. Luego reemplazar la base principal con la copia de
seguridad. Verificar al abrir que aparece el slot y que puede cargarse. La
copia incluye todos los slots existentes en ese instante.

## Limitaciones explícitas

- No hay botón Guardar/Cargar ni autosave, preservando la UX aprobada.
- Los cambios de modelo futuros necesitarán una migración declarada o una nueva
  versión de `manager_state`, en lugar de saltarse el contrato.
- Guardar la sesión completa puede crecer con muchas ligas y temporadas. Antes
  de normalizar datos se realizarán mediciones de rendimiento/espacio.
- El estado que ya estaba cargado **antes de TS-15** no aparece automáticamente
  en la base: hay que crear un slot al menos una vez.
- Los nuevos sistemas de economía, contratos, juveniles, empleados o predio
  tendrán sus propias secciones versionadas cuando existan.
- Se deben completar las pruebas de Windows y el flujo manual con la API antes
  de considerar TS-15 integrado en `main`.

## Pruebas

```powershell
python -m pytest -ra tests/test_ts_15_career_save_reliability.py
python -m pytest -ra tests/test_ts_14_persistence_architecture.py
python -m pytest -ra
```

Las pruebas específicas abarcan continuidad determinista tras guardar/cargar,
identidad canónica de futbolistas, integridad de datos e índices, corrupción,
revisión concurrente, backups y endpoints HTTP locales. Sin Node.js.
