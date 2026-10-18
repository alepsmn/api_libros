class JobNotFound(Exception):
    def __init__(self, id):
        mensaje = f"El job con id: {id}, no ha sido encontrado"
        super().__init__(mensaje)

class InvalidDataStructure(Exception):
    def __init__(self, posted_fields: set[str], required_fields: set[str]):
        mensaje = f"Estructura introducida: {posted_fields} - Incompatible con la esperada (minima): {required_fields}"
        super().__init__(mensaje)