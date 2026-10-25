from api_libros.custom_exc import InvalidDataStructure
from api_libros.processor import waiting, calculating

class ServiceValidation:
    def __init__(self, storage):
        # Job: {1-payload, 2-estado, 3-resultado, 4-id}
        self.storage = storage
        self.required_fields = {"type", "ms"}

    def _check_payload_integrity(self, data: dict[str, str]):
        posted_fields = set(data.keys())
        if not self.required_fields.issubset(posted_fields):
            raise InvalidDataStructure(posted_fields, self.required_fields)

    def val_save(self, data: dict[str, str]):
        self._check_payload_integrity(data)

        data['result'] = None

        if data['type'] == 'wait':
            waiting(data['ms'])
        elif data['type'] == 'calculate':
            calculating(data['ms'])

        return self.storage.save(data['type'], data['ms'])

    def val_get(self, id: int):
        return self.storage.get(id)

    def val_get_all(self):
        return self.storage.get_all()

    def val_update(self, id: int, data: dict[str, str]):
        self._check_payload_integrity(data)
        
        data['result'] = None
        return self.storage.update(id, data['type'], data['ms'])

    def val_delete(self, id: int):
        return self.storage.delete(id)