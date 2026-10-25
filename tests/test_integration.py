import json, pytest, threading, time, urllib.request

from http.server import HTTPServer
from urllib.error import HTTPError
from api_libros.server import JobHandler
from api_libros.service_validation import ServiceValidation
from api_libros.raw_data import RawData

# uv run pytest tests/test_integration.py -v

# Exito:
# POST /jobs con payload valido → 201
# GET /jobs → 200, lista con el job creado
# GET /jobs/{id} → 200, el job correcto
# PUT /jobs/{id} con payload → 200, dato actualizado
# DELETE /jobs/{id} → 204

# Errores:
# 6. POST /jobs con JSON invalido → 400
# 7. GET /jobs/abc → 400
# 8. GET /ruta_falsa → 404

@pytest.fixture(scope="module")
def server():
    server_address = ('', 0)
    httpd = HTTPServer(server_address, JobHandler)
    httpd.service_validator = ServiceValidation(RawData())

    hilo = threading.Thread(target=httpd.serve_forever)
    hilo.daemon = True
    hilo.start()

    time.sleep(0.01)

    port = httpd.server_address[1]
    yield f"http://localhost:{port}"

    httpd.shutdown()

def test_post(server):
    url = f"{server}/jobs"
    # "tarea_prueba" -> dict[str]
    body = json.dumps({"type": "calculate", "ms": 100}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    answer = urllib.request.urlopen(req) # tras este open -> answer.close (conexion abierta)

    assert int(answer.status) == 201

    data = json.loads(answer.read())
    assert data['state'] == 'pending'
    assert data['work_type'] == 'calculate'
    assert data['duration_ms'] == 100

    # ----------------------- POST: WRONG STRUCTURE
    body_2 = json.dumps({"paylo": {"type": "wait", "ms": 100}}).encode("utf-8")
    with pytest.raises(HTTPError) as exc:
        req_2 = urllib.request.Request(url, data=body_2, headers=headers, method='POST')
        urllib.request.urlopen(req_2)

    assert exc.value.code == 400

def test_get_all(server):
    url = f"{server}/jobs"
    answer = urllib.request.urlopen(f"{url}")
    assert int(answer.status) == 200
    data = json.loads(answer.read())

    # por simplicidad -> literal
    # correcto: hacer llamada con get y extraer su id,
    # asi se verifica la propia API - no literales
    p = next(p for p in data['jobs'] if p['id'] == 0)
    assert p['state'] == 'pending'

    # EJ
    # para varios assert -> crear dict con indices por key
    by_id= {p['id']: p for p in data['jobs']}
    job = by_id[0] # -> variar
    assert job['state'] == 'pending'

def test_get(server):
    url = f"{server}/jobs/0"
    answer = urllib.request.urlopen(f"{url}")
    assert int(answer.status) == 200

    with pytest.raises(HTTPError) as exc_info:
        url = f"{server}/jobs/9999"
        urllib.request.urlopen(url)
    assert exc_info.value.code == 404

    with pytest.raises(HTTPError) as exc_info:
        url = f"{server}/jobs/abc"
        urllib.request.urlopen(url)
    assert exc_info.value.code == 400

    with pytest.raises(HTTPError) as exc_info:
        url = f"{server}/books/abc"
        urllib.request.urlopen(url)
    assert exc_info.value.code == 404

def test_update(server):
    url = f"{server}/jobs/0"
    body = json.dumps({"type": "wait", "ms": 100}).encode('utf-8')
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=body, headers=headers, method='PUT')
    answer = urllib.request.urlopen(req)

    assert int(answer.status) == 200
    data = json.loads(answer.read())
    assert data['state'] == 'pending'
    assert data['work_type'] == 'wait'
    assert data['duration_ms'] == 100
    assert data['id'] == 0

# ---------------------------------------
    url_2 = f"{server}/jobs/99"
    with pytest.raises(HTTPError) as exc_info:
        req = urllib.request.Request(url_2, data=body, headers=headers, method='PUT')
        urllib.request.urlopen(req)

    assert exc_info.value.code == 404

def test_delete(server):
    url = f"{server}/jobs/0"
    req = urllib.request.Request(url, method='DELETE')
    answer = urllib.request.urlopen(req)

    assert int(answer.status) == 204

# ----------------------------------------
    url_2 = f"{server}/jobs/99"
    with pytest.raises(HTTPError) as exc_info:
        req = urllib.request.Request(url_2, method='DELETE')
        urllib.request.urlopen(req)
    assert exc_info.value.code == 404
