import json, pytest, time, threading, urllib.request

from api_libros.server import JobHandler, JobServer
from api_libros.service_validation import ServiceValidation
from api_libros.raw_data import RawData

@pytest.fixture(scope="module")
def server():
    server_address = ('', 0) # con 0 -> SO elige puerto libre
    httpd = JobServer(server_address, JobHandler)
    httpd.service_validator = ServiceValidation(RawData(yield_point=lambda: time.sleep(0)))

    hilo = threading.Thread(target=httpd.serve_forever)
    hilo.daemon = True
    hilo.start()

    time.sleep(0.01)

    port = httpd.server_address[1]
    yield f"http://localhost:{port}"

    httpd.shutdown()

def post_concurr(url_base, i, results, ):
    url = f"{url_base}/jobs"
    body = json.dumps({"payload": "tarea_preuba"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    for a in range(200):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req) as answer:
                status = answer.status
                data = json.loads(answer.read().decode("utf-8"))
                results.append({"id": i, "status": status, "data": data, "error": None})
        except Exception as e:
            results.append({"id": i, "status": None, "data": None, "error": e})

    

def test_concurrency(server):
    zreads = []
    results = []
    for i in range(15):
        zread = threading.Thread(target=post_concurr, args=(server, i, results))
        zreads.append(zread)
        zread.start()

    for zread in zreads:
        zread.join()

    failures = [result for result in results if result['error'] is not None]
    assert len(failures) == 0

    # con N resultados no afirmas N veces, agregas y afirmas una.
    assert {r['status'] for r in results} == {201} # colapsas los estados ocurridos y comparas

    assert len({result['data']['id'] for result in results}) == 3000

