from http.server import HTTPServer, BaseHTTPRequestHandler

from urllib.parse import urlparse
from api_libros.service_validation import ServiceValidation
from api_libros.raw_data import RawData
from api_libros.custom_exc import JobNotFound, InvalidDataStructure

import json

class JobHandler(BaseHTTPRequestHandler):
    # Job: {id, estado, payload, resultado}
    def do_GET(self):
        # unico metodo donde parsear, ya que pueden venir otros parametros
        parsed_url = urlparse(self.path)
        parts_url = parsed_url.path.split('/') # antes / jobs / id
        if parts_url[1] == 'jobs':
            # si hay mas de dos elementos -> existe id
            if len(parts_url) > 2:
                try:
                    id_job = int(parts_url[2])
                except ValueError:
                    self.response(400, {"error": "Invalid Id"})
                    return
                try:
                    job = self.server.service_validator.val_get(id_job)
                    self.response(200, job)
                except JobNotFound:
                    self.response(404, {"error": "Job no encontrado"})

            else:
                jobs = self.server.service_validator.val_get_all()
                self.response(200, {"jobs": jobs})
        else:
            self.response(404, {"error": "Route not found"}) # -> not found

    def do_POST(self):
        parts_url = self.path.split('/')
        if parts_url[1] == 'jobs':
            # cliente tiene q enviar este header - try/except
            content_lenght = int(self.headers["Content-Length"])
            body = self.rfile.read(content_lenght)
            data = json.loads(body)
            try:
                job = self.server.service_validator.val_save(data)
                self.response(201, job)
            except InvalidDataStructure:
                self.response(400, {"error": "Invalid data structure"})
        else:
            self.response(404, {"error": "Route not found"})

    def do_PUT(self):
        parts_url = self.path.split('/')
        if parts_url[1] == 'jobs':
            if len(parts_url) > 2:
                try:
                    id_job = int(parts_url[2])
                except ValueError:
                    self.response(400, {"error": "Invalid Id"})
                    return
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                data = json.loads(body)
                try:
                    job = self.server.service_validator.val_update(id_job, data)
                    self.response(200, job)
                except InvalidDataStructure:
                    self.response(400, {"error": "Invalid data structure"})
                except JobNotFound:
                    self.response(404, {"error": "Job not found"})

            else:
                self.response(400, {"error": "Se necesita un id para realizar esta opearcion"})
        else:
            self.response(404, {"error": "Route not found"})

    def do_DELETE(self):
        parts_url = self.path.split('/')
        if parts_url[1] == 'jobs':
            if len(parts_url) > 2:
                try:
                    id_job = int(parts_url[2])
                except ValueError:
                    self.response(400, {"error": "Invalid Id"})
                    return
                try:
                    self.server.service_validator.val_delete(id_job)
                    self.response(204)
                except JobNotFound:
                    self.response(404, {"error": "Job not found"})
            else:
                self.response(400, {"error": "An Id is needed for this operation"})
        else:
            self.response(404, {"error": "Route not found"})

    def response(self, code: int, message: dict[str, str] | None = None):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if message is not None:
            self.wfile.write((json.dumps(message)+'\n').encode('utf-8'))

def run(server_class=HTTPServer, handler_class=JobHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.service_validator = ServiceValidation(RawData())
    httpd.serve_forever()

if __name__ == '__main__':
    run()