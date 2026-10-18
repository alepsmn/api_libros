Objeto de consulta:
- Libro: id, titulo, autor, anio, genero, pais (futuro: ISBN, numero paginas, editorial)
- Endpoints:
    [
        GET: id, offset - size (limit)
        sin parametros devuelve todo - /books
        con parametros filtra por ese - id, por simplicidad (futuro: resto) - /books/{id}
        POST:
        un libro por peticion (id generado por el sistema) - /books/

        PUT:
        un libro por peticion (id) - /books/{id}

        DELETE:
        un libro por peticion (id) - /books/{id}

        
        Exito: GET, PUT, DELETE - 200; POST - 201 CREATED
            Si DELETE no devuelve body - 204 EXITO SIN CONTENIDO DE RESPUESTA

        Si GET, PUT, DELETE no encuentran id - 404 NOT FOUND
        Si POST con mal body - 400 BAD REQUEST
        Si hay algun fallo de ruta - 400
    ]