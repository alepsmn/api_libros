from api_libros.custom_exc import JobNotFound

class RawData:
    def __init__(self):
        self.jobs = {}
        self.counter = 0

    def save(self, data: dict[str, str]) -> dict[str, str|int]:
        data['id'] = self.counter
        self.jobs[self.counter] = data
        self.counter += 1
        return data

    def get(self, id: int) -> dict[str, str|int]:
        if id not in self.jobs:
            raise JobNotFound(id)
        return self.jobs[id]

    def get_all(self) -> dict[int, dict[str, str|int]]:
        return self.jobs # OJO, esto devuelve el dict interno

    def update(self, id: int, data: dict[str, str]) -> dict[str, str|int]:
        if id not in self.jobs:
            raise JobNotFound(id)
        data['id'] = id
        self.jobs[id] = data
        return data

    def delete(self, id: int):
        if id not in self.jobs:
            raise JobNotFound(id)
        deleted = self.jobs.pop(id, None)
        return deleted