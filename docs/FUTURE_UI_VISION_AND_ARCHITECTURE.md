# Visión y arquitectura de la futura interfaz

**Proyecto:** Football Manager Game (juego de gestión futbolística propio)  
**Estado:** lineamientos acordados para una fase futura; **no implementado**  
**Ubicación sugerida:** `docs/FUTURE_UI_VISION_AND_ARCHITECTURE.md`

## 1. Decisión de producto

Queremos una interfaz **original**, con personalidad visual propia. **No utilizar la interfaz de Football Manager como referencia obligatoria:** al usuario no le gusta su diseño actual y no quiere reproducir su navegación ni su estética.

Buscamos combinar dos cualidades:

- **Sensación de videojuego moderno:** animaciones cuidadas, transiciones fluidas, una presentación visual atractiva y pantallas inmersivas cuando aporten valor.
- **Profundidad de una herramienta deportiva de alta calidad:** datos, análisis, filtros, comparaciones, navegación rápida e información densa sin que se vuelva confusa.

La interfaz debe priorizar legibilidad, rendimiento y facilidad de uso; las animaciones no deben entorpecer la gestión cotidiana. No se trata de copiar pantallas de otro producto, sino de diseñar nuestra propia experiencia.

## 2. Dirección tecnológica preferida (provisional)

**Frontend preferido:** React + TypeScript, con HTML/CSS y librerías visuales seleccionadas según necesidad.  
**Motor y reglas del juego:** Python, conservando los sistemas existentes.

Esta preferencia **no es una elección irreversible ni una implementación ya iniciada**. Antes de adoptarla definitivamente se construirá un prototipo y se evaluarán su experiencia, integración, distribución y mantenimiento.

Para empaquetar una aplicación de escritorio podrán evaluarse Tauri, Electron u otra solución. **No se eligió todavía un empaquetador ni un protocolo concreto de comunicación con Python.** Si Tauri fuese elegido, ello no implica reescribir el motor en Rust.

## 3. Principio arquitectónico no negociable

La interfaz debe poder reemplazarse o rediseñarse **sin reescribir el motor del juego**.

```text
Interfaz (Tkinter DEV hoy; React + TypeScript posiblemente después)
                         |
            Contratos / capa de aplicación
                         |
    Servicios del juego (consultas y comandos)
                         |
 Núcleo Python (jugadores, tácticas, competiciones, simulación,
              calendarios, carrera, persistencia)
```

Reglas:

1. La interfaz **no** debe calcular por su cuenta reglas de juego, resultados, clasificaciones, atributos, ACT/OVR, economía o decisiones de simulación.
2. Los sistemas del dominio **no** deben importar componentes ni depender de la tecnología de interfaz.
3. Las acciones del usuario deben pasar por servicios/casos de uso claros (por ejemplo: consultar plantel, cambiar táctica, simular partido, avanzar fecha, consultar calendario).
4. Los datos expuestos a la interfaz deben tener contratos claros, tipados y verificables; evitar que la UI dependa de estructuras privadas del motor.
5. La persistencia debe seguir perteneciendo al núcleo o a sus servicios, **no** al frontend.
6. Mantener pruebas de dominio y agregar pruebas de integración entre interfaz y servicios cuando llegue el momento.

Cambiar de React a otra tecnología seguirá requiriendo reconstruir las pantallas; el objetivo es **proteger la lógica y los datos del juego**, no prometer una migración gratuita.

## 4. Rol del sandbox actual

El sandbox en **Tkinter continúa siendo la herramienta de desarrollo y pruebas** durante la etapa 7.x. Es deliberadamente descartable: permite inspeccionar mecanismos nuevos sin desviar tiempo hacia una UI definitiva.

- **No migrarlo ahora a React.**
- **No detener el desarrollo de sistemas de gestión** por cuestiones estéticas.
- Cada fase nueva debe seguir incorporando controles DEV suficientes para probarla.
- Al implementar nuevas funciones, procurar que la lógica quede en servicios reutilizables, no dentro de callbacks de Tkinter.

## 5. Experiencia visual deseada

Las siguientes son **direcciones de diseño**, no pantallas ya diseñadas ni requisitos técnicos cerrados:

- **Inicio / club:** panel con próximos partidos, objetivos, noticias y decisiones prioritarias.
- **Plantel:** tablas y tarjetas de jugador personalizables, búsqueda y filtros, métricas de condición, moral, rendimiento y desarrollo.
- **Tácticas:** cancha interactiva con formación, roles, instrucciones y cambios claros; información contextual sin saturar la pantalla.
- **Calendario y competiciones:** navegación temporal fluida, resultados comprensibles, tablas, llaves y estadísticas.
- **Mercado y scouting:** búsqueda, seguimiento y comparaciones cuando esos sistemas existan.
- **Partidos:** visualización e información del encuentro; cualquier futura experiencia 2D/3D se definirá en una fase específica, sin rehacer prematuramente el motor espacial legacy.

Es importante diseñar tanto para consultas rápidas como para operaciones complejas, con buena jerarquía visual, accesibilidad, escalado de resolución y rendimiento aceptable en equipos normales.

## 6. Cuándo empezar

**Fase 7.x:** construir la profundidad de gestión (jugadores y planteles persistentes, contratos, fichajes, entrenamientos, economía, etc.) y ordenar los servicios que consumirá cualquier interfaz. Se pueden explorar ideas visuales y flujos, pero sin rehacer el sandbox.

**Fase 8.x (propuesta, aún no cerrada):** prototipar el frontend, validar tecnología y experiencia, crear una primera interfaz propia y conectarla a los servicios Python de manera incremental.

**Después:** ampliar presentación de partidos y funcionalidades visuales según las prioridades del juego y la evidencia de rendimiento.

No es necesario que **todos** los sistemas de gestión estén completos para empezar el frontend: basta con tener un núcleo consistente que permita una primera experiencia jugable.

## 7. Validación antes de elegir stack definitivo

Antes de adoptar React + TypeScript para producción:

- Prototipar **dos pantallas representativas**, por ejemplo Plantel y Tácticas, con datos provenientes de servicios Python existentes.
- Medir navegación, filtros, tiempo de respuesta, consumo de recursos y facilidad de empaquetado para Windows.
- Comprobar cómo se coordinan frontend, proceso Python, guardado/carga y manejo de errores.
- Evaluar los costos reales de desarrollo y mantenimiento frente a una alternativa como Qt Quick/QML.
- Confirmar con el usuario la dirección artística y la experiencia de uso **antes** de multiplicar pantallas.

## 8. Decisiones que NO deben asumirse

- No se ha elegido todavía una tecnología definitiva para la interfaz.
- No se ha elegido Tauri, Electron ni Qt para la distribución final.
- No hay mockups finales, identidad visual cerrada ni biblioteca de componentes obligatoria.
- No se va a reemplazar Python como motor principal por adoptar TypeScript en la interfaz.
- No hay que reescribir el simulador ni la arquitectura de competiciones solo por comenzar el frontend.

**Resumen:** motor Python modular y duradero; sandbox Tkinter hasta que convenga migrar; React + TypeScript como principal candidato para una interfaz original, moderna, visualmente ambiciosa y desacoplada.

## Addendum — 2026-10-08 UI-1 started

The earlier wording in this document describes a **previous provisional roadmap**. After reviewing two dashboard mockups, the user approved a React + TypeScript presentation prototype with the first mockup's proportions and a more lively editorial style. `frontend/` now contains UI-1, but no API, full game flow or desktop packager has been implemented. The actual `Continue` behavior (one day at a time) and contextual **OVR** are product requirements; UI-1 still uses labeled demo data and a display-only date increment. The later 7.x vs 8.x phasing proposed above is no longer a hard dependency for starting frontend work. See `docs/PHASE_UI_1_DASHBOARD_SHELL.md`.


## Addendum — UI-2 Squad and Tactics approved and implemented

The user approved three views (lineup, individual role/instruction editor, team tactics) with a shared In/Out of Possession selector. The team tactics diagram uses anonymous discs and reacts schematically to changes, without claiming to replay the legacy 2D engine. The shared local Python/UI-2 implementation runs in Windows without Node/npm; React remains the host technology for the shell. `docs/PHASE_UI_2_SQUAD_TACTICS.md` is the authoritative scope and lists missing saves/set pieces/daily Continue.
