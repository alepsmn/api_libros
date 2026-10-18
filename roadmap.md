Roadmap: reconstruccion desde cero

Referencia: contrato_biblioteca.md
Modelo: Libro (id, titulo, autor, anio, genero, pais)
Codigo anterior: src/api_libros/ (solo como consulta, no se modifica)

Paso 1 - Servidor minimo
  HTTPServer + BaseHTTPRequestHandler
  Que responda {"status": "ok"} a cualquier request
  Entender: socket, handler, wfile vs send_response/send_header

  socket - canal bidireccional (client, server) creado y escucha por HTTPServer: abstraido
  wfile/rfile - file like objects que wrappean al socket (exponen interfaz facil para actuar sobre el)

Paso 2 - Routing basico
  GET /books -> lista vacia, cualquier otra ruta -> 404
  Parseo de URL con urlparse, split
  Validar que no crashee con rutas invalidas

Paso 3 - Almacen en memoria
  Capa de datos con dict
  Implementar save_book y get_all_books
  Conectarlo al handler, probar con curl

Paso 4 - CRUD completo
  GET /books/{id}, POST /books, PUT /books/{id}, DELETE /books/{id}
  Manejar errores: libro no existe, JSON mal formado, id no numerico
  Codigos HTTP correctos: 200, 201, 404, 400

Paso 5 - Capa de validacion
  Separar validacion del handler
  Por que tener esa capa intermedia

Paso 6 - Tests
  Tests para la capa de datos
  Tests para la capa de validacion
  Tests de integracion para los endpoints

Paso 7 - SQLite
  Reemplazar el dict por SQLite
  Que la interfaz (los metodos) se mantenga igual
  Migracion como ejercicio de diseno
