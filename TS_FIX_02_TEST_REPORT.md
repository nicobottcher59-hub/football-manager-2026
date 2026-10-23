# TS-FIX-02 — Mercado, negociaciones y UX

## Base y alcance

Parche incremental para el proyecto entregado en football-manager-2026.zip, en TS-UI-08.03, **con TS-FIX-01 previamente aplicado**. No es un repositorio completo. No incluye partidas, fotos nuevas, paquetes externos ni dependencias nuevas de runtime.

Los hashes de los dos ZIP de origen constan en `reports/ts_fix_02_build_inputs.json`. El manifiesto del parche identifica cada archivo entregado, su SHA-256 y el hash anterior cuando corresponde. La cantidad del archivo ZIP incluye el propio manifiesto.

## 1. Interfaz aprobada

Se conserva la estructura de dos columnas: propuesta a la izquierda; tolerancia, condiciones comunicadas e historial a la derecha. Arriba quedan retrato, nombre, edad, puesto, bandera, OVR general, valor, escudo vendedor, escudo propio y presupuesto. Se conserva la ruta real Scouting > Market y la navegación existente, sin inventar secciones del juego para copiar literalmente etiquetas del mockup.

La identidad principal toma los colores del club dirigido. El club vendedor conserva su identidad contextual. Se usan los resolutores compartidos de retratos y escudos: cuando existe un recurso real, se utiliza; cuando falta, aparece el respaldo ilustrado o con iniciales. El parche no genera fotografías ni escudos oficiales ausentes.

**OVR y valor siempre tienen un espacio visible.** Un dato desconocido llega como `null` y se muestra `??`. El OVR es el general, no el ajustado por el estado del partido. Se conserva la regla de jugadores propios y jugadores públicos de 85+; un informe completado muestra su evaluación registrada, no una consulta nueva del valor interno. El precio pedido por el vendedor es información comunicada durante la negociación, distinta del valor de mercado.

Toda propuesta nueva comienza en cero, incluso con scouting completo. Al continuar una negociación puede recuperarse el borrador de la propuesta propia anterior; nunca se precarga la valoración oculta. Reiniciar el borrador no borra la historia ni recupera tolerancia. Los importes llevan símbolo y separadores. Los botones de incremento son sumas manuales, no recomendaciones de precio.

Evaluar propuesta resume obligaciones propias. No muestra probabilidad privada de aceptación, precio mínimo interno ni rango recomendado. Los comentarios del vendedor se basan en sus respuestas reales. Se eliminaron los `confirm/alert` nativos del flujo interclubes revisado; el cierre que registra al jugador y compromete dinero usa una confirmación integrada.

## 2. Cuotas independientes y obligaciones reales

El pago inicial y el importe adicional en cuotas son campos distintos. Las barras eligen **2/4/6 pagos** y, por separado, **cada 6/12/18 meses**. La primera cuota vence un intervalo después del cierre efectivo del fichaje. El plazo total es cantidad por intervalo.

Cuatro pagos anuales vencen a los 12, 24, 36 y 48 meses. No se copiaron las marcas incorrectas 6/18/30/42 del mockup generado. Se muestra también el horizonte de nueve años que resulta de seis pagos cada 18 meses. La previsualización aclara que presupone un cierre hoy; las fechas definitivas nacen al completar el traspaso.

Los importes enteros se conservan exactamente, llevando el resto a la última cuota. Se contemplan finales de mes y años bisiestos. Pago inicial más cuotas constituye el total garantizado; los bonus son adicionales condicionales.

Las deudas quedan en el registro del acuerdo, se pagan al avanzar el mundo y se muestran en Finances como pagos y cobros pendientes. Guardar y recargar no repite pagos. Una reventa o retiro no elimina la obligación del club. Los porcentajes de reventa se liquidan sobre dinero efectivamente recibido, usando como costo de adquisición el total garantizado de la compra anterior.

**Decisión de balance implementada:** el crédito para pagos diferidos se limita al 25 % del ingreso recurrente anual, descontando deudas y compromisos ya reservados. Es una regla del juego, no una norma oficial ni una pista sobre el precio del jugador. Se mantienen los controles de presupuesto/caja del pago inicial. No hay banda de oferta basada en la valoración oculta ni paso obligatorio de 5.000 libras. Hay un límite técnico de 500 millones garantizados por operación. Un error de presupuesto no consume paciencia.

## 3. IA y tolerancia

El vendedor evalúa efectivo inicial, cuotas garantizadas descontadas por plazo, bonus, porcentaje de reventa, recompra, importancia deportiva y urgencia financiera. Puede modificar la estructura, acortar plazos, agregar condiciones de rendimiento/reventa y conceder gradualmente, en vez de repetir una subida del fijo. Los bonus especulativos no reemplazan cantidades ilimitadas de dinero garantizado.

La paciencia persiste. Ofertas muy insuficientes o repetidas sin mejora consumen más; una mejora significativa suele consumir menos. Hay un aviso crítico antes de una ruptura que de otro modo sería abrupta. Las conversaciones cerradas aplican una espera de reapertura de 14 días. La barra representa paciencia, no la probabilidad de que acepten un importe.

La IA es determinista y basada en reglas, sin servicios externos. El consentimiento del jugador y el contrato personal siguen siendo necesarios para registrar el traspaso. La renovación y la negociación profunda con jugador/agente pertenecen al siguiente bloque, no a esta entrega.

## 4. Ofertas entrantes y calendario

Durante la ventana, el interés se revisa en los días 1/8/15/22/29 según necesidades y mejoras de plantilla, presupuesto, salarios e interés del jugador. El proceso semanal limita la cantidad a dos nuevas propuestas por revisión y cinco pendientes: son topes, no cuotas obligatorias de ofertas. Continúa el mercado mensual entre clubes IA. Se filtran propuestas duplicadas o demasiado recientes para el mismo comprador y jugador.

Una plantilla corta del usuario ya no impide que un comprador se interese. La seguridad de plantilla se controla al concretar la venta. **No se vende ningún jugador del usuario automáticamente.**

Ofertas, contrapropuestas y acuerdos pendientes de consentimiento interrumpen el avance automático. Se conserva la fecha objetivo, incluso guardando y recargando, y Calendar permite retomar. Los resultados producidos el día de la interrupción no se pierden ni se duplican. Una nueva ronda puede generar un mensaje aunque el estado siga siendo `manager_turn`. Las lecturas no fabrican mensajes repetidos. Las ofertas reales ya pendientes al crear la bandeja también se notifican.

## 5. Guardado y compatibilidad

El formato pasa de **26 a 27**. La migración agrega los campos de cuotas, tolerancia, reloj y fecha objetivo sin reiniciar jugadores, sharpness, resultados ni condiciones anteriores. Los acuerdos existentes sin cuotas no adquieren deudas nuevas.

Se actualizó explícitamente la lista de atributos permitidos de la partida para guardar el destino pendiente del calendario; no se relajó la validación para admitir campos arbitrarios. Un guardado nuevo en 27 no puede abrirse con el código anterior. Volver atrás requiere restaurar **código y partida anteriores**.

## 6. Pruebas

- **119 pruebas aprobadas** sobre una copia limpia de la base con el parche aplicado: 63 nuevas de TS-FIX-02 y 56 de TS-FIX-01.
- **30 comprobaciones JavaScript** de importes, calendarios, redondeos y validaciones.
- **26 comprobaciones de navegador** entre el constructor y el recorrido de calendario.
- La selección adicional inicial tuvo 118 casos: 109 aprobados y nueve discrepancias. Cuatro ya fallaban en la base por exigir formato 17; cinco correspondían al cambio deliberado de formato 26 a 27, datos ocultos y estructura del header. Se actualizaron esas expectativas, manteniendo las comprobaciones funcionales, y se repitieron los nueve casos. También se adaptó y repitió el arranque de Inbox para permitir ofertas reales existentes: diez casos actualizados aprobados. No se ejecutó toda la suite histórica del repositorio.
- Sintaxis de los archivos Python y JavaScript modificados, integridad del ZIP y manifiesto SHA-256 verificados.

La prueba de integración avanzó 35 días, del 21/08/2026 al 25/09/2026. Registró **377 resultados nuevos y 377 resultados únicos emitidos**, revisó siete ofertas entrantes en tres pausas, autorizó cero ventas automáticas del usuario y mantuvo 16 operaciones completadas entre clubes IA. El fichaje controlado conservó una deuda de 308.000 libras al guardar y recargar. La prueba respondió las decisiones: no evitó las interrupciones para avanzar.

Se creó además una partida SQLite real con la base anterior y TS-FIX-01 (versión 26), no simplemente cambiando una etiqueta de versión. Cargó con sharpness intacto, 74 resultados y la oferta pendiente original. Guardó/recargó en 27, conservó una pausa del calendario y continuó hasta el 23/08/2026 con 119 resultados. El nuevo guardado volvió a cargar correctamente.

Las pruebas de navegador usaron HTML/CSS/JS de producción y el servidor HTTP local real. El entorno bloquea la navegación superior por una política del host; por eso se cargó la página en about:blank con un adaptador de transporte local para fetch, recursos e historial. No se modificó la política del host. Es una prueba de interfaz y acciones reales, **no una validación de navegación nativa sin adaptador en Windows**. Se comprobaron importes, sliders, datos conocidos/desconocidos, envío y contrapropuesta, persistencia de tolerancia, cláusulas, pausa/revisión/reanudación y ausencia de errores JavaScript/diálogos nativos. Las comprobaciones de desborde incluyeron anchos de 1366, 1024 y 390 píxeles, además del escritorio de referencia. La captura entregada es del juego ejecutado, no del mockup.

## 7. Límites documentados

No se probó tu partida concreta con la temporada terminada. No se hizo una nueva temporada completa ni una simulación financiera de nueve años: las pruebas liquidan calendarios completos de cuotas y cubren todas las combinaciones, pero no sustituyen la calibración longitudinal.

Una cuota contractual sigue siendo deuda aunque falte caja: no se perdona silenciosamente. No se agregaron reglas de insolvencia o renegociación de deuda.

La protección de conocimiento se aplica a búsqueda de traspasos, negociación interclubes y evaluación. Todavía no se unificaron todos los perfiles generales antiguos ni las vistas de préstamos y libres. Por tanto, **no se considera cerrado el ocultamiento de datos de todo el juego**.

No se incluyeron el rediseño profundo de contratos/renovaciones ni el resto del backlog de Club Info, nombres/competiciones del calendario o distribución general de resultados entre Noticias y Mensajes. Las fotos y escudos ausentes mantienen su respaldo.

## 8. Instalación y comprobaciones

Detener juego y Python. Respaldar proyecto y partidas. Extraer el ZIP en la raíz de football-manager-2026, donde está pyproject.toml, preservando carpetas y reemplazando los archivos incluidos. Reiniciar y hacer Ctrl+F5.

Comprobaciones opcionales desde la raíz:

```text
python tools/verify_ts_fix_02_install.py
node tools/verify_ts_fix_02_payments.cjs
python -m pytest tests/test_ts_fix_02_market_negotiation.py
python tools/validate_ts_fix_02.py --days 35
```

La herramienta de integración crea carreras temporales y no modifica las partidas del usuario.

Rama nueva sugerida: `fix/ts-fix-02-market-negotiation-ux`.

Commit: `feat(transfers): TS-FIX-02 negotiation UX, installments and live market`.
