import json, pytest, threading, time, urllib.request


from http.server import HTTPServer
from api_libros.server import BookHandler
from api_libros.service_validation import ServiceValidation
from api_libros.datos import DatosLibros

libro = {
        '0': {
            "Libro": "Niebla",
            "Autor": "M. Unamuno",
            "id": 0
        }
    }

libro1 = {
    "Libro": "Niebla",
    "Autor": "M. Unamuno",
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

libros_total = [libro2, libro3, libro4, libro5]

@pytest.fixture
def servidor():

    puerto = 8000
    host = 'localhost'
    server_address = f'http://{host}:{puerto}/books'

    httpd = HTTPServer((host, puerto), BookHandler)
    httpd.service_validator = ServiceValidation(DatosLibros())

    hilo = threading.Thread(target=httpd.serve_forever)
    hilo.daemon = True
    hilo.start()

    time.sleep(0.01)

    httpd.service_validator.val_save_book({"Libro": "Niebla", "Autor": "M. Unamuno", "id": 0})

    yield server_address, httpd.service_validator
    httpd.shutdown()

def test_get_books(servidor):
    url, _ = servidor
    respuesta = urllib.request.urlopen(f'{url}')
    assert int(respuesta.status) == 200
    bytes_libro = respuesta.read()
    libros = json.loads(bytes_libro)
    assert libros == libro

def test_get_pagination(servidor):
    url, _ = servidor
    for libro_pag in libros_total:
        datos_bytes = json.dumps(libro_pag).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=datos_bytes,
            method='POST'
        )
        urllib.request.urlopen(req)

    url2 = f'{url}?page=1&size=2'
    respuesta = urllib.request.urlopen(url2)
    assert int(respuesta.status) == 200
    bytes_libros = respuesta.read()
    libros = json.loads(bytes_libros)
    libro1['id'] = 0
    libro2['id'] = 1
    assert libros == [libro1, libro2]

def test_post_book(servidor):
    url, _ = servidor
    nuevo_libro = {
        "Libro": "El Quijote",
        "Autor": "Miguel de Cervantes",
    }

    datos_bytes = json.dumps(nuevo_libro).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=datos_bytes,
        method='POST'
    )

    respuesta = urllib.request.urlopen(req)
    assert int(respuesta.status) == 201
    bytes_libro = respuesta.read()
    libro_enviado = json.loads(bytes_libro)

    id_libro_enviado = libro_enviado["id"]
    nuevo_libro['id'] = id_libro_enviado
    assert libro_enviado == nuevo_libro

    respuesta = urllib.request.urlopen(f'{url}/{id_libro_enviado}')
    assert int(respuesta.status) == 200
    bytes_libro = respuesta.read()
    libro = json.loads(bytes_libro)
    assert libro == nuevo_libro

def test_post_error_struct(servidor):
    url, _ = servidor
    nuevo_libro = {
        "Agua": "El Quijote",
        "Aceite": "Miguel de Cervantes",
    }

    datos_bytes = json.dumps(nuevo_libro).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=datos_bytes,
        method='POST'
    )

    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(req)
    assert error.value.code == 400

def test_put_book(servidor):
    url, _ = servidor
    libro_modificado = {
        "Libro": "Dune",
        "Autor": "Frank Herbert",
        "id": 0
    }
    url2 = f"{url}/{libro_modificado['id']}"
    datos_bytes = json.dumps(libro_modificado).encode('utf-8')
    req = urllib.request.Request(
        url2,
        data=datos_bytes,
        method='PUT'
    )

    respuesta = urllib.request.urlopen(req)
    assert int(respuesta.status) == 200
    bytes_libro = respuesta.read()
    libro_enviado = json.loads(bytes_libro)


    assert libro_enviado == libro_modificado

    respuesta = urllib.request.urlopen(f"{url}/{libro_modificado['id']}")
    assert int(respuesta.status) == 200
    bytes_libro = respuesta.read()
    libro = json.loads(bytes_libro)
    assert libro == libro_modificado


def test_delete_book(servidor):
    url, service_val = servidor
    nuevo_libro = {
        "Libro": "El Quijote",
        "Autor": "Miguel de Cervantes",
    }

    datos_bytes = json.dumps(nuevo_libro).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=datos_bytes,
        method='POST'
    )

    respuesta = urllib.request.urlopen(req)
    assert int(respuesta.status) == 201
    bytes_libro = respuesta.read()
    libro_enviado = json.loads(bytes_libro)

    id_libro_enviado = libro_enviado["id"]
    nuevo_libro['id'] = id_libro_enviado
    assert libro_enviado == nuevo_libro

    url2 = f"{url}/{nuevo_libro['id']}"
    req = urllib.request.Request(
        url2,
        method='DELETE'
    )

    respuesta = urllib.request.urlopen(req)
    assert int(respuesta.status) == 200
    bytes_libro = respuesta.read()
    libro_borrado = json.loads(bytes_libro)

    assert libro_borrado == nuevo_libro
    assert service_val.storage.libros == {0: {"Libro": "Niebla", "Autor": "M. Unamuno", "id": 0}}

def test_error_get(servidor):
    url, _ = servidor
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(f"{url}/999")

    assert error.value.code == 404

def test_error_put(servidor):
    url, _ = servidor
    url2 = f"{url}/999"
    nuevo_libro = {
        "fdkl;jsjfsld": "JLJKL:",
    }
    datos_bytes = json.dumps(nuevo_libro).encode('utf-8')
    with pytest.raises(urllib.error.HTTPError) as error:

        req = urllib.request.Request(
            url2,
            data=datos_bytes,
            method='PUT'
        )
        urllib.request.urlopen(req)

    assert error.value.code == 400

def test_error_delete(servidor):
    url, _ = servidor
    url2 = f"{url}/999"
    with pytest.raises(urllib.error.HTTPError) as error:
    
        req = urllib.request.Request(
            url2,
            method='DELETE'
        )
        urllib.request.urlopen(req)

    assert error.value.code == 404