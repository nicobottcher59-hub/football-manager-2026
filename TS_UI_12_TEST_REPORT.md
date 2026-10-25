# TS-UI-12 — Finances y presupuesto independiente de personal

## Base y alcance

Base verificada: TS-UI-11 + TS-UI-10.02. Parche incremental de **8 archivos de codigo/pruebas** sobre esa base. El formato de guardado se mantiene en **v32**.

### Implementacion

- Cabecera compacta con retrato deportivo **generico**, nombre/escudo del club y colores por ID mediante `FMClubIdentity` + `FMEntityAssets`. Ya no hay un nombre de club antiguo escrito en Finances.
- Cuatro vistas en la misma pantalla: Overview, Contracts, Transfer Finances y Financial History.
- Indicadores de caja, presupuesto de fichajes, presupuesto de salarios de jugadores, **Staff Budget** y resultado mensual estimado.
- Wage Structure y Staff Budget separados, con barras de utilizacion y empleados de mayor salario. Los importes salen de los contratos registrados en el motor Python.
- Contract Priorities utiliza **vencimientos reales** y conserva `Open negotiation` enlazado al sistema existente de agentes. Lista completa con busqueda, filtros y ordenamiento, sin reimplementar contratos.
- Transfer Finances muestra cuotas pendientes, cobros futuros y Loan Fees liquidados. Los compromisos proceden de los registros reales.
- Financial History utiliza exclusivamente cierres mensuales guardados. Cuando todavia no existen, el panel muestra una **prevision expresamente etiquetada**, no un grafico falso.
- En Staff aparece el limite presupuestario y se valida al enviar ofertas: una oferta que incrementa el total salarial mas alla del tope no puede aceptarse. Los salarios contratados antes del parche se respetan; reducir nomina siempre es posible.
- Staff Budget se deriva de ingresos recurrentes del club, division y nomina inicial; **no se incrementa cuando se contrata alguien**, y se recalcula al cambiar la economia de la siguiente temporada. Esto evita una migracion de guardados y no inventa dinero nuevo.
- Solo usa GBP, la moneda ya modelada por el motor. Queda pendiente una capa de presentacion multimoneda si se incorpora mas adelante.

### Pruebas completadas

- **4 nuevas pruebas Python de TS-UI-12**: presupuesto independiente y estable, proyeccion consistente de contratos, prohibicion de exceder tope sin mutacion, mensualidades y Loan Fees basados en los registros reales.
- **3 regresiones Python seleccionadas** de `test_ts_ui_05_01_staff_negotiations.py`, incluyendo contrataciones/renovaciones y guardado/restauracion.
- `node --check` en los tres modulos JS cambiados.
- **Chromium aislado**: anchos 1550, 1024 y 390 px. Ningun desbordamiento horizontal ni error JavaScript. Las cuatro vistas y los botones de negociacion y gestion Staff se probaron con el modulo JS real y una respuesta del modelo Python tomada de una sesion de prueba.
- Integridad SHA-256 del ZIP y aplicacion en una copia de la base TS-UI-11.

### Limites

- **No** hay prueba end-to-end sobre una partida del usuario ni simulacion anual completa.
- La suite historica completa de contratos y finanzas alcanzo 26 tests sin fallos, pero se agoto el tiempo durante una simulacion larga; **no se cuenta como aprobada**.
- La verificacion de navegador fue aislada porque el navegador del entorno bloquea abrir la direccion local del servidor. El modelo Python se probo por separado; no se afirma una integracion nativa completa navegador-servidor.
- Los empleados no cuentan con fotos reales asociadas a IDs en la BD actual. Se utiliza un avatar de respaldo.
- El presupuesto Staff no crea controles nuevos de junta directiva ni cambios de dinero artificiales. El algoritmo de asignacion es una politica provisional uniforme, ajustable cuando exista un modelo de directiva mas amplio.
