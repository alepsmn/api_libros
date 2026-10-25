from http.server import BaseHTTPRequestHandler

from urllib.parse import urlparse
from urllib.parse import urlparse
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
                    self.response(200, job.to_dict())
                except JobNotFound:
                    self.response(404, {"error": "Job not found"})

            else:
                jobs = self.server.service_validator.val_get_all()
                self.response(200, {"jobs": sorted(jobs.values(), key=lambda o: o.id)})
                # 'jobs': [{job1}, {job2}, ...]
        else:
            self.response(404, {"error": "Route not found"}) # -> not found

    def do_POST(self):
        parts_url = self.path.split('/')
        if parts_url[1] == 'jobs':
            # comprobar si el len > 2?
            # cliente tiene q enviar este header - try/except
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)
            try:
                job = self.server.service_validator.val_save(data)
                self.response(201, job.to_dict())
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
                    self.response(200, job.to_dict())
                except InvalidDataStructure:
                    self.response(400, {"error": "Invalid data structure"})
                except JobNotFound:
                    self.response(404, {"error": "Job not found"})

            else:
                self.response(400, {"error": "An Id is needed for this operation"})
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
            self.wfile.write((json.dumps(message, default=lambda o: o.to_dict())+'\n').encode('utf-8'))