Proyecto de aprendizaje: API REST de libros sin framework.

Objetivo: construir una API HTTP desde cero usando solo la stdlib de Python,
para aprender HTTP, diseño por capas y testing de integracion.

## Rol de Claude

Revisor tecnico. No dar arquitectura, no decir que clases crear, no reescribir
la solucion salvo peticion explicita.

Cuando proponga un diseño o implementacion:

1. Verificar si es correcto.
2. Identificar acoplamiento, abstracciones innecesarias, responsabilidades mal
   asignadas, o malentendidos de Python/HTTP.
3. Pedir justificacion de decisiones de diseño importantes.
4. Señalar alternativas solo cuando haya razon concreta.

Preguntas tipo:
- ¿Que pasa si dos requests modifican el mismo recurso a la vez?
- ¿Este componente se puede testear sin levantar el servidor?
- ¿Que contrato tiene esta capa con la de arriba?
- ¿Por que esta validacion vive aqui y no en otra parte?
- ¿Que devuelve el servidor si el body es JSON mal formado?

## Requisitos funcionales

La API debe exponer operaciones sobre un catalogo de libros:

* crear un libro
* obtener un libro por identificador
* listar libros con paginacion
* actualizar un libro
* eliminar un libro
* buscar/filtrar libros por campos

Cada libro tiene al menos: titulo, autor, anio de publicacion, genero.
Las reglas de validacion concretas se deciden durante la implementacion.

## Requisitos de ingenieria

La implementacion debe llegar a contener uso justificado de:

* clases y composicion
* separacion de responsabilidades por capas
* type hints
* contratos claros entre componentes
* excepciones custom donde se justifiquen
* HTTP correcto: metodos, status codes, content-type, idempotencia
* respuestas de error consistentes
* logging
* tests unitarios y de integracion con pytest
* fixtures y tests parametrizados
* paginacion

No son cajas a rellenar. Si un mecanismo no se justifica, debo poder explicar
por que no lo uso.

## Persistencia

Empezar con datos en memoria. Migrar a base de datos (SQLite) cuando el diseño
lo pida — esa migracion es un ejercicio de diseño en si misma.

## Regla de desarrollo

Trabajo incremental. No construir todo de una vez.

Una vez funcione y este testeado, introducir requisitos nuevos de uno en uno
que fuercen al diseño a evolucionar.

## Estado actual

Completado:
* CRUD completo (GET, POST, PUT, DELETE) con tests de integracion (9 tests)
* Separacion en 3 capas: handler HTTP, servicio (validacion), storage
* Dos implementaciones de storage intercambiables: dict en memoria y SQLite
* Excepciones custom: LibroNoEncontrado, EstructuraLibroInvalida
* Inyeccion de dependencias: el servicio recibe el storage desde fuera
* Paginacion con LIMIT/OFFSET en SQLite

Estructura de archivos:
* server.py — handler HTTP (BookHandler) y funcion run()
* service_validation.py — capa de negocio (validacion de campos)
* datos.py — storage en memoria (DatosLibros)
* datos_sqlite.py — storage SQLite (DatosLibrosSQLite)
* excepciones.py — LibroNoEncontrado, EstructuraLibroInvalida
* tests/test_integracion.py — 9 tests de integracion con pytest

## Siguientes pasos viables

Cada paso introduce un problema concreto que fuerza a aprender algo nuevo.
Evaluarlos por orden de interes, no hace falta hacerlos todos ni en secuencia.

1. **Threading** (lo necesitas ya para que los tests con SQLite funcionen) el storage en memoria no es thread-safe.
   Dos requests simultaneos pueden corromper datos. Resolver con locks ensena
   race conditions y programacion concurrente.
2. **Errores HTTP** (te da una base sólida para iterar sin explosiones) hoy si el body no es JSON valido, o si
   la URL tiene un ID no numerico (/books/abc), el servidor crashea. Capturar
   esos errores y devolver 400 con mensaje util es HTTP correcto.
3. **Campos faltantes** (esquema + validación + tests) anio de publicacion y genero aun no estan
   implementados. Anadirlos fuerza a modificar la tabla SQLite, la validacion,
   y los tests — ejercicio de migracion y consistencia entre capas.
4. **Búsqueda/filtrado** (depende de que los campos existan) requisito funcional pendiente. Implementar
   GET /books?autor=X&genero=Y fuerza a construir queries SQL dinamicas con
   filtros opcionales — buen ejercicio de SQL y de diseño de interfaz REST.
5. **Tests unitarios** (a estas alturas tendrás suficiente lógica para que valga la pena aislar) hoy solo hay tests de integracion
   que levantan el servidor. Testear DatosLibrosSQLite y ServiceValidation
   aislados (sin HTTP) da cobertura mas rapida y precisa. Fuerza a pensar en
   que testear sin red y en fixtures mas finas.
6. **Logging/Router** (cuando la complejidad lo pida) entender que pasa en el servidor sin mirar el codigo. Que requests
   llegan, cuanto tardan, que fallo. Usar el modulo logging de la
   stdlib — decidir que se loguea, a que nivel, y donde. 
