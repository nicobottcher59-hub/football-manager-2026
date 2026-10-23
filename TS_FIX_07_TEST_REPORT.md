# TS-FIX-07 — Noticias, Inbox, confirmaciones y Loan Fee

**Fecha de revisión:** 23/10/2026  
**Base requerida:** TS-UI-09.01, instalada sobre TS-FIX-06.  
**Tipo:** ZIP incremental, sin partidas de usuario ni dependencias nuevas.  
**Guardados:** versión 31 → **32** (migración de `LoanTerms` y `LoanAgreement`).

## 1. Cambios funcionales

### Loan Fee (cesiones)
- Campo independiente en el constructor **Loan** de la misma pantalla de negociación, inicializado en **£0**, con símbolo de moneda y separadores de miles.
- El Loan Fee es una **suma única** que el club receptor paga al propietario, sin confundirse con el reparto de salario ni con la futura opción de compra.
- Admite `£0` (cesión gratuita) o una cantidad positiva hasta el límite técnico de £500 millones. Comprueba caja y presupuesto del receptor; nunca se propone automáticamente un precio al usuario.
- La IA considera este importe en las **contraofertas**, junto con salario, minutos, duración, repesca y opción de compra. Los factores deportivos siguen contando, sin excluir jugadores por edad.
- Los acuerdos fuera de ventana **no cobran ni inscriben** al jugador hasta el mercado correspondiente. Al registrar la cesión se actualizan caja y presupuesto de **ambos clubes**, una sola vez; la opción de compra conserva sus propios pagos independientes.
- Los importes quedan persistidos en negociaciones, rondas y acuerdo registrado. La lectura pública de préstamos y el historial presentan el Loan Fee.

### Noticias vs. Inbox
- Los resultados de partidos se publican como noticias del partido (mismo registro canónico que antes), **no** como un mensaje rutinario en Inbox. Al sincronizar se retiran duplicados históricos del buzón sin tocar resultados de la partida.
- Las operaciones **confirmadas** entre clubes, incluso entre equipos IA y sin mínimo de £5 millones, aparecen en Noticias. Las propuestas y acuerdos pendientes no se anuncian como traspasos consumados.
- Las **cesiones inscritas** generan noticias con club propietario, receptor, fechas, salario compartido y Loan Fee; una eventual compra futura se anuncia cuando se complete realmente como transferencia.
- La actividad general de mercado y las cesiones confirmadas dejan de crear mensajes duplicados en Inbox. Se mantienen ofertas que exigen respuesta, contratos, scouting, lesiones y comunicaciones específicas dirigidas al entrenador.
- Las noticias de mercado abren Transfers y las de competición mantienen acceso a la competición.

### Confirmaciones
- Sustituidos `window.alert()` y `window.confirm()` nativos de **Staff, Medical Centre, Youth Academy y Transfers** por un diálogo accesible (cancelación, Escape, foco) y notificaciones integradas. No se rediseñaron esas secciones.
- Los estilos usan la identidad global del club (`--ui-club-highlight`) donde está disponible.

## 2. Pruebas ejecutadas

| Control | Resultado |
|---|---|
| 10 pruebas nuevas `tests/test_ts_fix_07_news_and_loan_fee.py` | **10 aprobadas** |
| Regresiones puntuales de TS-FIX-06 y TS-UI-09.01 (negociación, cesión y tolerancia) | **4 aprobadas** |
| Navegador Chromium con código real de formularios + modal, ancho 1366 y 390 px | **2 recorridos aprobados** |
| Entrada de £1,500,000, evaluación de formulario, confirmación / Escape, avisos integrados | Aprobado |
| Errores JS durante esos recorridos | **0** |
| HTTP servidor real: `fm_dialog.js`, `fm_dialog.css`, `loan_negotiations.js`, `index.html`, `/api/news` | **5 respuestas HTTP 200** |
| `python -m compileall`, `node --check` de scripts implicados | Aprobado |
| Migración de un grafo reducido 31→32 conservando importes 0 para préstamos antiguos | Aprobado |
| Integridad ZIP, aplicación sobre copia limpia de TS-UI-09.01 | Aprobado (SHA-256) |

## 3. Límites y supuestos

- **No** se ejecutó una temporada completa en este entorno ni se probó la partida específica del usuario.
- La batería histórica extensa excedió el límite de tiempo. Parte de los tests heredados espera versiones antiguas del guardado y no se presenta como aprobada.
- La prueba de navegador usó componentes reales y un montaje aislado; **no** implica una prueba de navegación integral con la partida del usuario.
- La versión 32 se probó con un grafo real pequeño y una migración 31→32; no se completó en esta entrega un ciclo de save/load de un mundo completo de varias temporadas.
- El Loan Fee se trata como un pago único **no reembolsable** en los términos iniciales de este parche; no se implementaron reembolsos por repesca o ruptura anticipada.
- Por ahora no se filtran los traspasos globales por competición u OVR; ese filtro quedó para una futura iteración, como se acordó.

## 4. Archivos de código y pruebas

- `frontend/portable/club_support.js`
- `frontend/portable/fm_dialog.css`
- `frontend/portable/fm_dialog.js`
- `frontend/portable/index.html`
- `frontend/portable/loan_negotiations.js`
- `frontend/portable/news.css`
- `frontend/portable/news.js`
- `frontend/portable/transfers.js`
- `frontend/portable/youth_academy.js`
- `src/football_manager/domain/loan_market.py`
- `src/football_manager/domain/loan_negotiation.py`
- `src/football_manager/persistence/session_codec.py`
- `src/football_manager/services/loan_bargaining.py`
- `src/football_manager/services/loan_market.py`
- `src/football_manager/services/manager_inbox.py`
- `src/football_manager/ui_shell/home_news.py`
- `tests/test_ts_fix_07_news_and_loan_fee.py`

## 5. Instalación

1. Aplicar **solo sobre TS-UI-09.01**. Cerrar el juego y Python.
2. Respaldar tanto `football-manager-2026` como la partida.
3. Descomprimir el parche **en la raíz del proyecto** (donde está `pyproject.toml`) y reemplazar los archivos, conservando carpetas.
4. Reiniciar, forzar actualización del navegador con `Ctrl + F5`, comprobar **Loan → Loan Fee**, Noticias e Inbox.
5. Como el formato pasa de 31 a 32, para revertir restaurar **código y guardado** de la copia previa.

**Branch nueva:** `fix/ts-fix-07-news-loan-fee`  
**Commit summary:** `fix(news,loans): TS-FIX-07 news routing, loan fees and dialogs`
