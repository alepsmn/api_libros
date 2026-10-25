from api_libros.custom_exc import JobNotFound
from threading import Lock
from dataclasses import dataclass
from enum import StrEnum

class State(StrEnum):
    PENDING = "pending"
    RUNNING = 'running'
    DONE = "done"
    FAILED = "failed"
  
@dataclass(frozen=True)
class Job:
    id: int
    work_type: str
    duration_work_ms: int
    result: str
    state: State

    def to_dict(self):
        return {"id": self.id,
                "work_type": self.work_type,
                "duration_ms": self.duration_work_ms,
                "state": self.state.value,
                "result": self.result}

class RawData:
    def __init__(self, yield_point=None):
        '''Un job guardado es inmutable,  para cambiarlo se reemplaza la entrada,
        nunca se muta en sitio.'''
        self.jobs = {}
        self.counter = 0
        self.yield_point = yield_point
        self.lock = Lock() # acquire / release

    # -------------QUITAR LOS .COPY() PARA VER SI LOS TEST CAPTURAN LO QUE BUSCAN - MUTABILIDAD DEL ESTADOS
    def save(self, type: str, ms: int):
        with self.lock:
            job = Job(id=self.counter, work_type=type, duration_work_ms=ms,
                    state=State.PENDING, result=None)
            self.jobs[self.counter] = job
            if self.yield_point: # causes race conditions -> test: ~1-2900 perdidas
                self.yield_point()
            self.counter += 1
        return job
    
    def get(self, id: int):
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            return self.jobs[id]

    def get_all(self):
        with self.lock:
        # Aqui no vale copia superficial -> copia claves, valores = a los de estado
            return dict(self.jobs)

    def update(self, id: int, type: str, ms: int):
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            job = Job(id=id, work_type=type, duration_work_ms=ms,
                state=State.PENDING, result=None)
            self.jobs[id] = job
        return job

    def delete(self, id: int):
        with self.lock:
            if id not in self.jobs:
                raise JobNotFound(id)
            deleted = self.jobs.pop(id) # -> none puede esconder fallo 2 deletes, con lock no hace falta
        return deleted