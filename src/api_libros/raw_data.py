from api_libros.custom_exc import JobNotFound
from threading import Lock

class RawData:
    def __init__(self, yield_point=None):
        '''Un job guardado es inmutable,  para cambiarlo se reemplaza la entrada,
        nunca se muta en sitio.'''
        self.jobs = {0:{"payload":"agua"}}
        self.counter = 0
        self.yield_point = yield_point
        self.lock = Lock() # acquire / release

    # -------------QUITAR LOS .COPY() PARA VER SI LOS TEST CAPTURAN LO QUE BUSCAN - MUTABILIDAD DEL ESTADOS
    def save(self, data: dict[str, str]) -> dict[str, str|int]:
        with self.lock:
            # no puedo guardarme el dato recibido, el exterior tiene referencia a el
            data['id'] = self.counter
            self.jobs[self.counter] = data.copy() # me guardo una copia del objeto mutado
            if self.yield_point: # causes race conditions -> test: ~1-2900 perdidas
                self.yield_point()
            self.counter += 1
        return data # devuelvo el mismo objeto recibido pero mutado

    def get(self, id: int) -> dict[str, str|int]:
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            return self.jobs[id].copy()

    def get_all(self) -> dict[int, dict[str, str|int]]:
        with self.lock:
        # Aqui no vale copia superficial -> copia claves, valores = a los de estado
            return {k: v.copy() for k, v in self.jobs.items()} # ya no es codigo C, es python: tiene puntos de cesion

    def update(self, id: int, data: dict[str, str]) -> dict[str, str|int]:
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            data['id'] = id
            self.jobs[id] = data.copy()
        return data

    def delete(self, id: int):
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            deleted = self.jobs.pop(id) # -> none puede esconder fallo 2 deletes, con lock no hace falta
        return deleted