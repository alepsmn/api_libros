from http.server import ThreadingHTTPServer

from api_libros.service_validation import ServiceValidation
from api_libros.raw_data import RawData
from api_libros.jobhandler import JobHandler

class JobServer(ThreadingHTTPServer):
    request_queue_size = 128 # tapa el sintoma (por ahora)

def run(server_class=JobServer, handler_class=JobHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.service_validator = ServiceValidation(RawData())
    httpd.serve_forever()

if __name__ == '__main__':
    run()