from api_libros.custom_exc import InvalidDataStructure

class ServiceValidation:
    def __init__(self, storage):
        # Job: {id, estado, payload, resultado}
        self.storage = storage
        self.required_fields = {"payload"}

    def val_save(self, data: dict[str, str]):
        posted_fields = set(data.keys())
        if not self.required_fields.issubset(posted_fields):
            raise InvalidDataStructure(posted_fields, self.required_fields)

        data['state'] = 'pending'
        data['result'] = None
        return self.storage.save(data)

    def val_get(self, id: int):
        return self.storage.get(id)

    def val_get_all(self):
        return self.storage.get_all()

    def val_update(self, id: int, data: dict[str, str]):
        posted_fields = set(data.keys())
        if not self.required_fields.issubset(posted_fields):
            raise InvalidDataStructure(posted_fields, self.required_fields)
        data['state'] = 'pending'
        data['result'] = None
        return self.storage.update(id, data)

    def val_delete(self, id: int):
        return self.storage.delete(id)