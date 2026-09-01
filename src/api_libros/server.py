from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from api_libros.service_validation import ServiceValidation
from api_libros.datos import DatosLibros
from api_libros.excepciones import LibroNoEncontrado, EstructuraLibroInvalida
import json

class BookHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        # .../books/1
        parsed_url = urlparse(self.path)
        partes_url = parsed_url.path.split('/') # antes / despues - splitea por ambos
        if partes_url[1] == 'books':
            # Solo capturo dos casos
            # 1. si hay id
            if len(partes_url) > 2:
                id_libro = int(partes_url[2])
                try:
                    read_libro = self.server.service_validator.val_get_book(id_libro)
                    self.responder(200, read_libro)
                except LibroNoEncontrado:
                    self.responder(404, {"error": "Libro no encontrado"})
            # 2. si hay pag y size
            else:
                parametros = parse_qs(parsed_url.query) # dict de lists
                # pagina a leer
                page_n = parametros.get('page')
                # cuantos por pagina
                size_n = parametros.get('size')
                if page_n and size_n:
                    page = int(page_n[0])
                    size = int(size_n[0])
                    pagina = self.server.service_validator.val_list_book(page, size)
                    self.responder(200, pagina)
                else:
                    self.responder(200, self.server.service_validator.val_get_all_books())
        else:
            self.responder(400, {"error": "Ruta no encontrada"})

    # POST /usuarios?id=10 HTTP/1.1  ───►  self.command = "POST"
    #                                  self.path = "/usuarios?id=10"
    # ─────────────────────────────
    # Host: localhost:8080           ───►  self.headers = {
    # Content-Type: application/json              'Host': 'localhost:8080',
    # Content-Length: 42                          'Content-Type': 'application/json',
    #                                             'Content-Length': '42'
    #                                     }
    # ─────────────────────────────
    # (Línea en blanco)              ───►  Indica fin de headers (Python la procesa solo)
    # ─────────────────────────────
    # {"nombre": "Ana"}              ───►  self.rfile.read(42) = b'{"nombre": "Ana"}'


    def do_POST(self):
        partes_url = self.path.split('/')
        if partes_url[1]== 'books':
            content_length = int(self.headers['Content-Length'])
            # lee el No de caracteres exactos del stream
            body = self.rfile.read(content_length)
            data = json.loads(body)
            try:
                libro_guardado = self.server.service_validator.val_save_book(data)
                self.responder(201, libro_guardado)
            except EstructuraLibroInvalida:
                self.responder(400, {'error': 'Estructura del dato incorrecta.'})
        else:
            self.responder(400, {'error': 'Ruta no encontrada'})

    def do_PUT(self):
        # .../books/1
        partes_url = self.path.split('/')

        if partes_url[1]== 'books':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            # acepta bytes / json desde python 3.6, siempre que este en utf-8,16,32
            data = json.loads(body)
            book_id = int(partes_url[2])
            try:
                libro = self.server.service_validator.val_update_book(book_id, data)
                self.responder(200, libro)
            except LibroNoEncontrado:
                self.responder(404, {"error": "Libro no encontrado"})
            except EstructuraLibroInvalida:
                self.responder(400, {"error": "Estructura del dato incorrecta"})

        else:
            self.responder(400, {"error": "Ruta no encontrada"})

    def do_DELETE(self):
        # .../books/1
        partes_url = self.path.split('/')

        if partes_url[1] == 'books':
            book_id = int(partes_url[2])
            try:
                libro_eliminado = self.server.service_validator.val_delete_book(book_id)
                self.responder(200, libro_eliminado)
            except LibroNoEncontrado:
                self.responder(404, {"error": "Libro no encontrado"})
        else:
            self.responder(400, {"error": "Ruta no encontrada"})

    def responder(self, code: int, message: dict[str, str]):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write((json.dumps(message)+'\n').encode('utf-8'))

libro1 = {
        "Libro": "Niebla",
        "Autor": "Miguel de Unamuno",
    }

libro2 = {
        "Libro": "Dune",
        "Autor": "Frank Herbert",
    }

libro3 = {
        "Libro": "Neuromancer",
        "Autor": "William Gibson",
    }

libro4 = {
        "Libro": "Corazon de las Tinieblas",
        "Autor": "Joseph Conrad",
    }

libro5 = {
        "Libro": "El Innombrable",
        "Autor": "Samuel Beckett",
    }

libros = [libro1, libro2, libro3, libro4, libro5]

def run(server_class=HTTPServer, handler_class=BookHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.service_validator = ServiceValidation(DatosLibros())
    for libro in libros:
        httpd.service_validator.val_save_book(libro)
    httpd.serve_forever()

if __name__ == '__main__':
    run()