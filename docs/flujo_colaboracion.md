# Guía de colaboración — Femto-UN

**Repositorio:** `Femto-UN/riscv-vlsi`  
**GitHub Project:** `RISC-V Desarrollo y Seguimiento`

## 1. Objetivo

Establecer un flujo de trabajo colaborativo para organizar las actividades, desarrollar implementaciones, realizar pruebas, documentar resultados y revisar contribuciones.

Todos los integrantes pueden participar en cualquier área del proyecto.

## 2. Flujo general

**Issue → Rama → Desarrollo y pruebas → Pull Request → Revisión → Integración en main**

### Paso 1. Crear una actividad (Issue)

1. Entrar al repositorio → **Issues → New issue**.
2. Seleccionar la plantilla `Actividad` o `Reporte de error`.
3. Describir el trabajo, su objetivo y los resultados esperados.
4. Crear el Issue y agregarlo al Project `RISC-V Desarrollo y Seguimiento`.
5. Asignar un responsable y completar los campos del Project:
   - **Área:** RTL, Verificación, FPGA, ASIC, PCB, etc.
   - **Tipo:** Implementación, Debugging, Documentación, etc.
   - **Prioridad:** Alta, Media o Baja.
   - **Estado:** Por hacer.

### Paso 2. Crear una rama (Branch)

1. Abrir el Issue e identificar su número.
2. En **Development → Create a branch**, crear una rama desde `main`.
3. Utilizar el siguiente formato obligatorio:

   **`tipo/numero-issue-descripcion`**

   Ejemplos:

   - `docs/1-documentation`
   - `feat/2-implementacion-uart`
   - `fix/3-error-interrupciones`
   - `test/4-verificacion-spi`

4. Cambiar el estado de la actividad a **En progreso**.

**Importante:** toda rama debe incluir el número del Issue asociado. Esto facilita identificar el propósito de los cambios y relacionar las ramas con sus actividades.

### Paso 3. Desarrollar y comprobar

1. Trabajar exclusivamente en la rama creada.
2. Realizar cambios mediante commits descriptivos.
3. Ejecutar las pruebas correspondientes.
4. Documentar los cambios y resultados relevantes.

**Importante:** las implementaciones deben incluir evidencias de funcionamiento cuando corresponda. Si existen limitaciones o pruebas pendientes, deben indicarse.

### Paso 4. Crear un Pull Request (PR)

1. Entrar en **Pull requests → New pull request**.
2. Seleccionar:
   - **Base:** `main`.
   - **Compare:** rama de trabajo.
3. Completar la plantilla del PR:
   - Cambios realizados.
   - Motivo de los cambios.
   - Pruebas ejecutadas y resultados.
   - Observaciones o limitaciones.
4. Vincular el Issue utilizando `Closes #N`, donde N es su número.
5. Solicitar revisión a otro integrante.
6. Cambiar el estado a **En revisión**.

### Paso 5. Revisar los cambios

El revisor debe:

1. Abrir el PR → **Files changed**.
2. Revisar el código, la documentación y las evidencias.
3. Comentar los errores o mejoras necesarias.
4. Seleccionar **Review changes → Approve** si está conforme, o **Request changes** si necesita correcciones.

**Todo PR requiere al menos una aprobación de un integrante distinto del autor.**

### Paso 6. Integrar los cambios

Después de obtener la aprobación:

1. Comprobar que las verificaciones requeridas sean satisfactorias.
2. Seleccionar **Merge pull request**.
3. Confirmar que los cambios estén en `main`.
4. Cerrar el Issue si no se cerró automáticamente.
5. Cambiar su estado a **Terminado** si es necesario.
6. Eliminar la rama de trabajo cuando ya no se necesite.

## 3. Estados de las actividades

| Estado | Significado |
|---|---|
| Pendiente | Actividad identificada, aún sin definir completamente. |
| Por hacer | Actividad definida y lista para iniciar. |
| En progreso | Se está desarrollando. |
| En revisión | Espera revisión o aprobación. |
| Bloqueado | Existe un impedimento documentado. |
| Terminado | Resultado completado y verificado. |

## 4. Acuerdos del equipo

- No modificar directamente `main` durante el trabajo habitual.
- Registrar las actividades importantes mediante Issues.
- **Nombrar todas las ramas incluyendo el número del Issue correspondiente.**
- Desarrollar cada cambio en una rama.
- Solicitar revisión antes de integrar contribuciones.
- Mantener actualizados los estados del Project.
- Documentar las implementaciones, pruebas y problemas relevantes.
- Registrar las decisiones técnicas importantes en `docs/decisions/`.
- Rotar responsabilidades para que todos conozcan las diferentes áreas.
- Mantener una comunicación respetuosa y constructiva durante las revisiones.

## 5. Criterios para finalizar una actividad

Antes de cerrar un Issue, comprobar que:

- [ ] Se cumplió el resultado esperado.
- [ ] Se realizaron las pruebas aplicables.
- [ ] Se documentaron los cambios relevantes.
- [ ] La contribución recibió la revisión correspondiente.
- [ ] Los cambios fueron integrados cuando era necesario.

**Principio del equipo:** cualquier integrante debe poder comprender, revisar y continuar el trabajo realizado por sus compañeros.
