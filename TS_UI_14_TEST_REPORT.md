# TS-UI-14 — Other Leagues: identidad visual escalable

## Alcance
Parche incremental sobre **TS-UI-13.01 — Competition Centre Hero** (y todos los anteriores).

- Cabecera independiente **Other Leagues**, con arte genérico de estadio ya incluido en TS-UI-13.01. No se vincula a un club específico.
- Colores independientes y distinguibles por ID para las seis competiciones adicionales del mundo Python: Championship, League One, League Two, EFL Trophy, Europa League y Conference League. No se alteran los cuatro temas de Competitions del club.
- El bloque de logo de la competición seleccionada es flexible: conserva la proporción de PNGs anchos o altos con `object-fit: contain`, sin recorte.
- El importador de activos acepta `source/competitions/COMPETITION_ID.png` y colores opcionales `primary_color` y `secondary_color` desde `metadata.competitions[ID]`. La pantalla usa el ID, no el nombre ni el país codificado como clave.
- Cuando falta un PNG, se muestra el recurso visual genérico. No se atribuyen logos de otras competiciones.
- Se elimina `Club squads & tactical identities` de **Other Leagues**, sin borrar esa función del juego ni modificar su vista existente de Competitions.
- Se conservan filtros, tabla, fixtures, navegación entre jornadas, copas y brackets, consultas al backend y temporadas anteriores.

## Importación posterior de nuevas ligas

La ruta genérica es `source/competitions/COMPETITION_ID.png` (o JPG/WEBP), tal como ya admitía el importador. Para asignar colores sin editar JavaScript:

```json
{
  "competitions": {
    "dev-championship": {
      "primary_color": "#77B8ED",
      "secondary_color": "#14344E"
    }
  }
}
```

El parámetro `--metadata` del importador lee ese JSON. Los valores RGB se validan estrictamente; un color inválido se ignora. Los archivos deben denominarse con el ID exacto que usa el motor del juego. Si el ID no tiene imagen, se conserva el marcador genérico y puede importarse el PNG después.

## Pruebas completadas

- **32 pruebas Python seleccionadas aprobadas**, entre ellas el nuevo test TS-UI-14, el directorio UI-3.3.2, el parche TS-UI-13, el catálogo de competición, el calendario y el importador de assets.
- **2 suites JavaScript ejecutadas**: marca compartida preexistente y controles nuevos de seis paletas, importación de PNG, colores sobrescritos, fallback y sanitización.
- **Chromium aislado con modelos reales de `DevelopmentSession`** en 1550, 1024 y 390 px: sin overflow horizontal y sin errores JavaScript. Se verificó el header, filtros, cambio entre Championship y League Two, resultado vacío para España, PNG ancho importado, ausencia de plantillas en Other Leagues, y continuidad de la vista Competitions del club.
- Comprobación de sintaxis de módulos JS y del importador Python.
- Validación ZIP y SHA-256 e instalación incremental sobre copia de TS-UI-13.01.

## Límites

La prueba visual de navegador se hizo en un montaje aislado con datos proyectados del motor Python, **no** como sesión integral dentro del juego ejecutándose con su servidor. No se simuló una temporada completa. No se cargaron logos reales nuevos de otras ligas: la pantalla y el importador quedan listos para recibirlos. No se modifica backend deportivo ni versión de guardado (v32).
