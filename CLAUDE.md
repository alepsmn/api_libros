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

Empezar con la version mas pequena que funcione:

**Servidor HTTP que responde a un unico endpoint con datos hardcodeados.**

Una vez funcione y este testeado, introducir requisitos nuevos de uno en uno
que fuercen al diseño a evolucionar.