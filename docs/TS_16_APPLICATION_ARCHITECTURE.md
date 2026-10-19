# TS-16 — Application Architecture (sobre TS-15)

## Objetivo

Separar las decisiones de aplicación del transporte HTTP y dejar de depender
exclusivamente de la estructura del repositorio para encontrar la interfaz.
**No cambia la experiencia de usuario, los endpoints, la simulación, ni el
formato de la base SQLite.** Tampoco incluye nuevas mecánicas.

## Límites entre módulos

```text
Navegador portable actual  (sin cambios)
           |
ui_shell/server.py       (HTTP: origen, JSON, códigos y rutas)
           |
ui_shell/application.py  (comandos de aplicación y publicación atómica)
           |
ui_shell/runtime.py      (estado mutable de la sesión, lock, jobs y admin)
           |
Domain / Fast Simulator / Progression / SQLite save repository
```

- `GameApplication.command(accion, datos)` no acepta rutas HTTP: utiliza
  `squad.command`, `match.command`, `progression.command`, `progression.job`,
  `career.save` y `career.load`. Esto permite una futura interfaz de escritorio
  sin tener que enviar peticiones a un servidor local para cada acción.
- `GameApplication.list_saves()` devuelve el mismo modelo de datos que `/api/career/saves`.
- El transporte sigue mapeando exactamente los mismos endpoints y errores;
  conserva `/api/...`, códigos HTTP, validación del origen, y JSON actuales.
- `UIRuntime` se movió a un módulo independiente. `server.UIRuntime`,
  `server.default_save_path` y `FootballUIHandler._match_command` conservan
  sus imports / firmas anteriores para compatibilidad.
- Las operaciones síncronas requieren `with runtime.lock:`. La API HTTP
  **ya mantiene** ese lock; quien consuma `GameApplication` directamente debe
  mantenerlo. Las simulaciones asíncronas mantienen su sincronización existente.
- El guardado/carga continúa siendo *opt-in* mediante la API y no hay autosave.

## Archivos de interfaz y empaquetado

`ui_shell/static_assets.py` busca el frontend en este orden:

1. Raíz inyectada mediante `create_server(frontend_root=...)`, útil para tests
   y un futuro instalador.
2. Variable de entorno `FM_FRONTEND_DIR`, si se configuró.
3. `frontend/` del repositorio editable.
4. `web_assets/` incluido dentro del paquete Python distribuido.

El servidor restringe los archivos servibles a `/portable/`, `/public/squad/`
y `/squad/`, y verifica que las rutas reales permanezcan dentro del subárbol
permitido (incluyendo links simbólicos). Mantiene el redirect `/` → `/portable/`.

`setup.py` copia **en el momento de compilar el wheel** los archivos originales
`frontend/portable` y `frontend/public/squad` a los recursos del paquete; por
eso no se mantienen dos frontends editables separados. `MANIFEST.in` incorpora
estos originales al source distribution. No se necesita Node, npm ni Vite.

**Límite:** esto permite construir un paquete Python instalable con la interfaz
portable, pero **no crea un `.exe`/instalador Windows**, no compila la demo React
y no modifica cómo se inicia la aplicación desde VS Code / BAT.

## Verificación

```powershell
python -m pytest -ra tests/test_ts_16_application_architecture.py
python -m pytest -ra tests/test_ts_15_career_save_reliability.py tests/test_ts_11_session_application_reliability.py
python -m pytest -ra
```

Para verificar el empaquetado, opcionalmente:

```powershell
python -m pip wheel . --no-deps --wheel-dir dist-test
```

Esto puede requerir setuptools actualizado, pero no Node.js. El wheel incluye
los recursos estáticos; las rutas locales no cambian.

El parche fue validado en Python 3.13 en Linux. Es necesario repetir pruebas
en Windows antes de integrar a `main`.

## Fuera de alcance

- Cambiar apariencia, navegación, roles, simulación, tácticas o lógica deportiva.
- Agregar botones Guardar / Cargar o autosave.
- Reemplazar la UI portable con React; empaquetar un ejecutable Windows.
- Migrar a servicios remotos ni incluir una base de datos servidor.

La auditoría completa de regresión, uso de memoria y continuidad de carrera se
mantiene como hito TS-17.
