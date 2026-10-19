TS-22 - SQUAD & MATCH PRESENTATION
Incremental sobre TS-21.1.1 - Sin Node/npm para instalar o jugar.

ANTES DE INSTALAR
Guarda la carrera y conserva una copia externa del proyecto y los guardados.
Cierra el juego y el servidor Python. Extrae el ZIP en la raiz, donde esta
INICIAR_INTERFAZ_WINDOWS.bat, reemplazando archivos y manteniendo las rutas.
No borres carpetas de datos, slots o tu repositorio .git.

VERIFICAR
python tools/verify_ts22_package.py

PRUEBAS OBLIGATORIAS (pytest instalado como en las versiones anteriores)
python -m pytest -ra tests/test_ts_22_presentation.py

Reinicia con INICIAR_INTERFAZ_WINDOWS.bat y recarga con Ctrl + F5.
Carga tu carrera desde su slot SQLite completo; no uses el JSON de resultados
como reemplazo de un guardado completo. No hay autoguardado nuevo.
El estado completo pasa a version 6. Para volver a una version anterior del
juego utiliza la copia previa de tu guardado, no el slot regrabado por TS-22.

DONDE PROBAR
Squad: nombre del jugador -> detalles y radares. +/Mas -> menu contextual.
Squad / Season stats: filtro de temporada y competicion, datos reales.
Tactics/Home: GRL actual como numero destacado en las fichas de alineacion.
Partido: misma pestana, prepartido con GRL actual y condicion de ambos equipos.
Nombre/escudo de un club: su Squad de consulta; no edita al rival.
Home: las pestanas cambian el recuadro; Ver competicion abre la vista completa.

NORTHBRIDGE
Carreras nuevas: ajuste inicial aplicado, sin cambios en formulas o fatiga.
Carreras existentes: Squad -> Review and apply, solo si hay originales
sin modificaciones elegibles. Es opcional, requiere confirmacion y se aplica
una sola vez. Guarda despues. No rebaja fichajes ni modifica otros clubes.

LIMITES EXPLICITOS
No hay historial de desarrollo de atributos todavia; no se fabrican flechas.
xA y tackles no se muestran como estadisticas implementadas.
Los datos historicos ausentes y estadios/capacidades no se inventan.
Los clubes externos sin plantilla persistente lo indican al abrir el perfil.
El proximo rival de copa figura pendiente de sorteo si no esta confirmado.

DETALLE Y EVIDENCIA
TS_22_TEST_REPORT.md
TS_22_VALIDATION.json

GITHUB DESKTOP
BRANCH: feat/ts-22-squad-match-presentation
SUMMARY: feat(ui): add squad insights, season stats and integrated match navigation

La migracion de GitHub y sus workflows no se modifica en este paquete.
